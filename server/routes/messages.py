from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models.user import User
from models.message import Message
from models.chat import ChatMember
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str | None
    sender_name: str | None
    message_type: str
    content: str | None
    encrypted_content: str | None
    file_url: str | None
    file_name: str | None
    file_size: int | None
    reply_to_id: str | None
    is_edited: bool
    is_deleted: bool
    created_at: datetime


class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]
    has_more: bool


@router.get("/{chat_id}", response_model=MessagesListResponse)
async def get_messages(
    chat_id: str,
    limit: int = Query(50, le=100),
    before: datetime | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Проверяем доступ
    membership = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == str(current_user.id)
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(403, "Нет доступа к чату")

    # Получаем сообщения
    query = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.created_at))
        .limit(limit + 1)
    )

    if before:
        query = query.where(Message.created_at < before)

    result = await db.execute(query)
    messages = list(result.scalars().all())

    has_more = len(messages) > limit
    messages = messages[:limit]
    messages.reverse()

    # Получаем имена отправителей
    sender_names = {}
    for msg in messages:
        if msg.sender_id and msg.sender_id not in sender_names:
            user_result = await db.execute(
                select(User).where(User.id == msg.sender_id)
            )
            user = user_result.scalar_one_or_none()
            sender_names[msg.sender_id] = user.display_name if user else "Unknown"

    return MessagesListResponse(
        messages=[
            MessageResponse(
                id=str(m.id),
                chat_id=str(m.chat_id),
                sender_id=str(m.sender_id) if m.sender_id else None,
                sender_name=sender_names.get(m.sender_id),
                message_type=m.message_type,
                content=m.content if not m.is_deleted else None,
                encrypted_content=m.encrypted_content if not m.is_deleted else None,
                file_url=m.file_url if not m.is_deleted else None,
                file_name=m.file_name,
                file_size=m.file_size,
                reply_to_id=str(m.reply_to_id) if m.reply_to_id else None,
                is_edited=m.is_edited,
                is_deleted=m.is_deleted,
                created_at=m.created_at
            )
            for m in messages
        ],
        has_more=has_more
    )


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(404, "Сообщение не найдено")

    if str(message.sender_id) != str(current_user.id):
        raise HTTPException(403, "Можно удалять только свои сообщения")

    message.is_deleted = True
    message.content = None
    message.encrypted_content = None

    return {"status": "deleted"}