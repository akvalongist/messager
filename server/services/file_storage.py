import os
import uuid
import aiofiles
from config import get_settings

settings = get_settings()


class FileStorageService:
    def __init__(self):
        self.upload_dir = settings.upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_file(
        self,
        file_data: bytes,
        original_filename: str,
        content_type: str
    ) -> dict:
        ext = os.path.splitext(original_filename)[1]
        object_name = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(self.upload_dir, object_name)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_data)

        url = f"/uploads/{object_name}"

        return {
            "url": url,
            "object_name": object_name,
            "file_size": len(file_data),
            "mime_type": content_type
        }

    async def delete_file(self, object_name: str):
        file_path = os.path.join(self.upload_dir, object_name)
        if os.path.exists(file_path):
            os.remove(file_path)

    async def get_file_path(self, object_name: str) -> str:
        return os.path.join(self.upload_dir, object_name)


file_storage = FileStorageService()
