import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    AddMessageRequest,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
)

router = APIRouter(prefix="/api/conversations")

VALID_ROLES = {"user", "assistant", "system"}
VALID_STATUSES = {"active", "cancelled", "archived"}


def _err(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@router.post("", status_code=201)
async def create_conversation(body: CreateConversationRequest, db: AsyncSession = Depends(get_db)):
    if not body.model or not body.provider:
        return _err(400, "MISSING_FIELD", "model and provider are required")

    conversation = Conversation(model=body.model, provider=body.provider, title=body.title)
    db.add(conversation)
    try:
        await db.commit()
        await db.refresh(conversation)
    except Exception:
        await db.rollback()
        return _err(500, "INTERNAL_ERROR", "Failed to create conversation")

    return JSONResponse(status_code=201, content=ConversationResponse.from_orm(conversation).model_dump())


@router.get("")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    conversations = result.scalars().all()
    return [ConversationListItem.from_orm(c).model_dump() for c in conversations]


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    conversation = await db.scalar(select(Conversation).where(Conversation.id == cid))
    if not conversation:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    result = await db.execute(
        select(Message).where(Message.conversation_id == cid).order_by(Message.sequence.asc())
    )
    messages = result.scalars().all()

    return ConversationDetailResponse.from_orm(conversation, messages).model_dump()


@router.patch("/{conversation_id}/cancel")
async def cancel_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    conversation = await db.scalar(select(Conversation).where(Conversation.id == cid))
    if not conversation:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    conversation.status = "cancelled"
    try:
        await db.commit()
        await db.refresh(conversation)
    except Exception:
        await db.rollback()
        return _err(500, "INTERNAL_ERROR", "Failed to cancel conversation")

    return {"id": str(conversation.id), "status": conversation.status}


@router.post("/{conversation_id}/messages", status_code=201)
async def add_message(conversation_id: str, body: AddMessageRequest, db: AsyncSession = Depends(get_db)):
    if not body.role or not body.content:
        return _err(400, "MISSING_FIELD", "role and content are required")

    if body.role not in VALID_ROLES:
        return _err(400, "INVALID_ROLE", f"role must be one of: {', '.join(sorted(VALID_ROLES))}")

    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    conversation = await db.scalar(select(Conversation).where(Conversation.id == cid))
    if not conversation:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    if conversation.status == "cancelled":
        return _err(409, "CONVERSATION_CANCELLED", f"Conversation {conversation_id} is cancelled")

    max_seq = await db.scalar(select(func.max(Message.sequence)).where(Message.conversation_id == cid))
    next_seq = (max_seq + 1) if max_seq is not None else 0

    message = Message(conversation_id=cid, role=body.role, content=body.content, sequence=next_seq)
    db.add(message)

    await db.execute(
        update(Conversation).where(Conversation.id == cid).values(updated_at=func.now())
    )

    try:
        await db.commit()
        await db.refresh(message)
    except Exception:
        await db.rollback()
        return _err(500, "INTERNAL_ERROR", "Failed to add message")

    return JSONResponse(status_code=201, content=MessageResponse.from_orm(message).model_dump())
