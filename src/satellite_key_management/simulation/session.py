"""Локальная модель доверенной раздачи, проверки долей и приёма пакетов.

Схема разделения секрета задаётся параметром `scheme`:
    "feldman_vss" (по умолчанию) — проверяемая раздача, как в прежней версии;
    "shamir", "blakley"          — доверенный дилер, p из FIELDS;
    "xor", "crt"                 — требуют k = n.

Для обратной совместимости `self.vss` остаётся FeldmanVSS(), а `self.scheme`
— SchemeAdapter; `commitments` есть только при feldman_vss.
"""
from __future__ import annotations

import secrets

from satellite_key_management.analysis.threshold import choose_threshold
from satellite_key_management.crypto.aes_gcm import decrypt, encrypt
from satellite_key_management.crypto.threshold_sig import verify
from satellite_key_management.crypto.feldman_vss import FeldmanVSS
from satellite_key_management.crypto.schemes import SCHEMES, SchemeAdapter


class SessionSimulator:
    def __init__(self, leo_model, n=12, k=8, *, scheme: str = "feldman_vss",
                 initial_signer=None, bits: int = 128):
        if scheme not in SCHEMES:
            raise ValueError(f"Неизвестная схема: {scheme!r}")
        if not 1 <= k <= n:
            raise ValueError("Требуется 1 ≤ k ≤ n")

        self.initial_signer = initial_signer
        self.scheme_name = scheme
        self.leo = leo_model
        self.n, self.k = n, k
        self.bits = bits

        # Адаптер схемы (создаётся один раз; split/reconstruct — на нём).
        self.scheme = SchemeAdapter(scheme, n, k, bits)
        # Для обратной совместимости: attacks.py и dashboard.py смотрят на .vss.
        self.vss = self.scheme.impl if scheme == "feldman_vss" else FeldmanVSS()

        self.secret_key = secrets.randbelow(2**bits)
        self.shares: dict[int, tuple] | None = None
        self.current_k = k
        self.commitments: tuple[int, ...] = ()
        self.verifiable = scheme == "feldman_vss"
        self.epoch = 0
        self.relay = None
        self.last_received = -1
        self.next_sequence = 0

    def distribute(self):
        ss = self.scheme.split(self.secret_key)
        # ss.shares = dict[sid -> int]; приводим к единому формату проекта:
        # self.shares = dict[sid -> (sid, value)]
        self.shares = {sid: (sid, v) for sid, v in ss.shares.items()}
        self.commitments = ss.commitments
        self.current_k = self.k
        self.epoch += 1
        return self.shares

    def refresh(self):
        if self.shares is None:
            raise ValueError("Сначала раздайте доли")
        if self.scheme_name not in ("feldman_vss", "shamir"):
            raise NotImplementedError(
                f"refresh не поддержан для схемы {self.scheme_name!r}; "
                "используйте distribute_adaptive() для полной перераздачи"
            )
        delta_ss = self.scheme.split(0)
        # self.shares[sid] = (sid, int); delta_ss.shares[sid] = int
        updated = {
            sid: (sid, (self.shares[sid][1] + delta_ss.shares[sid]) % self.scheme.p)
            for sid in self.shares
        }
        if self.verifiable:
            self.commitments = tuple(
                a * b % self.scheme.p
                for a, b in zip(self.commitments, delta_ss.commitments)
            )
        self.shares = updated
        self.epoch += 1

    def _valid_shares(self, visible):
        if self.shares is None:
            return []
        valid = []
        for sid in sorted(set(visible).intersection(self.shares)):
            share = self.shares[sid]
            if self.scheme_name == "blakley":
                # share = (sid, plane), plane = tuple[int, ...]
                if not (isinstance(share, tuple) and len(share) == 2
                        and isinstance(share[0], int)
                        and isinstance(share[1], tuple)
                        and all(type(v) is int for v in share[1])):
                    continue
            else:
                if not (isinstance(share, (tuple, list)) and len(share) == 2
                        and all(type(v) is int for v in share) and share[0] == sid):
                    continue
            if not self.scheme.verify_share(sid, share, self._as_ss()):
                continue
            valid.append(share)
        return valid

    def _as_ss(self):
        """Мини-снимок ShareSet для verify_share (без повторного split)."""
        from satellite_key_management.crypto.schemes import ShareSet
        return ShareSet(self.scheme_name, self.shares or {},
                        self.commitments, self.verifiable)

    def verified_key(self, visible):
        valid = self._valid_shares(visible)
        if len(valid) < self.k:
            return None, len(valid)
        key = self.scheme.reconstruct(valid[:self.k])
        if not self.scheme.verify_reconstructed(key, self._as_ss()):
            return None, len(valid)
        return key, len(valid)

    def collect_and_reconstruct(self, t_min, gs_lat=55.0, gs_lon=37.0):
        key, count = self.verified_key(self.leo.visible_at(t_min, gs_lat, gs_lon))
        return key is not None, count

    # -- канал -------------------------------------------------------------
    def _key_bytes(self, key_int: int) -> bytes:
        return key_int.to_bytes(16, "big")  # AES-128 по контракту seal/receive

    def seal(self, payload):
        sequence = self.next_sequence
        self.next_sequence += 1
        aad = sequence.to_bytes(8, "big")
        return sequence, encrypt(self._key_bytes(self.secret_key), payload, aad)

    def receive(self, packet, visible):
        sequence, encrypted = packet
        if sequence <= self.last_received:
            raise ValueError("Повтор или устаревший номер пакета")
        valid = self._valid_shares(visible)
        if len(valid) < self.k:
            return None
        key = self.scheme.reconstruct(valid[:self.k])
        message = decrypt(self._key_bytes(key), *encrypted, sequence.to_bytes(8, "big"))
        if self.last_received < 0 and self.initial_signer is not None:
            if len(message) < 96 or not verify(message[:-96], message[-96:], self.initial_signer):
                raise ValueError("Неверная пороговая подпись первого пакета")
            message = message[:-96]
        if all(sid != self.relay for sid, _ in valid):
            self.relay = valid[0][0]
        self.last_received = sequence
        return message

    # -- динамический порог ------------------------------------------------
    def dynamic_k(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        visible = {i for i in self.leo.visible_at(t_min, gs_lat, gs_lon)
                   if 1 <= i <= self.n}
        return choose_threshold(self.n, len(visible), threat_level)

    def distribute_adaptive(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        threshold = self.dynamic_k(t_min, threat_level, gs_lat, gs_lon)
        if threshold is None:
            return None
        self.secret_key = secrets.randbelow(2**self.bits)
        self.k = threshold
        self.last_received, self.next_sequence, self.relay = -1, 0, None
        return self.distribute()