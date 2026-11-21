"""Измерения в памяти. Настройка поля, открытых модулей и построение графиков вне таймера."""
import secrets
from dataclasses import dataclass
from functools import partial
from statistics import median
from timeit import repeat

if __package__ == "analysis":  # старый способ запуска симуляции из src/satellite_key_management
    from crypto.blakley import Blakley, FIELDS
    from crypto.shamir import ShamirGFp
    from crypto.xor_scheme import CRTScheme, XorScheme
else:
    from ..crypto.blakley import Blakley, FIELDS
    from ..crypto.shamir import ShamirGFp
    from ..crypto.xor_scheme import CRTScheme, XorScheme


@dataclass(frozen=True)
class Measurement:
    scheme: str
    bits: int
    n: int
    scenario_k: int
    threshold: int
    share_bytes: float
    split_us: float
    recover_us: float

    @property
    def safe_shares(self):
        """Сколько долей можно раскрыть без однозначного восстановления."""
        return self.threshold - 1


def byte_width(max_value: int) -> int:
    return max(1, (max_value.bit_length() + 7) // 8)


def measure(bits=128, n=6, k=3, repeats=7, number=30) -> list[Measurement]:
    """Один сценарий, общий случайный b-битный ключ, медианы стоимости одной операции."""
    if not (1 <= bits <= 520 and 1 <= k <= n and repeats >= 1 and number >= 1):
        raise ValueError("Проверьте ширину ключа (1…520), k/n и число повторов")
    p = next(p for p in FIELDS if p >= 1 << bits and p >= n + k)
    secret = secrets.randbits(bits)
    shamir, blakley = ShamirGFp(p), Blakley(p)
    xor, crt = XorScheme(n, bits), CRTScheme(n, bits)
    word = byte_width(p - 1)
    label = byte_width(n)
    # Для Блэкли передаётся само уравнение. Для CRT номер выбирает открытый модуль.
    variants = [
        ("Шамир", k, label + word, partial(shamir.split_secret, secret, n, k), shamir.reconstruct),
        ("Блэкли", k, (k + 1) * word, partial(blakley.split_secret, secret, n, k), blakley.reconstruct),
        ("XOR", n, label + byte_width((1 << bits) - 1), partial(xor.split_secret, secret), xor.reconstruct),
        ("CRT", n, label + sum(byte_width(m - 1) for m in crt.moduli) / n,
         partial(crt.split_secret, secret), crt.reconstruct),
    ]
    results = []
    for name, threshold, size, split, reconstruct in variants:
        shares = split()
        selected = (shares[::2] + shares[1::2])[:threshold]
        recover = partial(reconstruct, selected)
        if recover() != secret:
            raise RuntimeError(f"Ошибка восстановления {name}")
        split_us = median(repeat(split, repeat=repeats, number=number)) * 1e6 / number
        recover_us = median(repeat(recover, repeat=repeats, number=number)) * 1e6 / number
        results.append(Measurement(name, bits, n, k, threshold, size, split_us, recover_us))
    return results
