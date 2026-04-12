from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, Integer, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VOICE = "voice"
    VIDEO = "video"
    SYSTEM = "system"


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_type = Column(String(20), default=MessageType.TEXT.value)

    content = Column(Text, nullable=True)
    encrypted_content = Column(Text, nullable=True)

    file_url = Column(Text, nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)

    reply_to_id = Column(String(36), ForeignKey("messages.id"), nullable=True)
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utc_now, index=True)
    edited_at = Column(DateTime, nullable=True)

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")
    reply_to = relationship("Message", remote_side=[id])
    read_receipts = relationship("ReadReceipt", back_populates="message", cascade="all, delete-orphan")


class ReadReceipt(Base):
    __tablename__ = "read_receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    read_at = Column(DateTime, default=utc_now)

    message = relationship("Message", back_populates="read_receipts")
