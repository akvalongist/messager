from sqlalchemy import (
    Column, String, DateTime, Integer, Text, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from database import Base


class FileType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    OTHER = "other"


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    uploader_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)

    file_type = Column(String(20), default=FileType.OTHER.value)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False, default="application/octet-stream")
    file_size = Column(Integer, nullable=False)
    file_url = Column(Text, nullable=False)

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    thumbnail_url = Column(Text, nullable=True)

    is_encrypted = Column(Boolean, default=False)
    file_hash = Column(String(128), nullable=True)

    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    uploader = relationship("User", foreign_keys=[uploader_id])

    @property
    def file_size_readable(self) -> str:
        size = self.file_size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ТБ"

    @staticmethod
    def detect_file_type(mime_type: str) -> str:
        if mime_type.startswith("image/"):
            return FileType.IMAGE.value
        elif mime_type.startswith("video/"):
            return FileType.VIDEO.value
        elif mime_type.startswith("audio/"):
            return FileType.AUDIO.value
        return FileType.OTHER.value
