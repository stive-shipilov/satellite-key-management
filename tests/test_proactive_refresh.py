"""Юнит-тесты proactive refresh: секрет стабилен, новые доли совместимы,
смесь старых и новых долей несовместима."""
import random

import pytest

from crypto.proactive_refresh import (
    refresh,
    refresh_shares,
    refresh_shares_gf256,
)
from crypto.shamir import P, ShamirGF256, ShamirGFp


class TestRefreshGFp:
    def setup_method(self):
        self.shamir = ShamirGFp()

    def test_secret_stable_after_refresh(self):
        n, k = 7, 4
        secret = 7654321
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh_shares(original, n, k, P)
        assert self.shamir.reconstruct(refreshed) == secret

    def test_new_shares_reconstruct_any_k(self):
        n, k = 7, 4
        secret = 123456789
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh_shares(original, n, k, P)
        for _ in range(30):
            assert self.shamir.reconstruct(random.sample(refreshed, k)) == secret

    def test_mixed_old_new_incompatible(self):
        n, k = 7, 4
        secret = 55555
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh_shares(original, n, k, P)
        mixed = refreshed[:2] + original[2:4]
        # Смесь поколений должна давать неверное восстановление.
        assert self.shamir.reconstruct(mixed) != secret

    def test_refresh_unified(self):
        n, k = 5, 3
        secret = 99
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh(original, n, k, field="GF(p)", p=P)
        assert self.shamir.reconstruct(refreshed) == secret

    def test_wrong_share_count(self):
        with pytest.raises(ValueError):
            refresh_shares([(1, 2), (2, 3)], 5, 3, P)


class TestRefreshGF256:
    def setup_method(self):
        self.shamir = ShamirGF256()

    def test_secret_stable_after_refresh(self):
        n, k = 7, 4
        secret = b"0123456789ab"
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh_shares_gf256(original, n, k)
        assert self.shamir.reconstruct(refreshed) == secret

    def test_mixed_old_new_incompatible(self):
        n, k = 7, 4
        secret = b"abcdefgh"
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh_shares_gf256(original, n, k)
        mixed = refreshed[:2] + original[2:4]
        assert self.shamir.reconstruct(mixed) != secret

    def test_refresh_unified(self):
        n, k = 5, 3
        secret = b"xyz"
        original = self.shamir.split_secret(secret, n, k)
        refreshed = refresh(original, n, k, field="GF(2^8)")
        assert self.shamir.reconstruct(refreshed) == secret