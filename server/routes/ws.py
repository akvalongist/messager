from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import json
import uuid

from database import async_session
from models.user import User
from models.message import Message, MessageType
from models.chat import ChatMember
from middleware.auth_middleware import decode_token

router = APIRouter()


class ConnectionManager:
    """Менеджер WebSocket соединений"""

    def __init__(self):
        # user_id -> list of WebSocket connections (мультидевайс)
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            dead = []
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[user_id].remove(ws)

    async def send_to_chat(self, chat_member_ids: list[str], message: dict, exclude_user: str = None):
        for uid in chat_member_ids:
            if uid != exclude_user:
                await self.send_to_user(uid, message)

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections


manager = ConnectionManager()


async def get_chat_member_ids(chat_id: str) -> list[str]:
    async with async_session() as db:
        result = await db.execute(
            select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
        )
        return [str(row[0]) for row in result.all()]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Аутентификация через первое сообщение
    await websocket.accept()

    try:
        # Ждём токен
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return

        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

    except Exception:
        await websocket.close(code=4001, reason="Auth failed")
        return

    # Переподключаемся через менеджер
    manager.active_connections.setdefault(user_id, []).append(websocket)

    # Обновляем статус
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.is_online = True
            await db.commit()

    try:
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        while True:
            data = await websocket.receive_json()
            await handle_ws_message(user_id, data)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS Error: {e}")
    finally:
        manager.disconnect(websocket, user_id)
        # Обновляем статус оффлайн
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and not manager.is_online(user_id):
                user.is_online = False
                user.last_seen = datetime.utcnow()
                await db.commit()


async def handle_ws_message(sender_id: str, data: dict):
    msg_type = data.get("type")

    if msg_type == "message":
        await handle_new_message(sender_id, data)
    elif msg_type == "typing":
        await handle_typing(sender_id, data)
    elif msg_type == "read":
        await handle_read_receipt(sender_id, data)
    elif msg_type == "edit":
        await handle_edit_message(sender_id, data)


async def handle_new_message(sender_id: str, data: dict):
    chat_id = data.get("chat_id")
    content = data.get("content")
    encrypted_content = data.get("encrypted_content")
    message_type = data.get("message_type", "text")
    reply_to_id = data.get("reply_to_id")
    file_url = data.get("file_url")
    file_name = data.get("file_name")
    file_size = data.get("file_size")
    mime_type = data.get("mime_type")

    async with async_session() as db:
        # Проверяем доступ
        membership = await db.execute(
            select(ChatMember).where(
                and_(ChatMember.chat_id == chat_id, ChatMember.user_id == sender_id)
            )
        )
        if not membership.scalar_one_or_none():
            return

        # Получаем имя отправителя
        user_result = await db.execute(select(User).where(User.id == sender_id))
        sender = user_result.scalar_one()

        # Сохраняем сообщение
        message = Message(
            chat_id=uuid.UUID(chat_id),
            sender_id=uuid.UUID(sender_id),
            message_type=MessageType(message_type),
            content=content,
            encrypted_content=encrypted_content,
            reply_to_id=uuid.UUID(reply_to_id) if reply_to_id else None,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

    # Рассылаем всем участникам чата
    member_ids = await get_chat_member_ids(chat_id)

    await manager.send_to_chat(member_ids, {
        "type": "new_message",
        "message": {
            "id": str(message.id),
            "chat_id": chat_id,
            "sender_id": sender_id,
            "sender_name": sender.display_name,
            "message_type": message_type,
            "content": content,
            "encrypted_content": encrypted_content,
            "file_url": file_url,
            "file_name": file_name,
            "file_size": file_size,
            "reply_to_id": reply_to_id,
            "created_at": message.created_at.isoformat()
        }
    })


async def handle_typing(sender_id: str, data: dict):
    chat_id = data.get("chat_id")
    member_ids = await get_chat_member_ids(chat_id)

    await manager.send_to_chat(member_ids, {
        "type": "typing",
        "chat_id": chat_id,
        "user_id": sender_id
    }, exclude_user=sender_id)


async def handle_read_receipt(sender_id: str, data: dict):
    chat_id = data.get("chat_id")
    message_id = data.get("message_id")

    member_ids = await get_chat_member_ids(chat_id)

    await manager.send_to_chat(member_ids, {
        "type": "read",
        "chat_id": chat_id,
        "message_id": message_id,
        "user_id": sender_id,
        "timestamp": datetime.utcnow().isoformat()
    }, exclude_user=sender_id)


async def handle_edit_message(sender_id: str, data: dict):
    message_id = data.get("message_id")
    new_content = data.get("content")

    async with async_session() as db:
        result = await db.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()
        if not message or str(message.sender_id) != sender_id:
            return

        message.content = new_content
        message.is_edited = True
        message.edited_at = datetime.utcnow()
        await db.commit()

    member_ids = await get_chat_member_ids(str(message.chat_id))
    await manager.send_to_chat(member_ids, {
        "type": "message_edited",
        "message_id": message_id,
        "content": new_content,
        "edited_at": datetime.utcnow().isoformat()
    })
