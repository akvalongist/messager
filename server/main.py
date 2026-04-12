import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database import init_db
from logging_config import configure_logging
from routes import messages, notifications
from routes import auth_stable as auth
from routes import chats_stable as chats
from routes import files_secure as files
from routes import stickers_stable as stickers
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
    print("Messenger started")
    print("API: http://localhost:8000/docs")
    print("Chat: http://localhost:8000")
    yield
    logger.info("Messenger stopped")
    print("Messenger stopped")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws.router)
app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(stickers.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/")
async def root():
    return FileResponse(settings.static_dir / "index.html")


app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.app_env == "development")
