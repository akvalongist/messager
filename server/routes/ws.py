from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import json
import uuid
import traceback

from database import async_session
from models.user import User
from models.message import Message, MessageType
from models.chat import ChatMember
from middleware.auth_middleware import decode_token

router = APIRouter()  # ← УБРАЛ prefix="/ws"


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"🟢 Пользователь {user_id} подключился")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"🔴 Пользователь {user_id} отключился")

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            dead_connections = []
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    print(f"❌ Ошибка отправки пользователю {user_id}: {e}")
                    dead_connections.append(ws)
            
            for ws in dead_connections:
                if user_id in self.active_connections:
                    if ws in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(ws)

    async def send_to_chat(self, chat_member_ids: list[str], message: dict, exclude_user: str = None):
        for uid in chat_member_ids:
            if uid != exclude_user:
                await self.send_to_user(uid, message)


manager = ConnectionManager()


async def get_chat_member_ids(chat_id: str) -> list[str]:
    async with async_session() as db:
        result = await db.execute(
            select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
        )
        return [str(row[0]) for row in result.all()]


@router.websocket("/ws")  # ← ТЕПЕРЬ МАРШРУТ /ws
async def websocket_endpoint(websocket: WebSocket):
    user_id = None
    try:
        await websocket.accept()

        # Получаем токен
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

        # Подключаем пользователя
        await manager.connect(websocket, user_id)

        # Отправляем подтверждение
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Обновляем статус онлайн
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = True
                await db.commit()

        # Основной цикл
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                await handle_new_message(user_id, data)
            elif msg_type == "typing":
                await handle_typing(user_id, data)
            elif msg_type == "read":
                await handle_read_receipt(user_id, data)
            elif msg_type == "edit":
                await handle_edit_message(user_id, data)

    except WebSocketDisconnect:
        print(f"🔌 Пользователь {user_id} разорвал соединение")
    except Exception as e:
        print(f"🔥 КРИТИЧЕСКАЯ ОШИБКА WS: {e}")
        print(traceback.format_exc())
    finally:
        if user_id:
            manager.disconnect(websocket, user_id)
            async with async_session() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.is_online = False
                    user.last_seen = datetime.utcnow()
                    await db.commit()


async def handle_new_message(sender_id: str, data: dict):
    try:
        chat_id = data.get("chat_id")
        content = data.get("content", "")
        encrypted_content = data.get("encrypted_content")
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")
        file_url = data.get("file_url")
        file_name = data.get("file_name")
        file_size = data.get("file_size")
        mime_type = data.get("mime_type")

        async with async_session() as db:
            membership = await db.execute(
                select(ChatMember).where(
                    and_(
                        ChatMember.chat_id == chat_id,
                        ChatMember.user_id == sender_id
                    )
                )
            )
            if not membership.scalar_one_or_none():
                print(f"❌ Пользователь {sender_id} не имеет доступа к чату {chat_id}")
                return

            user_result = await db.execute(select(User).where(User.id == sender_id))
            sender = user_result.scalar_one()

            message = Message(
                chat_id=chat_id,
                sender_id=sender_id,
                message_type=message_type,
                content=content,
                encrypted_content=encrypted_content,
                reply_to_id=reply_to_id,
                file_url=file_url,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)

            print(f"📨 Сообщение сохранено: ID={message.id}")

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
        }, exclude_user=sender_id)

    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")
        print(traceback.format_exc())


async def handle_typing(sender_id: str, data: dict):
    try:
        chat_id = data.get("chat_id")
        member_ids = await get_chat_member_ids(chat_id)
        await manager.send_to_chat(member_ids, {
            "type": "typing",
            "chat_id": chat_id,
            "user_id": sender_id
        }, exclude_user=sender_id)
    except Exception as e:
        print(f"❌ Ошибка индикатора набора: {e}")


async def handle_read_receipt(sender_id: str, data: dict):
    try:
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
    except Exception as e:
        print(f"❌ Ошибка прочитанного: {e}")


async def handle_edit_message(sender_id: str, data: dict):
    try:
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
    except Exception as e:
        print(f"❌ Ошибка редактирования: {e}")