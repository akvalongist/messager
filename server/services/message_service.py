from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app_config import get_settings
from models.chat import Chat, ChatMember, ChatType
from models.message import Message
from models.user import User
from services.chat_service import chat_service
from services.notifications import notification_service


settings = get_settings()


class MessageService:
    async def create_message(
        self,
        db: AsyncSession,
        sender_id: str,
        payload: dict[str, Any],
    ) -> tuple[Message, User, list[str], Chat]:
        chat_id = payload.get("chat_id")
        if not chat_id:
            raise HTTPException(status_code=400, detail="chat_id is required")

        content = (payload.get("content") or "").strip()
        if content and len(content) > settings.max_message_length:
            raise HTTPException(status_code=400, detail="Message is too long")

        await chat_service.ensure_membership(db, chat_id, sender_id)

        sender_result = await db.execute(select(User).where(User.id == sender_id))
        sender = sender_result.scalar_one_or_none()
        if not sender:
            raise HTTPException(status_code=404, detail="User not found")

        chat = await chat_service.get_chat(db, chat_id)

        message = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            message_type=payload.get("message_type", "text"),
            content=content or None,
            reply_to_id=payload.get("reply_to_id"),
            file_url=payload.get("file_url"),
            file_name=payload.get("file_name"),
            file_size=payload.get("file_size"),
            mime_type=payload.get("mime_type"),
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        member_ids = await chat_service.list_chat_member_ids(db, chat_id)
        return message, sender, member_ids, chat

    async def serialize_message(self, message: Message, sender_name: str) -> dict[str, Any]:
        return {
            "id": str(message.id),
            "chat_id": str(message.chat_id),
            "sender_id": str(message.sender_id) if message.sender_id else None,
            "sender_name": sender_name,
            "message_type": message.message_type,
            "content": message.content,
            "file_url": message.file_url,
            "file_name": message.file_name,
            "file_size": message.file_size,
            "mime_type": message.mime_type,
            "reply_to_id": str(message.reply_to_id) if message.reply_to_id else None,
            "is_edited": message.is_edited,
            "is_deleted": message.is_deleted,
            "created_at": message.created_at.isoformat(),
        }

    async def notify_recipients(
        self,
        member_ids: list[str],
        sender_id: str,
        sender_name: str,
        chat: Chat,
        message: Message,
    ) -> None:
        preview = message.content or message.file_name or "New attachment"
        for user_id in member_ids:
            if user_id == sender_id:
                continue
            await notification_service.notify_new_message(
                recipient_id=user_id,
                sender_name=sender_name,
                message_preview=preview,
                chat_id=str(chat.id),
                message_id=str(message.id),
                sender_id=sender_id,
                chat_name=chat.name,
                is_group=chat.chat_type == ChatType.GROUP.value,
            )


message_service = MessageService()
