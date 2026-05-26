import logging

import httpx

logger = logging.getLogger("deepx_sdk")


async def ingest(payload: dict, url: str, api_key: str | None) -> None:
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=payload, headers=headers)
    except Exception:
        logger.warning("DeepX ingestion failed — metadata not recorded", exc_info=True)
