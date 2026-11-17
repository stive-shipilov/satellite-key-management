"""Пороговая подпись (threshold signature) — телеметрия подписывается только
при участии k спутников.

Зачем. Один спутник не должен иметь возможность подделать телеметрию.
Ключ подписи разделён по Шамиру между n спутниками, и подпись валидна
только тогда, когда её построили минимум k участников. Меньшее число
спутников не может выработать корректную подпись.

Схема. Классическая подпись Шнорра, адаптированная под порог:
    * закрытый ключ x раздаётся по Шамиру (доли x_i в Z_q),
      публичный ключ Y = g^x mod p;
    * nonce k = H(m) детерминирован по сообщению (единый для всех участников,
      его не нужно разделять), R = g^k, e = H(R || m);
    * каждый участник i считает частичную подпись s_i = k + e * x_i mod q;
    * k частичных подписей объединяются интерполяцией Лагранжа:
          s = Σ λ_i * s_i = k + e * x mod q;
    * проверка: g^s == R * Y^e mod p.

Замечание. Детерминированный nonce k = H(m) — учебный вариант (безопасность
на уровне энтропии коллизии хэша). Полноценная threshold-ECDSA со
слепым nonce-разделением существенно сложнее и здесь не реализуется;
церковно-учебная цель (k из n, невозможность подделки одним узлом) достигается.

Практический момент: частичные подписи и публичный ключ проходят через VSS
(обязательства), т.е. каждая доля подписи тоже верифицируема.
"""
from __future__ import annotations

import hashlib

from .feldman_vss import FeldmanVSS, SAFE_G, SAFE_P, SAFE_Q


def _Hq(data: bytes, q: int) -> int:
    """SHA-256, свёрнутый в Z_q."""
    return int.from_bytes(hashlib.sha256(data).digest(), "big") % q


def _compose(seed: bytes, q: int) -> int:
    """k = H(m) — детерминированный nonce из хэша сообщения."""
    return _Hq(seed, q)


class ThresholdSchnorr:
    """Пороговая подпись Шнорра с ключом, разделённым по Шамиру."""

    def __init__(self, p: int = SAFE_P, q: int = SAFE_Q, g: int = SAFE_G):
        self.p = p
        self.q = q
        self.g = g
        self.vss = FeldmanVSS(p=p, q=q, g=g)

    # -- генерация ключа и раздача долей ------------------------------------
    def generate_key(self, n: int, k: int) -> tuple[int, int, list[tuple[int, int]], list[int]]:
        """Сгенерировать ключ подписи и раздать n долей.

        Возвращает (x, Y, shares, commitments):
            x — закрытый ключ (для справки/эталонной подписи; в реальном
                пороговом сценарии ни у кого не хранится целиком);
            Y = g^x — публичный ключ;
            shares — доли (i, x_i) в Z_q;
            commitments — обязательства VSS к коэффициентам полинома.
        """
        x = _Hq(b"threshold-schnorr-keygen" + self.p.to_bytes(32, "big"), self.q)
        shares, commitments = self.vss.dealer_commit(x, n, k)
        Y = pow(self.g, x, self.p)
        return x, Y, shares, commitments

    # -- эталонная подпись полным ключом (для сверки) -----------------------
    def _challenge(self, message: bytes, R: int) -> int:
        return _Hq(R.to_bytes(64, "big") + message, self.q)

    def sign_full(self, x: int, message: bytes) -> tuple[int, int]:
        """Подпись полным закрытым ключом (деaler-эталон). Sig = (R, s)."""
        k = _compose(message, self.q)
        R = pow(self.g, k, self.p)
        e = self._challenge(message, R)
        s = (k + e * x) % self.q
        return R, s

    # -- частичные подписи и объединение -----------------------------------
    def sign_share(self, share: tuple[int, int], message: bytes) -> tuple[int, int, int]:
        """Один участник подписывает сообщение своей долей.

        Возвращает (x_i, s_i, R) — метку доли, частичную подпись и общий
        одноразовый элемент R = g^k (одинаков для всех, т.к. k детерминирован).
        """
        xi, x_i = share
        k = _compose(message, self.q)
        R = pow(self.g, k, self.p)
        e = self._challenge(message, R)
        s_i = (k + e * x_i) % self.q
        return xi, s_i, R

    def combine_signs(self, partials: list[tuple[int, int, int]], message: bytes) -> tuple[int, int]:
        """Объединить k частичных подписей в одну подпись (R, s).

        Каждый элемент partials — (xi, s_i, R) из ``sign_share``.
        """
        if len(partials) < 1:
            raise ValueError("Нужна хотя бы одна частичная подпись")
        # R и e одинаковы для всех участников.
        k = _compose(message, self.q)
        R = pow(self.g, k, self.p)
        e = self._challenge(message, R)
        s = 0
        for i, (xi, s_i, _R) in enumerate(partials):
            # веса Лагранжа для константного члена (интерполяция в 0)
            num, den = 1, 1
            for j, (xj, _, _) in enumerate(partials):
                if i != j:
                    num = (num * (-xj)) % self.q
                    den = (den * (xi - xj)) % self.q
            lam = (num * pow(den, -1, self.q)) % self.q
            s = (s + lam * s_i) % self.q
        return R, s

    # -- проверка -----------------------------------------------------------
    def verify(self, message: bytes, signature: tuple[int, int], Y: int) -> bool:
        """Проверить подпись (R, s) публичным ключом Y."""
        R, s = signature
        if not (1 <= R < self.p and 0 <= s < self.q):
            return False
        e = self._challenge(message, R)
        return pow(self.g, s, self.p) == (R * pow(Y, e, self.p)) % self.p


# --- Модульный интерфейс ------------------------------------------------------
def generate_key(n: int, k: int):
    return ThresholdSchnorr().generate_key(n, k)


def sign_share(share: tuple[int, int], message: bytes):
    return ThresholdSchnorr().sign_share(share, message)


def combine_signs(partials: list[tuple[int, int]], message: bytes):
    return ThresholdSchnorr().combine_signs(partials, message)


def verify(message: bytes, signature: tuple[int, int], Y: int) -> bool:
    return ThresholdSchnorr().verify(message, signature, Y)