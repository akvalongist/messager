from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models.user import User
from middleware.auth_middleware import get_current_user
from services.notifications import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    body: str
    chat_id: str | None
    message_id: str | None
    sender_id: str | None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int


class RegisterDeviceRequest(BaseModel):
    token: str
    platform: str  # "android", "ios", "web"
    device_name: str | None = None


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user)
):
    notifications = await notification_service.get_user_notifications(
        user_id=str(current_user.id),
        unread_only=unread_only,
        limit=limit,
        offset=offset
    )

    unread_count = await notification_service.get_unread_count(
        str(current_user.id)
    )

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                notification_type=n.notification_type.value,
                title=n.title,
                body=n.body,
                chat_id=str(n.chat_id) if n.chat_id else None,
                message_id=str(n.message_id) if n.message_id else None,
                sender_id=str(n.sender_id) if n.sender_id else None,
                is_read=n.is_read,
                created_at=n.created_at
            )
            for n in notifications
        ],
        unread_count=unread_count
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user)
):
    count = await notification_service.get_unread_count(str(current_user.id))
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user)
):
    success = await notification_service.mark_as_read(
        notification_id, str(current_user.id)
    )
    return {"success": success}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user)
):
    count = await notification_service.mark_all_as_read(str(current_user.id))
    return {"marked_count": count}


@router.post("/chat/{chat_id}/read")
async def mark_chat_as_read(
    chat_id: str,
    current_user: User = Depends(get_current_user)
):
    count = await notification_service.mark_chat_as_read(
        str(current_user.id), chat_id
    )
    return {"marked_count": count}


@router.post("/device/register")
async def register_device(
    req: RegisterDeviceRequest,
    current_user: User = Depends(get_current_user)
):
    device = await notification_service.register_device(
        user_id=str(current_user.id),
        token=req.token,
        platform=req.platform,
        device_name=req.device_name
    )
    return {
        "status": "registered",
        "device_id": str(device.id)
    }


@router.post("/device/unregister")
async def unregister_device(
    token: str,
    current_user: User = Depends(get_current_user)
):
    await notification_service.unregister_device(token)
    return {"status": "unregistered"}
