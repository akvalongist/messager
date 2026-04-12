import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from database import async_session
from middleware.auth_middleware import decode_token
from models.user import User
from services.message_service import message_service


logger = logging.getLogger(__name__)
router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    def add(self, user_id: str, websocket: WebSocket) -> None:
        self.active_connections.setdefault(user_id, []).append(websocket)
        logger.info("User %s connected to websocket", user_id)

    def remove(self, user_id: str, websocket: WebSocket) -> None:
        if user_id in self.active_connections and websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)
        if user_id in self.active_connections and not self.active_connections[user_id]:
            del self.active_connections[user_id]
        logger.info("User %s disconnected from websocket", user_id)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        sockets = self.active_connections.get(user_id, [])
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(user_id, ws)

    async def send_to_chat(self, member_ids: list[str], message: dict, exclude: str | None = None) -> None:
        for user_id in member_ids:
            if user_id != exclude:
                await self.send_to_user(user_id, message)


manager = ConnectionManager()


async def get_chat_members(chat_id: str) -> list[str]:
    async with async_session() as db:
        from services.chat_service import chat_service

        return await chat_service.list_chat_member_ids(db, chat_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None

    try:
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        if not token:
            await websocket.close(code=4001, reason="No token")
            return

        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="No user_id")
            return

        manager.add(user_id, websocket)
        await websocket.send_json({"type": "connected", "user_id": user_id})

        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = True
                await db.commit()

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "message":
                await handle_message(user_id, data)
            elif msg_type == "typing":
                await handle_typing(user_id, data)
            elif msg_type == "read":
                await handle_read(user_id, data)
    except WebSocketDisconnect:
        logger.info("Websocket disconnected for %s", user_id)
    except Exception as exc:
        logger.exception("Websocket error: %s", exc)
        logger.debug(traceback.format_exc())
    finally:
        if user_id:
            manager.remove(user_id, websocket)
            async with async_session() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.is_online = False
                    user.last_seen = utc_now()
                    await db.commit()


async def handle_message(sender_id: str, data: dict) -> None:
    async with async_session() as db:
        message, sender, member_ids, chat = await message_service.create_message(db, sender_id, data)

    payload = {
        "type": "new_message",
        "message": await message_service.serialize_message(message, sender.display_name),
    }

    await manager.send_to_user(sender_id, payload)
    for user_id in member_ids:
        if user_id != sender_id:
            await manager.send_to_user(user_id, payload)

    await message_service.notify_recipients(
        member_ids=member_ids,
        sender_id=sender_id,
        sender_name=sender.display_name,
        chat=chat,
        message=message,
    )


async def handle_typing(sender_id: str, data: dict) -> None:
    chat_id = data.get("chat_id")
    if not chat_id:
        return
    member_ids = await get_chat_members(chat_id)
    await manager.send_to_chat(
        member_ids,
        {"type": "typing", "chat_id": chat_id, "user_id": sender_id},
        exclude=sender_id,
    )


async def handle_read(sender_id: str, data: dict) -> None:
    chat_id = data.get("chat_id")
    if not chat_id:
        return
    member_ids = await get_chat_members(chat_id)
    await manager.send_to_chat(
        member_ids,
        {
            "type": "read",
            "chat_id": chat_id,
            "message_id": data.get("message_id"),
            "user_id": sender_id,
        },
        exclude=sender_id,
    )
