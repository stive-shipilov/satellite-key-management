"""Локальная модель доверенной раздачи, проверки долей и приёма пакетов."""

import secrets

from satellite_key_management.analysis.threshold import choose_threshold
from satellite_key_management.crypto.aes_gcm import decrypt, encrypt
from satellite_key_management.crypto.feldman_vss import FeldmanVSS


class SessionSimulator:
    def __init__(self, leo_model, n=12, k=8):
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

    def verified_key(self, visible):
        """Проверить идентификатор и обязательства до интерполяции."""
        available = sorted(set(visible).intersection(self.shares or {}))
        valid = [
            self.shares[i]
            for i in available
            if self.shares[i][0] == i
            and self.vss.verify_share(self.shares[i], self.commitments)
        ]
        if len(valid) < self.k:
            return None, len(valid)
        return self.vss.reconstruct(valid[: self.k]), len(valid)

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
        visible = sorted(set(visible))
        key, _ = self.verified_key(visible)
        if key is None:
            return None
        message = decrypt(
            key.to_bytes(16, "big"), *encrypted, sequence.to_bytes(8, "big")
        )
        valid_relays = [
            i
            for i in visible
            if i in self.shares
            and self.shares[i][0] == i
            and self.vss.verify_share(self.shares[i], self.commitments)
        ]
        if self.relay not in valid_relays:
            self.relay = valid_relays[0]
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
