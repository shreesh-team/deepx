# deepx-sdk

Lightweight Python wrapper for Google Gemini that automatically ships inference metadata to [DeepX](https://github.com/your-org/deepx).

## Install

```bash
pip install httpx  # only dependency
# copy sdk/deepx_sdk/ into your project, or pip install -e sdk/
```

## Usage

**Before:**
```python
from google import genai

client = genai.Client(api_key="YOUR_GEMINI_KEY")
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents="Explain async/await in Python",
)
print(response.text)
```

**After (3 lines changed):**
```python
from google import genai
from deepx_sdk import DeepXWrapper

client = genai.Client(api_key="YOUR_GEMINI_KEY")
deepx = DeepXWrapper(
    client,
    ingestion_url="http://localhost:8000/api/ingest",
    conversation_id="<optional-uuid>",  # groups calls in the dashboard
    api_key="<optional-bearer-token>",  # matches DEEPX_INGEST_API_KEY on the server
)

response = await deepx.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents="Explain async/await in Python",
)
print(response.text)
```

### Streaming

```python
async for chunk in deepx.generate_content_stream(
    model="gemini-2.0-flash-preview-image-generation",
    contents="Write a haiku about observability",
):
    print(chunk.text, end="", flush=True)
```

Metadata (latency, token counts, previews) is sent to DeepX **after the stream completes**, never blocking output.

## Configuration

| Parameter | Description | Default |
|---|---|---|
| `ingestion_url` | DeepX `/api/ingest` endpoint | required |
| `api_key` | Bearer token (matches `DEEPX_INGEST_API_KEY`) | `None` |
| `conversation_id` | Groups related calls in the dashboard | `None` |
| `preview_max` | Max characters for input/output previews | `500` |

## Captured metadata

Each call records: model, provider, latency (ms), input/output token counts, timestamps, status (`success`/`error`), error message, input preview, output preview, conversation ID.

Ingestion errors are **swallowed silently** — your LLM call always succeeds regardless.
