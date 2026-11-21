"""Сценарий сессии: раздача долей, сбор k, восстановление ключа, AES-GCM."""
import secrets
from crypto.shamir import split_secret, reconstruct
from crypto.xor_scheme import xor_split, xor_combine

class SessionSimulator:
    def __init__(self, leo_model, n=12, k=8):
        self.leo = leo_model
        self.n = n
        self.k = k
        self.secret_key = secrets.randbits(128)
        self.shares = None
        self.current_k = k

    def distribute(self):
        """Раздать доли спутникам (по Шамиру)."""
        self.shares = {sid: sh for sid, sh in
                       zip(range(1, self.n + 1), split_secret(self.secret_key, self.n, self.k))}
        return self.shares

    def collect_and_reconstruct(self, t_min, gs_lat=55.0, gs_lon=37.0):
        visible = self.leo.visible_at(t_min, gs_lat, gs_lon)
        collected = [self.shares[sid] for sid in visible if sid in self.shares]
        if len(collected) >= self.k:
            recovered = reconstruct(collected[:self.k])
            return recovered == self.secret_key, len(collected)
        return False, len(collected)

    def dynamic_k(self, t_min, threat_level=0.0):
        """Динамический порог: чем больше видимых спутников и угроза — тем выше k."""
        visible = len(self.leo.visible_at(t_min))
        base = max(1, visible // 2)
        self.current_k = min(self.n, base + int(threat_level * visible))
        return self.current_k