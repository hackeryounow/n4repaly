"""
PFCP Packet Interceptor
Holds matching packets for user inspection and modification
"""
import asyncio
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ..pfcp.builder import build_pfcp_message
from ..pfcp.constants import EDITABLE_FIELDS

logger = logging.getLogger(__name__)


class HeldPacket:
    """Represents a packet being held for interception"""

    def __init__(self, intercept_id: str, packet: Dict[str, Any],
                 raw_data: bytes, src_addr: tuple, from_side: str):
        self.intercept_id = intercept_id
        self.packet = packet
        self.raw_data = raw_data
        self.src_addr = src_addr
        self.from_side = from_side
        self.status = "held"  # held, released, dropped
        self.modifications: Dict[str, Any] = {}
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.intercept_id,
            "packet_id": self.packet.get("id", 0),
            "timestamp": self.timestamp,
            "direction": self.packet.get("direction", "Unknown"),
            "message_type": self.packet.get("message_type", "Unknown"),
            "seid": self.packet.get("seid"),
            "sequence_number": self.packet.get("sequence_number", 0),
            "length": self.packet.get("length", 0),
            "status": self.status,
        }

    def to_detail(self) -> Dict[str, Any]:
        summary = self.to_summary()
        summary.update({
            "header": self.packet.get("header", {}),
            "ies": self.packet.get("ies", []),
            "raw_hex": self.packet.get("raw_hex", ""),
            "editable_fields": EDITABLE_FIELDS,
        })
        return summary


class Interceptor:
    """Manages intercepted packets"""

    def __init__(self, max_held: int = 100):
        self.enabled = False
        self.max_held = max_held
        self._held_packets: Dict[str, HeldPacket] = {}
        self._lock = asyncio.Lock()
        self._relay_server = None  # Set by relay server

    def set_relay(self, relay_server):
        self._relay_server = relay_server

    async def hold(self, packet: Dict[str, Any], raw_data: bytes,
                   src_addr: tuple, from_side: str) -> bool:
        """
        Hold a packet for interception.
        Returns True if the packet was held, False otherwise.
        """
        if not self.enabled:
            return False

        async with self._lock:
            # Check capacity
            if len(self._held_packets) >= self.max_held:
                logger.warning("Intercept buffer full, dropping oldest")
                oldest_id = next(iter(self._held_packets))
                del self._held_packets[oldest_id]

            intercept_id = str(uuid.uuid4())[:8]
            held = HeldPacket(intercept_id, packet, raw_data, src_addr, from_side)
            self._held_packets[intercept_id] = held
            packet["intercept_id"] = intercept_id
            packet["intercepted"] = True

            logger.info(f"Intercepted packet: {intercept_id} - {packet.get('message_type', 'Unknown')}")
            return True

    async def get_held(self) -> List[Dict[str, Any]]:
        """Get all held packets"""
        async with self._lock:
            return [hp.to_summary() for hp in self._held_packets.values()]

    async def get_held_detail(self, intercept_id: str) -> Optional[Dict[str, Any]]:
        """Get detail of a specific held packet"""
        async with self._lock:
            hp = self._held_packets.get(intercept_id)
            if hp:
                return hp.to_detail()
        return None

    async def modify(self, intercept_id: str, modifications: Dict[str, Any]) -> bool:
        """
        Apply modifications to a held packet.
        The modifications will be applied when the packet is released.
        """
        async with self._lock:
            hp = self._held_packets.get(intercept_id)
            if not hp:
                return False
            if hp.status != "held":
                return False

            hp.modifications = modifications
            logger.info(f"Modifications set for intercept {intercept_id}")
            return True

    async def release(self, intercept_id: str) -> Optional[Dict[str, Any]]:
        """
        Release a held packet (forward it to the destination).
        Applies any modifications before forwarding.
        """
        async with self._lock:
            hp = self._held_packets.get(intercept_id)
            if not hp:
                return None
            if hp.status != "held":
                return {"error": f"Packet status is {hp.status}, cannot release"}

            # Build the (potentially modified) message
            try:
                if hp.modifications:
                    data = build_pfcp_message(hp.packet, hp.modifications)
                else:
                    data = hp.raw_data
            except Exception as e:
                logger.exception(f"Error building modified packet for {intercept_id}")
                return {"error": f"Failed to build modified packet: {str(e)}"}

            hp.status = "released"

            # Forward the packet
            if self._relay_server:
                # Determine forwarding direction
                if hp.from_side == "listen":
                    # Came from SMF, forward to UPF
                    await self._relay_server.forward_raw(data, "target")
                else:
                    # Came from UPF ("upf" on listen socket or "target" on target socket)
                    # Forward to SMF — let forward_raw use its tracked SMF address
                    await self._relay_server.forward_raw(data, "listen")

            logger.info(f"Released intercept {intercept_id}")
            return hp.to_summary()

    async def drop(self, intercept_id: str) -> Optional[Dict[str, Any]]:
        """Drop a held packet (don't forward it)"""
        async with self._lock:
            hp = self._held_packets.get(intercept_id)
            if not hp:
                return None

            hp.status = "dropped"
            del self._held_packets[intercept_id]
            logger.info(f"Dropped intercept {intercept_id}")
            return hp.to_summary()

    async def get_held_packet(self, intercept_id: str) -> Optional[HeldPacket]:
        """Get the HeldPacket object"""
        async with self._lock:
            return self._held_packets.get(intercept_id)

    async def release_all(self) -> Dict[str, Any]:
        """Release all held packets (forward them to destination)"""
        released = 0
        errors = 0
        async with self._lock:
            held_ids = [iid for iid, hp in self._held_packets.items() if hp.status == "held"]

        for iid in held_ids:
            result = await self.release(iid)
            if result and not (isinstance(result, dict) and "error" in result):
                released += 1
            else:
                errors += 1

        logger.info(f"Release all: {released} released, {errors} errors")
        return {"released": released, "errors": errors}

    async def drop_all(self) -> Dict[str, Any]:
        """Drop all held packets (don't forward)"""
        dropped = 0
        async with self._lock:
            held_ids = [iid for iid, hp in self._held_packets.items() if hp.status == "held"]

        for iid in held_ids:
            result = await self.drop(iid)
            if result is not None:
                dropped += 1

        logger.info(f"Drop all: {dropped} dropped")
        return {"dropped": dropped}

    @property
    def held_count(self) -> int:
        return len(self._held_packets)
