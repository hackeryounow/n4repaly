"""
Template-based auto-responder for PFCP messages.
When an incoming packet matches a template, the relay automatically:
  1. Drops the incoming packet (does not forward to UPF/SMF)
  2. Sends the template's pre-built response back to the sender
"""
import json
import struct
import logging
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# PFCP header constants
_PFCP_HEADER_NO_SEID = 8
_PFCP_HEADER_WITH_SEID = 16


class TemplateStore:
    """Manages response templates for auto-responding to PFCP messages."""

    def __init__(self, persist_path: str = "/app/data/templates.json"):
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._persist_path = Path(persist_path)

    async def load_from_disk(self):
        """Load templates from persistent storage."""
        if not self._persist_path.exists():
            logger.info("No template file found, starting with empty store")
            return
        try:
            with open(self._persist_path, 'r') as f:
                data = json.load(f)
            async with self._lock:
                self._templates = data
            logger.info(f"Loaded {len(self._templates)} templates from disk")
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")

    async def save_to_disk(self):
        """Persist templates to disk."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._lock:
                data = dict(self._templates)
            with open(self._persist_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save templates: {e}")

    async def add(self, template: Dict[str, Any]) -> str:
        """Add a new template. Returns the generated ID."""
        tid = uuid.uuid4().hex[:8]
        template["id"] = tid
        template.setdefault("enabled", True)
        template.setdefault("hit_count", 0)
        template.setdefault("auto_seq", True)
        template.setdefault("auto_seid", False)
        template.setdefault("match_seid", None)
        async with self._lock:
            self._templates[tid] = template
        await self.save_to_disk()
        logger.info(f"Template added: {tid} - {template.get('name', 'unnamed')}")
        return tid

    async def update(self, tid: str, updates: Dict[str, Any]) -> bool:
        """Update an existing template."""
        async with self._lock:
            if tid not in self._templates:
                return False
            self._templates[tid].update(updates)
        await self.save_to_disk()
        return True

    async def delete(self, tid: str) -> bool:
        """Delete a template."""
        async with self._lock:
            if tid not in self._templates:
                return False
            del self._templates[tid]
        await self.save_to_disk()
        logger.info(f"Template deleted: {tid}")
        return True

    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all templates."""
        async with self._lock:
            return list(self._templates.values())

    async def get(self, tid: str) -> Optional[Dict[str, Any]]:
        """Get a single template by ID."""
        async with self._lock:
            return self._templates.get(tid)

    async def set_enabled(self, tid: str, enabled: bool) -> bool:
        """Enable or disable a template."""
        return await self.update(tid, {"enabled": enabled})

    async def increment_hit(self, tid: str):
        """Increment the hit counter for a template."""
        async with self._lock:
            if tid in self._templates:
                self._templates[tid]["hit_count"] = self._templates[tid].get("hit_count", 0) + 1

    def find_match(self, msg_type: int, seid: Optional[int]) -> Optional[Dict[str, Any]]:
        """
        Find an active template matching the incoming message.
        Synchronous for use in the packet processing hot path.
        """
        for t in self._templates.values():
            if not t.get("enabled", True):
                continue
            if t.get("match_msg_type") != msg_type:
                continue
            # If template specifies a SEID filter, check it
            match_seid = t.get("match_seid")
            if match_seid is not None and seid != match_seid:
                continue
            return t
        return None

    def build_response(self, template: Dict[str, Any],
                       request_data: bytes) -> Optional[bytes]:
        """
        Build a response packet from a template, patching dynamic fields
        from the incoming request (sequence number, SEID).

        Returns raw bytes ready to send, or None on error.
        """
        response_hex = template.get("response_hex")
        if not response_hex:
            logger.warning(f"Template {template.get('id')} has no response data")
            return None

        response_data = bytearray(bytes.fromhex(response_hex))

        # Determine header format from the response packet
        if len(response_data) < 4:
            return None

        resp_s_flag = response_data[0] & 0x01
        resp_header_len = _PFCP_HEADER_WITH_SEID if resp_s_flag else _PFCP_HEADER_NO_SEID

        # Determine header format from the request packet
        if len(request_data) < 4:
            return None

        req_s_flag = request_data[0] & 0x01
        req_header_len = _PFCP_HEADER_WITH_SEID if req_s_flag else _PFCP_HEADER_NO_SEID

        # Patch sequence number from request
        if template.get("auto_seq", True):
            if req_s_flag and len(request_data) >= 15 and resp_s_flag and len(response_data) >= 15:
                # Session messages: seq is at bytes 12-14
                response_data[12] = request_data[12]
                response_data[13] = request_data[13]
                response_data[14] = request_data[14]
            elif not req_s_flag and len(request_data) >= 7 and not resp_s_flag and len(response_data) >= 7:
                # Node messages: seq is at bytes 4-6
                response_data[4] = request_data[4]
                response_data[5] = request_data[5]
                response_data[6] = request_data[6]

        # Patch SEID from request (for session messages only)
        if template.get("auto_seid", False):
            if req_s_flag and resp_s_flag and len(request_data) >= 12 and len(response_data) >= 12:
                response_data[4:12] = request_data[4:12]

        return bytes(response_data)
