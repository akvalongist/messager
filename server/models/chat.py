from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime, timezone
import uuid
import enum

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatType(str, enum.Enum):
    DIRECT = "direct"
    GROUP = "group"
    CHANNEL = "channel"


class MemberRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_type = Column(String(20), nullable=False, default=ChatType.DIRECT.value)
    name = Column(String(100), nullable=True)
    description = Column(String(500), default="")
    avatar_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    invite_code = Column(String(32), unique=True, nullable=True)

    members = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), default=MemberRole.MEMBER.value)
    joined_at = Column(DateTime, default=utc_now)
    is_muted = Column(Boolean, default=False)
    last_read_at = Column(DateTime, default=utc_now)

    chat = relationship("Chat", back_populates="members")
    user = relationship("User", back_populates="chat_members")
