from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    bio = Column(String(500), default="")
    public_key = Column(Text, nullable=True)

    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    chat_members = relationship("ChatMember", back_populates="user")
