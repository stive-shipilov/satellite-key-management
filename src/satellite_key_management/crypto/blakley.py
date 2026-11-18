"""Схема Блэкли. Доля (a₁, …, aₖ, c) задаёт плоскость a·x + c = 0 в GF(p)."""
import secrets
from math import isqrt

from .shamir import P

# Простые числа для опытов с ключами до 256 бит.
FIELDS = (2**89 - 1, P, 2**255 - 19, 2**521 - 1)
Plane = tuple[int, ...]


class Blakley:
    """Секрет — первая координата. Поддерживает известные поля и учебные p < 2³²."""

    def __init__(self, p: int = P):
        if p not in FIELDS:
            if not 2 <= p < 2**32 or any(p % i == 0 for i in range(2, isqrt(p) + 1)):
                raise ValueError("Нужно простое учебное p < 2³² или один из модулей FIELDS")
        self.p = p

    def split_secret(self, secret: int, n: int, k: int) -> list[Plane]:
        """Построить n уравнений через одну точку, любые k нормалей независимы."""
        p = self.p
        if not 1 <= k <= n or n + k > p:
            raise ValueError("Требуются 1 ≤ k ≤ n и n + k ≤ p для матрицы Коши")
        if not 0 <= secret < p:
            raise ValueError("Секрет вне поля")
        point = [secret] + [secrets.randbelow(p) for _ in range(k - 1)]
        planes = []
        for x in range(k, k + n):
            normal = tuple(pow(x - y, -1, p) for y in range(k))
            constant = -sum(a * b for a, b in zip(normal, point)) % p
            planes.append((*normal, constant))
        return planes

    def reconstruct(self, shares: list[Plane]) -> int:
        """Решить систему методом Гаусса, проверив ранг и лишние уравнения."""
        if not shares:
            raise ValueError("Нужны уравнения плоскостей")
        k = len(shares[0]) - 1
        if k < 1 or len(shares) < k:
            raise ValueError("Недостаточно плоскостей для восстановления")
        p = self.p
        matrix = []
        for plane in shares:
            if len(plane) != k + 1 or any(not 0 <= x < p for x in plane):
                raise ValueError("Неверная размерность или коэффициент вне поля")
            matrix.append([*plane[:-1], -plane[-1] % p])
        for j in range(k):
            pivot = next((r for r in range(j, len(matrix)) if matrix[r][j]), None)
            if pivot is None:
                raise ValueError("Линейно зависимые плоскости не определяют точку")
            matrix[j], matrix[pivot] = matrix[pivot], matrix[j]
            inverse = pow(matrix[j][j], -1, p)
            row = [(v * inverse) % p for v in matrix[j]]
            matrix[j] = row
            for i, other in enumerate(matrix):
                if i != j and other[j]:
                    factor = other[j]
                    matrix[i] = [(a - factor * b) % p for a, b in zip(other, row)]
        if any(row[-1] for row in matrix[k:]):
            raise ValueError("Противоречивые уравнения")
        return matrix[0][-1]
