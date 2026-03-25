"""
Сервис шифрования.
На сервере храним только зашифрованные данные.
Реальное E2EE происходит на клиенте — сервер просто передаёт.
Здесь — серверная криптография для хранения и верификации.
"""
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import os
import base64


class CryptoService:
    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """Генерация пары ключей X25519 (для клиента)"""
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        return (
            base64.b64encode(private_bytes).decode(),
            base64.b64encode(public_bytes).decode()
        )

    @staticmethod
    def encrypt_message(plaintext: str, key: bytes) -> str:
        """AES-256-GCM шифрование"""
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    @staticmethod
    def decrypt_message(encrypted: str, key: bytes) -> str:
        """AES-256-GCM дешифрование"""
        data = base64.b64decode(encrypted)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()

    @staticmethod
    def derive_shared_key(private_key_b64: str, public_key_b64: str) -> bytes:
        """Получение общего ключа из пары ключей (Diffie-Hellman)"""
        private_bytes = base64.b64decode(private_key_b64)
        public_bytes = base64.b64decode(public_key_b64)

        private_key = x25519.X25519PrivateKey.from_private_bytes(private_bytes)
        public_key = x25519.X25519PublicKey.from_public_bytes(public_bytes)

        shared_key = private_key.exchange(public_key)

        # Derive AES key
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"messenger-e2ee"
        ).derive(shared_key)

        return derived_key


crypto_service = CryptoService()
