from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import get_current_user
from models.chat import Chat, ChatMember, ChatType, MemberRole
from models.user import User
from services.chat_service import chat_service


router = APIRouter(prefix="/chats", tags=["chats"])


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


@router.post("/direct", response_model=ChatResponse)
async def create_direct_chat(
    req: CreateDirectChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat, other_user = await chat_service.find_or_create_direct_chat(db, current_user, req.user_id)
    return ChatResponse(
        id=str(chat.id),
        chat_type=ChatType.DIRECT.value,
        name=other_user.display_name,
        description="",
        avatar_url=other_user.avatar_url,
        members_count=2,
        created_at=chat.created_at,
    )


@router.post("/group", response_model=ChatResponse)
async def create_group(
    req: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat, members_count = await chat_service.create_group(
        db, current_user, req.name, req.description, req.member_ids
    )
    return ChatResponse(
        id=str(chat.id),
        chat_type=ChatType.GROUP.value,
        name=chat.name,
        description=chat.description or "",
        avatar_url=None,
        members_count=members_count,
        invite_code=chat.invite_code,
        created_at=chat.created_at,
    )


@router.get("/", response_model=ChatListResponse)
async def get_my_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memberships = await db.execute(
        select(ChatMember.chat_id).where(ChatMember.user_id == str(current_user.id))
    )
    chat_ids = [str(row[0]) for row in memberships.all()]
    if not chat_ids:
        return ChatListResponse(chats=[])

    chat_list: list[ChatResponse] = []
    for chat_id in chat_ids:
        chat = await chat_service.get_chat(db, chat_id)
        members_result = await db.execute(select(ChatMember).where(ChatMember.chat_id == chat_id))
        members = members_result.scalars().all()
        name = chat.name
        avatar = chat.avatar_url

        if chat.chat_type == ChatType.DIRECT.value:
            other_member = next((m for m in members if str(m.user_id) != str(current_user.id)), None)
            if other_member:
                other_user = await chat_service.get_user(db, str(other_member.user_id))
                name = other_user.display_name
                avatar = other_user.avatar_url

        chat_list.append(
            ChatResponse(
                id=str(chat.id),
                chat_type=chat.chat_type,
                name=name,
                description=chat.description or "",
                avatar_url=avatar,
                members_count=len(members),
                invite_code=chat.invite_code,
                created_at=chat.created_at,
            )
        )

    return ChatListResponse(chats=chat_list)


@router.get("/{chat_id}/info", response_model=ChatInfoResponse)
async def get_chat_info(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await chat_service.ensure_membership(db, chat_id, str(current_user.id))
    chat = await chat_service.get_chat(db, chat_id)

    members_result = await db.execute(select(ChatMember).where(ChatMember.chat_id == chat_id))
    members = members_result.scalars().all()
    member_list: list[MemberResponse] = []
    for member in members:
        user = await chat_service.get_user(db, str(member.user_id))
        member_list.append(
            MemberResponse(
                user_id=str(user.id),
                username=user.username,
                display_name=user.display_name,
                role=member.role,
                is_online=user.is_online,
                joined_at=member.joined_at,
            )
        )

    return ChatInfoResponse(
        id=str(chat.id),
        chat_type=chat.chat_type,
        name=chat.name,
        description=chat.description or "",
        invite_code=chat.invite_code,
        members=member_list,
        created_at=chat.created_at,
    )


@router.post("/{chat_id}/members", response_model=dict)
async def add_member(
    chat_id: str,
    req: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await chat_service.get_chat(db, chat_id)
    if chat.chat_type != ChatType.GROUP.value:
        raise HTTPException(status_code=400, detail="Can add members only to group chats")

    await chat_service.ensure_membership(db, chat_id, str(current_user.id))
    new_user = await chat_service.get_user(db, req.user_id)

    existing = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == req.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already in the group")

    db.add(ChatMember(chat_id=chat_id, user_id=req.user_id, role=MemberRole.MEMBER.value))
    return {"status": "added", "user_id": req.user_id, "display_name": new_user.display_name}


@router.delete("/{chat_id}/members/{user_id}")
async def remove_member(
    chat_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    my_member = await chat_service.ensure_membership(db, chat_id, str(current_user.id))
    if my_member.role not in [MemberRole.OWNER.value, MemberRole.ADMIN.value]:
        raise HTTPException(status_code=403, detail="Only owner or admin can remove members")

    target_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.role == MemberRole.OWNER.value:
        raise HTTPException(status_code=400, detail="Cannot remove the owner")

    await db.delete(target)
    return {"status": "removed", "user_id": user_id}


@router.post("/{chat_id}/leave")
async def leave_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await chat_service.ensure_membership(db, chat_id, str(current_user.id))
    if membership.role == MemberRole.OWNER.value:
        raise HTTPException(status_code=400, detail="Owner cannot leave the group")
    await db.delete(membership)
    return {"status": "left", "chat_id": chat_id}


@router.post("/join/{invite_code}", response_model=ChatResponse)
async def join_by_invite(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chat).where(Chat.invite_code == invite_code))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")

    existing = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == str(chat.id),
            ChatMember.user_id == str(current_user.id),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already in the group")

    db.add(ChatMember(chat_id=str(chat.id), user_id=str(current_user.id), role=MemberRole.MEMBER.value))
    members_result = await db.execute(select(ChatMember).where(ChatMember.chat_id == str(chat.id)))
    members_count = len(members_result.scalars().all()) + 1
    return ChatResponse(
        id=str(chat.id),
        chat_type=chat.chat_type,
        name=chat.name,
        description=chat.description or "",
        avatar_url=chat.avatar_url,
        members_count=members_count,
        invite_code=chat.invite_code,
        created_at=chat.created_at,
    )
