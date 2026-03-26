from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from datetime import datetime

from database import get_db
from models.user import User
from models.sticker import StickerPack, Sticker, UserStickerPack
from middleware.auth_middleware import get_current_user
from services.file_storage import file_storage

router = APIRouter(prefix="/stickers", tags=["stickers"])


# ==================== Схемы ====================

class StickerResponse(BaseModel):
    id: str
    emoji: str
    file_url: str
    order: int


class StickerPackResponse(BaseModel):
    id: str
    name: str
    description: str
    cover_url: str | None
    creator_id: str | None
    is_default: bool
    is_public: bool
    is_installed: bool = False
    sticker_count: int = 0
    stickers: list[StickerResponse] = []


class CreatePackRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class UpdatePackRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddStickerRequest(BaseModel):
    emoji: str = "😀"


# ==================== Паки ====================

@router.get("/packs", response_model=list[StickerPackResponse])
async def get_my_packs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить установленные паки пользователя"""
    # Получаем ID установленных паков
    installed = await db.execute(
        select(UserStickerPack.pack_id).where(
            UserStickerPack.user_id == str(current_user.id)
        ).order_by(UserStickerPack.order)
    )
    installed_ids = [str(row[0]) for row in installed.all()]

    # Добавляем дефолтные паки
    defaults = await db.execute(
        select(StickerPack).where(StickerPack.is_default == True)
    )
    default_packs = defaults.scalars().all()

    all_pack_ids = list(set(installed_ids + [str(p.id) for p in default_packs]))

    result = []
    for pack_id in all_pack_ids:
        pack_result = await db.execute(
            select(StickerPack).where(StickerPack.id == pack_id)
        )
        pack = pack_result.scalar_one_or_none()
        if not pack:
            continue

        stickers_result = await db.execute(
            select(Sticker).where(Sticker.pack_id == pack_id).order_by(Sticker.order)
        )
        stickers = stickers_result.scalars().all()

        result.append(StickerPackResponse(
            id=str(pack.id),
            name=pack.name,
            description=pack.description or "",
            cover_url=pack.cover_url or (stickers[0].file_url if stickers else None),
            creator_id=pack.creator_id,
            is_default=pack.is_default,
            is_public=pack.is_public,
            is_installed=pack_id in installed_ids or pack.is_default,
            sticker_count=len(stickers),
            stickers=[
                StickerResponse(
                    id=str(s.id),
                    emoji=s.emoji,
                    file_url=s.file_url,
                    order=s.order
                ) for s in stickers
            ]
        ))

    return result


@router.get("/packs/browse", response_model=list[StickerPackResponse])
async def browse_packs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Каталог публичных паков"""
    packs_result = await db.execute(
        select(StickerPack).where(StickerPack.is_public == True)
    )
    packs = packs_result.scalars().all()

    # Установленные паки пользователя
    installed = await db.execute(
        select(UserStickerPack.pack_id).where(
            UserStickerPack.user_id == str(current_user.id)
        )
    )
    installed_ids = [str(row[0]) for row in installed.all()]

    result = []
    for pack in packs:
        stickers_result = await db.execute(
            select(Sticker).where(Sticker.pack_id == str(pack.id)).order_by(Sticker.order)
        )
        stickers = stickers_result.scalars().all()

        result.append(StickerPackResponse(
            id=str(pack.id),
            name=pack.name,
            description=pack.description or "",
            cover_url=pack.cover_url or (stickers[0].file_url if stickers else None),
            creator_id=pack.creator_id,
            is_default=pack.is_default,
            is_public=pack.is_public,
            is_installed=str(pack.id) in installed_ids or pack.is_default,
            sticker_count=len(stickers),
            stickers=[
                StickerResponse(
                    id=str(s.id), emoji=s.emoji,
                    file_url=s.file_url, order=s.order
                ) for s in stickers[:5]  # Превью — первые 5
            ]
        ))

    return result


@router.post("/packs", response_model=StickerPackResponse)
async def create_pack(
    req: CreatePackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать свой стикерпак"""
    pack = StickerPack(
        name=req.name,
        description=req.description,
        creator_id=str(current_user.id),
        is_default=False,
        is_public=True
    )
    db.add(pack)
    await db.flush()

    # Автоматически устанавливаем создателю
    db.add(UserStickerPack(
        user_id=str(current_user.id),
        pack_id=str(pack.id)
    ))

    return StickerPackResponse(
        id=str(pack.id),
        name=pack.name,
        description=pack.description or "",
        cover_url=None,
        creator_id=str(current_user.id),
        is_default=False,
        is_public=True,
        is_installed=True,
        sticker_count=0,
        stickers=[]
    )


@router.put("/packs/{pack_id}", response_model=StickerPackResponse)
async def update_pack(
    pack_id: str,
    req: UpdatePackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Редактировать свой пак"""
    result = await db.execute(select(StickerPack).where(StickerPack.id == pack_id))
    pack = result.scalar_one_or_none()

    if not pack:
        raise HTTPException(404, "Пак не найден")
    if pack.creator_id != str(current_user.id):
        raise HTTPException(403, "Можно редактировать только свои паки")

    if req.name is not None:
        pack.name = req.name
    if req.description is not None:
        pack.description = req.description

    stickers_result = await db.execute(
        select(Sticker).where(Sticker.pack_id == pack_id).order_by(Sticker.order)
    )
    stickers = stickers_result.scalars().all()

    return StickerPackResponse(
        id=str(pack.id),
        name=pack.name,
        description=pack.description or "",
        cover_url=pack.cover_url,
        creator_id=pack.creator_id,
        is_default=pack.is_default,
        is_public=pack.is_public,
        is_installed=True,
        sticker_count=len(stickers),
        stickers=[
            StickerResponse(id=str(s.id), emoji=s.emoji, file_url=s.file_url, order=s.order)
            for s in stickers
        ]
    )


@router.delete("/packs/{pack_id}")
async def delete_pack(
    pack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить свой пак"""
    result = await db.execute(select(StickerPack).where(StickerPack.id == pack_id))
    pack = result.scalar_one_or_none()

    if not pack:
        raise HTTPException(404, "Пак не найден")
    if pack.creator_id != str(current_user.id):
        raise HTTPException(403, "Можно удалять только свои паки")
    if pack.is_default:
        raise HTTPException(400, "Нельзя удалить встроенный пак")

    await db.delete(pack)
    return {"status": "deleted"}


# ==================== Установка / удаление паков ====================

@router.post("/packs/{pack_id}/install")
async def install_pack(
    pack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Установить пак"""
    pack_result = await db.execute(select(StickerPack).where(StickerPack.id == pack_id))
    if not pack_result.scalar_one_or_none():
        raise HTTPException(404, "Пак не найден")

    existing = await db.execute(
        select(UserStickerPack).where(
            UserStickerPack.user_id == str(current_user.id),
            UserStickerPack.pack_id == pack_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Пак уже установлен")

    db.add(UserStickerPack(
        user_id=str(current_user.id),
        pack_id=pack_id
    ))

    return {"status": "installed"}


@router.delete("/packs/{pack_id}/install")
async def uninstall_pack(
    pack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить пак из своего списка"""
    result = await db.execute(
        select(UserStickerPack).where(
            UserStickerPack.user_id == str(current_user.id),
            UserStickerPack.pack_id == pack_id
        )
    )
    usp = result.scalar_one_or_none()
    if not usp:
        raise HTTPException(404, "Пак не установлен")

    await db.delete(usp)
    return {"status": "uninstalled"}


# ==================== Стикеры ====================

@router.post("/packs/{pack_id}/stickers")
async def add_sticker(
    pack_id: str,
    emoji: str = Query("😀"),
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Добавить стикер в свой пак"""
    pack_result = await db.execute(select(StickerPack).where(StickerPack.id == pack_id))
    pack = pack_result.scalar_one_or_none()

    if not pack:
        raise HTTPException(404, "Пак не найден")
    if pack.creator_id != str(current_user.id):
        raise HTTPException(403, "Можно добавлять стикеры только в свои паки")

    # Загружаем файл
    contents = await file.read()
    if len(contents) > 1 * 1024 * 1024:  # 1MB лимит для стикеров
        raise HTTPException(413, "Стикер слишком большой. Максимум 1MB")

    result = await file_storage.upload_file(
        file_data=contents,
        original_filename=file.filename or "sticker.png",
        content_type=file.content_type or "image/png"
    )

    # Считаем порядок
    count_result = await db.execute(
        select(func.count(Sticker.id)).where(Sticker.pack_id == pack_id)
    )
    order = count_result.scalar() or 0

    sticker = Sticker(
        pack_id=pack_id,
        emoji=emoji,
        file_url=result["url"],
        file_name=file.filename,
        order=order
    )
    db.add(sticker)
    await db.flush()

    # Обновляем обложку если первый стикер
    if not pack.cover_url:
        pack.cover_url = result["url"]

    return {
        "id": str(sticker.id),
        "emoji": sticker.emoji,
        "file_url": sticker.file_url,
        "order": sticker.order
    }


@router.delete("/stickers/{sticker_id}")
async def delete_sticker(
    sticker_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить стикер"""
    result = await db.execute(select(Sticker).where(Sticker.id == sticker_id))
    sticker = result.scalar_one_or_none()

    if not sticker:
        raise HTTPException(404, "Стикер не найден")

    pack_result = await db.execute(select(StickerPack).where(StickerPack.id == sticker.pack_id))
    pack = pack_result.scalar_one_or_none()

    if pack and pack.creator_id != str(current_user.id):
        raise HTTPException(403, "Можно удалять стикеры только из своих паков")

    await db.delete(sticker)
    return {"status": "deleted"}