from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File as FastAPIFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from middleware.auth_middleware import get_current_user
from models.chat import ChatMember
from models.user import User
from services.file_storage import file_storage
from services.validation import validate_mime_type, validate_upload_size


router = APIRouter(prefix="/files", tags=["files"])
settings = get_settings()


@router.post("/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    chat_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if chat_id:
        membership = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == str(current_user.id),
            )
        )
        if not membership.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="No access to this chat")

    contents = await file.read()
    validate_upload_size(
        len(contents),
        settings.max_file_size_mb,
        f"File too large. Maximum: {settings.max_file_size_mb} MB",
    )
    mime_type = validate_mime_type(
        file.content_type,
        settings.allowed_upload_mime_types,
        "File type is not allowed",
    )

    return await file_storage.upload_file(
        file_data=contents,
        original_filename=file.filename or "unnamed",
        content_type=mime_type,
    )
