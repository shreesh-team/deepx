# Plan: Chat Conversation Backend

## Context

Implementing the database schema and REST API for storing and retrieving chat conversations and messages, as specified in `.claude/specs/02-chat-conversation.md`. This is the persistence layer for the DeepX LLM observability platform — enabling the chatbot UI to start conversations, append messages, and replay history.

DB connection and async SQLAlchemy setup already exist. Auth routes provide the pattern to follow.

---

## Files to Create / Modify

| Action   | File                              | Purpose                                    |
|----------|-----------------------------------|--------------------------------------------|
| Create   | `app/models/conversation.py`      | SQLAlchemy ORM models: `Conversation`, `Message` |
| Create   | `app/schemas/conversation.py`     | Pydantic request/response schemas          |
| Create   | `app/routers/conversations.py`    | All 5 route handlers                       |
| Modify   | `app/models/__init__.py`          | Export new models so `Base.metadata.create_all` picks them up |
| Modify   | `main.py`                         | Register the conversations router          |

---

## 1. Models — `app/models/conversation.py`

Use `sqlalchemy.dialects.postgresql.UUID` with `as_uuid=True` for UUID columns. Mirror the pattern in `app/models/user.py` (imports from `app.models.base.Base`).

```python
class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("idx_conversations_updated_at", "updated_at", postgresql_ops={"updated_at": "DESC"}),)

    id: UUID pk, default gen_random_uuid() via server_default
    title: TEXT nullable
    model: TEXT not null
    provider: TEXT not null
    status: TEXT not null, server_default "active"
    created_at: TIMESTAMPTZ not null, server_default now()
    updated_at: TIMESTAMPTZ not null, server_default now()

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence"),
        Index("idx_messages_conversation_id", "conversation_id"),
    )

    id: UUID pk, default gen_random_uuid()
    conversation_id: UUID FK → conversations.id ON DELETE CASCADE, not null
    role: TEXT not null
    content: TEXT not null
    sequence: INTEGER not null
    created_at: TIMESTAMPTZ not null, server_default now()
```

---

## 2. Schemas — `app/schemas/conversation.py`

Follow existing `from_orm` classmethod pattern (see `app/schemas/user.py`). Format all timestamps as `YYYY-MM-DDTHH:MM:SSZ`.

```
CreateConversationRequest   model, provider, title (optional, default None)
ConversationResponse        id, title, model, provider, status, created_at, updated_at
ConversationListItem        id, title, model, provider, status, updated_at
AddMessageRequest           role, content
MessageResponse             id, conversation_id, role, content, sequence, created_at
ConversationDetailResponse  id, title, status, model, provider, messages: list[MessageResponse]
ErrorDetail                 code, message
ErrorResponse               error: ErrorDetail
```

---

## 3. Routes — `app/routers/conversations.py`

Prefix: `/api/conversations`. Use `APIRouter(prefix="/api/conversations")`.

### POST `/api/conversations` → 201
- Validate no required fields missing (`model`, `provider`) → 400 `MISSING_FIELD`
- Insert `Conversation`; return `ConversationResponse`

### GET `/api/conversations` → 200
- `SELECT * FROM conversations ORDER BY updated_at DESC`
- Return `list[ConversationListItem]`

### GET `/api/conversations/:id` → 200
- Fetch conversation by id → 404 `CONVERSATION_NOT_FOUND` if missing
- Fetch messages `WHERE conversation_id = :id ORDER BY sequence ASC`
- Return `ConversationDetailResponse`

### PATCH `/api/conversations/:id/cancel` → 200
- Fetch conversation → 404 if missing
- Set `status = 'cancelled'`, return `{id, status}`

### POST `/api/conversations/:id/messages` → 201
- Validate `role` ∈ `{user, assistant, system}` → 400 `INVALID_ROLE`
- Fetch conversation → 404 if missing
- If `status == 'cancelled'` → 409 `CONVERSATION_CANCELLED`
- Compute next sequence: `SELECT MAX(sequence) FROM messages WHERE conversation_id = :id` → `(max or -1) + 1`
- Insert `Message`
- `UPDATE conversations SET updated_at = now() WHERE id = :id`
- Return `MessageResponse`

---

## 4. Error Handling

All errors return:
```json
{"error": {"code": "CONVERSATION_NOT_FOUND", "message": "..."}}
```

Helper: `def error_response(status_code, code, message)` using `JSONResponse`.

Mapping:
| Scenario | Status | Code |
|---|---|---|
| conversation not found | 404 | `CONVERSATION_NOT_FOUND` |
| invalid role | 400 | `INVALID_ROLE` |
| invalid status | 400 | `INVALID_STATUS` |
| append to cancelled | 409 | `CONVERSATION_CANCELLED` |
| missing required field | 400 | `MISSING_FIELD` |
| db failure | 500 | `INTERNAL_ERROR` |

---

## 5. Registration — `main.py`

```python
from app.routers.conversations import router as conversations_router
app.include_router(conversations_router)
```

---

## 6. Model Export — `app/models/__init__.py`

Import `Conversation` and `Message` so `Base.metadata.create_all` in the lifespan picks up both new tables.

---

## Verification

1. Start server: `uv run fastapi dev main.py` — confirm both tables created on startup.
2. `POST /api/conversations` with `{model, provider}` → 201 with UUID id.
3. `POST /api/conversations/:id/messages` twice → sequences 0 and 1.
4. `GET /api/conversations/:id` → messages in order.
5. `PATCH /api/conversations/:id/cancel` → status becomes `cancelled`.
6. `POST /api/conversations/:id/messages` after cancel → 409 `CONVERSATION_CANCELLED`.
7. `GET /api/conversations` → sorted by `updated_at DESC`.
8. Invalid role → 400 `INVALID_ROLE`. Missing field → 400 `MISSING_FIELD`. Unknown id → 404.
