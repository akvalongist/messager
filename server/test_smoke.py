import os
import sys
import unittest
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="messager-test-", dir=str(ROOT)))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(TEMP_DIR / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEMP_DIR / "uploads")
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


class MessengerSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def register(self, username: str, display_name: str) -> dict:
        response = self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "display_name": display_name,
                "password": "password123",
                "email": f"{username}@example.com",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_healthcheck(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_auth_chat_message_file_and_notifications_flow(self):
        alice = self.register("alice", "Alice")
        bob = self.register("bob", "Bob")

        me = self.client.get("/api/auth/me", headers=self.auth_headers(alice["token"]))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "alice")

        search = self.client.get("/api/auth/search/bo", headers=self.auth_headers(alice["token"]))
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["users"][0]["username"], "bob")

        direct_chat = self.client.post(
            "/api/chats/direct",
            json={"user_id": bob["user_id"]},
            headers=self.auth_headers(alice["token"]),
        )
        self.assertEqual(direct_chat.status_code, 200, direct_chat.text)
        chat_id = direct_chat.json()["id"]

        duplicate_chat = self.client.post(
            "/api/chats/direct",
            json={"user_id": bob["user_id"]},
            headers=self.auth_headers(alice["token"]),
        )
        self.assertEqual(duplicate_chat.status_code, 200)
        self.assertEqual(duplicate_chat.json()["id"], chat_id)

        group = self.client.post(
            "/api/chats/group",
            json={"name": "Team", "description": "Core", "member_ids": [bob["user_id"]]},
            headers=self.auth_headers(alice["token"]),
        )
        self.assertEqual(group.status_code, 200, group.text)
        invite_code = group.json()["invite_code"]

        carol = self.register("carol", "Carol")
        joined = self.client.post(
            f"/api/chats/join/{invite_code}",
            headers=self.auth_headers(carol["token"]),
        )
        self.assertEqual(joined.status_code, 200, joined.text)

        with self.client.websocket_connect("/ws") as alice_ws, self.client.websocket_connect("/ws") as bob_ws:
            alice_ws.send_json({"token": alice["token"]})
            bob_ws.send_json({"token": bob["token"]})
            self.assertEqual(alice_ws.receive_json()["type"], "connected")
            self.assertEqual(bob_ws.receive_json()["type"], "connected")

            alice_ws.send_json(
                {
                    "type": "message",
                    "chat_id": chat_id,
                    "content": "hello bob",
                    "message_type": "text",
                }
            )
            alice_message = alice_ws.receive_json()
            bob_message = bob_ws.receive_json()
            self.assertEqual(alice_message["type"], "new_message")
            self.assertEqual(bob_message["message"]["content"], "hello bob")
            message_id = bob_message["message"]["id"]

        history = self.client.get(f"/api/messages/{chat_id}", headers=self.auth_headers(alice["token"]))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["messages"][0]["content"], "hello bob")

        upload = self.client.post(
            f"/api/files/upload?chat_id={chat_id}",
            headers=self.auth_headers(alice["token"]),
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        self.assertTrue(upload.json()["url"].startswith("/uploads/"))

        notifications = self.client.get("/api/notifications/", headers=self.auth_headers(bob["token"]))
        self.assertEqual(notifications.status_code, 200, notifications.text)
        self.assertGreaterEqual(notifications.json()["unread_count"], 1)

        mark_all = self.client.post("/api/notifications/read-all", headers=self.auth_headers(bob["token"]))
        self.assertEqual(mark_all.status_code, 200)

        delete_response = self.client.delete(
            f"/api/messages/{message_id}",
            headers=self.auth_headers(alice["token"]),
        )
        self.assertEqual(delete_response.status_code, 200)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
