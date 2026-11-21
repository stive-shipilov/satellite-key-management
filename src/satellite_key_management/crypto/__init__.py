"""Криптографическое ядро: схемы разделения секрета и механизмы защиты ключа.

Публичный API модуля ``crypto``:

Разделение секрета (Shamir):
    * ``ShamirGFp`` / ``ShamirGF256`` — классы схемы Шамира над GF(p) и GF(2^8);
    * ``split`` / ``combine`` — единая точка входа для обоих полей;
    * ``split_secret`` / ``reconstruct`` / ``P`` — обратная совместимость
      (сигнатуры из старого кода, используются в simulation/ и attacks/).

Верифицируемое разделение (Feldman VSS):
    * ``FeldmanVSS``, ``dealer_commit``, ``verify_share``, ``reconstruct_shares``.

Proactive refresh:
    * ``refresh_shares`` (GF(p)), ``refresh_shares_gf256`` (GF(2^8)), ``refresh``.

Шифрование трафика (AES-GCM):
    * ``AESGCMCipher``, ``encrypt``, ``decrypt``.

Пороговая подпись (threshold Schnorr):
    * ``ThresholdSchnorr``, ``generate_key``, ``sign_share``, ``combine_signs``, ``verify``.
"""

# --- Shamir над GF(p) и GF(2^8) ---------------------------------------------
from .shamir import (
    P,
    ShamirGF256,
    ShamirGFp,
    combine,
    reconstruct,
    split,
    split_secret,
)

# --- Feldman VSS -------------------------------------------------------------
from .feldman_vss import (
    FeldmanVSS,
    dealer_commit,
    reconstruct_shares,
    verify_share,
)

# --- Proactive refresh -------------------------------------------------------
from .proactive_refresh import (
    refresh,
    refresh_shares,
    refresh_shares_gf256,
)

# --- AES-GCM -----------------------------------------------------------------
from .aes_gcm import AESGCMCipher, InvalidTag, decrypt, encrypt

# --- Пороговая подпись -------------------------------------------------------
from .threshold_sig import (
    ThresholdSchnorr,
    combine_signs,
    generate_key,
    sign_share,
    verify,
)

__all__ = [
    # Shamir
    "P", "ShamirGFp", "ShamirGF256", "split", "combine", "split_secret", "reconstruct",
    # VSS
    "FeldmanVSS", "dealer_commit", "verify_share", "reconstruct_shares",
    # Refresh
    "refresh", "refresh_shares", "refresh_shares_gf256",
    # AES-GCM
    "AESGCMCipher", "encrypt", "decrypt", "InvalidTag",
    # Threshold signature
    "ThresholdSchnorr", "generate_key", "sign_share", "combine_signs", "verify",
]