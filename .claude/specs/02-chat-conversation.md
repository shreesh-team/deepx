# Spec: Chat History Storage

## Overview

Implement the database schema and backend logic for storing and retrieving chat conversations and messages.

The system must support:
- Starting a new conversation with an LLM provider
- Appending messages (user and assistant turns) to a conversation
- Resuming a conversation by fetching its full message history
- Cancelling a conversation
- Listing all conversations sorted by most recent activity

DB connection to PostgreSQL is already established.


---

## Database Schema

### A. conversations

| Column       | Type        | Constraints                              |
|--------------|-------------|------------------------------------------|
| id           | UUID        | primary key, default gen_random_uuid()   |
| title        | TEXT        | nullable, auto-generated from first msg  |
| model        | TEXT        | not null                                 |
| provider     | TEXT        | not null                                 |
| status       | TEXT        | not null, default 'active'               |
| created_at   | TIMESTAMPTZ | not null, default now()                  |
| updated_at   | TIMESTAMPTZ | not null, default now()                  |

**Allowed values — status:** `active` | `cancelled` | `archived`

**Indexes:**
- `idx_conversations_updated_at` ON `conversations(updated_at DESC)`


### B. messages

| Column          | Type        | Constraints                                        |
|-----------------|-------------|----------------------------------------------------|
| id              | UUID        | primary key, default gen_random_uuid()             |
| conversation_id | UUID        | not null, FK → conversations(id) ON DELETE CASCADE |
| role            | TEXT        | not null                                           |
| content         | TEXT        | not null                                           |
| sequence        | INTEGER     | not null                                           |
| created_at      | TIMESTAMPTZ | not null, default now()                            |

**Allowed values — role:** `user` | `assistant` | `system`

**Constraints:**
- `UNIQUE(conversation_id, sequence)` — enforces message ordering per conversation

**Indexes:**
- `idx_messages_conversation_id` ON `messages(conversation_id)`


---

## Migration SQL

```sql
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT,
    model       TEXT NOT NULL,
    provider    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_updated_at ON conversations(updated_at DESC);

CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL,
    content          TEXT NOT NULL,
    sequence         INTEGER NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(conversation_id, sequence)
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
```


---

## Routes

| Method | Route                              | Description                          |
|--------|------------------------------------|--------------------------------------|
| POST   | `/api/conversations`               | Start a new conversation             |
| GET    | `/api/conversations`               | List all conversations               |
| GET    | `/api/conversations/:id`           | Get a conversation with all messages |
| PATCH  | `/api/conversations/:id/cancel`    | Cancel a conversation                |
| POST   | `/api/conversations/:id/messages`  | Append a new message                 |


### Request / Response Shapes

**POST `/api/conversations`**
```json
// Request
{
  "model": "claude-sonnet-4-5",
  "provider": "anthropic",
  "title": "Optional title"           // nullable
}

// Response 201
{
  "id": "uuid",
  "title": null,
  "model": "claude-sonnet-4-5",
  "provider": "anthropic",
  "status": "active",
  "created_at": "2026-05-24T10:00:00Z",
  "updated_at": "2026-05-24T10:00:00Z"
}
```

**GET `/api/conversations`**
```json
// Response 200
[
  {
    "id": "uuid",
    "title": "What is Python?",
    "model": "claude-sonnet-4-5",
    "provider": "anthropic",
    "status": "active",
    "updated_at": "2026-05-24T10:05:00Z"
  }
]
```

**GET `/api/conversations/:id`**
```json
// Response 200
{
  "id": "uuid",
  "title": "What is Python?",
  "status": "active",
  "model": "claude-sonnet-4-5",
  "provider": "anthropic",
  "messages": [
    { "id": "uuid", "role": "user",      "content": "What is Python?", "sequence": 0 },
    { "id": "uuid", "role": "assistant", "content": "Python is...",    "sequence": 1 }
  ]
}
```

**POST `/api/conversations/:id/messages`**
```json
// Request
{
  "role": "user",
  "content": "Tell me more"
}

// Response 201
{
  "id": "uuid",
  "conversation_id": "uuid",
  "role": "user",
  "content": "Tell me more",
  "sequence": 2,
  "created_at": "2026-05-24T10:06:00Z"
}
```

**PATCH `/api/conversations/:id/cancel`**
```json
// Response 200
{
  "id": "uuid",
  "status": "cancelled"
}
```


---

## Rules for Implementation

1. `sequence` must be computed as `MAX(sequence) + 1` for the given `conversation_id` before each message insert. Start at `0` for the first message.
2. Every INSERT into `messages` must also UPDATE `conversations SET updated_at = now()` for the parent conversation — this keeps the list sort accurate.
3. Timestamps must follow ISO 8601 format consistently: `YYYY-MM-DDTHH:MM:SSZ`
4. `role` and `status` must be validated against their allowed values before any DB write. Reject unknown values with a `400`.
5. Messages are append-only. No UPDATE or DELETE on the `messages` table.
6. Do not expose raw DB errors to the client. Map them to structured error responses (see Error Handling).


---

## Error Handling

All errors must return a consistent JSON envelope:

```json
{
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "No conversation found with id abc-123"
  }
}
```

| Scenario                              | HTTP Status | Error Code                  |
|---------------------------------------|-------------|-----------------------------|
| `conversation_id` not found           | 404         | `CONVERSATION_NOT_FOUND`    |
| Invalid `role` value                  | 400         | `INVALID_ROLE`              |
| Invalid `status` value                | 400         | `INVALID_STATUS`            |
| Appending to a cancelled conversation | 409         | `CONVERSATION_CANCELLED`    |
| Missing required field in request     | 400         | `MISSING_FIELD`             |
| DB write failure                      | 500         | `INTERNAL_ERROR`            |


---

## Definition of Done

1. A new conversation can be created with a model and provider.
2. Messages can be appended to a conversation in order, with `sequence` auto-assigned.
3. A conversation and its full message history can be fetched in sequence order.
4. A conversation can be cancelled; no further messages can be appended after cancellation.
5. All conversations can be listed, sorted by most recently updated.
6. All error cases in the error handling table return the correct HTTP status and error code.
7. The `UNIQUE(conversation_id, sequence)` constraint is active and enforced at the DB level.
8. `updated_at` on `conversations` reflects the timestamp of the latest message insert.