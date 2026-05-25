# Implementation Plan: LLM Connection — Live Chat via Google Gemini

## Context

Forward user conversations to Google Gemini and stream the response back to the UI in real time, persisting the completed AI response to the database. The backend always calls `gemini-3-flash-preview` regardless of any model name in the request.

---

## Files modified

| File | Change |
|------|--------|
| `pyproject.toml` | Added `google-genai` dependency (`uv add google-genai`) |
| `app/schemas/conversation.py` | Added `MessageTurn`, `ChatRequest` |
| `app/routers/conversations.py` | Added `_stream_and_save()` generator, `chat()` route, updated imports |

---

## New endpoint

`POST /api/conversations/{conversation_id}/chat`

**Request body:**
```json
{
  "api_key": "<gemini api key>",
  "context": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
    {"role": "user", "content": "How are you?"}
  ]
}
```

**Response:** SSE stream (`text/event-stream`)
- Chunks: `data: {"text": "..."}\n\n`
- Error: `data: {"error": "..."}\n\n`
- Done: `data: [DONE]\n\n`

---

## Key design decisions

- **Hardcoded model**: `gemini-3-flash-preview` — UI's model field is ignored.
- **Own DB session in generator**: `StreamingResponse` runs the generator after the route handler returns and FastAPI closes the injected `db` session. The generator opens its own `AsyncSessionLocal()` session to save the assistant message.
- **Role mapping**: Gemini uses `"model"` for AI turns; the context uses `"assistant"`. Mapped at call time.
- **API key not persisted**: Used only in the generator scope, never written to DB.

---

## Verification

1. `uv run fastapi dev main.py`
2. `POST /api/conversations` — create a conversation
3. `POST /api/conversations/{id}/messages` — add a user message
4. `POST /api/conversations/{id}/chat` with `api_key` + `context`
5. Verify SSE chunks stream in real time
6. `GET /api/conversations/{id}` — confirm assistant message saved with correct sequence
7. Test invalid API key → confirm `data: {"error": "..."}` is returned
