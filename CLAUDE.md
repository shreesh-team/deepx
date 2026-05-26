# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

DeepX is an LLM observability platform. The core idea:

```
User → Chatbot UI → [SDK Wrapper] → LLM API
                         ↓
                  Ingestion API → Database
```

The FastAPI backend serves as both the **Ingestion API** and a **chat proxy** — receiving and persisting conversation logs, and streaming LLM responses via the Google Gemini API.

## Commands

This project uses `uv` as the package manager.

```bash
# Run dev server (auto-reload)
uv run fastapi dev main.py

# Run production server
uv run fastapi run main.py

# Add a dependency
uv add <package>

# Run a script/one-off
uv run python -c "..."
```

## Architecture

**Entry point**: `main.py` — defines the FastAPI `app` and the `lifespan` context manager. The lifespan runs a `SELECT 1` health check, runs `Base.metadata.create_all` to auto-create tables, and disposes the connection pool on shutdown. Also registers CORS middleware (origins from `CORS_ORIGINS` env var) and a global `RequestValidationError` handler that returns structured `{"error": {"code": ..., "message": ...}}` JSON.

**Config** (`app/core/config.py`): `pydantic-settings` `Settings` class reads all config from `.env`. Key settings:
- `DATABASE_URL` — must use `postgresql+asyncpg://` scheme
- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_PRE_PING` — connection pool tuning
- `CORS_ORIGINS` — comma-separated allowed origins, defaults to `"*"`
- `GEMINI_API_KEY` — optional; if set, overrides the per-request `api_key` in chat requests
- `DEEPX_INGEST_API_KEY` — optional; if set, `POST /api/ingest` requires a matching `Authorization: Bearer <key>` header; if unset, the endpoint is open (dev-friendly)

**Database** (`app/db/database.py`): Creates a SQLAlchemy 2.0 async engine and an `async_sessionmaker` (`AsyncSessionLocal`). The `get_db()` async generator is the standard FastAPI dependency for per-request sessions. `AsyncSessionLocal` is also used directly inside the streaming generator (which runs outside the request lifecycle).

**Security** (`app/core/security.py`): Password hashing via `hashlib.pbkdf2_hmac` (SHA-256, 260k iterations) with a 32-byte random salt. No JWT — auth endpoints return user data directly; session management is left to the client.

## Models

All models use `app/models/base.py` (`DeclarativeBase`). Tables are auto-created on startup.

- **`User`** (`users`): `id` (int PK), `name`, `email` (unique), `password` (hashed), `created_at`
- **`Conversation`** (`conversations`): `id` (UUID PK), `title`, `model`, `provider`, `status` (default `"active"`), `created_at`, `updated_at`. Indexed on `updated_at`.
- **`Message`** (`messages`): `id` (UUID PK), `conversation_id` (FK → conversations, CASCADE), `role`, `content`, `sequence` (int, unique per conversation). Indexed on `conversation_id`.
- **`InferenceLog`** (`inference_logs`): `id` (UUID PK), `conversation_id` (nullable UUID, no FK), `model`, `provider`, `status` (`"success"` | `"error"`), `error_message` (nullable), `latency_ms` (int), `input_tokens`, `output_tokens`, `total_tokens` (all nullable int), `input_preview`, `output_preview` (both nullable str, SDK-truncated to `preview_max`), `requested_at`, `responded_at`, `created_at`.

## API Routes

### Auth (`app/routers/auth.py`)
- `POST /register` — create user; 409 if email taken
- `POST /login` — verify credentials; 401 on failure

### Conversations (`app/routers/conversations.py`, prefix `/api/conversations`)
- `POST /api/conversations` — create conversation (`model`, `provider` required)
- `GET /api/conversations` — list all, ordered by `updated_at` desc
- `GET /api/conversations/{id}` — get conversation with messages
- `PATCH /api/conversations/{id}/cancel` — set status to `"cancelled"`
- `POST /api/conversations/{id}/messages` — append a message (`role` ∈ `{user, assistant, system}`)
- `POST /api/conversations/{id}/chat` — stream a Gemini response (SSE); saves assistant reply and bumps `updated_at`

### Chat streaming detail
The `_stream_and_save` async generator calls `google-genai` (`gemini-3-flash-preview`) with SSE chunks formatted as `data: {"text": "..."}`. On completion it opens a new `AsyncSessionLocal` session to persist the assistant message (sequence auto-incremented) and update `updated_at`. Terminates with `data: [DONE]`.

### Ingestion (`app/routers/ingestion.py`, prefix `/api`)
- `POST /api/ingest` — accept an `IngestRequest` payload from the SDK, persist an `InferenceLog` row, return `{"id": "<uuid>"}`. Auth: validates `Authorization: Bearer` token against `DEEPX_INGEST_API_KEY` if that setting is set; otherwise open.

## Schemas (`app/schemas/`)

- `user.py`: `RegisterRequest`, `LoginRequest`, `UserResponse`
- `conversation.py`: `CreateConversationRequest`, `ConversationResponse`, `ConversationListItem`, `AddMessageRequest`, `MessageResponse`, `MessageTurn`, `ChatRequest`, `ConversationDetailResponse`
- `inference.py`: `IngestRequest`, `IngestResponse`

Auth/conversation schemas use manual `from_orm` class methods rather than Pydantic's `model_validate` / `from_attributes`. `IngestRequest` uses plain Pydantic fields (no ORM mapping needed).

## Environment

Copy `.env.example` to `.env` and fill in credentials before running:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/deepx
CORS_ORIGINS=http://localhost:3000
GEMINI_API_KEY=your_key_here          # optional
DEEPX_INGEST_API_KEY=your_secret_here # optional; secures POST /api/ingest
```

`.env` is gitignored. Never commit it.

## SDK (`sdk/`)

A standalone Python package (`deepx-sdk`) that wraps the `google-genai` client and ships inference metadata to `POST /api/ingest` after every call.

**Structure:**
```
sdk/
├── deepx_sdk/
│   ├── __init__.py      # exports DeepXWrapper
│   ├── wrapper.py       # DeepXWrapper — intercepts generate_content / generate_content_stream
│   └── ingestion.py     # async httpx POST with silent failure
├── pyproject.toml       # depends only on httpx>=0.27
└── README.md
```

**Usage (3 lines):**
```python
from deepx_sdk import DeepXWrapper
deepx = DeepXWrapper(client, ingestion_url="http://localhost:8000/api/ingest", conversation_id="<uuid>")
response = await deepx.generate_content(model="gemini-...", contents="...")
```

**Key behaviours:**
- Works for both non-streaming (`generate_content`) and streaming (`generate_content_stream`) calls
- Metadata is sent **after** the call completes (non-blocking `asyncio.create_task`)
- Ingestion errors are swallowed silently — LLM response is always returned
- Preview strings are truncated client-side to `preview_max` (default 500 chars) before sending
- `conversation_id` is optional; omitting it logs the call as standalone

**Install for local dev:**
```bash
pip install -e sdk/   # or: uv pip install -e sdk/
```
