"""Сценарий сессии: раздача долей, сбор кворума и выбор порога следующей сессии."""
import secrets

if __package__ == "simulation":  # запуск main.py из каталога пакета
    from analysis.threshold import choose_threshold
    from crypto.shamir import P, split_secret, reconstruct
else:
    from ..analysis.threshold import choose_threshold
    from ..crypto.shamir import P, split_secret, reconstruct


class SessionSimulator:
    def __init__(self, leo_model, n=12, k=8):
        if not 1 <= k <= n < P:
            raise ValueError("Требуется 1 ≤ k ≤ n < p")
        self.leo = leo_model
        self.n = n
        self.k = k
        self.secret_key = secrets.randbelow(P)
        self.shares = None
        self.current_k = k

    def distribute(self):
        """Раздать доли текущего ключа по Шамиру."""
        self.shares = dict(enumerate(split_secret(self.secret_key, self.n, self.k), 1))
        self.current_k = self.k
        return self.shares

    def collect_and_reconstruct(self, t_min, gs_lat=55.0, gs_lon=37.0):
        visible = set(self.leo.visible_at(t_min, gs_lat, gs_lon))
        shares = self.shares or {}
        collected = [shares[sid] for sid in visible if sid in shares]
        if len(collected) >= self.k:
            recovered = reconstruct(collected[:self.k])
            return recovered == self.secret_key, len(collected)
        return False, len(collected)

    def dynamic_k(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        """Рекомендация для новой сессии. При нехватке видимых узлов возвращает None."""
        visible = {i for i in self.leo.visible_at(t_min, gs_lat, gs_lon) if 1 <= i <= self.n}
        return choose_threshold(self.n, len(visible), threat_level, minimum=min(2, self.n))

    def distribute_adaptive(self, t_min, threat_level=0.0, gs_lat=55.0, gs_lon=37.0):
        """Начать новую сессию или отложить её, сохранив ранее выданные доли."""
        threshold = self.dynamic_k(t_min, threat_level, gs_lat, gs_lon)
        if threshold is None:
            return None
        key = secrets.randbelow(P)
        shares = dict(enumerate(split_secret(key, self.n, threshold), 1))
        self.secret_key, self.k, self.current_k, self.shares = key, threshold, threshold, shares
        return shares
