from __future__ import annotations

from fastapi import HTTPException

from app_config import get_settings


settings = get_settings()


def validate_upload_size(size_bytes: int, limit_mb: int, detail: str) -> None:
    if size_bytes > limit_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=detail)


def validate_mime_type(content_type: str | None, allowed_types: list[str], detail: str) -> str:
    mime_type = (content_type or "").lower()
    if mime_type not in allowed_types:
        raise HTTPException(status_code=400, detail=detail)
    return mime_type
