"""
Quick integration test for DeepXWrapper.
Tests non-streaming, streaming, error capture, and silent-failure.
Run with: uv run python test_sdk.py
"""
import asyncio
import sys

sys.path.insert(0, "sdk")

from unittest.mock import AsyncMock, MagicMock, patch
from deepx_sdk import DeepXWrapper


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_usage(prompt=10, candidates=50, total=60):
    u = MagicMock()
    u.prompt_token_count = prompt
    u.candidates_token_count = candidates
    u.total_token_count = total
    return u


def _make_response(text="Hello from Gemini", usage=None):
    r = MagicMock()
    r.text = text
    r.usage_metadata = usage or _make_usage()
    return r


async def fake_stream(chunks):
    for c in chunks:
        yield c


# ── tests ─────────────────────────────────────────────────────────────────────

async def test_non_streaming(ingestion_url: str):
    print("\n[1] Non-streaming generate_content")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=_make_response())

    ingested = []
    async def fake_ingest(payload, url, api_key):
        ingested.append(payload)

    deepx = DeepXWrapper(
        client,
        ingestion_url=ingestion_url,
        conversation_id="conv-123",
        preview_max=500,
    )

    with patch("deepx_sdk.wrapper.ingest", side_effect=fake_ingest):
        with patch("asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)):
            response = await deepx.generate_content(model="gemini-flash", contents="Hello")
            await asyncio.sleep(0.1)  # let the task run

    assert response.text == "Hello from Gemini", "Response not passed through"
    assert len(ingested) == 1, f"Expected 1 ingest call, got {len(ingested)}"
    p = ingested[0]
    assert p["status"] == "success"
    assert p["model"] == "gemini-flash"
    assert p["provider"] == "google"
    assert p["conversation_id"] == "conv-123"
    assert p["input_tokens"] == 10
    assert p["output_tokens"] == 50
    assert p["total_tokens"] == 60
    assert p["input_preview"] == "Hello"
    assert p["output_preview"] == "Hello from Gemini"
    assert p["latency_ms"] >= 0
    print("   PASS")


async def test_streaming(ingestion_url: str):
    print("\n[2] Streaming generate_content_stream")

    chunks = []
    for i, text in enumerate(["Async", "/await", " rocks"]):
        c = MagicMock()
        c.text = text
        c.usage_metadata = _make_usage(5, 20, 25) if i == 2 else None
        chunks.append(c)

    client = MagicMock()
    client.aio.models.generate_content_stream = AsyncMock(return_value=fake_stream(chunks))

    ingested = []
    async def fake_ingest(payload, url, api_key):
        ingested.append(payload)

    deepx = DeepXWrapper(client, ingestion_url=ingestion_url, preview_max=500)

    collected = []
    with patch("deepx_sdk.wrapper.ingest", side_effect=fake_ingest):
        with patch("asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)):
            async for chunk in deepx.generate_content_stream(model="gemini-flash", contents="Tell me"):
                collected.append(chunk.text)
            await asyncio.sleep(0.1)

    assert "".join(collected) == "Async/await rocks", f"Stream not forwarded: {collected}"
    assert len(ingested) == 1
    p = ingested[0]
    assert p["status"] == "success"
    assert p["output_preview"] == "Async/await rocks"
    assert p["input_tokens"] == 5
    print("   PASS")


async def test_error_capture(ingestion_url: str):
    print("\n[3] Error capture — LLM call raises, ingest records it, exception re-raised")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("quota exceeded"))

    ingested = []
    async def fake_ingest(payload, url, api_key):
        ingested.append(payload)

    deepx = DeepXWrapper(client, ingestion_url=ingestion_url)

    raised = False
    with patch("deepx_sdk.wrapper.ingest", side_effect=fake_ingest):
        with patch("asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)):
            try:
                await deepx.generate_content(model="gemini-flash", contents="Boom")
            except RuntimeError:
                raised = True
            await asyncio.sleep(0.1)

    assert raised, "Exception should have been re-raised"
    assert len(ingested) == 1
    p = ingested[0]
    assert p["status"] == "error"
    assert "quota exceeded" in p["error_message"]
    print("   PASS")


async def test_preview_truncation(ingestion_url: str):
    print("\n[4] Preview truncation at preview_max=20")
    client = MagicMock()
    long_output = "X" * 100
    client.aio.models.generate_content = AsyncMock(return_value=_make_response(text=long_output))

    ingested = []
    async def fake_ingest(payload, url, api_key):
        ingested.append(payload)

    deepx = DeepXWrapper(client, ingestion_url=ingestion_url, preview_max=20)

    with patch("deepx_sdk.wrapper.ingest", side_effect=fake_ingest):
        with patch("asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)):
            await deepx.generate_content(model="gemini-flash", contents="A" * 50)
            await asyncio.sleep(0.1)

    p = ingested[0]
    assert len(p["input_preview"]) == 20, f"input_preview len={len(p['input_preview'])}"
    assert len(p["output_preview"]) == 20, f"output_preview len={len(p['output_preview'])}"
    print("   PASS")


async def test_silent_failure(ingestion_url: str):
    print("\n[5] Silent failure — ingestion error swallowed, LLM response returned")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=_make_response())

    async def failing_ingest(payload, url, api_key):
        raise ConnectionError("ingestion endpoint down")

    deepx = DeepXWrapper(client, ingestion_url="http://bad-host/api/ingest")

    with patch("deepx_sdk.wrapper.ingest", side_effect=failing_ingest):
        with patch("asyncio.create_task", side_effect=lambda coro: asyncio.ensure_future(coro)):
            response = await deepx.generate_content(model="gemini-flash", contents="Hello")
            await asyncio.sleep(0.1)

    assert response.text == "Hello from Gemini", "LLM response must survive ingestion failure"
    print("   PASS")


async def main():
    url = "http://127.0.0.1:8002/api/ingest"
    print(f"=== DeepX SDK Tests (ingestion_url={url}) ===")
    await test_non_streaming(url)
    await test_streaming(url)
    await test_error_capture(url)
    await test_preview_truncation(url)
    await test_silent_failure(url)
    print("\n=== All tests PASSED ===")


asyncio.run(main())
