"""Заглушка (N,N)-схемы. Участник 2 заменит на Блэкли + XOR + CRT."""
import secrets

def xor_split(secret: int, n: int):
    parts = [secrets.randbits(secret.bit_length() or 1) for _ in range(n - 1)]
    last = secret
    for p in parts:
        last ^= p
    return parts + [last]

def xor_combine(parts):
    out = 0
    for p in parts:
        out ^= p
    return out