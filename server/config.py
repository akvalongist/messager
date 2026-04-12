from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # SQLite для разработки (PostgreSQL для продакшена)
    database_url: str = "sqlite+aiosqlite:///./messenger.db"

    # Redis (опционально для разработки)
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False  # Выключаем пока

    # JWT
    jwt_secret: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 720

    # File storage — локальное хранилище для разработки
    use_minio: bool = False
    upload_dir: str = "./uploads"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "messenger-files"
    minio_secure: bool = False

    # Limits
    max_file_size_mb: int = 50
    max_message_length: int = 4096
    max_group_members: int = 200

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


from app_config import BASE_DIR, Settings, get_settings  # noqa: E402,F401
