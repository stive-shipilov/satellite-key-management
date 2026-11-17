"""Юнит-тесты схемы Шамира: корректность, граничные случаи (k=1, k=n),
восстановление при разных наборах долей, оба поля."""
import random

import pytest

from crypto.shamir import (
    P,
    ShamirGF256,
    ShamirGFp,
    combine,
    reconstruct,
    split,
    split_secret,
)


# --- GF(p) -------------------------------------------------------------------
class TestShamirGFp:
    def test_reconstruct_any_k_subset(self):
        n, k = 12, 8
        shamir = ShamirGFp()
        secret = 0xDEADBEEFCAFE1234
        shares = shamir.split_secret(secret, n, k)
        assert len(shares) == n
        for _ in range(30):
            subset = random.sample(shares, k)
            assert shamir.reconstruct(subset) == secret

    def test_more_than_k_reconstructs(self):
        n, k = 12, 8
        shamir = ShamirGFp()
        secret = 42
        shares = shamir.split_secret(secret, n, k)
        for m in range(k, n + 1):
            assert shamir.reconstruct(random.sample(shares, m)) == secret

    def test_k_equals_1(self):
        # Порог 1: восстановление должно работать от любой одной доли.
        shamir = ShamirGFp()
        secret = 7
        shares = shamir.split_secret(secret, 5, 1)
        for share in shares:
            assert shamir.reconstruct([share]) == secret

    def test_k_equals_n(self):
        shamir = ShamirGFp()
        secret = 99
        shares = shamir.split_secret(secret, 5, 5)
        # любые 4 долей НЕ должны дать секрет (нужны все 5) — проверим
        # вероятностно, что ровно n восстанавливает:
        assert shamir.reconstruct(shares) == secret
        assert shamir.reconstruct(shares[:4]) != secret

    def test_invalid_bounds(self):
        shamir = ShamirGFp()
        with pytest.raises(ValueError):
            shamir.split_secret(1, 5, 0)
        with pytest.raises(ValueError):
            shamir.split_secret(1, 5, 6)

    def test_secret_range(self):
        shamir = ShamirGFp()
        with pytest.raises(ValueError):
            shamir.split_secret(P, 5, 3)  # вне [0, P)

    def test_legacy_api(self):
        # Совместимые сигнатуры из старого кода.
        secret = 123456789
        shares = split_secret(secret, 6, 4)
        assert reconstruct(shares) == secret

    def test_unified_split_combine(self):
        secret = 31337
        shares = split(secret, 6, 4, field="GF(p)")
        assert combine(shares, field="GF(p)") == secret


# --- GF(2^8) -----------------------------------------------------------------
class TestShamirGF256:
    def setup_method(self):
        self.shamir = ShamirGF256()

    def test_reconstruct_any_k_subset(self):
        n, k = 7, 4
        secret = b"secret-16-byte-key"
        shares = self.shamir.split_secret(secret, n, k)
        assert len(shares) == n
        for _ in range(30):
            subset = random.sample(shares, k)
            assert self.shamir.reconstruct(subset) == secret

    def test_k_equals_1(self):
        secret = b"abc"
        shares = self.shamir.split_secret(secret, 4, 1)
        for share in shares:
            assert self.shamir.reconstruct([share]) == secret

    def test_k_equals_n(self):
        secret = b"xyz"
        shares = self.shamir.split_secret(secret, 4, 4)
        assert self.shamir.reconstruct(shares) == secret
        assert self.shamir.reconstruct(shares[:3]) != secret

    def test_invalid_bounds(self):
        with pytest.raises(ValueError):
            self.shamir.split_secret(b"k", 3, 0)
        with pytest.raises(ValueError):
            self.shamir.split_secret(b"k", 3, 4)

    def test_unified_split_combine(self):
        secret = b"hello world!!"
        shares = split(secret, 9, 5, field="GF(2^8)")
        assert combine(shares, field="GF(2^8)") == secret

    def test_unknown_field(self):
        with pytest.raises(ValueError):
            split(1, 2, 2, field="nope")
        with pytest.raises(ValueError):
            combine([(1, 2)], field="nope")


# --- Поле GF(2^8) — базовые законы ------------------------------------------
class TestGF256Laws:
    def test_inverse(self):
        from crypto.shamir import _gf256_mul, _gf256_pow
        for a in range(1, 256):
            # Обратный элемент в GF(2^8) — a^254, т.к. a^255 == 1.
            assert _gf256_mul(a, _gf256_pow(a, 254)) == 1

    def test_associativity_small(self):
        from crypto.shamir import _gf256_mul
        for a in (1, 2, 17, 255):
            for b in (3, 19, 201):
                for c in (5, 53):
                    assert _gf256_mul(_gf256_mul(a, b), c) == _gf256_mul(a, _gf256_mul(b, c))