from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.inference import InferenceLog
from app.schemas.inference import IngestRequest, IngestResponse

router = APIRouter(prefix="/api")

_bearer = HTTPBearer(auto_error=False)


async def _check_auth(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if settings.DEEPX_INGEST_API_KEY is None:
        return
    if credentials is None or credentials.credentials != settings.DEEPX_INGEST_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest(
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_check_auth),
):
    log = InferenceLog(
        conversation_id=body.conversation_id,
        model=body.model,
        provider=body.provider,
        status=body.status,
        error_message=body.error_message,
        latency_ms=body.latency_ms,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        total_tokens=body.total_tokens,
        input_preview=body.input_preview,
        output_preview=body.output_preview,
        requested_at=datetime.fromisoformat(body.requested_at),
        responded_at=datetime.fromisoformat(body.responded_at),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return IngestResponse(id=str(log.id))
