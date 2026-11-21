"""VSS — верифицируемое разделение секрета по Фельдману (Feldman VSS).

Зачем. В обычной схеме Шамира дилер в принципе может раздать часть
участников корректные доли, а часть — мусор, и никто этого не заметит до
попытки восстановления. Feldman VSS позволяет каждому получателю проверить
свою долю, не раскрывая секрет: дилер публикует обязательства (commitments)
к коэффициентам полинома, и доля считается корректной, только если её
значение согласуется с этими обязательствами.

Модель. Работаем в группе простого порядка q по модулю безопасного
простого p = 2q + 1, с генератором g подгруппы порядка q. Секрет и
коэффициенты полинома лежат в Z_q; доля i-го участника — f(i) mod q.
Обязательство к коэффициенту a_j — это g^{a_j} mod p.

Проверка доли i: g^{f(i)} == Π_{j=0}^{k-1} (g^{a_j})^{i^j} mod p.
"""
from __future__ import annotations

import secrets


# --- Параметры группы (сгенерированы заранее, безопасное простое p = 2q+1) ---
# q — простое порядка 2^192; p — безопасное простое; g — генератор подгруппы
# порядка q. Достаточно для учебной демонстрации VSS.
SAFE_Q = 4446198671340520515123563451911276606216969453372647356209
SAFE_P = 8892397342681041030247126903822553212433938906745294712419
SAFE_G = 8658659276072068354748097288823447273570217079269105411067


class FeldmanVSS:
    """Схема верифицируемого разделения секрета по Фельдману.

    Параметры по умолчанию — безопасная группа, сгенерированная выше.
    """

    def __init__(self, p: int = SAFE_P, q: int = SAFE_Q, g: int = SAFE_G):
        if not (1 < q < p):
            raise ValueError("Должно быть 1 < q < p (p — безопасное простое)")
        self.p = p
        self.q = q
        self.g = g

    # -- внутренняя арифметика в Z_q ---------------------------------------
    def _eval_poly(self, coeffs: list[int], x: int) -> int:
        y = 0
        for c in reversed(coeffs):
            y = (y * x + c) % self.q
        return y

    def dealer_commit(self, secret: int, n: int, k: int) -> tuple[list[tuple[int, int]], list[int]]:
        """Дилер раздаёт доли и публикует обязательства.

        Возвращает (shares, commitments):
            shares      — список (номер_доли, значение_доли), значение mod q;
            commitments — список обязательств g^{a_j} mod p на каждый
                          коэффициент полинома (всего k штук).
        """
        if not (1 <= k <= n):
            raise ValueError("Должно выполняться 1 <= k <= n")
        if not (0 <= secret < self.q):
            raise ValueError(f"Секрет должен лежать в [0, {self.q})")
        coeffs = [secret % self.q] + [secrets.randbelow(self.q) for _ in range(k - 1)]
        shares = [(i, self._eval_poly(coeffs, i)) for i in range(1, n + 1)]
        commitments = [pow(self.g, a, self.p) for a in coeffs]
        return shares, commitments

    def verify_share(self, share: tuple[int, int], commitments: list[int]) -> bool:
        """Проверить, что доля (i, s_i) согласована с публичными обязательствами.

        g^{s_i} должно равняться Π_j (g^{a_j})^{i^j} mod p. Секрет не раскрывается.
        """
        i, s_i = share
        if not commitments or not 1 <= i < self.q or not 0 <= s_i < self.q:
            return False
        lhs = pow(self.g, s_i, self.p)
        rhs = 1
        for j, C_j in enumerate(commitments):
            rhs = (rhs * pow(C_j, pow(i, j, self.q), self.p)) % self.p
        return lhs == rhs

    def verify_reconstructed(self, secret: int, commitments: list[int]) -> bool:
        """Публичная проверка восстановленного секрета: g^secret == C_0."""
        return pow(self.g, secret, self.p) == commitments[0]

    def reconstruct(self, shares: list[tuple[int, int]]) -> int:
        """Интерполяция Лагранжа в точке 0 в Z_q — восстановить секрет."""
        if len(shares) < 1:
            raise ValueError("Нужна хотя бы одна доля")
        total = 0
        for i, (xi, yi) in enumerate(shares):
            num, den = 1, 1
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    num = (num * (-xj)) % self.q
                    den = (den * (xi - xj)) % self.q
            total = (total + yi * num * pow(den, -1, self.q)) % self.q
        return total


# --- Удобные функции на уровне модуля ----------------------------------------
def dealer_commit(secret: int, n: int, k: int) -> tuple[list[tuple[int, int]], list[int]]:
    """Функция-обёртка: раздать доли и получить обязательства (группа по умолчанию)."""
    return FeldmanVSS().dealer_commit(secret, n, k)


def verify_share(share: tuple[int, int], commitments: list[int]) -> bool:
    """Обёртка: проверить согласованность доли с обязательствами."""
    return FeldmanVSS().verify_share(share, commitments)


def reconstruct_shares(shares: list[tuple[int, int]]) -> int:
    """Обёртка: восстановить секрет из долей в Z_q."""
    return FeldmanVSS().reconstruct(shares)