"""
PFCP IE-specific parsers and builders per 3GPP TS 29.244
Each parser returns a dict with:
  - Parsed field values (for programmatic use)
  - _fields: ordered display lines for Wireshark-style tree rendering
  - _summary: short summary string for IE title line
"""
import struct
import socket
from typing import Dict, Any, List, Tuple

from .constants import (
    IEType, NODE_ID_TYPES, INTERFACE_VALUES, GATE_STATUS_VALUES,
    APPLY_ACTION_FLAGS, CAUSE_VALUES, GROUP_IE_TYPES,
    OUTER_HEADER_REMOVAL_DESCRIPTIONS, ALLOCATION_TYPE_NAMES,
    USAGE_REPORT_TRIGGER_BYTE1, USAGE_REPORT_TRIGGER_BYTE2,
    USAGE_REPORT_TRIGGER_BYTE3,
)


# ---------------------------------------------------------------------------
# Bit-field helpers
# ---------------------------------------------------------------------------

def _bit_pattern(byte_val: int, bits: list) -> str:
    """
    Build a Wireshark-style bit pattern string.
    bits: list of (start_bit, width) tuples marking the highlighted fields.
    Bits not in any field are shown as '.'.
    Bit numbering: bit 7 = MSB (leftmost), bit 0 = LSB (rightmost).
    """
    chars = ['.'] * 8
    for start, width in bits:
        for i in range(width):
            bit_pos = start - i  # e.g. start=7,width=3 → bits 7,6,5
            if 0 <= bit_pos <= 7:
                chars[7 - bit_pos] = str((byte_val >> bit_pos) & 1)
    return ''.join(chars)


def _byte_bits(byte_val: int) -> str:
    """Full 8-bit binary string: '00100011'"""
    return f'{byte_val:08b}'


def _bit_str(byte_val: int, start: int, width: int) -> str:
    """Extract bits from byte and return binary string.
    start = MSB bit position (7=leftmost), width = number of bits."""
    mask = ((1 << width) - 1) << (start - width + 1)
    val = (byte_val & mask) >> (start - width + 1)
    return f'{val:0{width}b}'


def _single_bit_pattern(byte_val: int, bit_pos: int) -> str:
    """Wireshark-style bit pattern for a single highlighted bit, with nibble space.
    e.g. bit_pos=7 -> '0... ....', bit_pos=3 -> '.... 1...'"""
    bit_val = str((byte_val >> bit_pos) & 1)
    chars = ['.'] * 8
    chars[7 - bit_pos] = bit_val
    return chars[0] + chars[1] + chars[2] + chars[3] + ' ' + chars[4] + chars[5] + chars[6] + chars[7]


# ---------------------------------------------------------------------------
# DNS wire format helpers
# ---------------------------------------------------------------------------

def _decode_dns_wire(data: bytes) -> str:
    """Decode a DNS wire-format name (label-length encoding) to FQDN string."""
    labels = []
    pos = 0
    while pos < len(data):
        label_len = data[pos]
        if label_len == 0:
            break
        pos += 1
        if pos + label_len > len(data):
            # Truncated - take what we can
            labels.append(data[pos:].decode('ascii', errors='replace'))
            break
        labels.append(data[pos:pos + label_len].decode('ascii', errors='replace'))
        pos += label_len
    return '.'.join(labels)


# ---------------------------------------------------------------------------
# IE Parsers - each returns dict with parsed values + _fields + _summary
# ---------------------------------------------------------------------------

def parse_node_id(data: bytes) -> Dict[str, Any]:
    """Parse Node ID IE (TS 29.244 8.2.2)"""
    if len(data) < 1:
        return {"error": "Insufficient data for Node ID", "_fields": [], "_summary": "error"}

    flags_byte = data[0]
    spare = (flags_byte >> 4) & 0x0F
    node_id_type = flags_byte & 0x0F
    type_name = NODE_ID_TYPES.get(node_id_type, f"Unknown ({node_id_type})")

    fields: list = [
        {"type": "bits", "label": "Spare", "value": spare,
         "bits": f"{spare:04b}. ...."},
        {"type": "bits", "label": "Address Type", "value": f"{type_name} ({node_id_type})",
         "bits": f".... {_bit_str(flags_byte, 3, 4)}"},
    ]

    result = {"node_id_type": type_name, "node_id_type_value": node_id_type}

    if node_id_type == 0:  # IPv4
        if len(data) >= 5:
            ip = socket.inet_ntoa(data[1:5])
            result["ipv4_address"] = ip
            fields.append({"type": "field", "label": "IPv4 address",
                           "value": f"{ip} ({ip})"})
        summary = f"IPv4: {result.get('ipv4_address', '?')}"
    elif node_id_type == 1:  # IPv6
        if len(data) >= 17:
            ip = socket.inet_ntop(socket.AF_INET6, data[1:17])
            result["ipv6_address"] = ip
            fields.append({"type": "field", "label": "IPv6 address", "value": ip})
        summary = f"IPv6: {result.get('ipv6_address', '?')}"
    elif node_id_type == 2:  # FQDN
        fqdn = _decode_dns_wire(data[1:])
        result["fqdn"] = fqdn
        fields.append({"type": "field", "label": "FQDN", "value": fqdn})
        summary = f"FQDN: {fqdn}"
    else:
        summary = type_name

    result["_fields"] = fields
    result["_summary"] = summary
    return result


def parse_f_seid(data: bytes) -> Dict[str, Any]:
    """Parse F-SEID IE (TS 29.244 8.2.3)"""
    if len(data) < 9:
        return {"error": "Insufficient data for F-SEID", "_fields": [], "_summary": "error"}

    flags = data[0]
    seid = struct.unpack("!Q", data[1:9])[0]
    v4 = bool(flags & 0x01)
    v6 = bool(flags & 0x02)

    parts = [f"SEID: 0x{seid:016x}"]
    if v4:
        parts.append("IPv4")
    if v6:
        parts.append("IPv6")

    fields: list = []
    # Flag bits breakdown - build Wireshark-style patterns for each bit
    flag_names = [
        ("Spare", 7), ("Spare", 6), ("Spare", 5), ("Spare", 4),
        ("Spare", 3), ("Spare", 2), ("V6 (IPv6)", 1), ("V4 (IPv4)", 0),
    ]
    for name, bit_pos in flag_names:
        bit_val = (flags >> bit_pos) & 1
        if name == "V4 (IPv4)":
            val_str = "Present" if bit_val else "Not Present"
            pattern = f".... ...{_bit_str(flags, 0, 1)}"
        elif name == "V6 (IPv6)":
            val_str = "Present" if bit_val else "Not Present"
            pattern = f".... ..{_bit_str(flags, 1, 1)}."
        else:
            val_str = str(bit_val)
            pattern = '.' * (7 - bit_pos) + str(bit_val) + '.' * bit_pos
        fields.append({"type": "bits", "label": name,
                        "value": val_str, "bits": pattern})

    result = {
        "seid": seid,
        "seid_hex": f"0x{seid:016x}",
        "flags": flags,
        "v4": v4,
        "v6": v6,
    }

    fields.append({"type": "field", "label": "SEID", "value": f"0x{seid:016x}"})

    offset = 9
    if v4 and len(data) >= offset + 4:
        ip = socket.inet_ntoa(data[offset:offset + 4])
        result["ipv4_address"] = ip
        fields.append({"type": "field", "label": "IPv4 address",
                        "value": f"{ip} ({ip})"})
        offset += 4
    if v6 and len(data) >= offset + 16:
        ip = socket.inet_ntop(socket.AF_INET6, data[offset:offset + 16])
        result["ipv6_address"] = ip
        fields.append({"type": "field", "label": "IPv6 address", "value": ip})

    result["_fields"] = fields
    result["_summary"] = ', '.join(parts)
    return result


def parse_f_teid(data: bytes) -> Dict[str, Any]:
    """Parse F-TEID IE (TS 29.244 8.2.4)"""
    if len(data) < 5:
        return {"error": "Insufficient data for F-TEID", "_fields": [], "_summary": "error"}

    flags = data[0]
    v4 = bool(flags & 0x01)
    v6 = bool(flags & 0x02)
    choose = bool(flags & 0x04)
    choose_id = bool(flags & 0x08)

    fields: list = [
        {"type": "bits", "label": "Spare", "value": f"{(flags >> 4) & 0x0F}",
         "bits": f"{_bit_str(flags, 7, 4)}. ...."},
        {"type": "bits", "label": "CHID (CHOOSE_ID)", "value": "True" if choose_id else "False",
         "bits": f".... {_bit_str(flags, 3, 1)}..."},
        {"type": "bits", "label": "CH (CHOOSE)", "value": "True" if choose else "False",
         "bits": f".... .{_bit_str(flags, 2, 1)}.."},
        {"type": "bits", "label": "V6 (IPv6)", "value": "Present" if v6 else "Not Present",
         "bits": f".... ..{_bit_str(flags, 1, 1)}."},
        {"type": "bits", "label": "V4 (IPv4)", "value": "Present" if v4 else "Not Present",
         "bits": f".... ...{_bit_str(flags, 0, 1)}"},
    ]

    result = {"flags": flags, "v4": v4, "v6": v6, "choose_id": choose_id,
              "ipv4_address": "", "ipv6_address": ""}

    parts = []
    offset = 1
    if len(data) >= offset + 4:
        teid = struct.unpack("!I", data[offset:offset + 4])[0]
        result["teid"] = teid
        result["teid_hex"] = f"0x{teid:08x}"
        fields.append({"type": "field", "label": "TEID", "value": f"0x{teid:08x}"})
        parts.append(f"TEID: 0x{teid:08x}")
        offset += 4

    if v4 and len(data) >= offset + 4:
        ip = socket.inet_ntoa(data[offset:offset + 4])
        result["ipv4_address"] = ip
        fields.append({"type": "field", "label": "IPv4 address",
                        "value": f"{ip} ({ip})"})
        parts.append(f"IPv4 {ip}")
        offset += 4
    else:
        # Always include IPv4 field so user can add one
        fields.append({"type": "field", "label": "IPv4 address", "value": ""})
    if v6 and len(data) >= offset + 16:
        ip = socket.inet_ntop(socket.AF_INET6, data[offset:offset + 16])
        result["ipv6_address"] = ip
        fields.append({"type": "field", "label": "IPv6 address", "value": ip})
        parts.append(f"IPv6 {ip}")
        offset += 16
    else:
        # Always include IPv6 field so user can add one
        fields.append({"type": "field", "label": "IPv6 address", "value": ""})

    if choose_id and len(data) > offset:
        result["choose_id_value"] = data[offset]
        fields.append({"type": "field", "label": "Choose ID", "value": data[offset]})

    result["_fields"] = fields
    result["_summary"] = ', '.join(parts) if parts else ""
    return result


def parse_ue_ip_address(data: bytes) -> Dict[str, Any]:
    """Parse UE IP Address IE (TS 29.244 8.2.62)"""
    if len(data) < 1:
        return {"error": "Insufficient data for UE IP Address", "_fields": [], "_summary": "error"}

    flags = data[0]
    v4 = bool(flags & 0x02)
    v6 = bool(flags & 0x01)
    ipv6d = bool(flags & 0x04)
    sd = bool(flags & 0x08)

    fields: list = [
        {"type": "bits", "label": "Spare", "value": "0",
         "bits": f"{_bit_str(flags, 7, 1)}... ...."},
        {"type": "bits", "label": "IPV6PL", "value": "Source IP address" if not (flags & 0x40) else "Prefix",
         "bits": f".{_bit_str(flags, 6, 1)}.. ...."},
        {"type": "bits", "label": "CHV6", "value": "Source IP address" if not (flags & 0x20) else "Assigned",
         "bits": f"..{_bit_str(flags, 5, 1)}. ...."},
        {"type": "bits", "label": "CHV4", "value": "Source IP address" if not (flags & 0x10) else "Assigned",
         "bits": f"...{_bit_str(flags, 4, 1)} ...."},
        {"type": "bits", "label": "IPv6D", "value": "Source IP address" if not ipv6d else "Prefix delegation",
         "bits": f".... {_bit_str(flags, 3, 1)}..."},
        {"type": "bits", "label": "S/D", "value": "Destination IP address" if sd else "Source IP address",
         "bits": f".... .{_bit_str(flags, 2, 1)}.."},
        {"type": "bits", "label": "V4 (IPv4)", "value": "Present" if v4 else "Not Present",
         "bits": f".... ..{_bit_str(flags, 1, 1)}."},
        {"type": "bits", "label": "V6 (IPv6)", "value": "Present" if v6 else "Not Present",
         "bits": f".... ...{_bit_str(flags, 0, 1)}"},
    ]

    result = {"flags": flags, "v4": v4, "v6": v6, "ipv6_prefix_delegation": ipv6d}

    offset = 1
    if v4 and len(data) >= offset + 4:
        ip = socket.inet_ntoa(data[offset:offset + 4])
        result["ipv4"] = ip
        fields.append({"type": "field", "label": "IPv4 address",
                        "value": f"{ip} ({ip})"})
        offset += 4
    if v6 and len(data) >= offset + 16:
        ip = socket.inet_ntop(socket.AF_INET6, data[offset:offset + 16])
        result["ipv6"] = ip
        fields.append({"type": "field", "label": "IPv6 address", "value": ip})
        offset += 16
    if ipv6d and len(data) > offset:
        result["ipv6_prefix_length"] = data[offset]
        fields.append({"type": "field", "label": "IPv6 Prefix Length", "value": data[offset]})

    ip_part = result.get("ipv4", result.get("ipv6", ""))
    result["_fields"] = fields
    result["_summary"] = ip_part
    return result


def parse_sdf_filter(data: bytes) -> Dict[str, Any]:
    """Parse SDF Filter IE (TS 29.244 8.2.5)"""
    if len(data) < 2:
        return {"error": "Insufficient data for SDF Filter", "_fields": [], "_summary": "error"}

    flags = data[0]
    bid = bool(flags & 0x10)
    fl = bool(flags & 0x08)
    spi = bool(flags & 0x04)
    ttc = bool(flags & 0x02)
    fd = bool(flags & 0x01)

    fields: list = [
        {"type": "bits", "label": "Spare", "value": f"{(flags >> 5) & 0x07}",
         "bits": f"{_bit_str(flags, 7, 3)} ...."},
        {"type": "bits", "label": "BID (Bidirectional SDF Filter)", "value": "True" if bid else "False",
         "bits": f"...{_bit_str(flags, 4, 1)} ...."},
        {"type": "bits", "label": "FL (Flow Label)", "value": "True" if fl else "False",
         "bits": f".... {_bit_str(flags, 3, 1)}..."},
        {"type": "bits", "label": "SPI (Security Parameter Index)", "value": "True" if spi else "False",
         "bits": f".... .{_bit_str(flags, 2, 1)}.."},
        {"type": "bits", "label": "TTC (ToS Traffic Class)", "value": "True" if ttc else "False",
         "bits": f".... ..{_bit_str(flags, 1, 1)}."},
        {"type": "bits", "label": "FD (Flow Description)", "value": "True" if fd else "False",
         "bits": f".... ...{_bit_str(flags, 0, 1)}"},
    ]

    result = {"flags": flags, "bid": bid, "fl": fl, "spi": spi, "ttc": ttc, "fd": fd}

    offset = 1
    # Spare byte
    if len(data) > offset:
        fields.append({"type": "field", "label": "Spare", "value": data[offset]})
        offset += 1

    if fd and len(data) >= offset + 2:
        fd_len = struct.unpack("!H", data[offset:offset + 2])[0]
        result["flow_description_length"] = fd_len
        fields.append({"type": "field", "label": "Length of Flow Description", "value": fd_len})
        offset += 2
        if len(data) >= offset + fd_len:
            fd_str = data[offset:offset + fd_len].decode('utf-8', errors='replace')
            result["flow_description"] = fd_str
            fields.append({"type": "field", "label": "Flow Description", "value": fd_str})
            offset += fd_len

    result["_fields"] = fields
    result["_summary"] = result.get("flow_description", "")
    return result


def parse_network_instance(data: bytes) -> Dict[str, Any]:
    """Parse Network Instance IE (TS 29.244 8.2.7)"""
    ni = data.decode('utf-8', errors='replace')
    fields: list = [
        {"type": "field", "label": "Network Instance", "value": ni}
    ]
    return {"network_instance": ni, "_fields": fields, "_summary": ni}


def parse_outer_header_creation(data: bytes) -> Dict[str, Any]:
    """Parse Outer Header Creation IE (TS 29.244 8.2.55)"""
    if len(data) < 2:
        return {"error": "Insufficient data for Outer Header Creation", "_fields": [], "_summary": "error"}

    desc = struct.unpack("!H", data[0:2])[0]
    result = {
        "description": desc,
        "description_flags": {
            "GTP-U_UDP_IPV4": bool(desc & 0x0100),
            "GTP-U_UDP_IPV6": bool(desc & 0x0200),
            "UDP_IPV4": bool(desc & 0x0400),
            "UDP_IPV6": bool(desc & 0x0800),
            "IPV4": bool(desc & 0x1000),
            "IPV6": bool(desc & 0x2000),
            "CTAG": bool(desc & 0x4000),
            "STAG": bool(desc & 0x8000),
        }
    }

    flag_names = [
        ("GTP-U/UDP/IPv4", 0x0100), ("GTP-U/UDP/IPv6", 0x0200),
        ("UDP/IPv4", 0x0400), ("UDP/IPv6", 0x0800),
        ("IPv4", 0x1000), ("IPv6", 0x2000),
        ("C-TAG", 0x4000), ("S-TAG", 0x8000),
    ]
    active = [n for n, b in flag_names if desc & b]

    fields: list = [
        {"type": "field", "label": "Description", "value": f"0x{desc:04x}"},
    ]
    for name, bit in flag_names:
        fields.append({"type": "field", "label": name,
                        "value": "True" if desc & bit else "False"})

    offset = 2
    if desc & 0x0300:  # GTP-U
        if len(data) >= offset + 4:
            teid = struct.unpack("!I", data[offset:offset + 4])[0]
            result["teid"] = teid
            result["teid_hex"] = f"0x{teid:08x}"
            fields.append({"type": "field", "label": "TEID", "value": f"0x{teid:08x}"})
            offset += 4
        if desc & 0x0100 and len(data) >= offset + 4:
            ip = socket.inet_ntoa(data[offset:offset + 4])
            result["ipv4_address"] = ip
            fields.append({"type": "field", "label": "IPv4 address",
                            "value": f"{ip} ({ip})"})
            offset += 4
        if desc & 0x0200 and len(data) >= offset + 16:
            ip = socket.inet_ntop(socket.AF_INET6, data[offset:offset + 16])
            result["ipv6_address"] = ip
            fields.append({"type": "field", "label": "IPv6 address", "value": ip})
            offset += 16
        if len(data) >= offset + 2:
            result["port"] = struct.unpack("!H", data[offset:offset + 2])[0]
            fields.append({"type": "field", "label": "Port", "value": result["port"]})
    elif desc & 0x0C00:  # UDP/IP
        if desc & 0x0400 and len(data) >= offset + 4:
            ip = socket.inet_ntoa(data[offset:offset + 4])
            result["ipv4_address"] = ip
            fields.append({"type": "field", "label": "IPv4 address",
                            "value": f"{ip} ({ip})"})
            offset += 4
        if desc & 0x0800 and len(data) >= offset + 16:
            ip = socket.inet_ntop(socket.AF_INET6, data[offset:offset + 16])
            result["ipv6_address"] = ip
            fields.append({"type": "field", "label": "IPv6 address", "value": ip})
            offset += 16
        if len(data) >= offset + 2:
            result["port"] = struct.unpack("!H", data[offset:offset + 2])[0]
            fields.append({"type": "field", "label": "Port", "value": result["port"]})

    result["_fields"] = fields
    result["_summary"] = ', '.join(active) if active else f"0x{desc:04x}"
    return result


def parse_outer_header_removal(data: bytes) -> Dict[str, Any]:
    """Parse Outer Header Removal IE (TS 29.244 8.2.64)"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    desc = data[0]
    desc_name = OUTER_HEADER_REMOVAL_DESCRIPTIONS.get(desc, f"Unknown ({desc})")

    fields: list = [
        {"type": "field", "label": "Outer Header Removal Description",
         "value": f"{desc_name} ({desc})"}
    ]
    return {
        "description": desc,
        "description_name": desc_name,
        "_fields": fields,
        "_summary": desc_name,
    }


def parse_cause(data: bytes) -> Dict[str, Any]:
    """Parse Cause IE (TS 29.244 8.2.12)"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    cause = data[0]
    cause_name = CAUSE_VALUES.get(cause, f"Unknown ({cause})")
    fields: list = [
        {"type": "field", "label": "Cause", "value": f"{cause_name} ({cause})"}
    ]
    return {"cause": cause, "cause_name": cause_name, "_fields": fields, "_summary": cause_name}

def parse_source_interface(data: bytes) -> Dict[str, Any]:
    """Parse Source Interface IE"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    byte_val = data[0]
    intf = byte_val & 0x0F
    intf_name = INTERFACE_VALUES.get(intf, f"Unknown ({intf})")

    fields: list = [
        {"type": "bits", "label": "Spare", "value": f"{(byte_val >> 4) & 0x0F}",
         "bits": f"{_bit_str(byte_val, 7, 4)}. ...."},
        {"type": "bits", "label": "Source Interface", "value": f"{intf_name} ({intf})",
         "bits": f".... {_bit_str(byte_val, 3, 4)}"},
    ]
    return {
        "interface": intf,
        "interface_name": intf_name,
        "_fields": fields,
        "_summary": intf_name,
    }


def parse_destination_interface(data: bytes) -> Dict[str, Any]:
    """Parse Destination Interface IE"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    byte_val = data[0]
    intf = byte_val & 0x0F
    intf_name = INTERFACE_VALUES.get(intf, f"Unknown ({intf})")

    fields: list = [
        {"type": "bits", "label": "Spare", "value": f"{(byte_val >> 4) & 0x0F}",
         "bits": f"{_bit_str(byte_val, 7, 4)}. ...."},
        {"type": "bits", "label": "Destination Interface", "value": f"{intf_name} ({intf})",
         "bits": f".... {_bit_str(byte_val, 3, 4)}"},
    ]
    return {
        "interface": intf,
        "interface_name": intf_name,
        "_fields": fields,
        "_summary": intf_name,
    }


def parse_apply_action(data: bytes) -> Dict[str, Any]:
    """Parse Apply Action IE (TS 29.244 8.2.26)"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    # Apply Action can be 1, 2, or 3 bytes
    if len(data) >= 3:
        action = struct.unpack("!I", b'\x00' + data[:3])[0]
    elif len(data) >= 2:
        action = struct.unpack("!H", data[:2])[0]
    else:
        action = data[0]

    flags = {}
    active = []
    for name, bit in APPLY_ACTION_FLAGS.items():
        flags[name] = bool(action & bit)
        if action & bit:
            active.append(name)

    fields: list = [
        {"type": "field", "label": "Action", "value": f"0x{action:04x}"},
    ]
    for name, bit in APPLY_ACTION_FLAGS.items():
        fields.append({"type": "field", "label": name,
                        "value": "True" if action & bit else "False"})

    return {
        "action_value": action,
        "action_hex": f"0x{action:04x}",
        "flags": flags,
        "_fields": fields,
        "_summary": ', '.join(active) if active else "None",
    }


def parse_gate_status(data: bytes) -> Dict[str, Any]:
    """Parse Gate Status IE"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    val = data[0]
    ul = (val >> 2) & 0x03
    dl = val & 0x03
    ul_name = GATE_STATUS_VALUES.get(ul, f"Unknown ({ul})")
    dl_name = GATE_STATUS_VALUES.get(dl, f"Unknown ({dl})")

    fields: list = [
        {"type": "field", "label": "UL Gate", "value": f"{ul_name} ({ul})"},
        {"type": "field", "label": "DL Gate", "value": f"{dl_name} ({dl})"},
    ]
    return {
        "value": val,
        "ul_gate": ul, "ul_gate_name": ul_name,
        "dl_gate": dl, "dl_gate_name": dl_name,
        "_fields": fields,
        "_summary": f"UL: {ul_name}, DL: {dl_name}",
    }


def parse_mbr(data: bytes) -> Dict[str, Any]:
    """Parse MBR IE (TS 29.244 8.2.14)"""
    result = {}
    fields: list = []
    if len(data) >= 5:
        ul = int.from_bytes(data[0:5], 'big')
        result["ul_mbr"] = ul
        result["ul_mbr_bps"] = ul * 1000
        result["ul_mbr_display"] = _format_bitrate(ul * 1000)
        fields.append({"type": "field", "label": "UL MBR", "value": result["ul_mbr_display"]})
    if len(data) >= 10:
        dl = int.from_bytes(data[5:10], 'big')
        result["dl_mbr"] = dl
        result["dl_mbr_bps"] = dl * 1000
        result["dl_mbr_display"] = _format_bitrate(dl * 1000)
        fields.append({"type": "field", "label": "DL MBR", "value": result["dl_mbr_display"]})
    result["_fields"] = fields
    result["_summary"] = f"UL: {result.get('ul_mbr_display', '?')}, DL: {result.get('dl_mbr_display', '?')}"
    return result


def parse_gbr(data: bytes) -> Dict[str, Any]:
    """Parse GBR IE (TS 29.244 8.2.15)"""
    result = {}
    fields: list = []
    if len(data) >= 5:
        ul = int.from_bytes(data[0:5], 'big')
        result["ul_gbr"] = ul
        result["ul_gbr_bps"] = ul * 1000
        result["ul_gbr_display"] = _format_bitrate(ul * 1000)
        fields.append({"type": "field", "label": "UL GBR", "value": result["ul_gbr_display"]})
    if len(data) >= 10:
        dl = int.from_bytes(data[5:10], 'big')
        result["dl_gbr"] = dl
        result["dl_gbr_bps"] = dl * 1000
        result["dl_gbr_display"] = _format_bitrate(dl * 1000)
        fields.append({"type": "field", "label": "DL GBR", "value": result["dl_gbr_display"]})
    result["_fields"] = fields
    result["_summary"] = f"UL: {result.get('ul_gbr_display', '?')}, DL: {result.get('dl_gbr_display', '?')}"
    return result


def parse_recovery_time_stamp(data: bytes) -> Dict[str, Any]:
    """Parse Recovery Time Stamp IE"""
    if len(data) < 4:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    ts = struct.unpack("!I", data[:4])[0]
    time_str = _ntp_to_datetime(ts)
    fields: list = [
        {"type": "field", "label": "Time Stamp", "value": time_str}
    ]
    return {"timestamp": ts, "time": time_str, "_fields": fields, "_summary": time_str}


def parse_volume_measurement(data: bytes) -> Dict[str, Any]:
    """Parse Volume Measurement IE (TS 29.244 8.2.44)"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    flags = data[0]
    tovol = bool(flags & 0x01)
    ulvol = bool(flags & 0x02)
    dlvol = bool(flags & 0x04)
    tonop = bool(flags & 0x08)
    ulnop = bool(flags & 0x10)
    dlnop = bool(flags & 0x20)

    fields: list = [
        {"type": "bits", "label": "Spare", "value": f"{(flags >> 6) & 0x03}",
         "bits": f"{_bit_str(flags, 7, 2)}.. ...."},
        {"type": "bits", "label": "DLNOP", "value": "True" if dlnop else "False",
         "bits": f"..{_bit_str(flags, 5, 1)}. ...."},
        {"type": "bits", "label": "ULNOP", "value": "True" if ulnop else "False",
         "bits": f"...{_bit_str(flags, 4, 1)} ...."},
        {"type": "bits", "label": "TONOP", "value": "True" if tonop else "False",
         "bits": f".... {_bit_str(flags, 3, 1)}..."},
        {"type": "bits", "label": "DLVOL", "value": "True" if dlvol else "False",
         "bits": f".... .{_bit_str(flags, 2, 1)}.."},
        {"type": "bits", "label": "ULVOL", "value": "True" if ulvol else "False",
         "bits": f".... ..{_bit_str(flags, 1, 1)}."},
        {"type": "bits", "label": "TOVOL", "value": "True" if tovol else "False",
         "bits": f".... ...{_bit_str(flags, 0, 1)}"},
    ]

    result = {"flags": flags}
    offset = 1

    if tovol and len(data) >= offset + 8:
        result["total_volume"] = struct.unpack("!Q", data[offset:offset + 8])[0]
        fields.append({"type": "field", "label": "Total Volume", "value": result["total_volume"]})
        offset += 8
    if ulvol and len(data) >= offset + 8:
        result["uplink_volume"] = struct.unpack("!Q", data[offset:offset + 8])[0]
        fields.append({"type": "field", "label": "Uplink Volume", "value": result["uplink_volume"]})
        offset += 8
    if dlvol and len(data) >= offset + 8:
        result["downlink_volume"] = struct.unpack("!Q", data[offset:offset + 8])[0]
        fields.append({"type": "field", "label": "Downlink Volume", "value": result["downlink_volume"]})
        offset += 8
    if tonop and len(data) >= offset + 8:
        result["total_packets"] = struct.unpack("!Q", data[offset:offset + 8])[0]
        fields.append({"type": "field", "label": "Total Number of Packets", "value": result["total_packets"]})
        offset += 8
    if ulnop and len(data) >= offset + 8:
        result["uplink_packets"] = struct.unpack("!Q", data[offset:offset + 8])[0]
        fields.append({"type": "field", "label": "Uplink Number of Packets", "value": result["uplink_packets"]})
        offset += 8
    if dlnop and len(data) >= offset + 8:
        result["downlink_packets"] = struct.unpack("!Q", data[offset:offset + 8])[0]
        fields.append({"type": "field", "label": "Downlink Number of Packets", "value": result["downlink_packets"]})

    result["_fields"] = fields
    result["_summary"] = ""
    return result


def parse_report_type(data: bytes) -> Dict[str, Any]:
    """Parse Report Type IE"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    flags = data[0]
    names = ["DLDR", "USAR", "ERIR", "UPIR", "TMIR"]
    fields: list = []
    active = []
    for i, name in enumerate(names):
        val = bool(flags & (1 << i))
        fields.append({"type": "field", "label": name, "value": "True" if val else "False"})
        if val:
            active.append(name)

    return {
        "flags": flags,
        "DLDR": bool(flags & 0x01), "USAR": bool(flags & 0x02),
        "ERIR": bool(flags & 0x04), "UPIR": bool(flags & 0x08),
        "TMIR": bool(flags & 0x10),
        "_fields": fields,
        "_summary": ', '.join(active) if active else "None",
    }


def parse_reporting_triggers(data: bytes) -> Dict[str, Any]:
    """Parse Reporting Triggers IE"""
    if len(data) < 2:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    if len(data) >= 3:
        val = int.from_bytes(data[:3], 'big')
    else:
        val = struct.unpack("!H", data[:2])[0]

    triggers = {
        "PERIODIC_ROUTING": bool(val & 0x01),
        "VOLTH": bool(val & 0x02), "TIMTH": bool(val & 0x04),
        "QUHTH": bool(val & 0x08), "STTHR": bool(val & 0x10),
        "QUVTI": bool(val & 0x20), "IPMJL": bool(val & 0x40),
        "VOLQU": bool(val & 0x80), "TIMQU": bool(val & 0x100),
        "LIUSA": bool(val & 0x200), "DROTH": bool(val & 0x400),
        "STOSP": bool(val & 0x800),
    }

    fields: list = [{"type": "field", "label": "Value", "value": f"0x{val:04x}"}]
    active = []
    for name, v in triggers.items():
        fields.append({"type": "field", "label": name, "value": "True" if v else "False"})
        if v:
            active.append(name)

    return {"value": val, "triggers": triggers, "_fields": fields,
            "_summary": ', '.join(active) if active else "None"}


def parse_measurement_method(data: bytes) -> Dict[str, Any]:
    """Parse Measurement Method IE"""
    if len(data) < 1:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}

    val = data[0]
    fields: list = [
        {"type": "field", "label": "DURAT (Duration)", "value": "True" if val & 0x01 else "False"},
        {"type": "field", "label": "VOLUM (Volume)", "value": "True" if val & 0x02 else "False"},
        {"type": "field", "label": "EVENT", "value": "True" if val & 0x04 else "False"},
    ]
    return {
        "value": val,
        "DURAT": bool(val & 0x01), "VOLUM": bool(val & 0x02), "EVENT": bool(val & 0x04),
        "_fields": fields,
        "_summary": "",
    }


# ---------------------------------------------------------------------------
# Simple IE helpers for fixed-size IEs
# ---------------------------------------------------------------------------

def _parse_id_ie(data: bytes, fmt: str, field_name: str, display_name: str = None) -> Dict:
    """Generic parser for simple ID IEs (PDR ID, FAR ID, QER ID, URR ID, etc.)"""
    size = struct.calcsize(fmt)
    if len(data) < size:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}
    val = struct.unpack(fmt, data[:size])[0]

    # For 32-bit IDs, first bit indicates allocation type
    alloc_prefix = ""
    fields: list = []
    if fmt == "!I" and field_name in ("far_id", "qer_id", "urr_id"):
        alloc_bit = (val >> 31) & 1
        alloc_name = ALLOCATION_TYPE_NAMES.get(alloc_bit, f"Unknown ({alloc_bit})")
        rule_id = val & 0x7FFFFFFF
        alloc_prefix = f"{alloc_name} "
        fields.append({"type": "bits", "label": "Allocation type", "value": alloc_name,
                        "bits": f"{_bit_str((val >> 24) & 0xFF, 7, 1)}... .... .... .... .... .... .... ...."})
        fields.append({"type": "bits", "label": f"{display_name or field_name.upper()}",
                        "value": str(rule_id),
                        "bits": f".{_bit_str((val >> 24) & 0xFF, 6, 7)} "
                                f"{_bit_str((val >> 16) & 0xFF, 7, 8)} "
                                f"{_bit_str((val >> 8) & 0xFF, 7, 8)} "
                                f"{_bit_str(val & 0xFF, 7, 8)}"})
    else:
        fields.append({"type": "field", "label": display_name or field_name.replace('_', ' ').title(),
                        "value": str(val)})

    summary = f"{alloc_prefix}{val}" if alloc_prefix else str(val)
    return {field_name: val, "_fields": fields, "_summary": summary}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _format_bitrate(bps: int) -> str:
    if bps >= 1_000_000_000:
        return f"{bps / 1_000_000_000:.2f} Gbps"
    elif bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"
    elif bps >= 1_000:
        return f"{bps / 1_000:.2f} Kbps"
    return f"{bps} bps"


def _ntp_to_datetime(ntp_ts: int) -> str:
    from datetime import datetime, timezone
    ntp_epoch = datetime(1900, 1, 1, tzinfo=timezone.utc)
    dt = ntp_epoch.timestamp() + ntp_ts
    try:
        return datetime.fromtimestamp(dt, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OSError, ValueError):
        return f"NTP:{ntp_ts}"


def parse_usage_report_trigger(data: bytes) -> Dict[str, Any]:
    """Parse Usage Report Trigger IE (TS 29.244 8.2.41) - 3 bytes"""
    if len(data) < 3:
        # Pad to 3 bytes if shorter
        data = data + b'\x00' * (3 - len(data))

    byte1, byte2, byte3 = data[0], data[1], data[2]
    fields: list = []

    # Byte 1 flags
    for name, bit_pos in USAGE_REPORT_TRIGGER_BYTE1:
        bit_val = (byte1 >> bit_pos) & 1
        fields.append({"type": "bits", "label": name,
                        "value": "True" if bit_val else "False",
                        "bits": _single_bit_pattern(byte1, bit_pos)})

    # Byte 2 flags
    for name, bit_pos in USAGE_REPORT_TRIGGER_BYTE2:
        bit_val = (byte2 >> bit_pos) & 1
        fields.append({"type": "bits", "label": name,
                        "value": "True" if bit_val else "False",
                        "bits": _single_bit_pattern(byte2, bit_pos)})

    # Byte 3: Spare(2 bits) + 6 flag bits
    spare3 = (byte3 >> 6) & 0x03
    fields.append({"type": "bits", "label": "Spare", "value": str(spare3),
                    "bits": f"{_bit_str(byte3, 7, 2)}.. ...."})
    for name, bit_pos in USAGE_REPORT_TRIGGER_BYTE3:
        bit_val = (byte3 >> bit_pos) & 1
        fields.append({"type": "bits", "label": name,
                        "value": "True" if bit_val else "False",
                        "bits": _single_bit_pattern(byte3, bit_pos)})

    # Collect active triggers
    active = []
    for name, bit_pos in USAGE_REPORT_TRIGGER_BYTE1:
        if (byte1 >> bit_pos) & 1:
            active.append(name.split('(')[0].strip())
    for name, bit_pos in USAGE_REPORT_TRIGGER_BYTE2:
        if (byte2 >> bit_pos) & 1:
            active.append(name.split('(')[0].strip())
    for name, bit_pos in USAGE_REPORT_TRIGGER_BYTE3:
        if (byte3 >> bit_pos) & 1:
            active.append(name.split('(')[0].strip())

    return {
        "byte1": byte1, "byte2": byte2, "byte3": byte3,
        "_fields": fields,
        "_summary": ', '.join(active) if active else "",
    }


def _parse_ntp_timestamp(data: bytes) -> str:
    """Parse an 8-byte NTP timestamp (4 bytes seconds + 4 bytes fraction) to display string."""
    from datetime import datetime, timezone, timedelta
    if len(data) < 4:
        return "N/A"
    ntp_seconds = struct.unpack("!I", data[:4])[0]
    ntp_fraction = struct.unpack("!I", data[4:8])[0] if len(data) >= 8 else 0
    # NTP epoch: Jan 1, 1900 00:00:00 UTC
    ntp_epoch = datetime(1900, 1, 1, tzinfo=timezone.utc)
    try:
        dt = ntp_epoch + timedelta(seconds=ntp_seconds, microseconds=ntp_fraction * 1000000 // 4294967296)
        ns = ntp_fraction * 1000000000 // 4294967296
        return dt.strftime(f"%b %d, %Y %H:%M:%S.{ns:09d} UTC")
    except (OSError, ValueError, OverflowError):
        return f"NTP:{ntp_seconds}.{ntp_fraction}"


def parse_start_time(data: bytes) -> Dict[str, Any]:
    """Parse Start Time IE (TS 29.244 8.2.89) - NTP timestamp"""
    if len(data) < 4:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}
    time_str = _parse_ntp_timestamp(data)
    ntp_seconds = struct.unpack("!I", data[:4])[0]
    fields: list = [
        {"type": "field", "label": "Start Time", "value": time_str}
    ]
    return {"ntp_seconds": ntp_seconds, "time": time_str, "_fields": fields, "_summary": time_str}


def parse_end_time(data: bytes) -> Dict[str, Any]:
    """Parse End Time IE (TS 29.244 8.2.137) - NTP timestamp"""
    if len(data) < 4:
        return {"error": "Insufficient data", "_fields": [], "_summary": "error"}
    time_str = _parse_ntp_timestamp(data)
    ntp_seconds = struct.unpack("!I", data[:4])[0]
    fields: list = [
        {"type": "field", "label": "End Time", "value": time_str}
    ]
    return {"ntp_seconds": ntp_seconds, "time": time_str, "_fields": fields, "_summary": time_str}


# ---------------------------------------------------------------------------
# Dispatch tables
# ---------------------------------------------------------------------------

IE_PARSERS = {
    IEType.NODE_ID: parse_node_id,
    IEType.F_SEID: parse_f_seid,
    IEType.F_TEID: parse_f_teid,
    IEType.UE_IP_ADDRESS: parse_ue_ip_address,
    IEType.SDF_FILTER: parse_sdf_filter,
    IEType.NETWORK_INSTANCE: parse_network_instance,
    IEType.OUTER_HEADER_CREATION: parse_outer_header_creation,
    IEType.OUTER_HEADER_REMOVAL: parse_outer_header_removal,
    IEType.CAUSE: parse_cause,
    IEType.SOURCE_INTERFACE: parse_source_interface,
    IEType.DESTINATION_INTERFACE: parse_destination_interface,
    IEType.APPLY_ACTION: parse_apply_action,
    IEType.GATE_STATUS: parse_gate_status,
    IEType.MBR: parse_mbr,
    IEType.GBR: parse_gbr,
    IEType.RECOVERY_TIME_STAMP: parse_recovery_time_stamp,
    IEType.VOLUME_MEASUREMENT: parse_volume_measurement,
    IEType.REPORT_TYPE: parse_report_type,
    IEType.REPORTING_TRIGGERS: parse_reporting_triggers,
    IEType.MEASUREMENT_METHOD: parse_measurement_method,
    IEType.USAGE_REPORT_TRIGGER: parse_usage_report_trigger,
    IEType.START_TIME: parse_start_time,
    IEType.END_TIME: parse_end_time,
}

# Simple fixed-size IE formats: (struct_format, field_name, display_name)
SIMPLE_IE_FORMATS = {
    IEType.PACKET_DETECTION_RULE_ID: ("!H", "pdr_id", "Rule ID"),
    IEType.FAR_ID: ("!I", "far_id", "FAR ID"),
    IEType.QER_ID: ("!I", "qer_id", "QER ID"),
    IEType.URR_ID: ("!I", "urr_id", "URR ID"),
    IEType.BAR_ID: ("!B", "bar_id", "BAR ID"),
    IEType.PRECEDENCE: ("!I", "precedence", "Precedence"),
    IEType.QER_CORRELATION_ID: ("!I", "qer_correlation_id", "QER Correlation ID"),
    IEType.SEQUENCE_NUMBER: ("!I", "sequence_number", "Sequence Number"),
    IEType.METRIC: ("!B", "metric", "Metric"),
    IEType.TIMER: ("!B", "timer_value", "Timer"),
    IEType.INACTIVITY_DETECTION_TIME: ("!I", "inactivity_detection_time", "Inactivity Detection Time"),
    IEType.TIME_THRESHOLD: ("!I", "time_threshold", "Time Threshold"),
    IEType.MONITORING_TIME: ("!I", "monitoring_time", "Monitoring Time"),
    IEType.PDN_TYPE: ("!B", "pdn_type", "PDN Type"),
    IEType.OFFENDING_IE: ("!H", "offending_ie_type", "Offending IE Type"),
    IEType.UR_SEQN: ("!I", "ur_seqn", "UR-SEQN"),
}

# IE Builders (keep for backward compatibility)
IE_BUILDERS = {
    IEType.NODE_ID: parse_node_id,  # builders not used in display path
    IEType.F_SEID: parse_f_seid,
    IEType.F_TEID: parse_f_teid,
}


def parse_simple_ie(ie_type: IEType, data: bytes) -> Dict[str, Any]:
    """Parse simple fixed-size IEs using format table"""
    if ie_type in SIMPLE_IE_FORMATS:
        fmt, name, display = SIMPLE_IE_FORMATS[ie_type]
        return _parse_id_ie(data, fmt, name, display)
    return {"raw": data.hex(), "_fields": [
        {"type": "field", "label": "Raw", "value": data.hex()}
    ], "_summary": data.hex()[:32]}


def build_simple_ie(ie_type: IEType, fields: Dict[str, Any], original_data: bytes) -> bytes:
    """Build simple fixed-size IEs"""
    if ie_type in SIMPLE_IE_FORMATS:
        fmt, name, _ = SIMPLE_IE_FORMATS[ie_type]
        if name in fields:
            return struct.pack(fmt, fields[name])
    return original_data
