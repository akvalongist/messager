from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime
import secrets

from database import get_db
from models.user import User
from models.chat import Chat, ChatMember, ChatType, MemberRole
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])


# ==================== Схемы ====================

class CreateDirectChatRequest(BaseModel):
    user_id: str


class CreateGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    member_ids: list[str] = []


class AddMemberRequest(BaseModel):
    user_id: str


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


class MemberResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    is_online: bool
    joined_at: datetime


class ChatInfoResponse(BaseModel):
    id: str
    chat_type: str
    name: str | None
    description: str
    invite_code: str | None
    members: list[MemberResponse]
    created_at: datetime


# ==================== Создание чатов ====================

@router.post("/direct", response_model=ChatResponse)
async def create_direct_chat(
    req: CreateDirectChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == req.user_id))
    other_user = result.scalar_one_or_none()
    if not other_user:
        raise HTTPException(404, "Пользователь не найден")

    if str(current_user.id) == str(req.user_id):
        raise HTTPException(400, "Нельзя создать чат с самим собой")

    # Проверяем существующий чат
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

    chat = Chat(chat_type=ChatType.DIRECT.value)
    db.add(chat)
    await db.flush()

    db.add(ChatMember(chat_id=str(chat.id), user_id=str(current_user.id), role=MemberRole.MEMBER.value))
    db.add(ChatMember(chat_id=str(chat.id), user_id=str(req.user_id), role=MemberRole.MEMBER.value))
    await db.flush()

    return ChatResponse(
        id=str(chat.id), chat_type=ChatType.DIRECT.value,
        name=other_user.display_name, description="",
        avatar_url=other_user.avatar_url, members_count=2,
        created_at=chat.created_at
    )


@router.post("/group", response_model=ChatResponse)
async def create_group(
    req: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    chat = Chat(
        chat_type=ChatType.GROUP.value,
        name=req.name,
        description=req.description,
        invite_code=secrets.token_urlsafe(16)
    )
    db.add(chat)
    await db.flush()

    db.add(ChatMember(chat_id=str(chat.id), user_id=str(current_user.id), role=MemberRole.OWNER.value))
    members_count = 1

    for member_id in req.member_ids:
        result = await db.execute(select(User).where(User.id == member_id))
        if result.scalar_one_or_none():
            db.add(ChatMember(chat_id=str(chat.id), user_id=str(member_id), role=MemberRole.MEMBER.value))
            members_count += 1

    await db.flush()

    return ChatResponse(
        id=str(chat.id), chat_type=ChatType.GROUP.value,
        name=chat.name, description=chat.description or "",
        avatar_url=None, members_count=members_count,
        invite_code=chat.invite_code, created_at=chat.created_at
    )


# ==================== Список чатов ====================

@router.get("/", response_model=ChatListResponse)
async def get_my_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    memberships = await db.execute(
        select(ChatMember.chat_id).where(ChatMember.user_id == str(current_user.id))
    )
    chat_ids = [str(row[0]) for row in memberships.all()]

    if not chat_ids:
        return ChatListResponse(chats=[])

    chat_list = []
    for chat_id in chat_ids:
        chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
        chat = chat_result.scalar_one_or_none()
        if not chat:
            continue

        members_result = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == chat_id)
        )
        members = members_result.scalars().all()

        name = chat.name
        avatar = chat.avatar_url

        if chat.chat_type == ChatType.DIRECT.value:
            other_member = next(
                (m for m in members if str(m.user_id) != str(current_user.id)), None
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
            id=str(chat.id), chat_type=chat.chat_type,
            name=name, description=chat.description or "",
            avatar_url=avatar, members_count=len(members),
            invite_code=chat.invite_code, created_at=chat.created_at
        ))

    return ChatListResponse(chats=chat_list)


# ==================== Информация о чате ====================

@router.get("/{chat_id}/info", response_model=ChatInfoResponse)
async def get_chat_info(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Проверяем что пользователь в чате
    membership = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == str(current_user.id)
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(403, "Вы не в этом чате")

    chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Чат не найден")

    # Получаем участников
    members_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id)
    )
    members = members_result.scalars().all()

    member_list = []
    for m in members:
        user_result = await db.execute(select(User).where(User.id == str(m.user_id)))
        user = user_result.scalar_one_or_none()
        if user:
            member_list.append(MemberResponse(
                user_id=str(user.id),
                username=user.username,
                display_name=user.display_name,
                role=m.role,
                is_online=user.is_online,
                joined_at=m.joined_at
            ))

    return ChatInfoResponse(
        id=str(chat.id),
        chat_type=chat.chat_type,
        name=chat.name,
        description=chat.description or "",
        invite_code=chat.invite_code,
        members=member_list,
        created_at=chat.created_at
    )


# ==================== Добавление участников ====================

@router.post("/{chat_id}/members", response_model=dict)
async def add_member(
    chat_id: str,
    req: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Проверяем что чат существует и это группа
    chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Чат не найден")
    if chat.chat_type != ChatType.GROUP.value:
        raise HTTPException(400, "Можно добавлять только в группы")

    # Проверяем что добавляющий в чате
    my_membership = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == str(current_user.id)
        )
    )
    if not my_membership.scalar_one_or_none():
        raise HTTPException(403, "Вы не в этом чате")

    # Проверяем что добавляемый существует
    user_result = await db.execute(select(User).where(User.id == req.user_id))
    new_user = user_result.scalar_one_or_none()
    if not new_user:
        raise HTTPException(404, "Пользователь не найден")

    # Проверяем что ещё не в чате
    existing = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == req.user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Пользователь уже в группе")

    # Добавляем
    db.add(ChatMember(
        chat_id=chat_id,
        user_id=req.user_id,
        role=MemberRole.MEMBER.value
    ))

    return {
        "status": "added",
        "user_id": req.user_id,
        "display_name": new_user.display_name
    }


# ==================== Удаление участников ====================

@router.delete("/{chat_id}/members/{user_id}")
async def remove_member(
    chat_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Проверяем права (owner или admin)
    my_membership = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == str(current_user.id)
        )
    )
    my_member = my_membership.scalar_one_or_none()
    if not my_member:
        raise HTTPException(403, "Вы не в этом чате")

    if my_member.role not in [MemberRole.OWNER.value, MemberRole.ADMIN.value]:
        raise HTTPException(403, "Только владелец или админ может удалять участников")

    # Нельзя удалить владельца
    target_membership = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id
        )
    )
    target = target_membership.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "Участник не найден")

    if target.role == MemberRole.OWNER.value:
        raise HTTPException(400, "Нельзя удалить владельца группы")

    await db.delete(target)

    return {"status": "removed", "user_id": user_id}


# ==================== Выход из группы ====================

@router.post("/{chat_id}/leave")
async def leave_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    membership = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == str(current_user.id)
        )
    )
    member = membership.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Вы не в этом чате")

    if member.role == MemberRole.OWNER.value:
        raise HTTPException(400, "Владелец не может покинуть группу. Передайте права или удалите группу.")

    await db.delete(member)

    return {"status": "left", "chat_id": chat_id}


# ==================== Присоединение по инвайт-коду ====================

@router.post("/join/{invite_code}", response_model=ChatResponse)
async def join_by_invite(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Chat).where(Chat.invite_code == invite_code))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, "Группа не найдена")

    existing = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == str(chat.id),
            ChatMember.user_id == str(current_user.id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Вы уже в этой группе")

    db.add(ChatMember(
        chat_id=str(chat.id),
        user_id=str(current_user.id),
        role=MemberRole.MEMBER.value
    ))

    members_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == str(chat.id))
    )
    members_count = len(members_result.scalars().all()) + 1

    return ChatResponse(
        id=str(chat.id), chat_type=chat.chat_type,
        name=chat.name, description=chat.description or "",
        avatar_url=chat.avatar_url, members_count=members_count,
        invite_code=chat.invite_code, created_at=chat.created_at
    )