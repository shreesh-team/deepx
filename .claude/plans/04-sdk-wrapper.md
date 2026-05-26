# Plan: SDK Wrapper for LLM Observability

## Context

The spec (`.claude/specs/04-sdk-wrapper.md`) calls for a Python SDK that wraps Gemini LLM calls and automatically ships inference metadata (latency, token counts, model, provider, timestamps, status, conversation_id, input/output previews) to the DeepX backend.

Two things need to be built:
1. **Backend** — a new ingestion endpoint + DB model to receive and store metadata
2. **SDK** — a lightweight Python package that wraps the `google-genai` client and POSTs to that endpoint

---

## Part 1: Backend Changes

### 1.1 — New model: `app/models/inference.py`

New `InferenceLog` table:
- `id` — UUID PK (gen_random_uuid)
- `conversation_id` — nullable UUID (no FK; SDK callers may not use backend conversations)
- `model` — str
- `provider` — str
- `status` — str (`"success"` | `"error"`)
- `error_message` — nullable str
- `latency_ms` — int (milliseconds)
- `input_tokens` — nullable int
- `output_tokens` — nullable int
- `total_tokens` — nullable int
- `input_preview` — nullable str (truncated)
- `output_preview` — nullable str (truncated)
- `requested_at` — datetime with tz
- `responded_at` — datetime with tz
- `created_at` — datetime with tz (auto server default)

Update `app/models/__init__.py` to export `InferenceLog`.

### 1.2 — New schema: `app/schemas/inference.py`

- `IngestRequest` — what the SDK POSTs (all fields from the model, datetimes as ISO strings, tokens nullable)
- `IngestResponse` — `{ "id": "<uuid>" }`

### 1.3 — New router: `app/routers/ingestion.py`

`POST /api/ingest`
- Accepts `IngestRequest`
- Optionally validates a bearer token against `settings.DEEPX_INGEST_API_KEY` (if set; open if not set — dev-friendly)
- Persists an `InferenceLog` row
- Returns `IngestResponse` with the new record's `id`

### 1.4 — Config update: `app/core/config.py`

Add:
```python
DEEPX_INGEST_API_KEY: str | None = None   # if set, SDK must send this as Bearer token
```

### 1.5 — Register router: `main.py`

Import and include `ingestion.router` with prefix `/api`.

---

## Part 2: SDK Package (`sdk/`)

New directory at repo root: `sdk/`

### Structure

```
sdk/
├── deepx_sdk/
│   ├── __init__.py      # exports: DeepXWrapper
│   ├── wrapper.py       # DeepXWrapper class — wraps genai.Client
│   └── ingestion.py     # background HTTP ingestion via httpx
├── pyproject.toml       # standalone package, depends on httpx
└── README.md
```

### `sdk/deepx_sdk/wrapper.py` — `DeepXWrapper`

```python
class DeepXWrapper:
    def __init__(self, client, *, ingestion_url, api_key=None,
                 conversation_id=None, preview_max=500): ...

    async def generate_content(self, model, contents, **kwargs): ...
    async def generate_content_stream(self, model, contents, **kwargs): ...
```

**Non-streaming flow:**
1. Record `requested_at = datetime.now(UTC)`
2. Call `client.aio.models.generate_content(...)`
3. Record `responded_at`, compute `latency_ms`
4. Extract token counts from `response.usage_metadata`
5. Build preview strings (truncated to `preview_max`)
6. Fire-and-forget: `asyncio.create_task(_ingest(metadata))`
7. Return original response untouched

**Streaming flow:**
1. Record `requested_at`
2. Call `client.aio.models.generate_content_stream(...)` — get async iterator
3. Yield each chunk to the caller as-is (transparent proxy)
4. Accumulate text chunks into `output_buf`
5. After last chunk, record `responded_at`, compute `latency_ms`, extract usage
6. `asyncio.create_task(_ingest(metadata))`

**Error handling:**
- Wrap the LLM call in try/except
- On exception: set `status="error"`, `error_message=str(e)`, still fire ingestion task, then re-raise

### `sdk/deepx_sdk/ingestion.py` — `_ingest()`

```python
async def ingest(payload: dict, url: str, api_key: str | None):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            await client.post(url, json=payload, headers=headers)
    except Exception:
        logging.getLogger("deepx_sdk").warning("DeepX ingestion failed", exc_info=True)
```

Silent drop on failure — never raises.

### `sdk/pyproject.toml`

```toml
[project]
name = "deepx-sdk"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["httpx>=0.27"]
```

### `sdk/README.md`

Minimal before/after snippet showing 3-line integration change.

---

## Build Order

1. `app/models/inference.py` + update `app/models/__init__.py`
2. `app/schemas/inference.py`
3. `app/core/config.py` — add `DEEPX_INGEST_API_KEY`
4. `app/routers/ingestion.py`
5. `main.py` — register ingestion router
6. `sdk/pyproject.toml`
7. `sdk/deepx_sdk/__init__.py`
8. `sdk/deepx_sdk/ingestion.py`
9. `sdk/deepx_sdk/wrapper.py`
10. `sdk/README.md`

---

## Verification

1. Start backend: `uv run fastapi dev main.py` — confirm `inference_logs` table auto-created
2. `POST /api/ingest` with sample payload — expect `{"id": "<uuid>"}` response
3. Auth: no/wrong token → 401; correct `Bearer` token → 201
4. SDK unit tests: `uv run python test_sdk.py` — all 5 tests pass
5. Kill ingestion endpoint mid-test — confirm LLM response still returned (silent failure)
