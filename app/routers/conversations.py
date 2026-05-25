import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal, get_db
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    AddMessageRequest,
    ChatRequest,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
)

router = APIRouter(prefix="/api/conversations")


async def _stream_and_save(api_key: str, context: list, conversation_id: uuid.UUID):
    from google import genai

    contents = [
        {"role": "model" if t.role == "assistant" else t.role, "parts": [{"text": t.content}]}
        for t in context
    ]

    client = genai.Client(api_key=api_key)
    full_response = []

    try:
        async for chunk in await client.aio.models.generate_content_stream(
            model="gemini-3-flash-preview",
            contents=contents,
        ):
            text = chunk.text or ""
            if text:
                full_response.append(text)
                yield f"data: {json.dumps({'text': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

    complete = "".join(full_response)
    if complete:
        async with AsyncSessionLocal() as session:
            max_seq = await session.scalar(
                select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
            )
            next_seq = (max_seq + 1) if max_seq is not None else 0
            msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=complete,
                sequence=next_seq,
            )
            session.add(msg)
            await session.execute(
                update(Conversation).where(Conversation.id == conversation_id).values(updated_at=func.now())
            )
            await session.commit()

    yield "data: [DONE]\n\n"

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


@router.post("/{conversation_id}/chat")
async def chat(conversation_id: str, body: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not body.api_key or not body.context:
        return _err(400, "MISSING_FIELD", "api_key and context are required")

    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    conversation = await db.scalar(select(Conversation).where(Conversation.id == cid))
    if not conversation:
        return _err(404, "CONVERSATION_NOT_FOUND", f"No conversation found with id {conversation_id}")

    api_key = settings.GEMINI_API_KEY or body.api_key

    return StreamingResponse(
        _stream_and_save(api_key, body.context, cid),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
