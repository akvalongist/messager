from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "messenger.db"
DEFAULT_UPLOAD_DIR = BASE_DIR / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "XAM Messenger"
    app_env: str = "development"
    log_level: str = "INFO"
    static_dir: Path = BASE_DIR / "static"
    upload_dir: Path = DEFAULT_UPLOAD_DIR

    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH.as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    use_minio: bool = False
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "messenger-files"
    minio_secure: bool = False

    max_file_size_mb: int = 50
    max_avatar_size_mb: int = 5
    max_sticker_size_mb: int = 1
    max_message_length: int = 4096
    max_group_members: int = 200
    allowed_upload_mime_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "video/mp4",
        "video/webm",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "application/pdf",
        "text/plain",
        "application/zip",
        "application/x-zip-compressed",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    allowed_avatar_mime_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    ]
    allowed_sticker_mime_types: list[str] = [
        "image/png",
        "image/webp",
        "image/gif",
    ]

    @field_validator("upload_dir", "static_dir", mode="before")
    @classmethod
    def resolve_path(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
