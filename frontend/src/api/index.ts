import axios from 'axios'
import type {
  StatusResponse,
  StatusUpdateRequest,
  PacketListResponse,
  PacketDetail,
  InterceptedPacket,
  InterceptedPacketDetail,
  ModifyRequest,
  ReleaseResponse,
  SuccessResponse,
  Template,
  TemplateCreate,
  TemplateUpdate,
} from '../types'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// Status
export async function getStatus(): Promise<StatusResponse> {
  const { data } = await api.get<StatusResponse>('/status')
  return data
}

export async function updateStatus(req: StatusUpdateRequest): Promise<StatusResponse> {
  const { data } = await api.put<StatusResponse>('/status', req)
  return data
}

// Packets
export async function listPackets(
  offset = 0,
  limit = 100,
  msgType?: string,
  direction?: string,
  excludeHeartbeat?: boolean,
): Promise<PacketListResponse> {
  const params: Record<string, any> = { offset, limit }
  if (msgType) params.msg_type = msgType
  if (direction) params.direction = direction
  if (excludeHeartbeat !== undefined) params.exclude_heartbeat = excludeHeartbeat
  const { data } = await api.get<PacketListResponse>('/packets', { params })
  return data
}

export async function getPacket(id: number): Promise<PacketDetail> {
  const { data } = await api.get<PacketDetail>(`/packets/${id}`)
  return data
}

export async function clearPackets(): Promise<SuccessResponse> {
  const { data } = await api.delete<SuccessResponse>('/packets')
  return data
}

// Intercepted
export async function listIntercepted(): Promise<InterceptedPacket[]> {
  const { data } = await api.get<InterceptedPacket[]>('/intercepted')
  return data
}

export async function getIntercepted(id: string): Promise<InterceptedPacketDetail> {
  const { data } = await api.get<InterceptedPacketDetail>(`/intercepted/${id}`)
  return data
}

export async function modifyIntercepted(id: string, req: ModifyRequest): Promise<SuccessResponse> {
  const { data } = await api.put<SuccessResponse>(`/intercepted/${id}`, req)
  return data
}

export async function releaseIntercepted(id: string): Promise<ReleaseResponse> {
  const { data } = await api.post<ReleaseResponse>(`/intercepted/${id}/release`)
  return data
}

export async function dropIntercepted(id: string): Promise<SuccessResponse> {
  const { data } = await api.post<SuccessResponse>(`/intercepted/${id}/drop`)
  return data
}

export async function releaseAllIntercepted(): Promise<SuccessResponse> {
  const { data } = await api.post<SuccessResponse>('/intercepted/release-all')
  return data
}

export async function dropAllIntercepted(): Promise<SuccessResponse> {
  const { data } = await api.post<SuccessResponse>('/intercepted/drop-all')
  return data
}

// Templates
export async function listTemplates(): Promise<Template[]> {
  const { data } = await api.get<Template[]>('/templates')
  return data
}

export async function createTemplate(req: TemplateCreate): Promise<Template> {
  const { data } = await api.post<Template>('/templates', req)
  return data
}

export async function getTemplate(id: string): Promise<Template> {
  const { data } = await api.get<Template>(`/templates/${id}`)
  return data
}

export async function updateTemplate(id: string, req: TemplateUpdate): Promise<Template> {
  const { data } = await api.put<Template>(`/templates/${id}`, req)
  return data
}

export async function deleteTemplate(id: string): Promise<SuccessResponse> {
  const { data } = await api.delete<SuccessResponse>(`/templates/${id}`)
  return data
}

export async function toggleTemplate(id: string): Promise<SuccessResponse> {
  const { data } = await api.post<SuccessResponse>(`/templates/${id}/toggle`)
  return data
}

// Parse hex
export async function parseHex(hex: string): Promise<{ header: Record<string, any>; ies: any[] }> {
  const { data } = await api.post<{ header: Record<string, any>; ies: any[] }>('/parse-hex', { hex })
  return data
}

// Rebuild hex (apply structural operations)
export interface HexOp {
  op: 'edit_header' | 'edit_ie' | 'add_ie' | 'delete_ie' | 'raw_edit'
  index?: number
  field?: string
  value?: string
  ie_type?: number
  hex?: string
  offset?: number
}
export async function rebuildHex(hex: string, operations: HexOp[]): Promise<{ hex: string; applied: string[] }> {
  const { data } = await api.post<{ hex: string; applied: string[] }>('/rebuild-hex', { hex, operations })
  return data
}

// Extract IE hex by index
export async function extractIE(hex: string, index: number): Promise<{ hex: string; type: number; length: number }> {
  const { data } = await api.post<{ hex: string; type: number; length: number }>('/extract-ie', { hex, index })
  return data
}

// Serialize structured IE fields to hex
export async function serializeIE(ieType: number, fields: Record<string, any>): Promise<{ hex: string; length: number }> {
  const { data } = await api.post<{ hex: string; length: number }>('/serialize-ie', { ie_type: ieType, fields })
  return data
}
