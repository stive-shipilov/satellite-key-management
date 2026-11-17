"""Юнит-тесты пороговой подписи (threshold Schnorr):
k из n объединяется в корректную подпись, k-1 не могут подделать."""
import random

from crypto.threshold_sig import (
    ThresholdSchnorr,
    combine_signs,
    generate_key,
    sign_share,
    verify,
)


class TestThresholdSchnorr:
    def setup_method(self):
        self.sig = ThresholdSchnorr()

    def test_full_key_reference_verifies(self):
        n, k = 7, 4
        x, Y, shares, commitments = generate_key(n, k)
        msg = b"telemetry: altitude=550km"
        R, s = self.sig.sign_full(x, msg)
        assert self.sig.verify(msg, (R, s), Y)

    def test_k_of_n_signature_verifies(self):
        n, k = 7, 4
        x, Y, shares, commitments = generate_key(n, k)
        msg = b"telemetry: power=42W"
        for _ in range(30):
            partials = [sign_share(s, msg) for s in random.sample(shares, k)]
            sig = combine_signs(partials, msg)
            assert verify(msg, sig, Y)

    def test_less_than_k_cannot_forge(self):
        n, k = 7, 4
        x, Y, shares, commitments = generate_key(n, k)
        msg = b"telemetry: ts=2026"
        partials = [sign_share(s, msg) for s in random.sample(shares, k - 1)]
        sig = combine_signs(partials, msg)
        assert not verify(msg, sig, Y)

    def test_wrong_message_rejected(self):
        n, k = 7, 4
        x, Y, shares, commitments = generate_key(n, k)
        msg = b"telemetry: genuine"
        partials = [sign_share(s, msg) for s in random.sample(shares, k)]
        sig = combine_signs(partials, msg)
        assert not verify(b"telemetry: tampered", sig, Y)

    def test_wrong_public_key_rejected(self):
        n, k = 7, 4
        x, Y, shares, commitments = generate_key(n, k)
        msg = b"telemetry"
        partials = [sign_share(s, msg) for s in random.sample(shares, k)]
        sig = combine_signs(partials, msg)
        # Другой публичный ключ не должен подтвердить подпись.
        other_Y = pow(self.sig.g, _secret_from_other_key(), self.sig.p)
        assert not verify(msg, sig, other_Y)


def _secret_from_other_key():
    import hashlib
    return int.from_bytes(hashlib.sha256(b"another-key").digest(), "big") % 4446198671340520515123563451911276606216969453372647356209