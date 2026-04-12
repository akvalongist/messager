import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from logging_config import configure_logging
from database import init_db
from config import get_settings
from routes import auth, messages, notifications, stickers
from routes import chats_stable as chats
from routes import files_secure as files
from routes import ws_stable as ws

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Messenger started")
    print("🚀 Мессенджер запущен!")
    print("📄 API: http://localhost:8000/docs")
    print("💬 Чат: http://localhost:8000")
    yield
    logger.info("Messenger stopped")
    print("👋 Мессенджер остановлен")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== ВАЖНО: Порядок имеет значение! =====

# 1. WebSocket — ПЕРВЫМ
app.include_router(ws.router)

# 2. REST API — ВТОРЫМ
app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(stickers.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


# 3. Главная страница — ПЕРЕД mount
@app.get("/")
async def root():
    return FileResponse(settings.static_dir / "index.html")


# 4. Статика — ПОСЛЕДНИМ (mount перехватывает всё!)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.app_env == "development")
