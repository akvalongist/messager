from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from datetime import datetime
import secrets

from database import get_db
from models.user import User
from models.chat import Chat, ChatMember, ChatType, MemberRole
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])


class CreateDirectChatRequest(BaseModel):
    user_id: str


class CreateGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    member_ids: list[str] = []


class ChatResponse(BaseModel):
    id: str
    chat_type: str
    name: str | None
    description: str
    avatar_url: str | None
    members_count: int
    invite_code: str | None = None
    created_at: datetime


class ChatListResponse(BaseModel):
    chats: list[ChatResponse]


@router.post("/direct", response_model=ChatResponse)
async def create_direct_chat(
    req: CreateDirectChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    print(f"📩 Создание чата: {current_user.id} -> {req.user_id}")

    # Проверяем что пользователь существует
    result = await db.execute(select(User).where(User.id == req.user_id))
    other_user = result.scalar_one_or_none()
    if not other_user:
        raise HTTPException(404, "Пользователь не найден")

    if str(current_user.id) == str(req.user_id):
        raise HTTPException(400, "Нельзя создать чат с самим собой")

    # Проверяем нет ли уже прямого чата
    my_memberships = await db.execute(
        select(ChatMember.chat_id).where(ChatMember.user_id == str(current_user.id))
    )
    my_chat_ids = [str(row[0]) for row in my_memberships.all()]

    if my_chat_ids:
        other_memberships = await db.execute(
            select(ChatMember.chat_id).where(
                ChatMember.user_id == str(req.user_id),
                ChatMember.chat_id.in_(my_chat_ids)
            )
        )
        common_chat_ids = [str(row[0]) for row in other_memberships.all()]

        for cid in common_chat_ids:
            chat_result = await db.execute(select(Chat).where(Chat.id == cid))
            chat = chat_result.scalar_one_or_none()
            if chat and chat.chat_type == ChatType.DIRECT.value:
                return ChatResponse(
                    id=str(chat.id),
                    chat_type=chat.chat_type,
                    name=other_user.display_name,
                    description="",
                    avatar_url=other_user.avatar_url,
                    members_count=2,
                    created_at=chat.created_at
                )

    # Создаём новый чат
    chat = Chat(chat_type=ChatType.DIRECT.value)
    db.add(chat)
    await db.flush()

    member1 = ChatMember(
        chat_id=str(chat.id),
        user_id=str(current_user.id),
        role=MemberRole.MEMBER.value
    )
    member2 = ChatMember(
        chat_id=str(chat.id),
        user_id=str(req.user_id),
        role=MemberRole.MEMBER.value
    )
    db.add(member1)
    db.add(member2)
    await db.flush()

    print(f"✅ Чат создан: {chat.id}")

    return ChatResponse(
        id=str(chat.id),
        chat_type=ChatType.DIRECT.value,
        name=other_user.display_name,
        description="",
        avatar_url=other_user.avatar_url,
        members_count=2,
        created_at=chat.created_at
    )


@router.post("/group", response_model=ChatResponse)
async def create_group(
    req: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    print(f"👥 Создание группы: {req.name}")

    chat = Chat(
        chat_type=ChatType.GROUP.value,
        name=req.name,
        description=req.description,
        invite_code=secrets.token_urlsafe(16)
    )
    db.add(chat)
    await db.flush()

    owner = ChatMember(
        chat_id=str(chat.id),
        user_id=str(current_user.id),
        role=MemberRole.OWNER.value
    )
    db.add(owner)

    members_count = 1

    for member_id in req.member_ids:
        result = await db.execute(select(User).where(User.id == member_id))
        if result.scalar_one_or_none():
            member = ChatMember(
                chat_id=str(chat.id),
                user_id=str(member_id),
                role=MemberRole.MEMBER.value
            )
            db.add(member)
            members_count += 1

    await db.flush()

    print(f"✅ Группа создана: {chat.id}")

    return ChatResponse(
        id=str(chat.id),
        chat_type=ChatType.GROUP.value,
        name=chat.name,
        description=chat.description or "",
        avatar_url=None,
        members_count=members_count,
        invite_code=chat.invite_code,
        created_at=chat.created_at
    )


@router.get("/", response_model=ChatListResponse)
async def get_my_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Получаем ID чатов пользователя
    memberships = await db.execute(
        select(ChatMember.chat_id).where(ChatMember.user_id == str(current_user.id))
    )
    chat_ids = [str(row[0]) for row in memberships.all()]

    if not chat_ids:
        return ChatListResponse(chats=[])

    chat_list = []

    for chat_id in chat_ids:
        # Получаем чат
        chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
        chat = chat_result.scalar_one_or_none()
        if not chat:
            continue

        # Получаем участников
        members_result = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == chat_id)
        )
        members = members_result.scalars().all()

        name = chat.name
        avatar = chat.avatar_url

        # Для личных чатов — показываем имя собеседника
        if chat.chat_type == ChatType.DIRECT.value:
            other_member = next(
                (m for m in members if str(m.user_id) != str(current_user.id)),
                None
            )
            if other_member:
                user_result = await db.execute(
                    select(User).where(User.id == str(other_member.user_id))
                )
                other_user = user_result.scalar_one_or_none()
                if other_user:
                    name = other_user.display_name
                    avatar = other_user.avatar_url

        chat_list.append(ChatResponse(
            id=str(chat.id),
            chat_type=chat.chat_type,
            name=name,
            description=chat.description or "",
            avatar_url=avatar,
            members_count=len(members),
            invite_code=chat.invite_code,
            created_at=chat.created_at
        ))

    return ChatListResponse(chats=chat_list)


@router.post("/join/{invite_code}", response_model=ChatResponse)
async def join_by_invite(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Chat).where(Chat.invite_code == invite_code)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Чат не найден")

    # Проверяем не состоит ли уже
    existing = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == str(chat.id),
            ChatMember.user_id == str(current_user.id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Вы уже в этом чате")

    member = ChatMember(
        chat_id=str(chat.id),
        user_id=str(current_user.id),
        role=MemberRole.MEMBER.value
    )
    db.add(member)

    members_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == str(chat.id))
    )
    members_count = len(members_result.scalars().all()) + 1

    return ChatResponse(
        id=str(chat.id),
        chat_type=chat.chat_type,
        name=chat.name,
        description=chat.description or "",
        avatar_url=chat.avatar_url,
        members_count=members_count,
        invite_code=chat.invite_code,
        created_at=chat.created_at
    )