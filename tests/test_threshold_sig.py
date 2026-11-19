import pytest
from py_ecc.bls import G2Basic

from crypto.threshold_sig import (
    VerificationKeys,
    combine_signs,
    generate_key,
    sign_share,
    verify,
)


@pytest.fixture(scope="module")
def signing_group():
    keys, shares = generate_key(4, 2)
    return keys, [sign_share(s, b"frame-42") for s in shares]


def test_independent_keys(signing_group):
    assert generate_key(4, 2)[0].public_key != signing_group[0].public_key


def test_distinct_quorums_same_standard_signature(signing_group):
    keys, parts = signing_group
    sig = combine_signs(parts[::2], b"frame-42", keys)
    assert sig == combine_signs(parts[1::2], b"frame-42", keys)
    assert G2Basic.Verify(keys.public_key, b"frame-42", sig)
    assert not verify(b"other", sig, keys.public_key)
    assert not verify(b"frame-42", sig, generate_key(1, 1)[0].public_key)


def test_bad_quorums(signing_group):
    keys, parts = signing_group
    for quorum in (parts[:1], [parts[0], parts[0]], [(2, parts[0][1]), parts[2]]):
        with pytest.raises(ValueError):
            combine_signs(quorum, b"frame-42", keys)
    with pytest.raises(ValueError):
        combine_signs(parts[:2], b"other", keys)


def test_interpolation_against_known_full_key():
    # f(x) = 42 + 5x. Координатор получает только частичные подписи.
    message = b"threshold reference"
    shares = [(i, 42 + 5 * i) for i in (1, 2, 3)]
    keys = VerificationKeys(
        2, G2Basic.SkToPk(42), tuple(G2Basic.SkToPk(y) for _, y in shares)
    )
    actual = combine_signs(
        [sign_share(shares[i], message) for i in (0, 2)], message, keys
    )
    assert actual == G2Basic.Sign(42, message)
