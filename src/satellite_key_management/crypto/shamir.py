"""Схема Шамира (Shamir's Secret Sharing).

Генерирует n долей секрета, из которых любые k (порог) позволяют
восстановить секрет, а k-1 долей не дают о нём никакой информации
(в терминах теории информации).

Два варианта поля:
    * GF(p)     — простое поле, арифметика по модулю большого простого P.
                  Доли — целые числа. Самый простой и наглядный вариант.
    * GF(2^8)   — поле байтов (многочлен x^8 + x^4 + x^3 + x + 1, 0x11b).
                  Доли — байты, естественно ложатся на AES-ключ.

Модуль сохраняет обратную совместимость: функции `split_secret` и
`reconstruct` (используются в simulation/session.py и attacks/attacks.py)
оставлены как тонкая обёртка над `ShamirGFp`.
"""
from __future__ import annotations

import secrets


# ---------------------------------------------------------------------------
# GF(p) — простое поле
# ---------------------------------------------------------------------------
# Mersenne-простое 2^127 - 1. Достаточно большое для 128-битного ключа и
# совместимо со старой заглушкой (см. P в attacks.py).
P = 2**127 - 1


class ShamirGFp:
    """Схема Шамира над простым полем GF(p)."""

    def __init__(self, p: int = P):
        if p < 2:
            raise ValueError("Модуль p должен быть простым числом >= 2")
        self.p = p

    def _eval_poly(self, coeffs: list[int], x: int) -> int:
        """Горнер: значение полинома с коэффициентами coeffs в точке x."""
        y = 0
        for c in reversed(coeffs):
            y = (y * x + c) % self.p
        return y

    def split_secret(self, secret: int, n: int, k: int) -> list[tuple[int, int]]:
        """Разбить секрет на n долей, порог k.

        Полином f(x) = a0 + a1*x + ... + a_{k-1}*x^{k-1}, где a0 = secret.
        Доля i — это точка (i, f(i)) для i = 1..n.
        """
        if not (1 <= k <= n):
            raise ValueError("Должно выполняться 1 <= k <= n")
        if not (0 <= secret < self.p):
            raise ValueError(f"Секрет должен лежать в [0, {self.p})")
        coeffs = [secret % self.p] + [secrets.randbelow(self.p) for _ in range(k - 1)]
        return [(i, self._eval_poly(coeffs, i)) for i in range(1, n + 1)]

    def reconstruct(self, shares: list[tuple[int, int]]) -> int:
        """Интерполяция Лагранжа в точке 0 — восстановить секрет.

        Принимает ровно k долей (или больше; лишние игнорируются).
        """
        if len(shares) < 1:
            raise ValueError("Для восстановления нужна хотя бы одна доля")
        total = 0
        for i, (xi, yi) in enumerate(shares):
            num, den = 1, 1
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    num = (num * (-xj)) % self.p
                    den = (den * (xi - xj)) % self.p
            total = (total + yi * num * pow(den, -1, self.p)) % self.p
        return total


# ---------------------------------------------------------------------------
# GF(2^8) — поле байтов
# ---------------------------------------------------------------------------
# Многочлен-модуль: x^8 + x^4 + x^3 + x + 1 (0x11b). Это стандартный
# отображающий многочлен для AES.
_GF256_MOD = 0x11B


def _gf256_mul(a: int, b: int) -> int:
    """Умножение в GF(2^8) без таблиц (Russian peasant / double-and-add)."""
    res = 0
    for _ in range(8):
        if b & 1:
            res ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= _GF256_MOD
        b >>= 1
    return res & 0xFF


def _gf256_pow(a: int, e: int) -> int:
    res = 1
    base = a
    while e:
        if e & 1:
            res = _gf256_mul(res, base)
        base = _gf256_mul(base, base)
        e >>= 1
    return res & 0xFF


def _gf256_inv(a: int) -> int:
    """Обратный элемент в GF(2^8): a^(254) (a^255 = 1 для ненулевых a)."""
    if a == 0:
        raise ZeroDivisionError("0 не имеет обратного элемента в GF(2^8)")
    return _gf256_pow(a, 254)


class ShamirGF256:
    """Схема Шамира над GF(2^8) — доли по байту.

    Подходит для поключевого разделения: байтовый вектор секрета
    разбивается независимо по каждому байту. Каждая доля — это пара
    ``(x, bytes)``, где x — номер/метка доли (обязательный: иначе при
    восстановлении нельзя восстановить x-координату полинома).
    """

    def _eval_poly(self, coeffs: list[int], x: int) -> int:
        y = 0
        for c in reversed(coeffs):
            y = _gf256_mul(y, x) ^ c
        return y & 0xFF

    def _split_byte(self, byte: int, n: int, k: int) -> list[int]:
        """Разбить один байт на n значений долей."""
        coeffs = [byte & 0xFF] + [secrets.randbelow(256) for _ in range(k - 1)]
        return [self._eval_poly(coeffs, x) & 0xFF for x in range(1, n + 1)]

    def split_secret(self, secret: bytes, n: int, k: int) -> list[tuple[int, bytes]]:
        """Разбить байтовый секрет на n долей ``(x, bytes)``.

        Доля x — это по одному байту на каждый байт секрета,
        интерполированный полиномом в точке x. Возвращает список из n долей.
        """
        if not (1 <= k <= n):
            raise ValueError("Должно выполняться 1 <= k <= n")
        cols: list[bytearray] = [bytearray(len(secret)) for _ in range(n)]
        for byte_idx, byte in enumerate(secret):
            vals = self._split_byte(byte, n, k)
            for share_idx in range(n):
                cols[share_idx][byte_idx] = vals[share_idx]
        return [(x + 1, bytes(cols[x])) for x in range(n)]

    def reconstruct(self, shares: list[tuple[int, bytes]]) -> bytes:
        """Восстановить секрет из k (или более) долей ``(x, bytes)``."""
        if not shares:
            raise ValueError("Нужна хотя бы одна доля")
        if any(s[0] <= 0 for s in shares):
            raise ValueError("Метки долей должны быть положительными")
        length = len(shares[0][1])
        if any(len(v) != length for _, v in shares):
            raise ValueError("Все доли должны быть одной длины")
        out = bytearray()
        for byte_idx in range(length):
            points = [(x, y[byte_idx]) for x, y in shares]
            out.append(self._interp_byte(points))
        return bytes(out)

    def _interp_byte(self, points: list[tuple[int, int]]) -> int:
        """Интерполяция Лагранжа в точке 0 в GF(2^8).

        В поле характеристики 2 вычитание = сложение (XOR), поэтому
        (0 - xj) = xj.
        """
        total = 0
        for i, (xi, yi) in enumerate(points):
            num, den = 1, 1
            for j, (xj, _) in enumerate(points):
                if i != j:
                    # Точка интерполяции x = 0, (0 - xj) == xj.
                    num = _gf256_mul(num, xj)
                    den = _gf256_mul(den, xi ^ xj)
            total ^= _gf256_mul(yi, _gf256_mul(num, _gf256_inv(den)))
        return total & 0xFF


# ---------------------------------------------------------------------------
# Общий интерфейс и обратная совместимость
# ---------------------------------------------------------------------------
def split(secret, n: int, k: int, field: str = "GF(p)"):
    """Единая точка входа для разбиения секрета на доли.

    field: "GF(p)" — целочисленный секрет; "GF(2^8)" — байтовый секрет.
    """
    field = field.upper().replace(" ", "")
    if field in ("GF(P)", "GFP", "PRIME"):
        return ShamirGFp().split_secret(secret, n, k)
    if field in ("GF(2^8)", "GF256", "BYTE"):
        return ShamirGF256().split_secret(secret, n, k)
    raise ValueError(f"Неизвестное поле: {field!r}")


def combine(shares, field: str = "GF(p)"):
    """Единая точка входа для восстановления секрета из долей."""
    field = field.upper().replace(" ", "")
    if field in ("GF(P)", "GFP", "PRIME"):
        return ShamirGFp().reconstruct(shares)
    if field in ("GF(2^8)", "GF256", "BYTE"):
        return ShamirGF256().reconstruct(shares)
    raise ValueError(f"Неизвестное поле: {field!r}")


# --- Обратная совместимость (бывшая заглушка) -------------------------------
def split_secret(secret: int, n: int, k: int) -> list[tuple[int, int]]:
    """Совместимая обёртка: Шамир над GF(p)."""
    return ShamirGFp().split_secret(secret, n, k)


def reconstruct(shares: list[tuple[int, int]]) -> int:
    """Совместимая обёртка: восстановление в GF(p)."""
    return ShamirGFp().reconstruct(shares)