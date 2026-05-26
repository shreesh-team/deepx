from pydantic import BaseModel


class IngestRequest(BaseModel):
    conversation_id: str | None = None
    model: str
    provider: str
    status: str
    error_message: str | None = None
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    requested_at: str
    responded_at: str


class IngestResponse(BaseModel):
    id: str
