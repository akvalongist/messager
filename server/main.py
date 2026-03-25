from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from database import init_db
from config import get_settings
from routes import auth, chats, messages, files, ws

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs("static", exist_ok=True)
    print("🚀 Мессенджер запущен!")
    print("📄 API документация: http://localhost:8000/docs")
    print("💬 Чат: http://localhost:8000")
    yield
    print("👋 Мессенджер остановлен")


app = FastAPI(
    title="Secure Messenger API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Загруженные файлы
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# REST маршруты
app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(files.router, prefix="/api")

# WebSocket
app.include_router(ws.router)

# Статика (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Главная страница
@app.get("/")
async def root():
    return FileResponse("static/index.html")
