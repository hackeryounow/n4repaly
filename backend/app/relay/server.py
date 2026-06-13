"""
Async UDP Relay Engine
Handles PFCP message forwarding between SMF and UPF

Uses asyncio.Queue + worker pool to handle burst traffic without
overwhelming the event loop. Incoming datagrams are enqueued
immediately by the UDP protocol handler and processed by a fixed
number of async workers, ensuring ordered, back-pressure-aware
packet processing.
"""
import asyncio
import logging
import struct
import time
import socket
from collections import deque
from typing import Dict, Any, Optional, Callable, List, Awaitable, Tuple
from datetime import datetime, timezone

from ..config import AppConfig
from ..pfcp.parser import parse_packet

logger = logging.getLogger(__name__)

# PFCP constants for NodeID rewriting
_NODE_ID_IE_TYPE = 60  # 0x003C
_NODE_ID_TYPE_IPV4 = 0
_NODE_ID_TYPE_IPV6 = 1
_NODE_ID_TYPE_FQDN = 2
_PFCP_HEADER_NO_SEID = 8
_PFCP_HEADER_WITH_SEID = 16


def _fqdn_to_dns_wire(fqdn: str) -> bytes:
    """Convert an FQDN string to DNS wire format (label-length encoding)."""
    parts = fqdn.rstrip('.').split('.')
    result = b''
    for part in parts:
        encoded = part.encode('utf-8')
        result += bytes([len(encoded)]) + encoded
    return result


def _parse_new_node_id(value: str) -> bytes:
    """Parse the config value into a Node ID IE value (type_byte + payload).

    Supports:
      - IPv4 address  (e.g. "172.22.0.38")  → type 0 + 4 bytes
      - IPv6 address  (e.g. "::1")          → type 1 + 16 bytes
      - FQDN          (e.g. "n4replay")     → type 2 + DNS wire format
    """
    import ipaddress
    try:
        addr = ipaddress.ip_address(value)
        if isinstance(addr, ipaddress.IPv4Address):
            return bytes([_NODE_ID_TYPE_IPV4]) + addr.packed
        else:
            return bytes([_NODE_ID_TYPE_IPV6]) + addr.packed
    except ValueError:
        # Not an IP address — treat as FQDN
        return bytes([_NODE_ID_TYPE_FQDN]) + _fqdn_to_dns_wire(value)


def rewrite_node_id(data: bytes, new_value_str: str) -> bytes:
    """
    Rewrite the NodeID IE (type 60) in a PFCP message.
    Supports IPv4, IPv6, and FQDN replacement values.
    Returns modified bytes. If NodeID IE is not found, returns original.
    """
    if len(data) < 4 or not new_value_str:
        return data

    # Pre-parse the replacement value into a Node ID IE value (type_byte + payload)
    new_node_value = _parse_new_node_id(new_value_str)

    # Check S flag (bit 0 of byte 0) to determine header length
    s_flag = data[0] & 0x01
    header_len = _PFCP_HEADER_WITH_SEID if s_flag else _PFCP_HEADER_NO_SEID

    if len(data) < header_len:
        return data

    # Message length (bytes 2-3) covers everything after first 4 bytes
    msg_length = struct.unpack('!H', data[2:4])[0]
    ies_start = header_len
    ies_end = 4 + msg_length

    if ies_end > len(data):
        ies_end = len(data)

    # Scan IEs to find NodeID
    pos = ies_start
    ie_count = 0
    while pos + 4 <= ies_end:
        ie_type = struct.unpack('!H', data[pos:pos + 2])[0]
        ie_len = struct.unpack('!H', data[pos + 2:pos + 4])[0]
        ie_count += 1

        if ie_type == _NODE_ID_IE_TYPE and pos + 4 + ie_len <= ies_end:
            # Found NodeID IE — rewrite regardless of original type
            old_value = data[pos + 4:pos + 4 + ie_len]
            new_ie_len = len(new_node_value)

            # Rebuild: header + IEs before NodeID + new NodeID IE + IEs after NodeID
            before = data[:pos]
            new_ie = struct.pack('!HH', ie_type, new_ie_len) + new_node_value
            after = data[pos + 4 + ie_len:]

            result = before + new_ie + after

            # Update message length field (bytes 2-3)
            new_msg_length = len(result) - 4
            result = result[:2] + struct.pack('!H', new_msg_length) + result[4:]

            logger.info(f"NodeID rewritten: old={old_value.hex()} -> new={new_node_value.hex()} "
                        f"(value={new_value_str})")
            return result

        pos += 4 + ie_len

    logger.debug(f"NodeID IE (type 60) not found after scanning {ie_count} IEs")
    return data

# Default queue / worker settings (can be overridden via config)
DEFAULT_QUEUE_SIZE = 10000
DEFAULT_WORKER_COUNT = 4


class PacketBuffer:
    """Ring buffer for storing captured packets"""

    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._counter = 0
        self._lock = asyncio.Lock()

    async def add(self, packet: Dict[str, Any]) -> int:
        async with self._lock:
            self._counter += 1
            packet["id"] = self._counter
            self._buffer.append(packet)
            return self._counter

    async def get(self, packet_id: int) -> Optional[Dict[str, Any]]:
        async with self._lock:
            for pkt in self._buffer:
                if pkt["id"] == packet_id:
                    return pkt
        return None

    async def get_all(self, offset: int = 0, limit: int = 100,
                      msg_type: Optional[str] = None,
                      direction: Optional[str] = None,
                      exclude_heartbeat: bool = False) -> tuple:
        async with self._lock:
            filtered = list(self._buffer)

            if exclude_heartbeat:
                filtered = [p for p in filtered if p.get("message_type_id") not in (1, 2)]
            if msg_type:
                filtered = [p for p in filtered if msg_type.lower() in p.get("message_type", "").lower()]
            if direction:
                filtered = [p for p in filtered if direction.lower() in p.get("direction", "").lower()]

            total = len(filtered)
            # Most recent first
            filtered = list(reversed(filtered))
            page = filtered[offset:offset + limit]
            return total, page

    async def clear(self):
        async with self._lock:
            self._buffer.clear()
            self._counter = 0

    @property
    def count(self) -> int:
        return len(self._buffer)


class RelayServer:
    """PFCP UDP Relay Server with queue-based packet processing

    Single-socket architecture:
      Uses ONE UDP socket bound to listen_addr:listen_port for ALL traffic.
      Both SMF and UPF send PFCP to this relay, so all packets arrive on the
      same socket.  Source disambiguation (by IP) tells SMF and UPF apart.
      All forwarding uses sendto() on the same socket, guaranteeing source
      port 8805 — the standard PFCP port that both endpoints expect.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.running = False
        self.start_time: Optional[float] = None
        self.buffer = PacketBuffer(config.buffer.max_packets)
        self.interceptor = None  # Set externally
        self.template_store = None  # Set externally (TemplateStore)

        # Single UDP transport for all relay traffic
        self._listen_transport = None
        self._loop = None

        # Packet processing queue + workers
        queue_size = config.queue.max_size
        worker_count = config.queue.workers
        self._packet_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._worker_count: int = worker_count
        self._workers: List[asyncio.Task] = []

        # Queue statistics for monitoring
        self._queue_overflow_count: int = 0  # packets dropped due to full queue
        self._queue_processed_count: int = 0  # total packets processed by workers

        # Callbacks for WebSocket notifications
        self._on_packet: List[Callable] = []
        self._on_intercept: List[Callable] = []

        # Session tracking: maps (src_addr, src_port, seq) -> direction info
        self._sessions: Dict[str, tuple] = {}

        # Track the SMF's address (set on first packet from SMF)
        self._smf_addr: Optional[tuple] = None
        # Resolved target (UPF) IP for source disambiguation and forwarding
        self._target_ip: Optional[str] = None
        # PFCP transaction tracking: seq_num -> (smf_addr, timestamp)
        # Used to distinguish UPF responses (to SMF requests) from UPF-initiated requests.
        self._pending_requests: Dict[int, Tuple[tuple, float]] = {}

    # PFCP message types that are *responses* (3GPP TS 29.244 Table 7.3-1)
    _PFCP_RESPONSE_TYPES = frozenset({
        2, 4, 6, 8, 10, 11, 13, 15,   # node-related responses
        51, 53, 55, 57, 59, 61,         # session-related responses
    })

    def on_packet(self, callback: Callable[[Dict], Awaitable[None]]):
        self._on_packet.append(callback)

    def on_intercept(self, callback: Callable[[Dict], Awaitable[None]]):
        self._on_intercept.append(callback)

    async def start(self):
        """Start the relay server and packet processing workers"""
        if self.running:
            return

        self._loop = asyncio.get_event_loop()

        # Create single UDP socket for all relay traffic
        listen_addr = self.config.relay.listen_addr
        listen_port = self.config.relay.listen_port

        self._listen_transport, _ = await self._loop.create_datagram_endpoint(
            lambda: RelayProtocol(self, "listen"),
            local_addr=(listen_addr, listen_port),
        )

        # Try to resolve target hostname (may fail if DNS not ready)
        await self._resolve_target()

        self.running = True
        self.start_time = time.time()

        # Start packet processing workers
        self._queue_overflow_count = 0
        self._queue_processed_count = 0
        for i in range(self._worker_count):
            task = asyncio.create_task(self._packet_worker(i))
            self._workers.append(task)

        target_addr = self.config.relay.target_addr
        target_port = self.config.relay.target_port
        logger.info(
            f"Relay started: listening on {listen_addr}:{listen_port}, "
            f"target {target_addr}:{target_port}, "
            f"queue_size={self._packet_queue.maxsize}, workers={self._worker_count}"
        )

    async def _resolve_target(self):
        """Resolve the target (UPF) hostname to an IP address.

        Does NOT create a separate socket — all forwarding uses the single
        listen socket via sendto().  This method only resolves DNS so we
        have the IP for disambiguation and forwarding.
        """
        target_addr = self.config.relay.target_addr
        target_port = self.config.relay.target_port

        try:
            target_ip = socket.gethostbyname(target_addr)
        except socket.gaierror:
            logger.warning(f"Cannot resolve target '{target_addr}', will retry on first packet")
            self._target_ip = None
            return

        self._target_ip = target_ip
        logger.info(f"Target resolved: {target_addr} -> {target_ip}:{target_port}")

    def _get_listen_ip(self) -> str:
        """Return the relay's own IP address for display purposes.

        If the listen address is 0.0.0.0, resolve the container hostname
        to get the actual routable IP.
        """
        listen_addr = self.config.relay.listen_addr
        if listen_addr and listen_addr != "0.0.0.0":
            return listen_addr
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            return "0.0.0.0"

    async def stop(self):
        """Stop the relay server and drain worker tasks"""
        if not self.running:
            return

        self.running = False

        # Signal workers to exit by sending sentinel values
        for _ in self._workers:
            try:
                self._packet_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

        # Wait for workers to finish
        for task in self._workers:
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                task.cancel()
        self._workers.clear()

        if self._listen_transport:
            self._listen_transport.close()
            self._listen_transport = None

        remaining = self._packet_queue.qsize()
        if remaining > 0:
            logger.warning(f"Relay stopped with {remaining} packets still in queue")

        self.start_time = None
        logger.info(
            f"Relay stopped. Processed {self._queue_processed_count} packets, "
            f"dropped {self._queue_overflow_count} (queue overflow)"
        )

    # ---- Queue-based packet processing ----

    def enqueue_packet(self, data: bytes, src_addr: tuple, from_side: str):
        """
        Enqueue an incoming datagram for processing.
        Called synchronously from the UDP protocol handler (non-async).
        If the queue is full, the packet is dropped and counted.
        """
        try:
            self._packet_queue.put_nowait((data, src_addr, from_side))
        except asyncio.QueueFull:
            self._queue_overflow_count += 1
            if self._queue_overflow_count <= 10 or self._queue_overflow_count % 1000 == 0:
                logger.warning(
                    f"Packet queue full ({self._packet_queue.maxsize}), "
                    f"dropped {self._queue_overflow_count} packets total"
                )

    async def _packet_worker(self, worker_id: int):
        """
        Worker coroutine that processes packets from the queue.
        Multiple workers run concurrently for parallel processing.
        """
        logger.debug(f"Packet worker {worker_id} started")
        while True:
            try:
                item = await self._packet_queue.get()
            except asyncio.CancelledError:
                break

            # Sentinel value means shutdown
            if item is None:
                break

            data, src_addr, from_side = item
            try:
                await self._process_packet(data, src_addr, from_side)
            except Exception:
                logger.exception(f"Worker {worker_id}: unhandled error processing packet")
            finally:
                self._queue_processed_count += 1

        logger.debug(f"Packet worker {worker_id} stopped")

    async def _process_packet(self, data: bytes, src_addr: tuple, from_side: str):
        """
        Process a single PFCP packet (parse, store, intercept or forward).
        Called by worker coroutines, not directly by the UDP handler.

        Single-socket architecture with transaction tracking:
          All packets arrive on the listen socket from either SMF or UPF.

          Disambiguation (three cases):
            1. src IP ≠ UPF IP  →  from_side = "listen"  (SMF → UPF)
            2. src IP == UPF IP AND is a PFCP response whose seq matches
               a previously forwarded SMF request
               →  from_side = "upf"  (UPF response → SMF)
            3. src IP == UPF IP AND not a tracked response
               →  from_side = "upf"  (UPF-initiated request → SMF)

          Cases 2 and 3 both forward to SMF, but the transaction tracker
          prevents responses from being misrouted back to the UPF.
        """
        is_upf_ip = self._target_ip and src_addr[0] == self._target_ip

        if is_upf_ip:
            from_side = "upf"
            # Expire stale transactions (older than 30 s)
            now = time.time()
            stale = [s for s, (_, t) in self._pending_requests.items()
                     if now - t > 30]
            for s in stale:
                del self._pending_requests[s]
            # Consume matching pending request (response routing)
            if len(data) >= 4:
                seq = self._extract_seq(data)
                self._pending_requests.pop(seq, None)
        else:
            from_side = "listen"

        # Track addresses and build display metadata
        # Relay's own listen address (the actual destination for all inbound packets)
        relay_addr = (self._get_listen_ip(), self.config.relay.listen_port)

        if from_side == "listen":
            # Packet from SMF → arrives at relay
            self._smf_addr = src_addr
            parsed_src = src_addr          # actual: SMF IP:port
            parsed_dst = relay_addr        # actual: relay IP:port
            logical_src = f"SMF ({src_addr[0]})"
            logical_dst = f"UPF ({self._target_ip or self.config.relay.target_addr})"
        else:
            # Packet from UPF → arrives at relay
            parsed_src = src_addr          # actual: UPF IP:port
            parsed_dst = relay_addr        # actual: relay IP:port
            logical_src = f"UPF ({src_addr[0]})"
            smf_ip = self._smf_addr[0] if self._smf_addr else "?"
            logical_dst = f"SMF ({smf_ip})"

        # Parse the packet
        packet = parse_packet(data, parsed_src, parsed_dst, from_side=from_side,
                              logical_src=logical_src, logical_dst=logical_dst)

        # Store in buffer
        pkt_id = await self.buffer.add(packet)

        # Notify WebSocket listeners
        for cb in self._on_packet:
            try:
                await cb(packet)
            except Exception:
                logger.exception("Error in packet callback")

        # Check template auto-responder (before intercept and forward)
        if self.template_store and await self._try_auto_respond(data, packet, src_addr, from_side):
            return  # Auto-responded, don't forward

        # Check if interception is enabled
        if self.interceptor and self.interceptor.enabled:
            held = await self.interceptor.hold(packet, data, src_addr, from_side)
            if held:
                # Notify intercept listeners
                for cb in self._on_intercept:
                    try:
                        await cb(packet)
                    except Exception:
                        logger.exception("Error in intercept callback")
                return  # Don't forward, it's being held

        # Forward the packet
        await self._forward(data, src_addr, from_side)

    async def _forward(self, data: bytes, src_addr: tuple, from_side: str):
        """Forward packet to the other side, rewriting NodeID if configured.

        Single-socket routing (all sendto on listen socket, source port 8805):
          - "listen" (SMF request)  → sendto UPF at target_ip:target_port
                                       + record seq in _pending_requests
                                       + rewrite SMF NodeID so UPF only sees relay IP
          - "upf"    (UPF any)      → sendto SMF at tracked _smf_addr
                                       + rewrite UPF NodeID so SMF only sees relay IP
        """
        try:
            node_id_cfg = self.config.relay.smf_upf_node_id

            # Resolve the Node ID replacement value (applies to both directions)
            node_id_value = None
            if node_id_cfg:
                if node_id_cfg in ("auto", "self", ""):
                    node_id_value = self._get_listen_ip()
                else:
                    node_id_value = node_id_cfg

            if from_side == "listen":
                # From SMF → forward to UPF and track the transaction
                if not self._target_ip:
                    await self._resolve_target()
                if self._target_ip and self._listen_transport:
                    # Rewrite SMF's Node ID so UPF doesn't learn SMF's real IP
                    if node_id_value:
                        data = rewrite_node_id(data, node_id_value)
                    # Track pending request by sequence number
                    if len(data) >= 4:
                        seq = self._extract_seq(data)
                        self._pending_requests[seq] = (src_addr, time.time())
                    self._listen_transport.sendto(
                        data, (self._target_ip, self.config.relay.target_port))
                else:
                    logger.warning("Target IP not resolved, dropping SMF packet")
            else:
                # From UPF (response or new request) → forward to SMF
                if node_id_value:
                    data = rewrite_node_id(data, node_id_value)
                if self._listen_transport and self._smf_addr:
                    self._listen_transport.sendto(data, self._smf_addr)
                elif self._listen_transport:
                    logger.warning("No SMF address tracked yet, dropping UPF message")
        except Exception:
            logger.exception(f"Error forwarding packet from {from_side}")

    @staticmethod
    def _extract_seq(data: bytes) -> int:
        """Extract the 24-bit sequence number from a raw PFCP message."""
        s_flag = data[0] & 0x01
        if s_flag and len(data) >= 15:
            return struct.unpack('!I', b'\x00' + data[12:15])[0]
        elif len(data) >= 7:
            return struct.unpack('!I', b'\x00' + data[4:7])[0]
        return -1

    async def forward_raw(self, data: bytes, to_side: str, dst_addr: tuple = None):
        """Forward raw bytes to a specific side (used by interceptor release).

        All forwarding uses the single listen socket (source port 8805).

        ``to_side`` semantics:
          - "target"  → send to UPF at target_ip:target_port
          - "listen"  → send to SMF at tracked _smf_addr (or dst_addr)
        """
        try:
            if to_side == "target":
                if not self._target_ip:
                    await self._resolve_target()
                if self._listen_transport and self._target_ip:
                    self._listen_transport.sendto(
                        data, (self._target_ip, self.config.relay.target_port))
            elif to_side == "listen":
                # Use provided dst_addr or fall back to tracked SMF address
                target = dst_addr or self._smf_addr
                if self._listen_transport and target:
                    self._listen_transport.sendto(data, target)
        except Exception:
            logger.exception(f"Error forwarding raw data to {to_side}")

    async def _try_auto_respond(self, data: bytes, packet: Dict[str, Any],
                                 src_addr: tuple, from_side: str) -> bool:
        """
        Check if the incoming packet matches a template. If so, build and send
        the template response, and return True (packet was handled, don't forward).
        """
        if not self.template_store:
            return False

        msg_type = packet.get("message_type_id", 0)
        seid = packet.get("seid")

        template = self.template_store.find_match(msg_type, seid)
        if not template:
            return False

        # Build response from template
        response_data = self.template_store.build_response(template, data)
        if not response_data:
            logger.warning(f"Template {template['id']} matched but failed to build response")
            return False

        # Use template's Node ID as-is (no rewriting for template responses)
        # The template's response_hex should contain the correct Node ID

        # Send response back to the sender (always from listen socket, port 8805)
        try:
            if from_side == "listen":
                # Packet came from SMF → send response back to SMF
                if self._listen_transport:
                    self._listen_transport.sendto(response_data, src_addr)
                    logger.info(
                        f"Auto-responded: template '{template.get('name', template['id'])}' "
                        f"matched {packet.get('message_type', 'unknown')} from SMF, "
                        f"sent {len(response_data)}B response"
                    )
            else:
                # Packet came from UPF → send response back to UPF
                if self._listen_transport and self._target_ip:
                    self._listen_transport.sendto(
                        response_data,
                        (self._target_ip, self.config.relay.target_port))
                    logger.info(
                        f"Auto-responded: template '{template.get('name', template['id'])}' "
                        f"matched {packet.get('message_type', 'unknown')} from UPF, "
                        f"sent {len(response_data)}B response"
                    )
        except Exception:
            logger.exception("Error sending auto-response")
            return False

        # Track hit count
        await self.template_store.increment_hit(template["id"])
        return True

    def update_target(self, addr: str, port: int):
        """Update target address (requires restart)"""
        self.config.relay.target_addr = addr
        self.config.relay.target_port = port

    @property
    def uptime(self) -> Optional[float]:
        if self.start_time:
            return time.time() - self.start_time
        return None

    @property
    def queue_stats(self) -> Dict[str, int]:
        """Return current queue statistics for monitoring"""
        return {
            "queue_depth": self._packet_queue.qsize(),
            "queue_max_size": self._packet_queue.maxsize,
            "queue_overflow_dropped": self._queue_overflow_count,
            "queue_processed_total": self._queue_processed_count,
            "worker_count": self._worker_count,
        }


class RelayProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol handler for the single relay socket"""

    def __init__(self, server: RelayServer, side: str):
        self.server = server
        self.side = side
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple):
        if not self.server.running:
            return
        self.server.enqueue_packet(data, addr, self.side)

    def error_received(self, exc):
        logger.error(f"UDP error on {self.side}: {exc}")

    def connection_lost(self, exc):
        if exc:
            logger.warning(f"Connection lost on {self.side}: {exc}")
