"""
REST API Routes for N4Relay
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..models import (
    StatusResponse, StatusUpdateRequest,
    PacketSummary, PacketDetail, PacketListResponse,
    InterceptedPacket, InterceptedPacketDetail,
    ModifyRequest, ReleaseResponse,
    ErrorResponse, SuccessResponse,
    TemplateCreate, TemplateUpdate, TemplateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["n4relay"])

# These will be set by main.py during app startup
_relay = None
_interceptor = None
_template_store = None


def set_dependencies(relay, interceptor, template_store=None):
    global _relay, _interceptor, _template_store
    _relay = relay
    _interceptor = interceptor
    _template_store = template_store


def _packet_to_summary(pkt: dict) -> dict:
    return {
        "id": pkt.get("id", 0),
        "timestamp": pkt.get("timestamp", ""),
        "direction": pkt.get("direction", "Unknown"),
        "message_type": pkt.get("message_type", "Unknown"),
        "message_type_id": pkt.get("message_type_id", 0),
        "seid": pkt.get("seid"),
        "sequence_number": pkt.get("sequence_number", 0),
        "length": pkt.get("length", 0),
        "src_addr": pkt.get("src_addr", ""),
        "dst_addr": pkt.get("dst_addr", ""),
        "logical_src": pkt.get("logical_src", ""),
        "logical_dst": pkt.get("logical_dst", ""),
    }


# ---- Status ----

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get current relay status including queue statistics"""
    q_stats = _relay.queue_stats if _relay else {}
    return StatusResponse(
        running=_relay.running if _relay else False,
        intercept_enabled=_interceptor.enabled if _interceptor else False,
        target_addr=_relay.config.relay.target_addr if _relay else "",
        target_port=_relay.config.relay.target_port if _relay else 8805,
        listen_addr=_relay.config.relay.listen_addr if _relay else "",
        listen_port=_relay.config.relay.listen_port if _relay else 8805,
        packets_captured=_relay.buffer.count if _relay else 0,
        packets_intercepted=_interceptor.held_count if _interceptor else 0,
        uptime_seconds=_relay.uptime if _relay else None,
        queue_depth=q_stats.get("queue_depth", 0),
        queue_max_size=q_stats.get("queue_max_size", 0),
        queue_overflow_dropped=q_stats.get("queue_overflow_dropped", 0),
        queue_processed_total=q_stats.get("queue_processed_total", 0),
        worker_count=q_stats.get("worker_count", 0),
    )


@router.put("/status", response_model=StatusResponse)
async def update_status(req: StatusUpdateRequest):
    """Update relay status (start/stop, toggle intercept, change target)"""
    if not _relay:
        raise HTTPException(500, "Relay not initialized")

    # Start/stop relay
    if req.running is not None:
        if req.running and not _relay.running:
            await _relay.start()
        elif not req.running and _relay.running:
            await _relay.stop()

    # Toggle intercept
    if req.intercept_enabled is not None and _interceptor:
        _interceptor.enabled = req.intercept_enabled

    # Update target
    if req.target_addr is not None or req.target_port is not None:
        addr = req.target_addr or _relay.config.relay.target_addr
        port = req.target_port or _relay.config.relay.target_port
        _relay.update_target(addr, port)

    return await get_status()


# ---- Packets ----

@router.get("/packets", response_model=PacketListResponse)
async def list_packets(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    msg_type: Optional[str] = Query(None, description="Filter by message type"),
    direction: Optional[str] = Query(None, description="Filter by direction"),
    exclude_heartbeat: bool = Query(True, description="Exclude heartbeat messages"),
):
    """List captured packets with optional filters"""
    if not _relay:
        raise HTTPException(500, "Relay not initialized")

    total, packets = await _relay.buffer.get_all(
        offset=offset, limit=limit, msg_type=msg_type, direction=direction,
        exclude_heartbeat=exclude_heartbeat
    )

    return PacketListResponse(
        total=total,
        packets=[PacketSummary(**_packet_to_summary(p)) for p in packets],
    )


@router.get("/packets/{packet_id}", response_model=PacketDetail)
async def get_packet(packet_id: int):
    """Get detailed info of a specific packet"""
    if not _relay:
        raise HTTPException(500, "Relay not initialized")

    pkt = await _relay.buffer.get(packet_id)
    if not pkt:
        raise HTTPException(404, f"Packet {packet_id} not found")

    summary = _packet_to_summary(pkt)
    return PacketDetail(
        **summary,
        header=pkt.get("header", {}),
        ies=pkt.get("ies", []),
        raw_hex=pkt.get("raw_hex", ""),
        parse_error=pkt.get("parse_error"),
    )


@router.delete("/packets", response_model=SuccessResponse)
async def clear_packets():
    """Clear all captured packets"""
    if not _relay:
        raise HTTPException(500, "Relay not initialized")

    await _relay.buffer.clear()
    return SuccessResponse(message="All packets cleared")


# ---- Intercepted ----

@router.get("/intercepted", response_model=list)
async def list_intercepted():
    """List all currently intercepted (held) packets"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")

    held = await _interceptor.get_held()
    return [InterceptedPacket(**h) for h in held]


@router.get("/intercepted/{intercept_id}", response_model=InterceptedPacketDetail)
async def get_intercepted(intercept_id: str):
    """Get detailed info of an intercepted packet"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")

    detail = await _interceptor.get_held_detail(intercept_id)
    if not detail:
        raise HTTPException(404, f"Intercepted packet '{intercept_id}' not found")

    return InterceptedPacketDetail(**detail)


@router.put("/intercepted/{intercept_id}")
async def modify_intercepted(intercept_id: str, req: ModifyRequest):
    """Modify an intercepted packet's fields"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")

    success = await _interceptor.modify(intercept_id, req.modifications)
    if not success:
        raise HTTPException(404, f"Cannot modify: packet '{intercept_id}' not found or not held")

    return SuccessResponse(message=f"Modifications applied to '{intercept_id}'. They will take effect on release.")


@router.post("/intercepted/{intercept_id}/release", response_model=ReleaseResponse)
async def release_intercepted(intercept_id: str):
    """Release (forward) an intercepted packet"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")

    result = await _interceptor.release(intercept_id)
    if result is None:
        raise HTTPException(404, f"Intercepted packet '{intercept_id}' not found")
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(400, result["error"])

    return ReleaseResponse(
        id=intercept_id,
        status="released",
        message="Packet forwarded to destination",
    )


@router.post("/intercepted/{intercept_id}/drop")
async def drop_intercepted(intercept_id: str):
    """Drop an intercepted packet (do not forward)"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")

    result = await _interceptor.drop(intercept_id)
    if result is None:
        raise HTTPException(404, f"Intercepted packet '{intercept_id}' not found")

    return SuccessResponse(message=f"Packet '{intercept_id}' dropped")


@router.post("/intercepted/release-all")
async def release_all_intercepted():
    """Release all held packets"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")
    result = await _interceptor.release_all()
    return SuccessResponse(message=f"Released {result['released']} packet(s)" + (f", {result['errors']} error(s)" if result['errors'] else ""))


@router.post("/intercepted/drop-all")
async def drop_all_intercepted():
    """Drop all held packets"""
    if not _interceptor:
        raise HTTPException(500, "Interceptor not initialized")
    result = await _interceptor.drop_all()
    return SuccessResponse(message=f"Dropped {result['dropped']} packet(s)")


# ---- Templates ----

from ..pfcp.constants import MessageType


def _template_to_response(t: dict) -> dict:
    """Convert a raw template dict to a TemplateResponse dict."""
    resp_hex = t.get("response_hex", "")
    return {
        "id": t["id"],
        "name": t.get("name", ""),
        "match_msg_type": t.get("match_msg_type", 0),
        "match_msg_type_name": MessageType.get_name(t.get("match_msg_type", 0)),
        "match_seid": t.get("match_seid"),
        "response_hex": resp_hex,
        "response_length": len(bytes.fromhex(resp_hex)) if resp_hex else 0,
        "auto_seq": t.get("auto_seq", True),
        "auto_seid": t.get("auto_seid", False),
        "enabled": t.get("enabled", True),
        "hit_count": t.get("hit_count", 0),
    }


@router.get("/templates")
async def list_templates():
    """List all response templates"""
    if not _template_store:
        raise HTTPException(500, "Template store not initialized")
    templates = await _template_store.get_all()
    return [_template_to_response(t) for t in templates]


@router.post("/templates")
async def create_template(req: TemplateCreate):
    """Create a new response template"""
    if not _template_store:
        raise HTTPException(500, "Template store not initialized")
    t = req.model_dump()
    tid = await _template_store.add(t)
    return _template_to_response(await _template_store.get(tid))


@router.get("/templates/{tid}")
async def get_template(tid: str):
    """Get a single template"""
    if not _template_store:
        raise HTTPException(500, "Template store not initialized")
    t = await _template_store.get(tid)
    if not t:
        raise HTTPException(404, f"Template '{tid}' not found")
    return _template_to_response(t)


@router.put("/templates/{tid}")
async def update_template(tid: str, req: TemplateUpdate):
    """Update a template"""
    if not _template_store:
        raise HTTPException(500, "Template store not initialized")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    ok = await _template_store.update(tid, updates)
    if not ok:
        raise HTTPException(404, f"Template '{tid}' not found")
    return _template_to_response(await _template_store.get(tid))


@router.delete("/templates/{tid}")
async def delete_template(tid: str):
    """Delete a template"""
    if not _template_store:
        raise HTTPException(500, "Template store not initialized")
    ok = await _template_store.delete(tid)
    if not ok:
        raise HTTPException(404, f"Template '{tid}' not found")
    return SuccessResponse(message=f"Template '{tid}' deleted")


# ---- Parse Hex ----

from ..pfcp.parser import parse_pfcp_message, PFCPParseError
from ..pfcp.constants import PFCP_HEADER_LEN_NO_SEID, PFCP_HEADER_LEN_WITH_SEID, IEType
from pydantic import BaseModel
from typing import List, Optional
import struct as _struct
import socket as _socket


class _ParseHexBody(BaseModel):
    hex: str


# Edit metadata config: which parsed fields are directly editable
_IE_EDIT_FIELDS = {
    19: [  # Cause
        {"label": "Cause", "key": "cause", "type": "number", "vk": "cause"},
    ],
    20: [  # Source Interface
        {"label": "Source Interface", "key": "interface", "type": "number", "vk": "interface"},
    ],
    22: [  # Network Instance (FQDN)
        {"label": "Network Instance", "key": "network_instance", "type": "text", "vk": "network_instance"},
    ],
    25: [  # Gate Status
        {"label": "UL Gate", "key": "ul_gate", "type": "number", "vk": "ul_gate"},
        {"label": "DL Gate", "key": "dl_gate", "type": "number", "vk": "dl_gate"},
    ],
    29: [{"label": "Precedence", "key": "precedence", "type": "number", "vk": "precedence"}],
    42: [  # Destination Interface
        {"label": "Destination Interface", "key": "interface", "type": "number", "vk": "interface"},
    ],
    56: [{"label": "Rule ID", "key": "pdr_id", "type": "number", "vk": "pdr_id"}],
    60: [  # Node ID
        {"label": "Address Type", "key": "node_id_type_value", "type": "number", "vk": "node_id_type_value"},
        {"label": "IPv4 address", "key": "ipv4_address", "type": "text", "vk": "ipv4_address"},
        {"label": "IPv6 address", "key": "ipv6_address", "type": "text", "vk": "ipv6_address"},
        {"label": "FQDN", "key": "fqdn", "type": "text", "vk": "fqdn"},
    ],
    81: [{"label": "URR ID", "key": "urr_id", "type": "number", "vk": "urr_id"}],
    88: [{"label": "BAR ID", "key": "bar_id", "type": "number", "vk": "bar_id"}],
    93: [  # UE IP Address
        {"label": "IPv4 address", "key": "ipv4", "type": "text", "vk": "ipv4"},
        {"label": "IPv6 address", "key": "ipv6", "type": "text", "vk": "ipv6"},
    ],
    95: [{"label": "Outer Header Removal Description", "key": "description", "type": "number", "vk": "description"}],
    108: [{"label": "FAR ID", "key": "far_id", "type": "number", "vk": "far_id"}],
    109: [{"label": "QER ID", "key": "qer_id", "type": "number", "vk": "qer_id"}],
    57: [  # F-SEID
        {"label": "SEID", "key": "seid", "type": "text", "vk": "seid_hex"},
        {"label": "IPv4 address", "key": "ipv4_address", "type": "text", "vk": "ipv4_address"},
        {"label": "IPv6 address", "key": "ipv6_address", "type": "text", "vk": "ipv6_address"},
    ],
    21: [  # F-TEID
        {"label": "TEID", "key": "teid", "type": "text", "vk": "teid_hex"},
        {"label": "IPv4 address", "key": "ipv4_address", "type": "text", "vk": "ipv4_address"},
        {"label": "IPv6 address", "key": "ipv6_address", "type": "text", "vk": "ipv6_address"},
    ],
    85: [  # Outer Header Creation
        {"label": "TEID", "key": "teid", "type": "text", "vk": "teid"},
        {"label": "IPv4 address", "key": "ipv4_address", "type": "text", "vk": "ipv4_address"},
        {"label": "IPv6 address", "key": "ipv6_address", "type": "text", "vk": "ipv6_address"},
        {"label": "Port", "key": "port", "type": "number", "vk": "port"},
    ],
}

# Flag-based IEs (special handling for Apply Action etc.)
_IE_FLAG_EDIT = {
    44: {  # Apply Action
        "flags_key": "flags",
        "items": [
            {"name": "DROP", "bit": 0x01},
            {"name": "FORWARD", "bit": 0x02},
            {"name": "BUFFER", "bit": 0x04},
            {"name": "NOTIFY", "bit": 0x08},
            {"name": "DUPLICATE", "bit": 0x10},
        ],
    },
    21: {  # F-TEID
        "flags_key": "flags",
        "value_key": "flags",
        "items": [
            {"name": "V4", "bit": 0x01},
            {"name": "V6", "bit": 0x02},
            {"name": "CH", "bit": 0x04},
            {"name": "CHID", "bit": 0x08},
        ],
    },
    57: {  # F-SEID
        "flags_key": "flags",
        "value_key": "flags",
        "items": [
            {"name": "V4", "bit": 0x01},
            {"name": "V6", "bit": 0x02},
        ],
    },
}


def _enrich_ie_edit_info(ie: dict):
    """Add edit_key, edit_type, edit_value to _fields entries for inline editing."""
    ie_type = ie.get("type", 0)

    # Recurse into group IEs
    if ie.get("group") and ie.get("ies"):
        for sub_ie in ie["ies"]:
            _enrich_ie_edit_info(sub_ie)
        # Add _edit_mode = 'group' to indicate group IE editing
        ie["_edit_mode"] = "group"
        return

    value = ie.get("value")
    if not value or not isinstance(value, dict):
        return

    fields = value.get("_fields")
    if not fields:
        return

    # Standard field-level editing
    edit_config = _IE_EDIT_FIELDS.get(ie_type, [])
    for spec in edit_config:
        label_prefix = spec["label"]
        for field in fields:
            if field.get("edit_key"):
                continue
            if str(field.get("label", "")).startswith(label_prefix):
                vk = spec["vk"]
                raw_val = value.get(vk)
                if raw_val is not None:
                    field["edit_key"] = spec["key"]
                    field["edit_type"] = spec["type"]
                    # For display: strip extra info from value for editing
                    if spec["type"] == "text":
                        # Extract clean value (before parenthetical info)
                        field["edit_value"] = str(raw_val)
                    else:
                        field["edit_value"] = raw_val
                break  # only match first occurrence

    # Flag-based editing (e.g., Apply Action)
    flag_config = _IE_FLAG_EDIT.get(ie_type)
    if flag_config:
        flags_raw = value.get(flag_config["flags_key"], {})
        ie["_edit_mode"] = "flags"
        ie["_flag_items"] = []
        for item in flag_config["items"]:
            # Support both dict flags (Apply Action) and integer bitfield flags (F-TEID/F-SEID)
            if isinstance(flags_raw, int):
                checked = bool(flags_raw & item["bit"])
            else:
                checked = bool(flags_raw.get(item["name"], False))
            ie["_flag_items"].append({
                "name": item["name"],
                "bit": item["bit"],
                "checked": checked,
            })

    # Mark the IE as having inline editing
    if edit_config or flag_config:
        ie["_edit_mode"] = ie.get("_edit_mode", "fields")


@router.post("/parse-hex")
async def parse_hex(req: _ParseHexBody):
    """Parse a PFCP hex string and return structured header + IEs."""
    hex_str = req.hex.strip().replace(" ", "").replace("\n", "")
    if not hex_str:
        raise HTTPException(400, "Empty hex string")
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError:
        raise HTTPException(400, "Invalid hex string")
    try:
        parsed = parse_pfcp_message(raw)
    except PFCPParseError as e:
        raise HTTPException(400, f"PFCP parse error: {e}")
    # Enrich IEs with inline-edit metadata
    for ie in parsed.get("ies", []):
        _enrich_ie_edit_info(ie)
    return {
        "header": parsed.get("header", {}),
        "ies": parsed.get("ies", []),
    }


# ---- Extract IE hex by index ----

class _ExtractIEBody(BaseModel):
    hex: str
    index: int


@router.post("/extract-ie")
async def extract_ie(req: _ExtractIEBody):
    """Return the raw hex of a specific IE by index from a PFCP message."""
    hex_str = req.hex.strip().replace(" ", "").replace("\n", "")
    if not hex_str:
        raise HTTPException(400, "Empty hex string")
    try:
        data = bytes.fromhex(hex_str)
    except ValueError:
        raise HTTPException(400, "Invalid hex string")
    if len(data) < PFCP_HEADER_LEN_NO_SEID:
        raise HTTPException(400, "Data too short")

    s_flag = data[0] & 0x01
    ie_start = PFCP_HEADER_LEN_WITH_SEID if s_flag else PFCP_HEADER_LEN_NO_SEID
    msg_length = _struct.unpack("!H", data[2:4])[0]
    ies_end = min(4 + msg_length, len(data))
    pos = ie_start
    current_idx = 0

    while pos + 4 <= ies_end:
        ie_type_val = _struct.unpack("!H", data[pos:pos + 2])[0]
        ie_len = _struct.unpack("!H", data[pos + 2:pos + 4])[0]
        if pos + 4 + ie_len > ies_end:
            break
        if current_idx == req.index:
            ie_data = data[pos + 4:pos + 4 + ie_len]
            return {"hex": ie_data.hex(), "type": ie_type_val, "length": ie_len}
        pos += 4 + ie_len
        current_idx += 1

    raise HTTPException(404, f"IE at index {req.index} not found")


# ---- Serialize IE value from structured fields ----

class _SerializeIEBody(BaseModel):
    ie_type: int
    fields: dict


def _encode_dns_wire(fqdn: str) -> bytes:
    """Encode an FQDN string to DNS wire-format (label-length encoding)."""
    result = b""
    for label in fqdn.split("."):
        label_bytes = label.encode("ascii", errors="replace")
        result += bytes([len(label_bytes)]) + label_bytes
    return result


def _serialize_ie_value(ie_type_val: int, fields: dict) -> bytes:
    """Serialize structured field values back to IE value bytes."""
    from ..pfcp.constants import IEType, CAUSE_VALUES, INTERFACE_VALUES
    import socket as _sock

    # Simple numeric ID IEs
    _SIMPLE_PACK = {
        56: ("!H", "pdr_id"),       # PDR ID
        108: ("!I", "far_id"),      # FAR ID
        109: ("!I", "qer_id"),      # QER ID
        81: ("!I", "urr_id"),       # URR ID
        88: ("!B", "bar_id"),       # BAR ID
        29: ("!I", "precedence"),   # Precedence
    }
    if ie_type_val in _SIMPLE_PACK:
        fmt, key = _SIMPLE_PACK[ie_type_val]
        val = int(fields.get(key, 0))
        return _struct.pack(fmt, val)

    # Cause (19)
    if ie_type_val == 19:
        cause = int(fields.get("cause", 1))
        return bytes([cause & 0xFF])

    # Source Interface (20) / Destination Interface (42)
    if ie_type_val in (20, 42):
        intf = int(fields.get("interface", 0))
        return bytes([intf & 0x0F])

    # Network Instance (22) - FQDN as plain UTF-8
    if ie_type_val == 22:
        ni = fields.get("network_instance", "")
        return ni.encode("utf-8")

    # Gate Status (25)
    if ie_type_val == 25:
        ul = int(fields.get("ul_gate", 0))
        dl = int(fields.get("dl_gate", 0))
        return bytes([((ul & 0x03) << 2) | (dl & 0x03)])

    # Apply Action (44)
    if ie_type_val == 44:
        action = int(fields.get("action", 0))
        if action <= 0xFF:
            return bytes([action])
        elif action <= 0xFFFF:
            return _struct.pack("!H", action)
        else:
            return _struct.pack("!I", action)[1:]  # 3 bytes

    # Node ID (60)
    if ie_type_val == 60:
        node_type = int(fields.get("node_id_type_value", 0))
        flags_byte = node_type & 0x0F
        if node_type == 0:  # IPv4
            ip = fields.get("ipv4_address", "0.0.0.0")
            return bytes([flags_byte]) + _sock.inet_aton(ip)
        elif node_type == 1:  # IPv6
            ip = fields.get("ipv6_address", "::")
            return bytes([flags_byte]) + _sock.inet_pton(_sock.AF_INET6, ip)
        elif node_type == 2:  # FQDN
            fqdn = fields.get("fqdn", "")
            return bytes([flags_byte]) + _encode_dns_wire(fqdn)
        return bytes([flags_byte])

    # UE IP Address (93)
    if ie_type_val == 93:
        flags = int(fields.get("flags", 0))
        result = bytes([flags])
        if flags & 0x02:  # V4
            ip = fields.get("ipv4", "0.0.0.0")
            result += _sock.inet_aton(ip)
        if flags & 0x01:  # V6
            ip = fields.get("ipv6", "::")
            result += _sock.inet_pton(_sock.AF_INET6, ip)
        return result

    # F-SEID (57)
    if ie_type_val == 57:
        flags = int(fields.get("flags", 0))
        seid = int(fields.get("seid", 0))
        result = bytes([flags]) + _struct.pack("!Q", seid)
        if flags & 0x01:  # V4
            ip = fields.get("ipv4_address", "0.0.0.0")
            result += _sock.inet_aton(ip)
        if flags & 0x02:  # V6
            ip = fields.get("ipv6_address", "::")
            result += _sock.inet_pton(_sock.AF_INET6, ip)
        return result

    # F-TEID (21)
    if ie_type_val == 21:
        flags = int(fields.get("flags", 0))
        teid = int(fields.get("teid", 0))
        result = bytes([flags]) + _struct.pack("!I", teid)
        if flags & 0x01:  # V4
            ip = fields.get("ipv4_address", "0.0.0.0")
            result += _sock.inet_aton(ip)
        if flags & 0x02:  # V6
            ip = fields.get("ipv6_address", "::")
            result += _sock.inet_pton(_sock.AF_INET6, ip)
        if flags & 0x08:  # CHID
            result += bytes([int(fields.get("choose_id_value", 0))])
        return result

    # Outer Header Removal (95)
    if ie_type_val == 95:
        desc = int(fields.get("description", 0))
        return bytes([desc & 0xFF])

    # Outer Header Creation (85)
    if ie_type_val == 85:
        desc = int(fields.get("description", 0))
        result = _struct.pack("!H", desc)
        if desc & 0x0300:  # GTP-U
            teid = int(fields.get("teid", 0))
            result += _struct.pack("!I", teid)
            if desc & 0x0100:  # IPv4
                result += _sock.inet_aton(fields.get("ipv4_address", "0.0.0.0"))
            if desc & 0x0200:  # IPv6
                result += _sock.inet_pton(_sock.AF_INET6, fields.get("ipv6_address", "::"))
            result += _struct.pack("!H", int(fields.get("port", 2152)))
        elif desc & 0x0C00:  # UDP/IP
            if desc & 0x0400:
                result += _sock.inet_aton(fields.get("ipv4_address", "0.0.0.0"))
            if desc & 0x0800:
                result += _sock.inet_pton(_sock.AF_INET6, fields.get("ipv6_address", "::"))
            result += _struct.pack("!H", int(fields.get("port", 0)))
        return result

    # Fallback: try to use "raw" hex from fields
    raw = fields.get("raw", "")
    if raw:
        return bytes.fromhex(raw.replace(" ", ""))

    raise ValueError(f"Cannot serialize IE type {ie_type_val}: unsupported or missing fields")


@router.post("/serialize-ie")
async def serialize_ie(req: _SerializeIEBody):
    """Serialize structured IE field values back to hex bytes."""
    try:
        data = _serialize_ie_value(req.ie_type, req.fields)
        return {"hex": data.hex(), "length": len(data)}
    except (ValueError, _struct.error, OSError) as e:
        raise HTTPException(400, f"Failed to serialize IE type {req.ie_type}: {e}")


# ---- Rebuild Hex (comprehensive IE manipulation) ----

class _HexOp(BaseModel):
    op: str  # edit_header | edit_ie | add_ie | delete_ie | raw_edit
    index: Optional[int] = None
    field: Optional[str] = None
    value: Optional[str] = None
    ie_type: Optional[int] = None
    hex: Optional[str] = None
    offset: Optional[int] = None


class _RebuildHexBody(BaseModel):
    hex: str
    operations: List[_HexOp]
    # Legacy support
    edits: Optional[List[dict]] = None


def _find_ie_positions(data: bytearray, s_flag: int) -> tuple:
    """Return (ie_start, ies_end, ie_positions) where ie_positions is list of (pos, total_len)."""
    ie_start = PFCP_HEADER_LEN_WITH_SEID if s_flag else PFCP_HEADER_LEN_NO_SEID
    msg_length = _struct.unpack("!H", data[2:4])[0]
    ies_end = min(4 + msg_length, len(data))
    positions = []
    pos = ie_start
    while pos + 4 <= ies_end:
        ie_len = _struct.unpack("!H", data[pos + 2:pos + 4])[0]
        if pos + 4 + ie_len > ies_end:
            break
        positions.append((pos, 4 + ie_len))
        pos += 4 + ie_len
    return ie_start, ies_end, positions


def _update_msg_length(data: bytearray):
    """Recalculate and update the message length field."""
    data[2:4] = _struct.pack("!H", len(data) - 4)


def _apply_header_edit(data: bytearray, s_flag: int, op: _HexOp, applied: list):
    """Apply a header field edit."""
    field = op.field or ""
    val_str = (op.value or "").strip()
    if field == "sequence_number":
        seq = int(val_str, 0)
        seq_bytes = _struct.pack("!I", seq)[1:]
        if s_flag and len(data) >= 15:
            data[12:15] = seq_bytes
        elif not s_flag and len(data) >= 7:
            data[4:7] = seq_bytes
        applied.append(f"header.{field}")
    elif field == "seid":
        if s_flag and len(data) >= 12:
            data[4:12] = _struct.pack("!Q", int(val_str, 0))
            applied.append("header.seid")
    elif field == "message_type":
        data[1] = int(val_str, 0) & 0xFF
        applied.append("header.message_type")
    elif field == "version":
        # Version is bits 7-5 of byte 0
        ver = int(val_str, 0) & 0x07
        data[0] = (data[0] & 0x1F) | (ver << 5)
        applied.append("header.version")
    elif field == "mp":
        # MP flag is bit 1 of byte 0
        if val_str.lower() in ("true", "1", "yes", "on"):
            data[0] |= 0x02
        else:
            data[0] &= ~0x02
        applied.append("header.mp")
    elif field == "fo":
        # Follow-On flag is bit 2 of byte 0
        if val_str.lower() in ("true", "1", "yes", "on"):
            data[0] |= 0x04
        else:
            data[0] &= ~0x04
        applied.append("header.fo")
    elif field == "seid_flag":
        # S flag is bit 0 of byte 0 — toggling changes header structure
        new_s = val_str.lower() in ("true", "1", "yes", "on")
        old_s = bool(data[0] & 0x01)
        if new_s != old_s:
            if new_s:
                # Enable S flag: insert 8 bytes (SEID) after byte 4
                data[0] |= 0x01
                seid_bytes = _struct.pack("!Q", 0)
                data[4:4] = seid_bytes
            else:
                # Disable S flag: remove 8 bytes (SEID) from bytes 4-12
                data[0] &= ~0x01
                del data[4:12]
            # Recalculate length field
            msg_length = len(data) - 4
            data[2:4] = _struct.pack("!H", msg_length)
        applied.append("header.seid_flag")
    elif field == "length":
        # Length field at bytes 2-3 (covers everything after first 4 bytes)
        new_len = int(val_str, 0) & 0xFFFF
        data[2:4] = _struct.pack("!H", new_len)
        applied.append("header.length")


def _apply_ie_edit(data: bytearray, s_flag: int, op: _HexOp, applied: list):
    """Replace an IE's value bytes."""
    idx = op.index
    new_hex = (op.hex or "").strip().replace(" ", "").replace("\n", "")
    if idx is None or not new_hex:
        return
    new_data = bytes.fromhex(new_hex)
    _, _, positions = _find_ie_positions(data, s_flag)
    if idx >= len(positions):
        return
    pos, total_len = positions[idx]
    ie_type_val = _struct.unpack("!H", data[pos:pos + 2])[0]
    new_ie = _struct.pack("!HH", ie_type_val, len(new_data)) + new_data
    data[pos:pos + total_len] = new_ie
    _update_msg_length(data)
    applied.append(f"edit_ie[{idx}]")


def _apply_ie_add(data: bytearray, s_flag: int, op: _HexOp, applied: list):
    """Add a new IE."""
    ie_type = op.ie_type
    new_hex = (op.hex or "").strip().replace(" ", "").replace("\n", "")
    if ie_type is None:
        return
    new_data = bytes.fromhex(new_hex) if new_hex else b""
    # Insert at the end of all data (after any existing IEs)
    insert_pos = len(data)
    new_ie = _struct.pack("!HH", ie_type, len(new_data)) + new_data
    data[insert_pos:insert_pos] = new_ie
    _update_msg_length(data)
    applied.append(f"add_ie(type={ie_type})")


def _apply_ie_delete(data: bytearray, s_flag: int, op: _HexOp, applied: list):
    """Delete an IE by index."""
    idx = op.index
    if idx is None:
        return
    _, _, positions = _find_ie_positions(data, s_flag)
    if idx >= len(positions):
        return
    pos, total_len = positions[idx]
    del data[pos:pos + total_len]
    _update_msg_length(data)
    applied.append(f"delete_ie[{idx}]")


@router.post("/rebuild-hex")
async def rebuild_hex(req: _RebuildHexBody):
    """Apply structural edits to a PFCP hex string with automatic length recalculation."""
    hex_str = req.hex.strip().replace(" ", "").replace("\n", "")
    if not hex_str:
        raise HTTPException(400, "Empty hex string")
    try:
        data = bytearray(bytes.fromhex(hex_str))
    except ValueError:
        raise HTTPException(400, "Invalid hex string")
    if len(data) < PFCP_HEADER_LEN_NO_SEID:
        raise HTTPException(400, "Data too short for PFCP header")

    s_flag = data[0] & 0x01
    applied: list[str] = []

    # Process structured operations
    for op in req.operations:
        try:
            if op.op == "edit_header":
                _apply_header_edit(data, s_flag, op, applied)
                # Re-read S flag after header edits (S flag toggle changes structure)
                s_flag = data[0] & 0x01
            elif op.op == "edit_ie":
                _apply_ie_edit(data, s_flag, op, applied)
            elif op.op == "add_ie":
                _apply_ie_add(data, s_flag, op, applied)
            elif op.op == "delete_ie":
                _apply_ie_delete(data, s_flag, op, applied)
            elif op.op == "raw_edit":
                # Direct byte patching at offset
                offset = op.offset or 0
                new_hex = (op.hex or "").strip().replace(" ", "")
                new_bytes = bytes.fromhex(new_hex)
                if offset + len(new_bytes) <= len(data):
                    data[offset:offset + len(new_bytes)] = new_bytes
                    applied.append(f"raw_edit@{offset}")
        except (ValueError, _struct.error, IndexError) as e:
            logger.warning(f"Failed to apply op {op.op}: {e}")
            continue

    # Legacy edits support (backward compatibility)
    if req.edits:
        for edit_dict in req.edits:
            field = edit_dict.get("field", "")
            val_str = edit_dict.get("value", "").strip()
            try:
                if field == "header.sequence_number":
                    seq = int(val_str, 0)
                    seq_bytes = _struct.pack("!I", seq)[1:]
                    if s_flag and len(data) >= 15:
                        data[12:15] = seq_bytes
                    elif not s_flag and len(data) >= 7:
                        data[4:7] = seq_bytes
                    applied.append(field)
                elif field == "header.seid" and s_flag and len(data) >= 12:
                    data[4:12] = _struct.pack("!Q", int(val_str, 0))
                    applied.append(field)
                elif field.startswith("ie."):
                    parts = field.split(".", 3)
                    if len(parts) >= 3:
                        ie_idx = int(parts[1])
                        _, _, positions = _find_ie_positions(data, s_flag)
                        if ie_idx < len(positions):
                            pos, total_len = positions[ie_idx]
                            ie_type_val = _struct.unpack("!H", data[pos:pos + 2])[0]
                            new_bytes = bytes.fromhex(val_str.replace(" ", ""))
                            new_ie = _struct.pack("!HH", ie_type_val, len(new_bytes)) + new_bytes
                            data[pos:pos + total_len] = new_ie
                            _update_msg_length(data)
                            applied.append(field)
            except (ValueError, _struct.error) as e:
                logger.warning(f"Failed legacy edit {field}: {e}")
                continue

    return {"hex": data.hex(), "applied": applied}


@router.post("/templates/{tid}/toggle")
async def toggle_template(tid: str):
    """Toggle a template's enabled state"""
    if not _template_store:
        raise HTTPException(500, "Template store not initialized")
    t = await _template_store.get(tid)
    if not t:
        raise HTTPException(404, f"Template '{tid}' not found")
    new_state = not t.get("enabled", True)
    await _template_store.set_enabled(tid, new_state)
    return SuccessResponse(message=f"Template '{tid}' {'enabled' if new_state else 'disabled'}")
