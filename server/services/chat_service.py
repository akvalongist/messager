from __future__ import annotations

import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.chat import Chat, ChatMember, ChatType, MemberRole
from models.user import User


class ChatService:
    async def get_user(self, db: AsyncSession, user_id: str) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    async def ensure_membership(self, db: AsyncSession, chat_id: str, user_id: str) -> ChatMember:
        result = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")
        return membership

    async def get_chat(self, db: AsyncSession, chat_id: str) -> Chat:
        result = await db.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chat

    async def list_chat_member_ids(self, db: AsyncSession, chat_id: str) -> list[str]:
        result = await db.execute(
            select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
        )
        return [str(row[0]) for row in result.all()]

    async def find_or_create_direct_chat(
        self,
        db: AsyncSession,
        current_user: User,
        other_user_id: str,
    ) -> tuple[Chat, User]:
        other_user = await self.get_user(db, other_user_id)
        if str(current_user.id) == str(other_user_id):
            raise HTTPException(status_code=400, detail="Cannot create a chat with yourself")

        my_memberships = await db.execute(
            select(ChatMember.chat_id).where(ChatMember.user_id == str(current_user.id))
        )
        my_chat_ids = [str(row[0]) for row in my_memberships.all()]

        if my_chat_ids:
            other_memberships = await db.execute(
                select(ChatMember.chat_id).where(
                    ChatMember.user_id == other_user_id,
                    ChatMember.chat_id.in_(my_chat_ids),
                )
            )
            common_chat_ids = [str(row[0]) for row in other_memberships.all()]

            for chat_id in common_chat_ids:
                chat = await self.get_chat(db, chat_id)
                if chat.chat_type == ChatType.DIRECT.value:
                    return chat, other_user

        chat = Chat(chat_type=ChatType.DIRECT.value)
        db.add(chat)
        await db.flush()

        db.add(ChatMember(chat_id=str(chat.id), user_id=str(current_user.id), role=MemberRole.MEMBER.value))
        db.add(ChatMember(chat_id=str(chat.id), user_id=other_user_id, role=MemberRole.MEMBER.value))
        await db.flush()
        return chat, other_user

    async def create_group(
        self,
        db: AsyncSession,
        current_user: User,
        name: str,
        description: str,
        member_ids: list[str],
    ) -> tuple[Chat, int]:
        chat = Chat(
            chat_type=ChatType.GROUP.value,
            name=name,
            description=description,
            invite_code=secrets.token_urlsafe(16),
        )
        db.add(chat)
        await db.flush()

        db.add(ChatMember(chat_id=str(chat.id), user_id=str(current_user.id), role=MemberRole.OWNER.value))
        members_count = 1

        for member_id in dict.fromkeys(member_ids):
            result = await db.execute(select(User).where(User.id == member_id))
            if result.scalar_one_or_none():
                db.add(ChatMember(chat_id=str(chat.id), user_id=str(member_id), role=MemberRole.MEMBER.value))
                members_count += 1

        await db.flush()
        return chat, members_count


chat_service = ChatService()
