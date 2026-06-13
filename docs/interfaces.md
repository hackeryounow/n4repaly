# N4Relay API Documentation

## Base URL

```
http://<host>:8080/api/v1
```

WebSocket endpoints:
```
ws://<host>:8080/ws/packets
ws://<host>:8080/ws/intercepted
```

---

## 1. Status

### 1.1 GET /api/v1/status

Get current relay status.

**Request:**

```
GET /api/v1/status
```

**Response:** `200 OK`

```json
{
  "running": true,
  "intercept_enabled": false,
  "target_addr": "upf",
  "target_port": 8805,
  "listen_addr": "0.0.0.0",
  "listen_port": 8805,
  "packets_captured": 1523,
  "packets_intercepted": 0,
  "uptime_seconds": 3600.5
}
```

| Field | Type | Description |
|-------|------|-------------|
| running | boolean | Whether the relay is currently forwarding packets |
| intercept_enabled | boolean | Whether packet interception is enabled |
| target_addr | string | Target UPF hostname or IP address |
| target_port | integer | Target UPF port number |
| listen_addr | string | Relay listen address |
| listen_port | integer | Relay listen port |
| packets_captured | integer | Total number of packets captured in buffer |
| packets_intercepted | integer | Number of currently held intercepted packets |
| uptime_seconds | float or null | Relay uptime in seconds (null if stopped) |

---

### 1.2 PUT /api/v1/status

Update relay configuration. All fields are optional; only provided fields are updated.

**Request:**

```
PUT /api/v1/status
Content-Type: application/json
```

```json
{
  "running": true,
  "intercept_enabled": false,
  "target_addr": "192.168.1.100",
  "target_port": 8805
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| running | boolean | No | Start (true) or stop (false) the relay |
| intercept_enabled | boolean | No | Enable (true) or disable (false) interception |
| target_addr | string | No | New target UPF address |
| target_port | integer | No | New target UPF port |

**Response:** `200 OK`

Returns the same `StatusResponse` as GET /status with updated values.

---

## 2. Packets

### 2.1 GET /api/v1/packets

List captured packets with optional filtering and pagination.

**Request:**

```
GET /api/v1/packets?offset=0&limit=100&msg_type=session&direction=SMF
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| offset | integer | No | 0 | Pagination offset |
| limit | integer | No | 100 | Page size (1-500) |
| msg_type | string | No | - | Filter by message type (substring match, case-insensitive) |
| direction | string | No | - | Filter by direction: "SMF" or "UPF" |

**Response:** `200 OK`

```json
{
  "total": 1523,
  "packets": [
    {
      "id": 1523,
      "timestamp": "2026-06-06 12:30:45.123",
      "direction": "SMF → UPF",
      "message_type": "Session Establishment Request",
      "message_type_id": 50,
      "seid": 1234567890,
      "sequence_number": 42,
      "length": 256,
      "src_addr": "10.0.0.1:8805",
      "dst_addr": "10.0.0.2:8805"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| total | integer | Total number of packets matching the filter |
| packets | array | Array of PacketSummary objects (most recent first) |

**PacketSummary fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique packet ID |
| timestamp | string | Capture timestamp (UTC) |
| direction | string | Packet direction ("SMF → UPF" or "UPF → SMF") |
| message_type | string | Human-readable PFCP message type name |
| message_type_id | integer | PFCP message type code |
| seid | integer or null | Session Endpoint Identifier (null for node messages) |
| sequence_number | integer | PFCP sequence number |
| length | integer | Packet length in bytes |
| src_addr | string | Source address:port |
| dst_addr | string | Destination address:port |

---

### 2.2 GET /api/v1/packets/{id}

Get detailed information of a specific packet, including parsed header, IEs, and raw hex.

**Request:**

```
GET /api/v1/packets/42
```

**Response:** `200 OK`

```json
{
  "id": 42,
  "timestamp": "2026-06-06 12:30:45.123",
  "direction": "SMF → UPF",
  "message_type": "Session Establishment Request",
  "message_type_id": 50,
  "seid": 1234567890,
  "sequence_number": 42,
  "length": 256,
  "src_addr": "10.0.0.1:8805",
  "dst_addr": "10.0.0.2:8805",
  "header": {
    "version": 1,
    "mp": false,
    "seid_flag": true,
    "message_type": 50,
    "message_type_name": "Session Establishment Request",
    "length": 252,
    "seid": 1234567890,
    "seid_hex": "0x00000000499602d2",
    "sequence_number": 42,
    "sequence_hex": "0x00002a",
    "header_length": 16
  },
  "ies": [
    {
      "type": 60,
      "type_name": "Node Id",
      "length": 5,
      "group": false,
      "value": {
        "node_id_type": "IPv4",
        "node_id_type_value": 0,
        "ipv4_address": "10.0.0.1"
      }
    },
    {
      "type": 57,
      "type_name": "F Seid",
      "length": 13,
      "group": false,
      "value": {
        "seid": 1234567890,
        "seid_hex": "0x00000000499602d2",
        "flags": 2,
        "v4": true,
        "v6": false,
        "ipv4_address": "10.0.0.1"
      }
    },
    {
      "type": 1,
      "type_name": "Create Pdr",
      "length": 120,
      "group": true,
      "ies": [
        {
          "type": 56,
          "type_name": "Packet Detection Rule Id",
          "length": 2,
          "group": false,
          "value": { "pdr_id": 1 }
        },
        {
          "type": 29,
          "type_name": "Precedence",
          "length": 4,
          "group": false,
          "value": { "precedence": 100 }
        }
      ]
    }
  ],
  "raw_hex": "213200fc00000000499602d200002a003c0005000a000001...",
  "parse_error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| header | object | Parsed PFCP header fields |
| ies | array | Array of parsed IE objects (may be nested for group IEs) |
| raw_hex | string | Raw packet data as hex string |
| parse_error | string or null | Parse error message if parsing failed |

**Error Responses:**

| Code | Description |
|------|-------------|
| 404 | Packet not found |

---

### 2.3 DELETE /api/v1/packets

Clear all captured packets from the buffer.

**Request:**

```
DELETE /api/v1/packets
```

**Response:** `200 OK`

```json
{
  "message": "All packets cleared"
}
```

---

## 3. Intercepted Packets

### 3.1 GET /api/v1/intercepted

List all currently intercepted (held) packets.

**Request:**

```
GET /api/v1/intercepted
```

**Response:** `200 OK`

```json
[
  {
    "id": "a1b2c3d4",
    "packet_id": 1024,
    "timestamp": "2026-06-06 12:31:00.456",
    "direction": "SMF → UPF",
    "message_type": "Session Modification Request",
    "seid": 1234567890,
    "sequence_number": 55,
    "length": 180,
    "status": "held"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique intercept ID (8-char UUID prefix) |
| packet_id | integer | Original packet ID in the buffer |
| timestamp | string | Intercept timestamp (UTC) |
| direction | string | Packet direction |
| message_type | string | PFCP message type name |
| seid | integer or null | SEID |
| sequence_number | integer | Sequence number |
| length | integer | Packet length in bytes |
| status | string | Status: "held", "released", or "dropped" |

---

### 3.2 GET /api/v1/intercepted/{id}

Get detailed information of an intercepted packet, including editable fields metadata.

**Request:**

```
GET /api/v1/intercepted/a1b2c3d4
```

**Response:** `200 OK`

```json
{
  "id": "a1b2c3d4",
  "packet_id": 1024,
  "timestamp": "2026-06-06 12:31:00.456",
  "direction": "SMF → UPF",
  "message_type": "Session Modification Request",
  "seid": 1234567890,
  "sequence_number": 55,
  "length": 180,
  "status": "held",
  "header": { "version": 1, "message_type": 52, "seid": 1234567890, "..." : "..." },
  "ies": [ "..." ],
  "raw_hex": "213400b400000000499602d2000037...",
  "editable_fields": {
    "header.seid": "uint64",
    "header.sequence_number": "uint24",
    "pdr_id": "uint16",
    "precedence": "uint32",
    "far_id": "uint32",
    "f_teid.teid": "uint32",
    "f_teid.ipv4_address": "ipv4",
    "ue_ip_address.ipv4": "ipv4",
    "apply_action": "flags",
    "gate_status.ul_gate": "enum",
    "source_interface": "enum",
    "destination_interface": "enum"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| editable_fields | object | Map of field paths to their types |

**Error Responses:**

| Code | Description |
|------|-------------|
| 404 | Intercepted packet not found |

---

### 3.3 PUT /api/v1/intercepted/{id}

Modify fields of an intercepted packet. Modifications are stored and applied when the packet is released.

**Request:**

```
PUT /api/v1/intercepted/a1b2c3d4
Content-Type: application/json
```

```json
{
  "modifications": {
    "header": {
      "seid": 9876543210
    },
    "ies": {
      "0": {
        "value": {
          "ipv4_address": "10.0.0.99"
        }
      }
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| modifications | object | Nested object describing field changes. Keys can be "header" (for header fields) or IE indices (for IE fields). |

**Response:** `200 OK`

```json
{
  "message": "Modifications applied to 'a1b2c3d4'. They will take effect on release."
}
```

**Error Responses:**

| Code | Description |
|------|-------------|
| 404 | Packet not found or not in "held" status |

---

### 3.4 POST /api/v1/intercepted/{id}/release

Release (forward) an intercepted packet. If modifications were set, they are applied before forwarding.

**Request:**

```
POST /api/v1/intercepted/a1b2c3d4/release
```

**Response:** `200 OK`

```json
{
  "id": "a1b2c3d4",
  "status": "released",
  "message": "Packet forwarded to destination"
}
```

**Error Responses:**

| Code | Description |
|------|-------------|
| 404 | Packet not found |
| 400 | Failed to build modified packet |

---

### 3.5 POST /api/v1/intercepted/{id}/drop

Drop an intercepted packet without forwarding it.

**Request:**

```
POST /api/v1/intercepted/a1b2c3d4/drop
```

**Response:** `200 OK`

```json
{
  "message": "Packet 'a1b2c3d4' dropped"
}
```

**Error Responses:**

| Code | Description |
|------|-------------|
| 404 | Packet not found |

---

## 4. WebSocket Endpoints

### 4.1 WS /ws/packets

Real-time notifications for new captured packets.

**Connection:**

```
ws://<host>:8080/ws/packets
```

**Message Format (server → client):**

```json
{
  "type": "new_packet",
  "data": {
    "id": 1524,
    "timestamp": "2026-06-06 12:31:01.789",
    "direction": "UPF → SMF",
    "message_type": "Session Establishment Response",
    "message_type_id": 51,
    "seid": 1234567890,
    "sequence_number": 42,
    "length": 64,
    "src_addr": "10.0.0.2:8805",
    "dst_addr": "10.0.0.1:8805",
    "intercepted": false
  }
}
```

**Keepalive:**

Client sends `ping`, server responds with `pong`.

---

### 4.2 WS /ws/intercepted

Real-time notifications for newly intercepted packets.

**Connection:**

```
ws://<host>:8080/ws/intercepted
```

**Message Format (server → client):**

```json
{
  "type": "new_intercept",
  "data": {
    "id": "a1b2c3d4",
    "packet_id": 1525,
    "timestamp": "2026-06-06 12:31:02.123",
    "direction": "SMF → UPF",
    "message_type": "Session Modification Request",
    "seid": 1234567890,
    "sequence_number": 56,
    "length": 200
  }
}
```

---

## 5. Error Responses

All error responses follow this format:

```json
{
  "detail": "Error description"
}
```

| HTTP Status | Description |
|-------------|-------------|
| 400 | Bad request (e.g., invalid modification data) |
| 404 | Resource not found |
| 500 | Internal server error |
