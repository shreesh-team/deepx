import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator

from deepx_sdk.ingestion import ingest


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _preview(text: str | None, max_len: int) -> str | None:
    if text is None:
        return None
    return text[:max_len] if len(text) > max_len else text


def _extract_input_text(contents) -> str:
    """Best-effort extraction of plain text from genai contents."""
    if isinstance(contents, str):
        return contents
    if isinstance(contents, list):
        parts = []
        for item in contents:
            if isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(item.text or "")
            elif hasattr(item, "parts"):
                for p in item.parts:
                    if hasattr(p, "text"):
                        parts.append(p.text or "")
        return " ".join(parts)
    return str(contents)


class DeepXWrapper:
    """
    Wraps a google-genai client to capture inference metadata and ship it
    to the DeepX ingestion endpoint after each call.

    Usage::

        from deepx_sdk import DeepXWrapper
        deepx = DeepXWrapper(
            client,
            ingestion_url="http://localhost:8000/api/ingest",
            api_key="optional-bearer-token",
            conversation_id="<uuid>",
        )
        response = await deepx.generate_content(model="gemini-...", contents=[...])
        async for chunk in deepx.generate_content_stream(model="gemini-...", contents=[...]):
            ...
    """

    def __init__(
        self,
        client,
        *,
        ingestion_url: str,
        api_key: str | None = None,
        conversation_id: str | None = None,
        preview_max: int = 500,
    ):
        self._client = client
        self._ingestion_url = ingestion_url
        self._api_key = api_key
        self._conversation_id = conversation_id
        self._preview_max = preview_max

    def _build_payload(
        self,
        *,
        model: str,
        status: str,
        error_message: str | None,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        input_preview: str | None,
        output_preview: str | None,
        requested_at: datetime,
        responded_at: datetime,
    ) -> dict:
        return {
            "conversation_id": self._conversation_id,
            "model": model,
            "provider": "google",
            "status": status,
            "error_message": error_message,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_preview": _preview(input_preview, self._preview_max),
            "output_preview": _preview(output_preview, self._preview_max),
            "requested_at": _iso(requested_at),
            "responded_at": _iso(responded_at),
        }

    def _fire_ingest(self, payload: dict) -> None:
        asyncio.create_task(ingest(payload, self._ingestion_url, self._api_key))

    async def generate_content(self, model: str, contents, **kwargs):
        input_text = _extract_input_text(contents)
        requested_at = _now()
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=contents, **kwargs
            )
            responded_at = _now()
            latency_ms = int((responded_at - requested_at).total_seconds() * 1000)

            usage = getattr(response, "usage_metadata", None)
            payload = self._build_payload(
                model=model,
                status="success",
                error_message=None,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "prompt_token_count", None),
                output_tokens=getattr(usage, "candidates_token_count", None),
                total_tokens=getattr(usage, "total_token_count", None),
                input_preview=input_text,
                output_preview=response.text if hasattr(response, "text") else None,
                requested_at=requested_at,
                responded_at=responded_at,
            )
            self._fire_ingest(payload)
            return response
        except Exception as exc:
            responded_at = _now()
            latency_ms = int((responded_at - requested_at).total_seconds() * 1000)
            payload = self._build_payload(
                model=model,
                status="error",
                error_message=str(exc),
                latency_ms=latency_ms,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                input_preview=input_text,
                output_preview=None,
                requested_at=requested_at,
                responded_at=responded_at,
            )
            self._fire_ingest(payload)
            raise

    async def generate_content_stream(self, model: str, contents, **kwargs) -> AsyncIterator:
        input_text = _extract_input_text(contents)
        requested_at = _now()
        output_buf: list[str] = []
        usage = None
        error_message: str | None = None
        status = "success"

        try:
            async for chunk in await self._client.aio.models.generate_content_stream(
                model=model, contents=contents, **kwargs
            ):
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    usage = chunk.usage_metadata
                if hasattr(chunk, "text") and chunk.text:
                    output_buf.append(chunk.text)
                yield chunk
        except Exception as exc:
            status = "error"
            error_message = str(exc)
            raise
        finally:
            responded_at = _now()
            latency_ms = int((responded_at - requested_at).total_seconds() * 1000)
            payload = self._build_payload(
                model=model,
                status=status,
                error_message=error_message,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "prompt_token_count", None),
                output_tokens=getattr(usage, "candidates_token_count", None),
                total_tokens=getattr(usage, "total_token_count", None),
                input_preview=input_text,
                output_preview="".join(output_buf) if output_buf else None,
                requested_at=requested_at,
                responded_at=responded_at,
            )
            self._fire_ingest(payload)
