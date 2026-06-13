"""
WebSocket handlers for real-time packet and intercept notifications
"""
import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for broadcasting events"""

    def __init__(self):
        self._packet_connections: Set[WebSocket] = set()
        self._intercept_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect_packet(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._packet_connections.add(ws)
        logger.info(f"Packet WS client connected. Total: {len(self._packet_connections)}")

    async def disconnect_packet(self, ws: WebSocket):
        async with self._lock:
            self._packet_connections.discard(ws)
        logger.info(f"Packet WS client disconnected. Total: {len(self._packet_connections)}")

    async def connect_intercept(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._intercept_connections.add(ws)
        logger.info(f"Intercept WS client connected. Total: {len(self._intercept_connections)}")

    async def disconnect_intercept(self, ws: WebSocket):
        async with self._lock:
            self._intercept_connections.discard(ws)
        logger.info(f"Intercept WS client disconnected. Total: {len(self._intercept_connections)}")

    async def broadcast_packet(self, packet: dict):
        """Send new packet notification to all packet WS clients"""
        message = json.dumps(_packet_to_ws(packet), ensure_ascii=False)
        async with self._lock:
            dead = set()
            for ws in self._packet_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            self._packet_connections -= dead

    async def broadcast_intercept(self, packet: dict):
        """Send new intercept notification to all intercept WS clients"""
        message = json.dumps(_intercept_to_ws(packet), ensure_ascii=False)
        async with self._lock:
            dead = set()
            for ws in self._intercept_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            self._intercept_connections -= dead


def _packet_to_ws(packet: dict) -> dict:
    """Convert parsed packet to WebSocket message format"""
    return {
        "type": "new_packet",
        "data": {
            "id": packet.get("id", 0),
            "timestamp": packet.get("timestamp", ""),
            "direction": packet.get("direction", "Unknown"),
            "message_type": packet.get("message_type", "Unknown"),
            "message_type_id": packet.get("message_type_id", 0),
            "seid": packet.get("seid"),
            "sequence_number": packet.get("sequence_number", 0),
            "length": packet.get("length", 0),
            "src_addr": packet.get("src_addr", ""),
            "dst_addr": packet.get("dst_addr", ""),
            "logical_src": packet.get("logical_src", ""),
            "logical_dst": packet.get("logical_dst", ""),
            "intercepted": packet.get("intercepted", False),
        }
    }


def _intercept_to_ws(packet: dict) -> dict:
    """Convert packet to intercept WebSocket message format"""
    return {
        "type": "new_intercept",
        "data": {
            "id": packet.get("intercept_id", ""),
            "packet_id": packet.get("id", 0),
            "timestamp": packet.get("timestamp", ""),
            "direction": packet.get("direction", "Unknown"),
            "message_type": packet.get("message_type", "Unknown"),
            "seid": packet.get("seid"),
            "sequence_number": packet.get("sequence_number", 0),
            "length": packet.get("length", 0),
        }
    }
