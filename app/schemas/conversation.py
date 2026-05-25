from datetime import datetime, timezone

from pydantic import BaseModel


def _fmt(dt) -> str:
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


class CreateConversationRequest(BaseModel):
    model: str
    provider: str
    title: str | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str | None
    model: str
    provider: str
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, c) -> "ConversationResponse":
        return cls(
            id=str(c.id),
            title=c.title,
            model=c.model,
            provider=c.provider,
            status=c.status,
            created_at=_fmt(c.created_at),
            updated_at=_fmt(c.updated_at),
        )


class ConversationListItem(BaseModel):
    id: str
    title: str | None
    model: str
    provider: str
    status: str
    updated_at: str

    @classmethod
    def from_orm(cls, c) -> "ConversationListItem":
        return cls(
            id=str(c.id),
            title=c.title,
            model=c.model,
            provider=c.provider,
            status=c.status,
            updated_at=_fmt(c.updated_at),
        )


class AddMessageRequest(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sequence: int
    created_at: str

    @classmethod
    def from_orm(cls, m) -> "MessageResponse":
        return cls(
            id=str(m.id),
            conversation_id=str(m.conversation_id),
            role=m.role,
            content=m.content,
            sequence=m.sequence,
            created_at=_fmt(m.created_at),
        )


class MessageTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    api_key: str
    context: list[MessageTurn]


class ConversationDetailResponse(BaseModel):
    id: str
    title: str | None
    status: str
    model: str
    provider: str
    messages: list[MessageResponse]

    @classmethod
    def from_orm(cls, c, messages: list) -> "ConversationDetailResponse":
        return cls(
            id=str(c.id),
            title=c.title,
            status=c.status,
            model=c.model,
            provider=c.provider,
            messages=[MessageResponse.from_orm(m) for m in messages],
        )
