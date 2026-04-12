"""
Сервис уведомлений.
- Push-уведомления через Firebase Cloud Messaging (FCM)
- Email-уведомления
- Внутренние уведомления (в БД)
"""

import json
import asyncio
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy import select, and_, update
import uuid

from database import Base, async_session
from config import get_settings

settings = get_settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# Модель уведомлений в БД
# ============================================================

class NotificationType(str, Enum):
    NEW_MESSAGE = "new_message"
    GROUP_INVITE = "group_invite"
    MENTION = "mention"
    REPLY = "reply"
    MISSED_CALL = "missed_call"
    FILE_SHARED = "file_shared"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    SYSTEM = "system"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Кому
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Тип
    notification_type = Column(
        SQLEnum(NotificationType),
        nullable=False,
        default=NotificationType.SYSTEM
    )

    # Контент
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)

    # Ссылки на связанные объекты
    chat_id = Column(String(36), nullable=True)
    message_id = Column(String(36), nullable=True)
    sender_id = Column(String(36), nullable=True)

    # Дополнительные данные (JSON)
    extra_data = Column(Text, nullable=True)

    # Статус
    is_read = Column(Boolean, default=False)
    is_pushed = Column(Boolean, default=False)  # Отправлен ли push

    created_at = Column(DateTime, default=utc_now, index=True)
    read_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])


# ============================================================
# Модель токенов устройств для push-уведомлений
# ============================================================

class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # FCM / APNs токен
    token = Column(String(500), nullable=False, unique=True)
    platform = Column(String(20), nullable=False)  # "android", "ios", "web"
    device_name = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    last_used_at = Column(DateTime, default=utc_now)

    user = relationship("User", foreign_keys=[user_id])


# ============================================================
# Firebase Cloud Messaging
# ============================================================

class FCMService:
    """Push-уведомления через Firebase"""

    def __init__(self):
        self._initialized = False

    def initialize(self, credentials_path: str = None):
        """
        Инициализация Firebase.
        Вызывать при старте приложения.
        """
        try:
            import firebase_admin
            from firebase_admin import credentials

            if credentials_path:
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
            else:
                # Используем переменные окружения
                firebase_admin.initialize_app()

            self._initialized = True
            print("✅ Firebase FCM инициализирован")
        except Exception as e:
            print(f"⚠️ Firebase не инициализирован: {e}")
            print("   Push-уведомления будут сохраняться только в БД")
            self._initialized = False

    async def send_push(
        self,
        token: str,
        title: str,
        body: str,
        data: dict = None,
        image_url: str = None
    ) -> bool:
        """Отправка push на одно устройство"""
        if not self._initialized:
            return False

        try:
            from firebase_admin import messaging

            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )

            # Android-специфичные настройки
            android_config = messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    click_action="OPEN_CHAT",
                    channel_id="messages"
                )
            )

            # iOS-специфичные настройки
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                        mutable_content=True
                    )
                )
            )

            # Web push настройки
            web_config = messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon="/icon.png",
                    image=image_url
                )
            )

            message = messaging.Message(
                notification=notification,
                android=android_config,
                apns=apns_config,
                webpush=web_config,
                data=data or {},
                token=token
            )

            response = messaging.send(message)
            print(f"✅ Push отправлен: {response}")
            return True

        except Exception as e:
            print(f"❌ Ошибка отправки push: {e}")
            return False

    async def send_push_to_multiple(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict = None
    ) -> dict:
        """Отправка push на несколько устройств"""
        if not self._initialized or not tokens:
            return {"success": 0, "failure": len(tokens)}

        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                tokens=tokens
            )

            response = messaging.send_each_for_multicast(message)

            return {
                "success": response.success_count,
                "failure": response.failure_count
            }

        except Exception as e:
            print(f"❌ Ошибка массовой отправки push: {e}")
            return {"success": 0, "failure": len(tokens)}


fcm_service = FCMService()


# ============================================================
# Основной сервис уведомлений
# ============================================================

class NotificationService:
    """
    Главный сервис уведомлений.
    Сохраняет в БД + отправляет push + WebSocket.
    """

    def __init__(self):
        self.fcm = fcm_service

    # --------------------------------------------------------
    # Создание и отправка уведомлений
    # --------------------------------------------------------

    async def notify_new_message(
        self,
        recipient_id: str,
        sender_name: str,
        message_preview: str,
        chat_id: str,
        message_id: str,
        sender_id: str,
        chat_name: str = None,
        is_group: bool = False
    ):
        """Уведомление о новом сообщении"""

        # Формируем заголовок
        if is_group and chat_name:
            title = f"{chat_name}"
            body = f"{sender_name}: {message_preview[:100]}"
        else:
            title = sender_name
            body = message_preview[:100]

        await self._create_and_send(
            user_id=recipient_id,
            notification_type=NotificationType.NEW_MESSAGE,
            title=title,
            body=body,
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender_id,
            data={
                "type": "new_message",
                "chat_id": chat_id,
                "message_id": message_id,
                "sender_id": sender_id
            }
        )

    async def notify_group_invite(
        self,
        recipient_id: str,
        inviter_name: str,
        group_name: str,
        chat_id: str,
        sender_id: str
    ):
        """Уведомление о приглашении в группу"""
        await self._create_and_send(
            user_id=recipient_id,
            notification_type=NotificationType.GROUP_INVITE,
            title="Приглашение в группу",
            body=f"{inviter_name} пригласил вас в «{group_name}»",
            chat_id=chat_id,
            sender_id=sender_id,
            data={
                "type": "group_invite",
                "chat_id": chat_id
            }
        )

    async def notify_mention(
        self,
        recipient_id: str,
        sender_name: str,
        message_preview: str,
        chat_id: str,
        message_id: str,
        sender_id: str
    ):
        """Уведомление об упоминании"""
        await self._create_and_send(
            user_id=recipient_id,
            notification_type=NotificationType.MENTION,
            title=f"{sender_name} упомянул вас",
            body=message_preview[:100],
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender_id,
            data={
                "type": "mention",
                "chat_id": chat_id,
                "message_id": message_id
            }
        )

    async def notify_reply(
        self,
        recipient_id: str,
        sender_name: str,
        message_preview: str,
        chat_id: str,
        message_id: str,
        sender_id: str
    ):
        """Уведомление об ответе на сообщение"""
        await self._create_and_send(
            user_id=recipient_id,
            notification_type=NotificationType.REPLY,
            title=f"{sender_name} ответил вам",
            body=message_preview[:100],
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender_id,
            data={
                "type": "reply",
                "chat_id": chat_id,
                "message_id": message_id
            }
        )

    async def notify_file_shared(
        self,
        recipient_id: str,
        sender_name: str,
        file_name: str,
        chat_id: str,
        sender_id: str
    ):
        """Уведомление о полученном файле"""
        await self._create_and_send(
            user_id=recipient_id,
            notification_type=NotificationType.FILE_SHARED,
            title=sender_name,
            body=f"📎 Отправил файл: {file_name}",
            chat_id=chat_id,
            sender_id=sender_id,
            data={
                "type": "file_shared",
                "chat_id": chat_id
            }
        )

    # --------------------------------------------------------
    # Работа с уведомлениями в БД
    # --------------------------------------------------------

    async def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> list[Notification]:
        """Получить уведомления пользователя"""
        async with async_session() as db:
            query = (
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            if unread_only:
                query = query.where(Notification.is_read == False)

            result = await db.execute(query)
            return list(result.scalars().all())

    async def get_unread_count(self, user_id: str) -> int:
        """Количество непрочитанных уведомлений"""
        from sqlalchemy import func

        async with async_session() as db:
            result = await db.execute(
                select(func.count(Notification.id)).where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False
                    )
                )
            )
            return result.scalar() or 0

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Пометить уведомление как прочитанное"""
        async with async_session() as db:
            result = await db.execute(
                select(Notification).where(
                    and_(
                        Notification.id == notification_id,
                        Notification.user_id == user_id
                    )
                )
            )
            notification = result.scalar_one_or_none()
            if notification:
                notification.is_read = True
                notification.read_at = utc_now()
                await db.commit()
                return True
            return False

    async def mark_all_as_read(self, user_id: str) -> int:
        """Пометить все уведомления как прочитанные"""
        async with async_session() as db:
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False
                    )
                )
                .values(is_read=True, read_at=utc_now())
            )
            await db.commit()
            return result.rowcount

    async def mark_chat_as_read(self, user_id: str, chat_id: str) -> int:
        """Пометить все уведомления чата как прочитанные"""
        async with async_session() as db:
            result = await db.execute(
                update(Notification)
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.chat_id == chat_id,
                        Notification.is_read == False
                    )
                )
                .values(is_read=True, read_at=utc_now())
            )
            await db.commit()
            return result.rowcount

    # --------------------------------------------------------
    # Управление токенами устройств
    # --------------------------------------------------------

    async def register_device(
        self,
        user_id: str,
        token: str,
        platform: str,
        device_name: str = None
    ) -> DeviceToken:
        """Регистрация устройства для push-уведомлений"""
        async with async_session() as db:
            # Проверяем существует ли токен
            existing = await db.execute(
                select(DeviceToken).where(DeviceToken.token == token)
            )
            device = existing.scalar_one_or_none()

            if device:
                # Обновляем привязку к пользователю
                device.user_id = user_id
                device.is_active = True
                device.last_used_at = utc_now()
            else:
                device = DeviceToken(
                    user_id=user_id,
                    token=token,
                    platform=platform,
                    device_name=device_name
                )
                db.add(device)

            await db.commit()
            return device

    async def unregister_device(self, token: str):
        """Удаление токена устройства"""
        async with async_session() as db:
            result = await db.execute(
                select(DeviceToken).where(DeviceToken.token == token)
            )
            device = result.scalar_one_or_none()
            if device:
                device.is_active = False
                await db.commit()

    async def get_user_device_tokens(self, user_id: str) -> list[str]:
        """Получить все активные токены пользователя"""
        async with async_session() as db:
            result = await db.execute(
                select(DeviceToken.token).where(
                    and_(
                        DeviceToken.user_id == user_id,
                        DeviceToken.is_active == True
                    )
                )
            )
            return [row[0] for row in result.all()]

    # --------------------------------------------------------
    # Приватные методы
    # --------------------------------------------------------

    async def _create_and_send(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        chat_id: str = None,
        message_id: str = None,
        sender_id: str = None,
        image_url: str = None,
        data: dict = None
    ):
        """Создать уведомление в БД и отправить push"""

        # 1. Сохраняем в БД
        async with async_session() as db:
            notification = Notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                body=body,
                image_url=image_url,
                chat_id=chat_id,
                message_id=message_id,
                sender_id=sender_id,
                extra_data=json.dumps(data) if data else None
            )
            db.add(notification)
            await db.commit()

        # 2. Отправляем push (не блокируем основной поток)
        asyncio.create_task(
            self._send_push_to_user(user_id, title, body, data, image_url)
        )

        # 3. Отправляем через WebSocket (если онлайн)
        await self._send_ws_notification(user_id, {
            "type": "notification",
            "notification": {
                "id": str(notification.id),
                "notification_type": notification_type.value,
                "title": title,
                "body": body,
                "chat_id": chat_id,
                "message_id": message_id,
                "sender_id": sender_id,
                "created_at": utc_now().isoformat()
            }
        })

    async def _send_push_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict = None,
        image_url: str = None
    ):
        """Отправить push на все устройства пользователя"""
        tokens = await self.get_user_device_tokens(user_id)

        if not tokens:
            return

        if len(tokens) == 1:
            await self.fcm.send_push(tokens[0], title, body, data, image_url)
        else:
            await self.fcm.send_push_to_multiple(tokens, title, body, data)

    async def _send_ws_notification(self, user_id: str, message: dict):
        """Отправить уведомление через WebSocket"""
        try:
            try:
                from routes.ws_stable import manager
            except Exception:
                from routes.ws import manager
            await manager.send_to_user(user_id, message)
        except Exception:
            pass  # WebSocket может быть не подключён


# ============================================================
# Глобальный экземпляр
# ============================================================

notification_service = NotificationService()
