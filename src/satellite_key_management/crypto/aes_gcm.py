"""Шифрование трафика AES-GCM.

Использует AES-256 в режиме GCM через `cryptography.hazmat.primitives`.
GCM — режим с аутентификацией (AEAD): шифротекст защищён и от чтения, и
от подмены (тег целостности). Тег проверяется при расшифровании, поэтому
подмена или повреждение шифротекста обнаруживается всегда.

Ключ — сессионный ключ, восстановленный из долей (bytes). Длина ключа
должна быть 16/24/32 байта (AES-128/192/256).
"""
from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


# --- Допустимые длины ключа -------------------------------------------------
_AES_KEY_SIZES = {16: "AES-128", 24: "AES-192", 32: "AES-256"}


class AESGCMCipher:
    """Обёртка над AES-GCM: шифрование с аутентификацией."""

    def __init__(self, key: bytes, nonce_size: int = 12):
        if len(key) not in _AES_KEY_SIZES:
            raise ValueError(
                f"Ключ должен быть 16/24/32 байт (AES-128/192/256), получено {len(key)}"
            )
        if not (8 <= nonce_size <= 16):
            raise ValueError("Размер nonce должен быть в диапазоне 8..16 байт")
        self.key = key
        self.nonce_size = nonce_size

    def encrypt(self, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes, bytes]:
        """Зашифровать plaintext. Возвращает (nonce, ciphertext, tag)."""
        nonce = os.urandom(self.nonce_size)
        encryptor = Cipher(algorithms.AES(self.key), modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(aad)
        ct = encryptor.update(plaintext) + encryptor.finalize()
        return nonce, ct, encryptor.tag

    def decrypt(self, nonce: bytes, ct: bytes, tag: bytes, aad: bytes = b"") -> bytes:
        """Расшифровать и проверить тег. Бросает InvalidTag при подмене."""
        decryptor = Cipher(algorithms.AES(self.key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(aad)
        return decryptor.update(ct) + decryptor.finalize()


# --- Удобные функции на уровне модуля ----------------------------------------
def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes, bytes]:
    """Зашифровать AES-GCM. Возвращает (nonce, ciphertext, tag)."""
    return AESGCMCipher(key).encrypt(plaintext, aad)


def decrypt(key: bytes, nonce: bytes, ct: bytes, tag: bytes, aad: bytes = b"") -> bytes:
    """Расшифровать AES-GCM. Бросает InvalidTag при подмене шифротекста."""
    return AESGCMCipher(key).decrypt(nonce, ct, tag, aad)


__all__ = ["AESGCMCipher", "encrypt", "decrypt", "InvalidTag"]