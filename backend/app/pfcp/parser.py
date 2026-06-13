"""
PFCP Message Parser per 3GPP TS 29.244
Parses binary PFCP messages into structured dictionaries.
"""
import struct
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .constants import (
    MessageType, IEType, PFCP_VERSION,
    PFCP_HEADER_LEN_NO_SEID, PFCP_HEADER_LEN_WITH_SEID,
    GROUP_IE_TYPES,
)
from .ies import IE_PARSERS, parse_simple_ie

logger = logging.getLogger(__name__)


class PFCPParseError(Exception):
    pass


def _bit_str(byte_val: int, start: int, width: int) -> str:
    """Extract bits from byte and return binary string."""
    mask = ((1 << width) - 1) << (start - width + 1)
    val = (byte_val & mask) >> (start - width + 1)
    return f'{val:0{width}b}'


def parse_pfcp_header(data: bytes) -> Dict[str, Any]:
    """
    Parse PFCP header with Wireshark-style field metadata.

    Header format (without SEID, for node-related messages):
      Octet 1: Version(3b) | Spare(3b) | MP(1b) | S(1b)
      Octet 2: Message Type
      Octet 3-4: Length
      Octet 5-7: Sequence Number
      Octet 8: Spare

    Header format (with SEID, for session-related messages):
      Octet 1: Version(3b) | Spare(3b) | MP(1b) | S(1b)
      Octet 2: Message Type
      Octet 3-4: Length
      Octet 5-12: SEID (64 bits)
      Octet 13-15: Sequence Number
      Octet 16: Message Priority (4b) | Spare (4b)
    """
    if len(data) < PFCP_HEADER_LEN_NO_SEID:
        raise PFCPParseError("Data too short for PFCP header")

    first_byte = data[0]
    version = (first_byte >> 5) & 0x07
    spare1 = (first_byte >> 3) & 0x03  # 2 spare bits
    spare2 = (first_byte >> 2) & 0x01  # 1 spare bit
    fo = bool(first_byte & 0x04)       # Follow On flag
    mp = bool(first_byte & 0x02)       # Message Priority flag
    seid_flag = bool(first_byte & 0x01)  # S flag

    msg_type = data[1]
    length = struct.unpack("!H", data[2:4])[0]

    # Build flag description string
    flag_parts = []
    if mp:
        flag_parts.append("Message Priority (MP)")
    if seid_flag:
        flag_parts.append("SEID (S)")
    if fo:
        flag_parts.append("Follow On (FO)")

    header = {
        "version": version,
        "mp": mp,
        "seid_flag": seid_flag,
        "fo": fo,
        "message_type": msg_type,
        "message_type_name": MessageType.get_name(msg_type),
        "length": length,
        "flags_raw": first_byte,
        "flags_hex": f"0x{first_byte:02x}",
        "flags_description": ', '.join(flag_parts) if flag_parts else "None",
    }

    # Wireshark-style header fields
    header["_fields"] = [
        {"type": "bits", "label": "Version", "value": str(version),
         "bits": f"{_bit_str(first_byte, 7, 3)}. ...."},
        {"type": "bits", "label": "Spare", "value": "0",
         "bits": f"...{_bit_str(first_byte, 4, 1)} ...."},
        {"type": "bits", "label": "Spare", "value": "0",
         "bits": f".... {_bit_str(first_byte, 3, 1)}..."},
        {"type": "bits", "label": "Follow On (FO)", "value": "True" if fo else "False",
         "bits": f".... .{_bit_str(first_byte, 2, 1)}.."},
        {"type": "bits", "label": "Message Priority (MP)", "value": "True" if mp else "False",
         "bits": f".... ..{_bit_str(first_byte, 1, 1)}."},
        {"type": "bits", "label": "SEID (S)", "value": "True" if seid_flag else "False",
         "bits": f".... ...{_bit_str(first_byte, 0, 1)}"},
        {"type": "field", "label": "Message Type",
         "value": f"{MessageType.get_name(msg_type)} ({msg_type})"},
        {"type": "field", "label": "Length", "value": str(length)},
    ]

    if seid_flag:
        if len(data) < PFCP_HEADER_LEN_WITH_SEID:
            raise PFCPParseError("Data too short for PFCP header with SEID")
        seid = struct.unpack("!Q", data[4:12])[0]
        seq = struct.unpack("!I", b'\x00' + data[12:15])[0]
        header["seid"] = seid
        header["seid_hex"] = f"0x{seid:016x}"
        header["sequence_number"] = seq
        header["sequence_hex"] = f"0x{seq:06x}"
        header["header_length"] = PFCP_HEADER_LEN_WITH_SEID

        header["_fields"].append({"type": "field", "label": "SEID",
                                   "value": f"0x{seid:016x}"})
        header["_fields"].append({"type": "field", "label": "Sequence Number",
                                   "value": str(seq)})

        # Message Priority byte (octet 16)
        if len(data) >= PFCP_HEADER_LEN_WITH_SEID:
            mp_byte = data[15]
            msg_priority = (mp_byte >> 4) & 0x0F
            mp_spare = mp_byte & 0x0F
            header["message_priority"] = msg_priority
            header["_fields"].append(
                {"type": "bits", "label": "Message Priority", "value": str(msg_priority),
                 "bits": f".... .... .... .... {_bit_str(mp_byte, 7, 4)} ...."})
            header["_fields"].append(
                {"type": "bits", "label": "Spare", "value": str(mp_spare),
                 "bits": f".... .... .... .... .... {_bit_str(mp_byte, 3, 4)}"})
    else:
        seq = struct.unpack("!I", b'\x00' + data[4:7])[0]
        header["seid"] = None
        header["sequence_number"] = seq
        header["sequence_hex"] = f"0x{seq:06x}"
        header["header_length"] = PFCP_HEADER_LEN_NO_SEID

        header["_fields"].append({"type": "field", "label": "Sequence Number",
                                   "value": str(seq)})

        # Spare byte (octet 8)
        if len(data) > PFCP_HEADER_LEN_NO_SEID:
            spare_byte = data[7]
            header["_fields"].append({"type": "field", "label": "Spare",
                                       "value": str(spare_byte)})

    return header


def parse_ies(data: bytes, total_length: int) -> List[Dict[str, Any]]:
    """
    Parse a list of IEs from the given data buffer.

    IE format:
      Octet 1-2: Type
      Octet 3-4: Length
      Octet 5...: Value (may contain nested IEs for group types)
    """
    ies = []
    offset = 0

    while offset + 4 <= total_length:
        if offset + 4 > len(data):
            break

        ie_type_val = struct.unpack("!H", data[offset:offset + 2])[0]
        ie_length = struct.unpack("!H", data[offset + 2:offset + 4])[0]

        if offset + 4 + ie_length > len(data):
            logger.warning(f"IE length exceeds available data at offset {offset}")
            break

        ie_data = data[offset + 4:offset + 4 + ie_length]

        try:
            ie_type = IEType(ie_type_val)
        except ValueError:
            ie_type = None

        ie_entry = {
            "type": ie_type_val,
            "type_name": IEType.get_name(ie_type_val) if ie_type else f"Unknown IE ({ie_type_val})",
            "length": ie_length,
        }

        # Parse IE value
        if ie_type and ie_type in GROUP_IE_TYPES:
            # Group IE - contains nested IEs
            ie_entry["group"] = True
            ie_entry["ies"] = parse_ies(ie_data, ie_length)
            # Build summary for group IE from first child (e.g., PDR ID)
            if ie_entry["ies"]:
                first_ie = ie_entry["ies"][0]
                summary_val = first_ie.get("value", {}).get("_summary", "")
                ie_entry["_summary"] = f"{first_ie.get('type_name', '')}: {summary_val}" if summary_val else ""
            else:
                ie_entry["_summary"] = ""
        elif ie_type and ie_type in IE_PARSERS:
            # Specific parser available
            ie_entry["group"] = False
            ie_entry["value"] = IE_PARSERS[ie_type](ie_data)
            ie_entry["_summary"] = ie_entry["value"].get("_summary", "")
        elif ie_type:
            # Try simple IE parser
            ie_entry["group"] = False
            ie_entry["value"] = parse_simple_ie(ie_type, ie_data)
            ie_entry["_summary"] = ie_entry["value"].get("_summary", "")
        else:
            # Unknown IE - store raw hex
            ie_entry["group"] = False
            ie_entry["value"] = {"raw": ie_data.hex(),
                                  "_fields": [{"type": "field", "label": "Raw", "value": ie_data.hex()}],
                                  "_summary": ie_data.hex()[:32]}
            ie_entry["_summary"] = ie_data.hex()[:32]

        ies.append(ie_entry)
        offset += 4 + ie_length

    return ies


def parse_pfcp_message(data: bytes) -> Dict[str, Any]:
    """
    Parse a complete PFCP message from raw bytes.
    Returns a structured dictionary with header and IEs.
    """
    if len(data) < PFCP_HEADER_LEN_NO_SEID:
        raise PFCPParseError("Data too short for PFCP message")

    header = parse_pfcp_header(data)
    header_len = header["header_length"]
    msg_length = header["length"]

    # IEs start after the header
    ies_data = data[header_len:header_len + msg_length - (header_len - 4)]

    ies = parse_ies(ies_data, len(ies_data))

    return {
        "header": header,
        "ies": ies,
    }


def parse_packet(data: bytes, src_addr: tuple, dst_addr: tuple, from_side: str = None,
                 logical_src: str = None, logical_dst: str = None) -> Dict[str, Any]:
    """
    Parse a full packet with metadata.
    Returns a complete packet structure for display and storage.
    from_side: 'listen' = packet from SMF, 'target'/'upf' = packet from UPF
    src_addr / dst_addr: actual network-level addresses (UDP source/destination)
    logical_src / logical_dst: human-readable PFCP endpoint labels (SMF/UPF)
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    try:
        parsed = parse_pfcp_message(data)
        parse_error = None
    except PFCPParseError as e:
        parsed = {"header": {}, "ies": []}
        parse_error = str(e)
    except Exception as e:
        logger.exception("Unexpected parse error")
        parsed = {"header": {}, "ies": []}
        parse_error = f"Unexpected error: {str(e)}"

    # Determine direction based on which side the packet arrived from
    if from_side == "listen":
        direction = "SMF → UPF"
    elif from_side in ("target", "upf"):
        direction = "UPF → SMF"
    else:
        direction = "Unknown"
        if src_addr and dst_addr:
            if src_addr[0] != dst_addr[0]:
                direction = "Unknown"

    # Build summary
    msg_type_name = parsed.get("header", {}).get("message_type_name", "Unknown")
    seid = parsed.get("header", {}).get("seid", None)
    seq = parsed.get("header", {}).get("sequence_number", 0)

    packet = {
        "timestamp": timestamp,
        "src_addr": f"{src_addr[0]}:{src_addr[1]}" if src_addr else "",
        "dst_addr": f"{dst_addr[0]}:{dst_addr[1]}" if dst_addr else "",
        "logical_src": logical_src or "",
        "logical_dst": logical_dst or "",
        "direction": direction,
        "message_type": msg_type_name,
        "message_type_id": parsed.get("header", {}).get("message_type", 0),
        "seid": seid,
        "sequence_number": seq,
        "length": len(data),
        "header": parsed.get("header", {}),
        "ies": parsed.get("ies", []),
        "raw_hex": data.hex(),
        "parse_error": parse_error,
    }

    return packet


def find_ie(ies: List[Dict], ie_type: int) -> Optional[Dict]:
    """Find first IE of given type in a list of IEs"""
    for ie in ies:
        if ie["type"] == ie_type:
            return ie
    return None


def find_ies(ies: List[Dict], ie_type: int) -> List[Dict]:
    """Find all IEs of given type"""
    return [ie for ie in ies if ie["type"] == ie_type]


def get_ie_value(ie: Dict, field_path: str) -> Any:
    """
    Get a nested value from an IE using dot-notation path.
    e.g., get_ie_value(ie, "value.ipv4_address")
    """
    parts = field_path.split(".")
    current = ie
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
