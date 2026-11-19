"""Локальная модель доверенной раздачи, проверки долей и приёма пакетов."""

import secrets

from satellite_key_management.analysis.threshold import choose_threshold
from satellite_key_management.crypto.aes_gcm import decrypt, encrypt
from satellite_key_management.crypto.threshold_sig import verify
from satellite_key_management.crypto.feldman_vss import FeldmanVSS


class SessionSimulator:
    def __init__(self, leo_model, n=12, k=8, *, initial_signer=None):
        self.initial_signer = initial_signer
        self.vss = FeldmanVSS()
        if not 1 <= k <= n < self.vss.q:
            raise ValueError("Требуется 1 ≤ k ≤ n < q")
        self.leo = leo_model
        self.n, self.k = n, k
        self.secret_key = secrets.randbelow(2**128)
        self.shares = None
        self.current_k = k
        self.commitments = ()
        self.epoch = 0
        self.relay = None
        self.last_received = -1
        self.next_sequence = 0

    def distribute(self):
        shares, commitments = self.vss.dealer_commit(self.secret_key, self.n, self.k)
        self.shares = {share[0]: share for share in shares}
        self.commitments = tuple(commitments)
        self.current_k = self.k
        self.epoch += 1
        return self.shares

    def refresh(self):
        """Прибавить проверяемую раздачу нуля, сохранив ключ и окно защиты от повторов."""
        if self.shares is None:
            raise ValueError("Сначала раздайте доли")
        delta, commitments = self.vss.dealer_commit(0, self.n, self.k)
        updated = {i: (i, (self.shares[i][1] + y) % self.vss.q) for i, y in delta}
        self.commitments = tuple(
            a * b % self.vss.p for a, b in zip(self.commitments, commitments)
        )
        self.shares = updated
        self.epoch += 1

    def _valid_shares(self, visible):
        valid = []
        for sid in sorted(set(visible).intersection(self.shares or {})):
            share = self.shares[sid]
            if (isinstance(share, (tuple, list)) and len(share) == 2
                    and all(type(v) is int for v in share) and share[0] == sid
                    and self.vss.verify_share(share, self.commitments)):
                valid.append(share)
        return valid

    def verified_key(self, visible):
        valid = self._valid_shares(visible)
        key = self.vss.reconstruct(valid[:self.k]) if len(valid) >= self.k else None
        return key, len(valid)

    def collect_and_reconstruct(self, t_min, gs_lat=55.0, gs_lon=37.0):
        key, count = self.verified_key(self.leo.visible_at(t_min, gs_lat, gs_lon))
        return key is not None and self.vss.verify_reconstructed(
            key, self.commitments
        ), count

    def seal(self, payload):
        sequence = self.next_sequence
        self.next_sequence += 1
        aad = sequence.to_bytes(8, "big")
        return sequence, encrypt(self.secret_key.to_bytes(16, "big"), payload, aad)

    def receive(self, packet, visible):
        """Упорядоченный канал. Продвигает счётчик только после проверки тега."""
        sequence, encrypted = packet
        if sequence <= self.last_received:
            raise ValueError("Повтор или устаревший номер пакета")
        valid = self._valid_shares(visible)
        if len(valid) < self.k:
            return None
        key = self.vss.reconstruct(valid[:self.k])
        message = decrypt(key.to_bytes(16, "big"), *encrypted, sequence.to_bytes(8, "big"))
        if self.last_received < 0 and self.initial_signer is not None:
            if len(message) < 96 or not verify(message[:-96], message[-96:], self.initial_signer):
                raise ValueError("Неверная пороговая подпись первого пакета")
            message = message[:-96]
        if all(sid != self.relay for sid, _ in valid):
            self.relay = valid[0][0]
        self.last_received = sequence
        return message

    def dynamic_k(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        visible = {
            i for i in self.leo.visible_at(t_min, gs_lat, gs_lon) if 1 <= i <= self.n
        }
        return choose_threshold(self.n, len(visible), threat_level)

    def distribute_adaptive(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        threshold = self.dynamic_k(t_min, threat_level, gs_lat, gs_lon)
        if threshold is None:
            return None
        self.secret_key = secrets.randbelow(2**128)
        self.k = threshold
        self.last_received, self.next_sequence, self.relay = -1, 0, None
        return self.distribute()
