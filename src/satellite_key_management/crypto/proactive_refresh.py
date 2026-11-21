"""Proactive refresh — периодическое обновление долей без смены секрета.

Идея. Противник, годами собирающий доли по одной (медленная атака), рано
или поздно накопит k долей и восстановит ключ. Proactive refresh ломает эту
атаку: периодически все доли заменяются новыми, но секрет остаётся тем же.
Старые доли становятся бесполезными, и накопление противника обнуляется
(на графиках — «зубчатая пила»).

Реализация. Секретный полином f(x) заменяется на f'(x) = f(x) + δ(x), где
δ(x) — случайный полином степени k-1 с δ(0) = 0. Тогда f'(0) = f(0) = секрет,
а новые доли s'_i = s_i + δ(i) отличаются от старых. Любая смесь старых и
новых долей, включающая разные поколения, даёт мусор, т.к. полином одного
поколения больше не согласован с долями другого.
"""
from __future__ import annotations

import secrets

from .shamir import ShamirGFp, ShamirGF256


def refresh_shares(shares: list[tuple[int, int]], n: int, k: int,
                   p: int) -> list[tuple[int, int]]:
    """Обновить доли над GF(p): секрет сохраняется, старые доли несовместимы.

    Возвращает новые доли (те же номера i, другие значения), образующие
    полином f'(x) = f(x) + δ(x) с тем же значением в нуле.
    """
    if len(shares) != n:
        raise ValueError("Число переданных долей должно быть равно n")
    if not (1 <= k <= n):
        raise ValueError("Должно выполняться 1 <= k <= n")
    # δ(x) со свободным членом 0: коэффициенты a_1..a_{k-1} случайные.
    delta = [0] + [secrets.randbelow(p) for _ in range(k - 1)]
    def eval_delta(x: int) -> int:
        y = 0
        for c in reversed(delta):
            y = (y * x + c) % p
        return y
    return [(i, (y + eval_delta(i)) % p) for i, y in shares]


def refresh_shares_gf256(shares: list[tuple[int, bytes]], n: int, k: int) -> list[tuple[int, bytes]]:
    """Обновить байтовые доли над GF(2^8): секрет сохраняется.

    Доли — пары (номер_доли, bytes). Для каждого байта применяется свой
    сдвиговый полином δ(0)=0.
    """
    if len(shares) != n:
        raise ValueError("Число переданных долей должно быть равно n")
    if not (1 <= k <= n):
        raise ValueError("Должно выполняться 1 <= k <= n")
    length = len(shares[0][1])

    def _eval_delta_byte(coeffs: list[int], x: int) -> int:
        # coeffs — список коэффициентов δ, где coeffs[0]=0 (свободный член).
        y = 0
        for c in reversed(coeffs):
            y = _gf_mul(y, x) ^ c
        return y & 0xFF

    # Строим δ-полиномы для каждого байта независимо.
    deltas = [
        [0] + [secrets.randbelow(256) for _ in range(k - 1)]
        for _ in range(length)
    ]
    new_shares = []
    for i, _ in shares:
        col = bytearray(length)
        for b in range(length):
            col[b] = (shares[i - 1][1][b] ^ _eval_delta_byte(deltas[b], i)) & 0xFF
        new_shares.append((i, bytes(col)))
    return new_shares


# Оптимизированное умножение в GF(2^8) без импорта модуля.
def _gf_mul(a: int, b: int) -> int:
    res = 0
    for _ in range(8):
        if b & 1:
            res ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x11B
        b >>= 1
    return res & 0xFF


# --- Удобные функции на уровне модуля ----------------------------------------
def refresh(shares, n: int, k: int, field: str = "GF(p)", **kwargs):
    """Обёртка: обновить доли в выбранном поле.

    field "GF(p)": доли — (i, int); needs параметр p (модуль).
    field "GF(2^8)": доли — (i, bytes).
    """
    field = field.upper().replace(" ", "")
    if field in ("GF(P)", "GFP", "PRIME"):
        p = kwargs.get("p", ShamirGFp().p)
        return refresh_shares(shares, n, k, p)
    if field in ("GF(2^8)", "GF256", "BYTE"):
        return refresh_shares_gf256(shares, n, k)
    raise ValueError(f"Неизвестное поле: {field!r}")