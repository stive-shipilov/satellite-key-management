"""Передача одного пакета в учебной LEO-модели с предварительной раздачей ключа."""
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import secrets

from ..crypto.aes_gcm import decrypt, encrypt
from ..crypto.blakley import Blakley, FIELDS
from ..crypto.shamir import ShamirGFp
from ..crypto.xor_scheme import CRTScheme, XorScheme


@dataclass
class TelemetrySession:
    """Снимок одной раздачи. Номера спутников отделены от индексов внутри схемы."""

    threshold: int
    shares: dict[int, tuple[int, ...]]
    recover: Callable
    packet: tuple[bytes, bytes, bytes]
    aad: bytes

    @classmethod
    def issue(cls, scheme: str, members: Sequence[int], k: int, message: bytes, aad: bytes = b""):
        """Создать ключ AES-128, распределить доли и зашифровать телеметрию."""
        n = len(members)
        if len(set(members)) != n or any(sid < 1 for sid in members) or not 1 <= k <= n:
            raise ValueError("Нужны разные положительные номера спутников и 1 ≤ k ≤ n")
        key = secrets.token_bytes(16)
        secret = int.from_bytes(key, "big")
        if scheme in ("shamir", "blakley"):
            p = next(p for p in FIELDS if p >= 2**128 and p >= n + k)
            sharing = ShamirGFp(p) if scheme == "shamir" else Blakley(p)
            shares = sharing.split_secret(secret, n, k)
        elif scheme in ("xor", "crt"):
            if k != n:
                raise ValueError("Для XOR и CRT требуется k = n")
            sharing = XorScheme(n, 128) if scheme == "xor" else CRTScheme(n, 128)
            shares = sharing.split_secret(secret)
        else:
            raise ValueError(f"Неизвестная схема: {scheme}")
        return cls(k, dict(zip(members, shares)), sharing.reconstruct,
                   encrypt(key, message, aad), aad)

    def receive(self, leo, minute: int, lat=55.0, lon=37.0) -> bytes | None:
        """Собрать доли видимых участников. Без кворума пакет остаётся зашифрованным."""
        visible = set(leo.visible_at(minute, lat, lon))
        shares = [share for sid, share in self.shares.items() if sid in visible]
        if len(shares) < self.threshold:
            return None
        key = self.recover(shares[:self.threshold]).to_bytes(16, "big")
        return decrypt(key, *self.packet, self.aad)
