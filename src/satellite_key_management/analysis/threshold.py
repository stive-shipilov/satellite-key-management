"""Выбор порога для следующей сессии при пассивной компрометации узлов."""
from fractions import Fraction
from math import ceil


def choose_threshold(n: int, visible: int, threat: float, minimum: int | None = None) -> int | None:
    """Возвращает достижимый k или None. threat задаёт бюджет ceil(threat·(n−1))."""
    if minimum is None:
        minimum = min(2, n)
    if not 1 <= minimum <= n or not 0 <= visible <= n or not 0 <= threat <= 1:
        raise ValueError("Некорректные размер созвездия, видимость, минимум или угроза")
    # Для введённых 0.14 и n=51 бюджет равен ровно 7 узлам.
    compromised = ceil(Fraction(str(threat)) * (n - 1))
    threshold = max(minimum, (visible + 1) // 2, compromised + 1)
    return threshold if threshold <= visible else None
