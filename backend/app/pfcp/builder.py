"""
PFCP Message Builder/Serializer per 3GPP TS 29.244
Re-serializes modified PFCP messages back to binary format.
"""
import struct
import copy
import logging
from typing import Dict, Any, List

from .constants import (
    IEType, PFCP_VERSION, GROUP_IE_TYPES,
    PFCP_HEADER_LEN_NO_SEID, PFCP_HEADER_LEN_WITH_SEID,
)
from .ies import IE_BUILDERS, build_simple_ie

logger = logging.getLogger(__name__)


def build_pfcp_header(header: Dict[str, Any], body_length: int) -> bytes:
    """
    Build PFCP header from parsed header dict.

    Adjusts the length field to match the actual body size.
    """
    version = header.get("version", PFCP_VERSION)
    mp = header.get("mp", False)
    seid_flag = header.get("seid_flag", False)
    msg_type = header.get("message_type", 0)
    seq = header.get("sequence_number", 0)

    first_byte = (version & 0x07) << 5
    if mp:
        first_byte |= 0x02
    if seid_flag:
        first_byte |= 0x01

    if seid_flag:
        # Header with SEID: 16 bytes
        # Length field = body_length + 12 (SEID + Seq + Spare)
        length = body_length + 12
        seid = header.get("seid", 0)
        result = struct.pack("!BBH", first_byte, msg_type, length)
        result += struct.pack("!Q", seid)
        result += struct.pack("!I", seq)[1:]  # 3 bytes seq
        result += struct.pack("!B", 0)  # spare
        return result
    else:
        # Header without SEID: 8 bytes
        # Length field = body_length + 4 (Seq + Spare)
        length = body_length + 4
        result = struct.pack("!BBH", first_byte, msg_type, length)
        result += struct.pack("!I", seq)[1:]  # 3 bytes seq
        result += struct.pack("!B", 0)  # spare
        return result


def build_ie(ie: Dict[str, Any], modifications: Dict[str, Any] = None) -> bytes:
    """
    Build a single IE from parsed IE dict, applying any modifications.

    Args:
        ie: The parsed IE structure
        modifications: Optional dict of field modifications to apply
    """
    ie_type_val = ie["type"]
    ie_data = _build_ie_value(ie, modifications or {})

    # IE header: type(2) + length(2)
    result = struct.pack("!HH", ie_type_val, len(ie_data))
    result += ie_data
    return result


def _build_ie_value(ie: Dict[str, Any], modifications: Dict[str, Any]) -> bytes:
    """Build the IE value (body) portion"""
    try:
        ie_type = IEType(ie["type"])
    except ValueError:
        ie_type = None

    # For group IEs, recursively build sub-IEs
    if ie.get("group") and "ies" in ie:
        sub_mods = modifications.get("ies", {})
        result = b""
        for i, sub_ie in enumerate(ie["ies"]):
            sub_mod = sub_mods.get(str(i), sub_mods.get(sub_ie.get("type_name", ""), {}))
            result += build_ie(sub_ie, sub_mod if isinstance(sub_mod, dict) else {})
        return result

    # Apply modifications to value if any
    value = copy.deepcopy(ie.get("value", {}))
    if "value" in modifications:
        _deep_merge(value, modifications["value"])

    # Use specific builder if available
    if ie_type and ie_type in IE_BUILDERS:
        return IE_BUILDERS[ie_type](value)

    # Use simple IE builder if available
    if ie_type:
        original_data = bytes.fromhex(ie.get("value", {}).get("raw", "")) if isinstance(ie.get("value"), dict) and "raw" in ie.get("value", {}) else b""
        return build_simple_ie(ie_type, value, original_data)

    # Fallback: use original raw hex
    if isinstance(ie.get("value"), dict) and "raw" in ie["value"]:
        return bytes.fromhex(ie["value"]["raw"])

    return b""


def build_ies(ies: List[Dict[str, Any]], modifications: Dict[str, Any] = None) -> bytes:
    """
    Build a list of IEs, applying modifications where specified.
    """
    result = b""
    mods = modifications or {}

    for i, ie in enumerate(ies):
        ie_mod = mods.get(str(i), mods.get(ie.get("type_name", ""), {}))
        result += build_ie(ie, ie_mod if isinstance(ie_mod, dict) else {})

    return result


def build_pfcp_message(packet: Dict[str, Any], modifications: Dict[str, Any] = None) -> bytes:
    """
    Rebuild a complete PFCP message from a parsed packet, applying modifications.

    Args:
        packet: The parsed packet structure (with header and ies)
        modifications: Optional modifications dict with "header" and/or "ies" keys

    Returns:
        bytes: The serialized PFCP message
    """
    mods = modifications or {}
    header = copy.deepcopy(packet.get("header", {}))
    ies = packet.get("ies", [])

    # Apply header modifications
    header_mods = mods.get("header", {})
    if header_mods:
        _deep_merge(header, header_mods)

    # Build IE body
    ie_mods = mods.get("ies", {})
    body = build_ies(ies, ie_mods)

    # Build header with correct length
    result = build_pfcp_header(header, len(body))
    result += body

    return result


def _deep_merge(base: dict, updates: dict):
    """Recursively merge updates into base dict"""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
