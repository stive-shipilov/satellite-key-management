"""Выбор порога для следующей сессии при пассивной компрометации узлов."""
from math import ceil


def choose_threshold(n: int, visible: int, threat: float, minimum: int = 2) -> int | None:
    """Возвращает достижимый k или None. threat задаёт бюджет ceil(threat·(n−1))."""
    if not 1 <= minimum <= n or not 0 <= visible <= n or not 0 <= threat <= 1:
        raise ValueError("Некорректные размер созвездия, видимость, минимум или угроза")
    compromised = ceil(threat * (n - 1))
    threshold = max(minimum, (visible + 1) // 2, compromised + 1)
    return threshold if threshold <= visible else None
