export interface StatusResponse {
  running: boolean
  intercept_enabled: boolean
  target_addr: string
  target_port: number
  listen_addr: string
  listen_port: number
  packets_captured: number
  packets_intercepted: number
  uptime_seconds: number | null
  queue_depth: number
  queue_max_size: number
  queue_overflow_dropped: number
  queue_processed_total: number
  worker_count: number
}

export interface StatusUpdateRequest {
  running?: boolean
  intercept_enabled?: boolean
  target_addr?: string
  target_port?: number
}

export interface PacketSummary {
  id: number
  timestamp: string
  direction: string
  message_type: string
  message_type_id: number
  seid: number | null
  sequence_number: number
  length: number
  src_addr: string
  dst_addr: string
  logical_src?: string
  logical_dst?: string
}

export interface PacketDetail extends PacketSummary {
  header: Record<string, any>
  ies: IEItem[]
  raw_hex: string
  parse_error: string | null
}

export interface IEItem {
  type: number
  type_name: string
  length: number
  group: boolean
  value?: Record<string, any>
  ies?: IEItem[]
  _summary?: string
  _edit_mode?: 'fields' | 'flags' | 'group'
  _flag_items?: { name: string; bit: number; checked: boolean }[]
  _rawHex?: string
}

/** A Wireshark-style display field (bit breakdown or key-value) */
export interface DisplayField {
  type: 'bits' | 'field'
  label: string
  value: string | number
  bits?: string  // Wireshark-style bit pattern e.g. "001. ...."
}

export interface PacketListResponse {
  total: number
  packets: PacketSummary[]
}

export interface InterceptedPacket {
  id: string
  packet_id: number
  timestamp: string
  direction: string
  message_type: string
  seid: number | null
  sequence_number: number
  length: number
  status: string
}

export interface InterceptedPacketDetail extends InterceptedPacket {
  header: Record<string, any>
  ies: IEItem[]
  raw_hex: string
  editable_fields: Record<string, string>
}

export interface ModifyRequest {
  modifications: Record<string, any>
}

export interface ReleaseResponse {
  id: string
  status: string
  message: string
}

export interface SuccessResponse {
  message: string
}

export interface WSPacketMessage {
  type: 'new_packet'
  data: PacketSummary & { intercepted: boolean }
}

export interface WSInterceptMessage {
  type: 'new_intercept'
  data: InterceptedPacket
}

export type WSMessage = WSPacketMessage | WSInterceptMessage

// ---- Template types ----

export interface TemplateCreate {
  name: string
  match_msg_type: number
  match_seid?: number | null
  response_hex: string
  auto_seq: boolean
  auto_seid: boolean
  enabled: boolean
}

export interface TemplateUpdate {
  name?: string
  match_msg_type?: number
  match_seid?: number | null
  response_hex?: string
  auto_seq?: boolean
  auto_seid?: boolean
  enabled?: boolean
}

export interface Template {
  id: string
  name: string
  match_msg_type: number
  match_msg_type_name: string
  match_seid: number | null
  response_hex: string
  response_length: number
  auto_seq: boolean
  auto_seid: boolean
  enabled: boolean
  hit_count: number
}
