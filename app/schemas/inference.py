from datetime import datetime, timezone

from pydantic import BaseModel


def _fmt(dt) -> str:
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


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


class InferenceLogResponse(BaseModel):
    id: str
    conversation_id: str | None
    model: str
    provider: str
    status: str
    error_message: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    input_preview: str | None
    output_preview: str | None
    requested_at: str
    responded_at: str
    created_at: str

    @classmethod
    def from_orm(cls, log) -> "InferenceLogResponse":
        return cls(
            id=str(log.id),
            conversation_id=str(log.conversation_id) if log.conversation_id else None,
            model=log.model,
            provider=log.provider,
            status=log.status,
            error_message=log.error_message,
            latency_ms=log.latency_ms,
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            total_tokens=log.total_tokens,
            input_preview=log.input_preview,
            output_preview=log.output_preview,
            requested_at=_fmt(log.requested_at),
            responded_at=_fmt(log.responded_at),
            created_at=_fmt(log.created_at),
        )


class PaginatedInferenceLogsResponse(BaseModel):
    items: list[InferenceLogResponse]
    total: int
    page: int
    page_size: int
