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
from dataclasses import dataclass
from uuid import uuid4

from satellite_key_management.analysis.threshold import choose_threshold
from satellite_key_management.crypto.aes_gcm import decrypt, encrypt
from satellite_key_management.crypto.threshold_sig import verify
from satellite_key_management.crypto.feldman_vss import FeldmanVSS
from satellite_key_management.crypto.schemes import SCHEMES, SchemeAdapter, ShareSet


class ReplayRejected(ValueError):
    """Пакет уже принят или вышел за границу окна приёма."""


@dataclass(frozen=True)
class Reception:
    message: bytes | None
    valid_shares: int


class SessionSimulator:
    def __init__(self, leo_model, n=12, k=8, *, scheme: str = "feldman_vss",
                 initial_signer=None, bits: int = 128, replay_window: int = 64):
        if scheme not in SCHEMES:
            raise ValueError(f"Неизвестная схема: {scheme!r}")
        if not 1 <= k <= n:
            raise ValueError("Требуется 1 ≤ k ≤ n")
        if replay_window < 1:
            raise ValueError("Окно приёма должно быть положительным")

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
        self.session_id = uuid4().bytes
        self.shares: dict[int, tuple] | None = None
        self.current_k = k
        self._commitments: tuple[int, ...] = ()
        self.verifiable = scheme == "feldman_vss"
        self.epoch = 0
        self._replay_mask = (1 << replay_window) - 1
        self.replay_window = replay_window
        self._reset_channel()

    def _reset_channel(self):
        self.relay = None
        self.last_received = -1
        self.next_sequence = 0
        self._received = 0

    @property
    def commitments(self):
        """Единый снимок обязательств от доверенного локального дилера."""
        return self._commitments

    def distribute(self):
        ss = self.scheme.split(self.secret_key)
        return self._install_shares(ss)

    def _install_shares(self, ss):
        self.shares = {sid: (sid, v) for sid, v in ss.shares.items()}
        self._commitments = ss.commitments
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
        active = self._valid_shares(self.shares)
        if len(active) != self.n:
            raise ValueError("Обновление требует полный набор исправных долей")
        updated = {sid: (value + delta_ss.shares[sid]) % self.scheme.p
                   for sid, value in active}
        commitments = ()
        if self.verifiable:
            if (len(delta_ss.commitments) != self.k or delta_ss.commitments[0] != 1):
                raise ValueError("Обновление должно быть раздачей нулевого секрета")
            commitments = tuple(
                a * b % self.vss.p
                for a, b in zip(self.commitments, delta_ss.commitments)
            )
            if not all(self.vss.verify_share((sid, value), commitments)
                       for sid, value in updated.items()):
                raise ValueError("Обновлённые доли не согласованы с обязательствами")
        self._install_shares(ShareSet(self.scheme_name, updated, commitments, self.verifiable))

    def _valid_shares(self, visible):
        if self.shares is None:
            return []
        valid = []
        ss = self._as_ss()
        for sid in sorted(set(visible).intersection(self.shares)):
            share = self.shares[sid]
            if self.scheme_name == "blakley":
                # share = (sid, plane), plane = tuple[int, ...]
                if not (isinstance(share, tuple) and len(share) == 2
                        and share[0] == sid
                        and isinstance(share[1], tuple)
                        and all(type(v) is int for v in share[1])):
                    continue
            else:
                if not (isinstance(share, (tuple, list)) and len(share) == 2
                        and all(type(v) is int for v in share) and share[0] == sid):
                    continue
            if not self.scheme.verify_share(sid, share, ss):
                continue
            valid.append((sid, share[1]))
        return valid

    def _as_ss(self):
        """Мини-снимок ShareSet для verify_share (без повторного split)."""
        return ShareSet(self.scheme_name, self.shares or {},
                        self.commitments, self.verifiable)

    def verified_key(self, visible):
        valid = self._valid_shares(visible)
        return self._recover_verified(valid), len(valid)

    def _recover_verified(self, valid):
        if len(valid) < self.k:
            return None
        key = self.scheme.reconstruct(valid[:self.k])
        if not self.scheme.verify_reconstructed(key, self._as_ss()):
            return None
        return key

    def collect_and_reconstruct(self, t_min, gs_lat=55.0, gs_lon=37.0):
        key, count = self.verified_key(self.leo.visible_at(t_min, gs_lat, gs_lon))
        return key is not None, count

    # -- канал -------------------------------------------------------------
    def _key_bytes(self, key_int: int) -> bytes:
        return key_int.to_bytes(16, "big")  # AES-128 по контракту seal/receive

    def _packet_context(self, sequence):
        if type(sequence) is not int or not 0 <= sequence < 2**64:
            raise ValueError("Номер пакета вне диапазона")
        return self.session_id + sequence.to_bytes(8, "big")

    def signing_payload(self, sequence, payload):
        return b"satellite-telemetry/initial/v1\x00" + self._packet_context(sequence) + payload

    def seal(self, payload):
        sequence = self.next_sequence
        encrypted = encrypt(self._key_bytes(self.secret_key), payload, self._packet_context(sequence))
        self.next_sequence += 1
        return sequence, encrypted

    def receive(self, packet, visible):
        return self.receive_with_status(packet, visible).message

    def receive_with_status(self, packet, visible) -> Reception:
        sequence, encrypted = packet
        aad = self._packet_context(sequence)
        offset = self.last_received - sequence
        if offset >= self.replay_window or (offset >= 0 and self._received & (1 << offset)):
            raise ReplayRejected("Повтор или устаревший номер пакета")
        valid = self._valid_shares(visible)
        key = self._recover_verified(valid)
        if key is None:
            return Reception(None, len(valid))
        message = decrypt(self._key_bytes(key), *encrypted, aad)
        if self.last_received < 0 and self.initial_signer is not None:
            if len(message) < 96 or not verify(
                self.signing_payload(sequence, message[:-96]), message[-96:], self.initial_signer
            ):
                raise ValueError("Неверная пороговая подпись первого пакета")
            message = message[:-96]
        if all(sid != self.relay for sid, _ in valid):
            self.relay = valid[0][0]
        if offset < 0:
            self._received = 0 if -offset >= self.replay_window else self._received << -offset
            self._received = (self._received | 1) & self._replay_mask
            self.last_received = sequence
        else:
            self._received |= 1 << offset
        return Reception(message, len(valid))

    # -- динамический порог ------------------------------------------------
    def dynamic_k(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        return self.threshold_for(self.leo.visible_at(t_min, gs_lat, gs_lon), threat_level)

    def threshold_for(self, visible, threat_level):
        count = len({i for i in visible if 1 <= i <= self.n})
        minimum = self.n if self.scheme_name in ("xor", "crt") else None
        return choose_threshold(self.n, count, threat_level, minimum)

    def distribute_adaptive(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0,
                            *, visible=None):
        if visible is None:
            visible = self.leo.visible_at(t_min, gs_lat, gs_lon)
        threshold = self.threshold_for(visible, threat_level)
        if threshold is None:
            return None
        scheme = SchemeAdapter(self.scheme_name, self.n, threshold, self.bits)
        return self._reissue(scheme)

    def rotate_key(self):
        """Начать новый сеанс с тем же порогом по решению доверенного дилера."""
        return self._reissue(self.scheme)

    def _reissue(self, scheme):
        key = secrets.randbelow(2**self.bits)
        shares = scheme.split(key)
        session_id = uuid4().bytes
        self.scheme = scheme
        if self.verifiable:
            self.vss = scheme.impl
        self.secret_key = key
        self.session_id = session_id
        self.k = scheme.k
        self._reset_channel()
        return self._install_shares(shares)
