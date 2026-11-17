"""Юнит-тесты VSS (схема Фельдмана): корректность, детект злого дилера,
подмены доли, восстановление при разных наборах."""
import random

import pytest

from crypto.feldman_vss import (
    FeldmanVSS,
    dealer_commit,
    reconstruct_shares,
    verify_share,
)


class TestFeldmanVSS:
    def setup_method(self):
        self.vss = FeldmanVSS()

    def test_honest_shares_verify(self):
        n, k = 7, 4
        secret = 987654321987654321
        shares, commitments = dealer_commit(secret, n, k)
        assert len(shares) == n
        assert len(commitments) == k
        for share in shares:
            assert verify_share(share, commitments)

    def test_reconstruct_any_k(self):
        n, k = 7, 4
        secret = 5555555555555555555
        shares, commitments = dealer_commit(secret, n, k)
        for _ in range(30):
            subset = random.sample(shares, k)
            assert self.vss.reconstruct(subset) == secret

    def test_tampered_share_rejected(self):
        n, k = 7, 4
        secret = 111
        shares, commitments = dealer_commit(secret, n, k)
        idx, val = shares[0]
        # Подмена значения доли.
        assert not verify_share((idx, val + 1), commitments)

    def test_tampered_commitment_detected(self):
        n, k = 7, 4
        secret = 222
        shares, commitments = dealer_commit(secret, n, k)
        # Подмена обязательства к свободному члену (a_0 = секрет).
        tampered = commitments[:]
        tampered[0] = (tampered[0] + 1) % self.vss.p
        # Доля больше не согласована с подменённым обязательством.
        assert any(not verify_share(s, tampered) for s in shares)

    def test_public_verify_reconstructed(self):
        n, k = 7, 4
        secret = 333
        shares, commitments = dealer_commit(secret, n, k)
        recon = self.vss.reconstruct(random.sample(shares, k))
        assert self.vss.verify_reconstructed(recon, commitments)

    def test_invalid_bounds(self):
        with pytest.raises(ValueError):
            dealer_commit(1, 4, 0)
        with pytest.raises(ValueError):
            dealer_commit(1, 4, 5)

    def test_module_reconstruct(self):
        n, k = 5, 3
        secret = 444
        shares, _ = dealer_commit(secret, n, k)
        assert reconstruct_shares(shares) == secret