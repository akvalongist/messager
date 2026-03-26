from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, and_
from datetime import datetime
import traceback

from database import async_session
from models.user import User
from models.message import Message
from models.chat import ChatMember
from middleware.auth_middleware import decode_token

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    def add(self, user_id: str, websocket: WebSocket):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"🟢 {user_id[:8]}... подключён ({len(self.active_connections)} онлайн)")

    def remove(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"🔴 {user_id[:8]}... отключён")

    async def send_to_user(self, user_id: str, message: dict):
        if user_id not in self.active_connections:
            return
        dead = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections[user_id].remove(ws)

    async def send_to_chat(self, member_ids: list[str], message: dict, exclude: str = None):
        for uid in member_ids:
            if uid != exclude:
                await self.send_to_user(uid, message)


manager = ConnectionManager()


async def get_chat_members(chat_id: str) -> list[str]:
    async with async_session() as db:
        result = await db.execute(
            select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
        )
        return [str(row[0]) for row in result.all()]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    user_id = None

    try:
        # 1. Ждём токен
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")

        if not token:
            await websocket.close(code=4001, reason="No token")
            return

        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
        except Exception:
            await websocket.close(code=4001, reason="Bad token")
            return

        if not user_id:
            await websocket.close(code=4001, reason="No user_id")
            return

        # 2. Регистрируем соединение
        manager.add(user_id, websocket)

        # 3. Подтверждаем
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id
        })

        # 4. Обновляем онлайн статус
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_online = True
                await db.commit()

        # 5. Слушаем сообщения
        while True:
            data = await websocket.receive_json()
            print(f"📩 Получено от {user_id[:8]}...: {data.get('type')}")

            msg_type = data.get("type")

            if msg_type == "message":
                await handle_message(user_id, data, websocket)
            elif msg_type == "typing":
                await handle_typing(user_id, data)
            elif msg_type == "read":
                await handle_read(user_id, data)

    except WebSocketDisconnect:
        print(f"🔌 {user_id[:8] if user_id else '???'}... отключился")
    except Exception as e:
        print(f"🔥 WS ошибка: {e}")
        print(traceback.format_exc())
    finally:
        if user_id:
            manager.remove(user_id, websocket)
            async with async_session() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.is_online = False
                    user.last_seen = datetime.utcnow()
                    await db.commit()


async def handle_message(sender_id: str, data: dict, websocket: WebSocket):
    try:
        chat_id = data.get("chat_id")
        content = data.get("content", "")
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")
        file_url = data.get("file_url")
        file_name = data.get("file_name")
        file_size = data.get("file_size")
        mime_type = data.get("mime_type")

        if not chat_id:
            print("❌ Нет chat_id")
            return

        async with async_session() as db:
            # Проверяем доступ
            mem = await db.execute(
                select(ChatMember).where(
                    ChatMember.chat_id == chat_id,
                    ChatMember.user_id == sender_id
                )
            )
            if not mem.scalar_one_or_none():
                print(f"❌ {sender_id[:8]}... не в чате {chat_id[:8]}...")
                return

            # Имя отправителя
            user_res = await db.execute(select(User).where(User.id == sender_id))
            sender = user_res.scalar_one()

            # Сохраняем
            message = Message(
                chat_id=chat_id,
                sender_id=sender_id,
                message_type=message_type,
                content=content if content else None,
                reply_to_id=reply_to_id,
                file_url=file_url,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)

            print(f"💾 Сообщение сохранено: {message.id}")

        # Формируем ответ
        msg_response = {
            "type": "new_message",
            "message": {
                "id": str(message.id),
                "chat_id": chat_id,
                "sender_id": sender_id,
                "sender_name": sender.display_name,
                "message_type": message_type,
                "content": content,
                "file_url": file_url,
                "file_name": file_name,
                "file_size": file_size,
                "reply_to_id": reply_to_id,
                "is_edited": False,
                "is_deleted": False,
                "created_at": message.created_at.isoformat()
            }
        }

        # Отправляем ВСЕМ в чате включая отправителя
               # Отправляем всем КРОМЕ отправителя
        member_ids = await get_chat_members(chat_id)

        # Отправителю — с его сообщением (для подтверждения)
        await manager.send_to_user(sender_id, msg_response)

        # Остальным участникам
        for uid in member_ids:
            if uid != sender_id:
                await manager.send_to_user(uid, msg_response)

    except Exception as e:
        print(f"❌ Ошибка сообщения: {e}")
        print(traceback.format_exc())


async def handle_typing(sender_id: str, data: dict):
    try:
        chat_id = data.get("chat_id")
        if not chat_id:
            return
        member_ids = await get_chat_members(chat_id)
        await manager.send_to_chat(member_ids, {
            "type": "typing",
            "chat_id": chat_id,
            "user_id": sender_id
        }, exclude=sender_id)
    except Exception as e:
        print(f"❌ Typing ошибка: {e}")


async def handle_read(sender_id: str, data: dict):
    try:
        chat_id = data.get("chat_id")
        message_id = data.get("message_id")
        if not chat_id:
            return
        member_ids = await get_chat_members(chat_id)
        await manager.send_to_chat(member_ids, {
            "type": "read",
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": sender_id
        }, exclude=sender_id)
    except Exception as e:
        print(f"❌ Read ошибка: {e}")