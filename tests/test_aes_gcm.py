"""Юнит-тесты AES-GCM: round-trip, отклонение неверного ключа/тега/AAD."""
import pytest

from crypto.aes_gcm import AESGCMCipher, InvalidTag, decrypt, encrypt


class TestAESGCM:
    def setup_method(self):
        self.key = bytes(range(32))  # AES-256
        self.cipher = AESGCMCipher(self.key)

    def test_roundtrip(self):
        pt = b"LEO satellite telemetry payload"
        nonce, ct, tag = self.cipher.encrypt(pt, aad=b"header")
        assert self.cipher.decrypt(nonce, ct, tag, aad=b"header") == pt

    def test_roundtrip_empty(self):
        nonce, ct, tag = self.cipher.encrypt(b"")
        assert self.cipher.decrypt(nonce, ct, tag) == b""

    def test_wrong_key_rejected(self):
        pt = b"data"
        nonce, ct, tag = self.cipher.encrypt(pt)
        other = AESGCMCipher(bytes(range(31, -1, -1)))
        with pytest.raises(InvalidTag):
            other.decrypt(nonce, ct, tag)

    def test_tampered_ct_rejected(self):
        pt = b"authenticated data"
        nonce, ct, tag = self.cipher.encrypt(pt)
        bad = bytes([ct[0] ^ 0x01]) + ct[1:]
        with pytest.raises(InvalidTag):
            self.cipher.decrypt(nonce, bad, tag)

    def test_wrong_aad_rejected(self):
        pt = b"data"
        nonce, ct, tag = self.cipher.encrypt(pt, aad=b"a")
        with pytest.raises(InvalidTag):
            self.cipher.decrypt(nonce, ct, tag, aad=b"b")

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            AESGCMCipher(b"short")  # 5 байт

    def test_module_functions(self):
        pt = b"module test"
        nonce, ct, tag = encrypt(self.key, pt, aad=b"x")
        assert decrypt(self.key, nonce, ct, tag, aad=b"x") == pt