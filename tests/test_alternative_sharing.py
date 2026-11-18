"""Порог, уравнения из пособия, неполные коалиции и границы открытых параметров."""
from collections import Counter
from itertools import combinations, product
from math import gcd, prod

import pytest

from satellite_key_management.crypto.blakley import Blakley
from satellite_key_management.crypto.xor_scheme import CRTScheme, XorScheme, xor_combine, xor_split


def test_blakley_textbook():
    planes = [(4, 8, 2, 6), (2, 6, 8, 3), (6, 8, 4, 1)]
    assert Blakley(11).reconstruct(planes) == 6


@pytest.mark.parametrize("k,n", [(1, 1), (1, 4), (2, 4), (3, 6), (4, 4)])
def test_every_blakley_quorum(k, n):
    scheme = Blakley(11)
    for key in (0, 10):
        shares = scheme.split_secret(key, n, k)
        for subset in combinations(shares, k):
            assert scheme.reconstruct(list(reversed(subset))) == key
        with pytest.raises(ValueError):
            scheme.reconstruct(shares[:k - 1])
        assert scheme.reconstruct(shares) == key


def test_blakley_every_secret_has_equally_many_completions():
    p, k = 7, 3
    shares = Blakley(p).split_secret(4, 4, k)
    for m in range(k):
        for planes in combinations(shares, m):
            counts = Counter(
                point[0] for point in product(range(p), repeat=k)
                if all((sum(a * b for a, b in zip(plane[:-1], point)) + plane[-1]) % p == 0
                       for plane in planes)
            )
            assert counts == {s: p**(k - 1 - m) for s in range(p)}


def test_invalid_blakley_equations_and_parameters():
    scheme = Blakley(11)
    shares = scheme.split_secret(7, 4, 2)
    with pytest.raises(ValueError):
        scheme.reconstruct([shares[0], shares[0]])
    with pytest.raises(ValueError):
        scheme.reconstruct(shares + [(*shares[0][:-1], (shares[0][-1] + 1) % 11)])
    for n, k, key in [(0, 0, 1), (3, 4, 1), (8, 4, 1), (3, 2, 11)]:
        with pytest.raises(ValueError):
            scheme.split_secret(key, n, k)
    with pytest.raises(ValueError):
        Blakley(15)


@pytest.mark.parametrize("factory", [XorScheme, CRTScheme])
@pytest.mark.parametrize("n,bits", [(1, 1), (3, 8), (6, 128), (10, 256)])
def test_all_party_roundtrip_and_invalid_coalitions(factory, n, bits):
    scheme = factory(n, bits)
    for key in (0, 1, (1 << bits) - 1):
        shares = scheme.split_secret(key)
        assert scheme.reconstruct(shares[::-1]) == key
        for missing in range(n):
            with pytest.raises(ValueError):
                scheme.reconstruct(shares[:missing] + shares[missing + 1:])
        with pytest.raises(ValueError):
            scheme.reconstruct([(n + 1, 0)] + shares[1:])
        if n > 1:
            with pytest.raises(ValueError):
                scheme.reconstruct([shares[1]] + shares[1:])
        with pytest.raises(ValueError):
            scheme.reconstruct([(1, -1)] + shares[1:])
    with pytest.raises(ValueError):
        scheme.split_secret(1 << bits)


def test_legacy_xor_and_declared_width(monkeypatch):
    widths = []

    def mask(bits):
        widths.append(bits)
        return (1 << bits) - 1

    monkeypatch.setattr("satellite_key_management.crypto.xor_scheme.secrets.randbits", mask)
    assert xor_combine(xor_split(0, 3, bits=256)) == 0
    assert widths == [256, 256]
    assert xor_combine(xor_split(2**300, 2)) == 2**300


def test_crt_public_parameters_and_privacy_bound_on_tiny_domain():
    scheme = CRTScheme(n=3, bits=1, margin_bits=1)
    for a, b in combinations(scheme.moduli, 2):
        assert gcd(a, b) == 1
    for pair in combinations(scheme.moduli, 2):
        observed_modulus = prod(pair)
        for secret in range(scheme.base):
            histogram = Counter((secret + scheme.base * a) % observed_modulus for a in range(scheme.lifts))
            assert len(histogram) == observed_modulus
            assert max(histogram.values()) - min(histogram.values()) <= 1
    invalid = scheme.product - 1
    with pytest.raises(ValueError):
        scheme.reconstruct([(i, invalid % m) for i, m in enumerate(scheme.moduli, 1)])
