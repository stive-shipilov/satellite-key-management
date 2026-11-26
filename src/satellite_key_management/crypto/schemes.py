"""Единый адаптер над схемами разделения секрета.

Сводит Shamir (GF(p), GF(2^8)), Blakley, Feldman VSS, XOR и CRT к одному
интерфейсу, который использует SessionSimulator. VSS — единственная схема,
которая умеет verify_share; остальные считаются «доверенными» (дилер честен).
"""
from __future__ import annotations

from dataclasses import dataclass

from .blakley import Blakley, FIELDS
from .feldman_vss import FeldmanVSS
from .shamir import ShamirGFp
from .xor_scheme import CRTScheme, XorScheme


SCHEMES = ("shamir", "blakley", "feldman_vss", "xor", "crt")


def pick_prime(bits: int, n: int, k: int) -> int:
    """Наибольшее простое из FIELDS, покрывающее bits и n+k (совместимо с benchmark)."""
    return next(p for p in FIELDS if p >= (1 << bits) and p >= n + k)


@dataclass
class ShareSet:
    """Результат раздачи: доли, публичные обязательства и режим проверки."""

    scheme: str
    shares: dict[int, tuple]              # sid -> доля в терминах схемы
    commitments: tuple[int, ...] = ()     # только для feldman_vss
    verifiable: bool = False              # есть ли verify_share


class SchemeAdapter:
    """Обёртка над конкретной схемой с единым API."""

    def __init__(self, name: str, n: int, k: int, bits: int):
        if name not in SCHEMES:
            raise ValueError(f"Неизвестная схема: {name!r}; ожидается одна из {SCHEMES}")
        if not (1 <= k <= n):
            raise ValueError("Должно быть 1 <= k <= n")
        self.name = name
        self.n, self.k, self.bits = n, k, bits

        if name in ("shamir", "blakley"):
            self.p = pick_prime(bits, n, k)
            self.impl = ShamirGFp(self.p) if name == "shamir" else Blakley(self.p)
        elif name == "feldman_vss":
            self.impl = FeldmanVSS()
            self.p = self.impl.q
        elif name in ("xor", "crt"):
            if k != n:
                raise ValueError(f"Схема {name} требует k = n")
            self.impl = XorScheme(n, bits) if name == "xor" else CRTScheme(n, bits)
            self.p = 1 << bits
        else:
            raise AssertionError(name)

    # -- раздача -----------------------------------------------------------
    def split(self, secret_int: int) -> ShareSet:
        if self.name == "feldman_vss":
            shares, commitments = self.impl.dealer_commit(secret_int, self.n, self.k)
            return ShareSet(self.name, dict(shares), tuple(commitments), verifiable=True)
        if self.name == "shamir":
            return ShareSet(
                self.name,
                dict(self.impl.split_secret(secret_int, self.n, self.k)),
                (), False,
            )
        if self.name == "blakley":
            # Плоскости не имеют sid внутри — нумеруем снаружи.
            planes = self.impl.split_secret(secret_int, self.n, self.k)
            return ShareSet(self.name, {i: p for i, p in enumerate(planes, 1)}, (), False)
        if self.name in ("xor", "crt"):
            return ShareSet(self.name, dict(self.impl.split_secret(secret_int)), (), False)
        raise AssertionError(self.name)

    # -- проверка доли (только VSS) ---------------------------------------
    def verify_share(self, sid: int, share: tuple, ss: ShareSet) -> bool:
        if not ss.verifiable:
            return True  # доверенный дилер
        return self.impl.verify_share(share, ss.commitments)

    def verify_reconstructed(self, secret_int: int, ss: ShareSet) -> bool:
        if not ss.verifiable:
            return True
        return self.impl.verify_reconstructed(secret_int, ss.commitments)

    # -- восстановление ----------------------------------------------------
    def reconstruct(self, selected) -> int:
        """Восстановить секрет.

        Принимает:
            dict[sid -> value]      — напрямую от split() через ss.shares
            list[(sid, value)]      — обычный список долей
            list[value]             — если передан только values (Blakley: plane-кортежи)

        Внутри приводит к тому формату, который ожидает impl.reconstruct.
        """
        # 1. Нормализуем вход в list[(sid, value)] или list[plane] (для blakley).
        if isinstance(selected, dict):
            items = list(selected.items())
        else:
            items = list(selected)

        if len(items) < self.k:
            raise ValueError(f"Нужно ≥ {self.k} долей, получено {len(items)}")

        # 2. Для blakley impl.reconstruct ждёт list[plane] (без sid).
        if self.name == "blakley":
            # Если items = [(sid, plane), ...] — берём plane
            planes = []
            for it in items:
                if isinstance(it, tuple) and len(it) == 2 and isinstance(it[0], int):
                    sid, plane = it
                    planes.append(plane if isinstance(plane, tuple) else (plane,))
                else:
                    planes.append(it)
            return self.impl.reconstruct(planes)

        # 3. Для остальных impl.reconstruct ждёт list[(sid, value)].
        shares = []
        for it in items:
            if isinstance(it, tuple) and len(it) == 2 and isinstance(it[0], int):
                shares.append(it)
            else:
                # пришёл голый value — присваиваем sid по порядку
                shares.append((len(shares) + 1, it))
        return self.impl.reconstruct(shares)
