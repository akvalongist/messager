from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query
from datetime import datetime

from config import get_settings
from models.user import User
from middleware.auth_middleware import get_current_user
from services.file_storage import file_storage

router = APIRouter(prefix="/files", tags=["files"])
settings = get_settings()


@router.post("/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    chat_id: str = Query(None),
    current_user: User = Depends(get_current_user)
):
    try:
        contents = await file.read()

        if len(contents) > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(
                413,
                f"Файл слишком большой. Максимум: {settings.max_file_size_mb} МБ"
            )

        result = await file_storage.upload_file(
            file_data=contents,
            original_filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream"
        )

        print(f"📁 Файл загружен: {file.filename} -> {result['url']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка загрузки файла: {e}")
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")