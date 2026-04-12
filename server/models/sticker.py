from sqlalchemy import (
    Column, String, DateTime, Integer, Text, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StickerPack(Base):
    __tablename__ = "sticker_packs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(500), default="")
    cover_url = Column(Text, nullable=True)  # Обложка пака
    creator_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_default = Column(Boolean, default=False)  # Встроенный пак
    is_public = Column(Boolean, default=True)  # Доступен всем

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    stickers = relationship("Sticker", back_populates="pack", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[creator_id])


class Sticker(Base):
    __tablename__ = "stickers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pack_id = Column(String(36), ForeignKey("sticker_packs.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(10), default="😀")  # Связанный эмодзи
    file_url = Column(Text, nullable=False)  # URL картинки
    file_name = Column(String(255), nullable=True)
    order = Column(Integer, default=0)  # Порядок в паке

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    pack = relationship("StickerPack", back_populates="stickers")


class UserStickerPack(Base):
    """Какие паки установлены у пользователя"""
    __tablename__ = "user_sticker_packs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pack_id = Column(String(36), ForeignKey("sticker_packs.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, default=0)  # Порядок в списке пользователя
    added_at = Column(DateTime, default=utc_now)
