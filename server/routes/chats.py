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
    # Проверяем что пользователь существует
    result = await db.execute(select(User).where(User.id == req.user_id))
    other_user = result.scalar_one_or_none()
    if not other_user:
        raise HTTPException(404, "Пользователь не найден")

    if str(current_user.id) == str(req.user_id):
        raise HTTPException(400, "Нельзя создать чат с самим собой")

    # Проверяем нет ли уже прямого чата
    my_chats = await db.execute(
        select(Chat)
        .join(ChatMember)
        .where(
            Chat.chat_type == ChatType.DIRECT.value,
            ChatMember.user_id == str(current_user.id)
        )
        .options(selectinload(Chat.members))
    )

    for chat in my_chats.scalars():
        member_ids = {str(m.user_id) for m in chat.members}
        if str(req.user_id) in member_ids:
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

    # Добавляем участников
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
    # Создаём группу
    chat = Chat(
        chat_type=ChatType.GROUP.value,
        name=req.name,
        description=req.description,
        invite_code=secrets.token_urlsafe(16)
    )
    db.add(chat)
    await db.flush()

    # Создатель = владелец
    owner = ChatMember(
        chat_id=str(chat.id),
        user_id=str(current_user.id),
        role=MemberRole.OWNER.value
    )
    db.add(owner)

    members_count = 1

    # Добавляем участников
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
    result = await db.execute(
        select(Chat)
        .join(ChatMember)
        .where(ChatMember.user_id == str(current_user.id))
        .options(selectinload(Chat.members).selectinload(ChatMember.user))
    )
    chats = result.scalars().unique().all()

    chat_list = []
    for chat in chats:
        name = chat.name
        avatar = chat.avatar_url

        if chat.chat_type == ChatType.DIRECT.value:
            other = next(
                (m.user for m in chat.members if str(m.user_id) != str(current_user.id)),
                None
            )
            if other:
                name = other.display_name
                avatar = other.avatar_url

        chat_list.append(ChatResponse(
            id=str(chat.id),
            chat_type=chat.chat_type,
            name=name,
            description=chat.description or "",
            avatar_url=avatar,
            members_count=len(chat.members),
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
        select(Chat)
        .where(Chat.invite_code == invite_code)
        .options(selectinload(Chat.members))
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Чат не найден")

    is_member = any(str(m.user_id) == str(current_user.id) for m in chat.members)
    if is_member:
        raise HTTPException(400, "Вы уже в этом чате")

    member = ChatMember(
        chat_id=str(chat.id),
        user_id=str(current_user.id),
        role=MemberRole.MEMBER.value
    )
    db.add(member)

    return ChatResponse(
        id=str(chat.id),
        chat_type=chat.chat_type,
        name=chat.name,
        description=chat.description or "",
        avatar_url=chat.avatar_url,
        members_count=len(chat.members) + 1,
        invite_code=chat.invite_code,
        created_at=chat.created_at
    )