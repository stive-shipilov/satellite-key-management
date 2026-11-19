"""Учебная пороговая BLS-подпись с доверенным дилером и проверкой частичных подписей."""

from dataclasses import dataclass
import secrets

from py_ecc.bls import G2Basic as BLS
from py_ecc.bls.g2_primitives import G2_to_signature, signature_to_G2
from py_ecc.optimized_bls12_381 import Z2, add, curve_order, multiply

from .shamir import ShamirGFp


@dataclass(frozen=True)
class VerificationKeys:
    """Открытые параметры одной раздачи, передаются по аутентифицированному каналу."""

    threshold: int
    public_key: bytes
    participants: tuple[bytes, ...]


def generate_key(n: int, k: int):
    """Раздать ключевые доли. Полный секрет остаётся только внутри процедуры дилера."""
    if not 1 <= k <= n < curve_order:
        raise ValueError("Нужно 1 ≤ k ≤ n < порядка группы")
    secret = BLS.KeyGen(secrets.token_bytes(32))
    sharing = ShamirGFp(curve_order)
    while True:
        shares = sharing.split_secret(secret, n, k)
        if all(value for _, value in shares):
            break
    public = VerificationKeys(
        k, BLS.SkToPk(secret), tuple(BLS.SkToPk(v) for _, v in shares)
    )
    return public, shares


def sign_share(share, message: bytes):
    sid, value = share
    return sid, BLS.Sign(value, message)


def combine_signs(partials, message: bytes, keys: VerificationKeys) -> bytes:
    """Проверить участников и интерполировать подписи в группе G2 в точке 0."""
    ids = [sid for sid, _ in partials]
    if not keys.threshold <= len(ids) <= len(keys.participants) or len(set(ids)) != len(
        ids
    ):
        raise ValueError("Требуется кворум различных подписантов")
    total = Z2
    for sid, signature in partials:
        if not 1 <= sid <= len(keys.participants) or not BLS.Verify(
            keys.participants[sid - 1], message, signature
        ):
            raise ValueError("Некорректная частичная подпись")
        weight = 1
        for other in ids:
            if other != sid:
                weight = (
                    weight * other * pow(other - sid, -1, curve_order) % curve_order
                )
        total = add(total, multiply(signature_to_G2(signature), weight))
    signature = G2_to_signature(total)
    if not verify(message, signature, keys.public_key):
        raise ValueError("Итоговая подпись не соответствует группе")
    return signature


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    return BLS.Verify(public_key, message, signature)
