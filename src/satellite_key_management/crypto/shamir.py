"""Заглушка схемы Шамира. Участник 1 заменит на полноценную реализацию."""
import secrets

# Простое поле GF(p), p — большое простое
P = 2**127 - 1

def _eval_poly(coeffs, x):
    y = 0
    for c in reversed(coeffs):
        y = (y * x + c) % P
    return y

def split_secret(secret: int, n: int, k: int):
    coeffs = [secret % P] + [secrets.randbelow(P) for _ in range(k - 1)]
    shares = [(i, _eval_poly(coeffs, i)) for i in range(1, n + 1)]
    return shares

def reconstruct(shares):
    """Интерполяция Лагранжа в точке 0."""
    total = 0
    for i, (xi, yi) in enumerate(shares):
        num, den = 1, 1
        for j, (xj, _) in enumerate(shares):
            if i != j:
                num = (num * (-xj)) % P
                den = (den * (xi - xj)) % P
        total = (total + yi * num * pow(den, -1, P)) % P
    return total