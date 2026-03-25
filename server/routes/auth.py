from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field
import bcrypt

from database import get_db
from models.user import User
from middleware.auth_middleware import create_access_token, get_current_user
from services.crypto import crypto_service

router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    """Хэширование пароля"""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверка пароля"""
    try:
        pwd_bytes = password.encode("utf-8")[:72]
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


# ==================== Схемы ====================

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    username: str
    display_name: str
    public_key: str | None = None


class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str
    bio: str
    avatar_url: str | None
    public_key: str | None


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    bio: str | None = None


# ==================== Эндпоинты ====================

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Проверяем существование пользователя
    query = select(User).where(User.username == req.username)
    if req.email:
        query = select(User).where(
            or_(User.username == req.username, User.email == req.email)
        )

    existing = await db.execute(query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким именем уже существует"
        )

    # Генерируем ключи E2EE
    private_key, public_key = crypto_service.generate_keypair()

    # Создаём пользователя
    user = User(
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        email=req.email,
        public_key=public_key
    )
    db.add(user)
    await db.flush()

    # Генерируем токен
    token = create_access_token(str(user.id))

    return AuthResponse(
        token=token,
        user_id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        public_key=public_key
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Ищем пользователя
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user = result.scalar_one_or_none()

    # Проверяем пароль
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль"
        )

    # Генерируем токен
    token = create_access_token(str(user.id))

    return AuthResponse(
        token=token,
        user_id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        public_key=user.public_key
    )


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        user_id=str(current_user.id),
        username=current_user.username,
        display_name=current_user.display_name,
        bio=current_user.bio or "",
        avatar_url=current_user.avatar_url,
        public_key=current_user.public_key
    )


@router.put("/me", response_model=UserProfile)
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if req.display_name is not None:
        current_user.display_name = req.display_name
    if req.bio is not None:
        current_user.bio = req.bio

    await db.flush()

    return UserProfile(
        user_id=str(current_user.id),
        username=current_user.username,
        display_name=current_user.display_name,
        bio=current_user.bio or "",
        avatar_url=current_user.avatar_url,
        public_key=current_user.public_key
    )


@router.get("/user/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return UserProfile(
        user_id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        bio=user.bio or "",
        avatar_url=user.avatar_url,
        public_key=user.public_key
    )


@router.get("/search/{username}")
async def search_users(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(
            User.username.ilike(f"%{username}%")
        ).limit(20)
    )
    users = result.scalars().all()

    return {
        "users": [
            {
                "user_id": str(u.id),
                "username": u.username,
                "display_name": u.display_name,
                "avatar_url": u.avatar_url,
                "is_online": u.is_online
            }
            for u in users
            if str(u.id) != str(current_user.id)
        ]
    }