from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.inference import InferenceLog
from app.schemas.inference import (
    InferenceLogResponse,
    IngestRequest,
    IngestResponse,
    PaginatedInferenceLogsResponse,
)

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


@router.get("/inference-logs", response_model=PaginatedInferenceLogsResponse)
async def list_inference_logs(
    status: str | None = Query(None),
    model: str | None = Query(None),
    conversation_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if status:
        filters.append(InferenceLog.status == status)
    if model:
        filters.append(InferenceLog.model == model)
    if conversation_id:
        filters.append(InferenceLog.conversation_id == conversation_id)

    base = select(InferenceLog).where(*filters)

    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.scalars(
        base.order_by(InferenceLog.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    return PaginatedInferenceLogsResponse(
        items=[InferenceLogResponse.from_orm(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
