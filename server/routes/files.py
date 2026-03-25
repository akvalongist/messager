from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from datetime import datetime
import hashlib

from config import get_settings
from database import get_db
from models.user import User
from models.file import File, FileType
from models.chat import ChatMember
from middleware.auth_middleware import get_current_user
from services.file_storage import file_storage

router = APIRouter(prefix="/files", tags=["files"])
settings = get_settings()


class FileResponse(BaseModel):
    id: str
    file_type: str
    original_name: str
    mime_type: str
    file_size: int
    file_size_readable: str
    file_url: str
    thumbnail_url: str | None
    width: int | None
    height: int | None
    duration_seconds: int | None
    created_at: datetime


class FileListResponse(BaseModel):
    files: list[FileResponse]
    total: int


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    chat_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Читаем файл
    contents = await file.read()

    # Проверка размера
    if len(contents) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            413,
            f"Файл слишком большой. Максимум: {settings.max_file_size_mb} МБ"
        )

    # Если указан чат — проверяем доступ
    if chat_id:
        membership = await db.execute(
            select(ChatMember).where(
                and_(
                    ChatMember.chat_id == chat_id,
                    ChatMember.user_id == current_user.id
                )
            )
        )
        if not membership.scalar_one_or_none():
            raise HTTPException(403, "Нет доступа к чату")

    # Загружаем в MinIO
    storage_result = await file_storage.upload_file(
        file_data=contents,
        original_filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream"
    )

    # Вычисляем хэш
    file_hash = hashlib.sha256(contents).hexdigest()

    # Определяем тип
    mime = file.content_type or "application/octet-stream"
    file_type = File.detect_file_type(mime)

    # Получаем размеры для изображений
    width, height = None, None
    if file_type == FileType.IMAGE:
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(contents))
            width, height = img.size
        except Exception:
            pass

    # Сохраняем в БД
    db_file = File(
        uploader_id=current_user.id,
        chat_id=chat_id,
        file_type=file_type,
        original_name=file.filename or "unnamed",
        stored_name=storage_result["object_name"],
        mime_type=mime,
        file_size=len(contents),
        file_url=storage_result["url"],
        width=width,
        height=height,
        file_hash=file_hash
    )
    db.add(db_file)
    await db.flush()

    return FileResponse(
        id=str(db_file.id),
        file_type=db_file.file_type.value,
        original_name=db_file.original_name,
        mime_type=db_file.mime_type,
        file_size=db_file.file_size,
        file_size_readable=db_file.file_size_readable,
        file_url=db_file.file_url,
        thumbnail_url=db_file.thumbnail_url,
        width=db_file.width,
        height=db_file.height,
        duration_seconds=db_file.duration_seconds,
        created_at=db_file.created_at
    )


@router.get("/chat/{chat_id}", response_model=FileListResponse)
async def get_chat_files(
    chat_id: str,
    file_type: FileType | None = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить все файлы чата (медиа-галерея)"""

    # Проверяем доступ
    membership = await db.execute(
        select(ChatMember).where(
            and_(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == current_user.id
            )
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(403, "Нет доступа к чату")

    query = (
        select(File)
        .where(
            and_(
                File.chat_id == chat_id,
                File.is_deleted == False
            )
        )
        .order_by(File.created_at.desc())
    )

    if file_type:
        query = query.where(File.file_type == file_type)

    # Считаем общее количество
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(File.id)).where(
            and_(File.chat_id == chat_id, File.is_deleted == False)
        )
    )
    total = count_result.scalar()

    # Получаем файлы
    result = await db.execute(query.limit(limit).offset(offset))
    files = result.scalars().all()

    return FileListResponse(
        files=[
            FileResponse(
                id=str(f.id),
                file_type=f.file_type.value,
                original_name=f.original_name,
                mime_type=f.mime_type,
                file_size=f.file_size,
                file_size_readable=f.file_size_readable,
                file_url=f.file_url,
                thumbnail_url=f.thumbnail_url,
                width=f.width,
                height=f.height,
                duration_seconds=f.duration_seconds,
                created_at=f.created_at
            )
            for f in files
        ],
        total=total
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(File).where(File.id == file_id))
    db_file = result.scalar_one_or_none()

    if not db_file:
        raise HTTPException(404, "Файл не найден")

    if str(db_file.uploader_id) != str(current_user.id):
        raise HTTPException(403, "Можно удалять только свои файлы")

    # Soft delete
    db_file.is_deleted = True
    db_file.deleted_at = datetime.utcnow()

    # Удаляем из хранилища
    await file_storage.delete_file(db_file.stored_name)

    return {"status": "deleted", "file_id": file_id}
