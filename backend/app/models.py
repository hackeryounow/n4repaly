"""
Pydantic models for API request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class StatusResponse(BaseModel):
    running: bool = Field(description="Whether the relay is currently running")
    intercept_enabled: bool = Field(description="Whether packet interception is enabled")
    target_addr: str = Field(description="Target UPF address")
    target_port: int = Field(description="Target UPF port")
    listen_addr: str = Field(description="Relay listen address")
    listen_port: int = Field(description="Relay listen port")
    packets_captured: int = Field(description="Total packets captured")
    packets_intercepted: int = Field(description="Number of currently held packets")
    uptime_seconds: Optional[float] = Field(default=None, description="Uptime in seconds")
    queue_depth: int = Field(default=0, description="Current packets waiting in processing queue")
    queue_max_size: int = Field(default=0, description="Maximum queue capacity")
    queue_overflow_dropped: int = Field(default=0, description="Packets dropped due to queue overflow")
    queue_processed_total: int = Field(default=0, description="Total packets processed by workers")
    worker_count: int = Field(default=0, description="Number of packet processing workers")


class StatusUpdateRequest(BaseModel):
    running: Optional[bool] = Field(default=None, description="Start/stop relay")
    intercept_enabled: Optional[bool] = Field(default=None, description="Enable/disable interception")
    target_addr: Optional[str] = Field(default=None, description="Update target address")
    target_port: Optional[int] = Field(default=None, description="Update target port")


class PacketSummary(BaseModel):
    id: int = Field(description="Packet ID")
    timestamp: str = Field(description="Capture timestamp")
    direction: str = Field(description="SMF→UPF or UPF→SMF")
    message_type: str = Field(description="PFCP message type name")
    message_type_id: int = Field(description="PFCP message type ID")
    seid: Optional[int] = Field(default=None, description="SEID (None for node messages)")
    sequence_number: int = Field(description="Sequence number")
    length: int = Field(description="Packet length in bytes")
    src_addr: str = Field(description="Actual UDP source address")
    dst_addr: str = Field(description="Actual UDP destination address")
    logical_src: str = Field(default="", description="Logical PFCP source (e.g. SMF)")
    logical_dst: str = Field(default="", description="Logical PFCP destination (e.g. UPF)")


class PacketDetail(PacketSummary):
    header: Dict[str, Any] = Field(description="Parsed PFCP header")
    ies: List[Dict[str, Any]] = Field(description="Parsed Information Elements")
    raw_hex: str = Field(description="Raw packet as hex string")
    parse_error: Optional[str] = Field(default=None, description="Parse error if any")


class PacketListResponse(BaseModel):
    total: int = Field(description="Total packets matching filter")
    packets: List[PacketSummary] = Field(description="List of packet summaries")


class InterceptedPacket(BaseModel):
    id: str = Field(description="Unique intercept ID")
    packet_id: int = Field(description="Original packet ID")
    timestamp: str = Field(description="Intercept timestamp")
    direction: str = Field(description="Packet direction")
    message_type: str = Field(description="PFCP message type")
    seid: Optional[int] = Field(default=None, description="SEID")
    sequence_number: int = Field(description="Sequence number")
    length: int = Field(description="Packet length")
    status: str = Field(description="Status: held, released, dropped")


class InterceptedPacketDetail(InterceptedPacket):
    header: Dict[str, Any] = Field(description="Parsed PFCP header")
    ies: List[Dict[str, Any]] = Field(description="Parsed Information Elements")
    raw_hex: str = Field(description="Raw packet as hex string")
    editable_fields: Dict[str, str] = Field(description="Map of editable field paths to types")


class ModifyRequest(BaseModel):
    modifications: Dict[str, Any] = Field(description="Field modifications to apply")


class ReleaseResponse(BaseModel):
    id: str = Field(description="Intercept ID")
    status: str = Field(description="Status after release")
    message: str = Field(description="Result message")


class ErrorResponse(BaseModel):
    error: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info")


class SuccessResponse(BaseModel):
    message: str = Field(description="Success message")


# ---- Template Models ----

class TemplateCreate(BaseModel):
    name: str = Field(description="Human-readable template name")
    match_msg_type: int = Field(description="PFCP message type ID to match")
    match_seid: Optional[int] = Field(default=None, description="SEID filter (None = match any)")
    response_hex: str = Field(description="Response packet as hex string")
    auto_seq: bool = Field(default=True, description="Auto-patch sequence number from request")
    auto_seid: bool = Field(default=False, description="Auto-patch SEID from request")
    enabled: bool = Field(default=True, description="Whether template is active")


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    match_msg_type: Optional[int] = None
    match_seid: Optional[int] = None
    response_hex: Optional[str] = None
    auto_seq: Optional[bool] = None
    auto_seid: Optional[bool] = None
    enabled: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: str = Field(description="Template ID")
    name: str = Field(description="Template name")
    match_msg_type: int = Field(description="Matched message type ID")
    match_msg_type_name: str = Field(description="Matched message type display name")
    match_seid: Optional[int] = Field(default=None, description="SEID filter")
    response_hex: str = Field(description="Response packet hex")
    response_length: int = Field(description="Response packet length in bytes")
    auto_seq: bool = Field(description="Auto-patch sequence number")
    auto_seid: bool = Field(description="Auto-patch SEID")
    enabled: bool = Field(description="Whether template is active")
    hit_count: int = Field(default=0, description="Number of times this template has triggered")


class ParseHexRequest(BaseModel):
    hex: str = Field(description="PFCP packet as hex string")


class ParseHexResponse(BaseModel):
    header: Dict[str, Any] = Field(description="Parsed PFCP header")
    ies: List[Dict[str, Any]] = Field(description="Parsed Information Elements")
