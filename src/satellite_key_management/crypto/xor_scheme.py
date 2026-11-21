"""Два варианта (N,N). Контекст раздачи задаёт N и публичную ширину ключа."""
import secrets
from functools import reduce
from math import lcm, prod
from operator import xor

Share = tuple[int, int]


def xor_split(secret: int, n: int, *, bits: int | None = None) -> list[int]:
    """Совместимый целочисленный API. Для ключей задавайте общую ширину bits."""
    if bits is None:
        # Совместимость с произвольными целыми, длина открыта с шагом 128 бит.
        bits = 128 * max(1, (secret.bit_length() + 127) // 128)
    if n < 1 or bits < 1 or not 0 <= secret < 1 << bits:
        raise ValueError("Проверьте n, ширину и диапазон секрета")
    masks = [secrets.randbits(bits) for _ in range(n - 1)]
    return masks + [reduce(xor, masks, secret)]


def xor_combine(parts) -> int:
    """XOR переданных значений. Старый формат без номеров не хранит порог."""
    parts = list(parts)
    if not parts or any(p < 0 for p in parts):
        raise ValueError("Нужны неотрицательные доли")
    return reduce(xor, parts)


def _all_values(shares: list[Share], n: int) -> list[int]:
    values = dict(shares)
    if len(shares) != n or values.keys() != set(range(1, n + 1)):
        raise ValueError("Требуется по одной доле от каждого из N участников")
    return [values[i] for i in range(1, n + 1)]


class XorScheme:
    """Строгий API для нумерованных долей одной раздачи."""

    def __init__(self, n: int, bits: int):
        if n < 1 or bits < 1:
            raise ValueError("n и bits должны быть положительными")
        self.n = n
        self.bits = bits

    def split_secret(self, secret: int) -> list[Share]:
        return list(enumerate(xor_split(secret, self.n, bits=self.bits), 1))

    def reconstruct(self, shares: list[Share]) -> int:
        parts = _all_values(shares, self.n)
        if any(not 0 <= value < 1 << self.bits for value in parts):
            raise ValueError("Доля вне диапазона")
        return xor_combine(parts)


class CRTScheme:
    """Рандомизированная (N,N)-схема типа Асмута — Блума для b-битных ключей.

    Восстанавливается случайное поднятие Y = S + 2ᵇ·A. Модули публичны,
    попарно взаимно просты и нечётны. margin_bits задаёт запас маскирования.
    """

    def __init__(self, n: int, bits: int, margin_bits: int = 64):
        if min(n, bits, margin_bits) < 1:
            raise ValueError("n, bits и margin_bits должны быть положительными")
        self.n = n
        self.base = 1 << bits
        # Любой простой делитель |i-j| делит step, но ни один модуль.
        step = lcm(2, *range(2, n + 1))
        lower = self.base << margin_bits
        first = (lower + step - 1) // step
        self.moduli = tuple((first + i) * step + 1 for i in range(n))
        self.product = prod(self.moduli)
        self.lifts = self.product // self.base
        self.weights = []
        for modulus in self.moduli:
            partial = self.product // modulus
            self.weights.append(partial * pow(partial, -1, modulus))

    def split_secret(self, secret: int) -> list[Share]:
        if not 0 <= secret < self.base:
            raise ValueError("Секрет вне заданного диапазона")
        lifted = secret + self.base * secrets.randbelow(self.lifts)
        return [(i, lifted % modulus) for i, modulus in enumerate(self.moduli, 1)]

    def reconstruct(self, shares: list[Share]) -> int:
        values = _all_values(shares, self.n)
        if any(not 0 <= r < m for r, m in zip(values, self.moduli)):
            raise ValueError("Остаток вне диапазона модуля")
        lifted = sum(r * w for r, w in zip(values, self.weights)) % self.product
        if lifted >= self.lifts * self.base:
            raise ValueError("Остатки задают значение вне диапазона выдачи")
        return lifted % self.base
