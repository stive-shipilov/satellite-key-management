"""Атаки на схему разделения секрета."""
import secrets
from crypto.shamir import reconstruct, P

from satellite_key_management.visualization.animation_plotly import COVER_RADIUS


def compromise_m(sim, m):
    """Компрометация m спутников: сколько долей у атакующего, восстановим ли ключ."""
    collected = [sim.shares[sid] for sid in list(sim.shares)[:m]]
    if m >= sim.k:
        recovered = reconstruct(collected[:sim.k])
        return recovered == sim.secret_key, m
    return False, m

def evil_dealer(sim, tamper_sid=3):
    """Злой дилер подменяет одну долю. VSS должен поймать (тут — заглушка проверки)."""
    bad = dict(sim.shares)
    sid, (x, y) = list(bad.items())[tamper_sid - 1]
    bad[sid] = (x, (y + 1) % P)         # подмена
    # Простая проверка: пересобрать и сверить с известным секретом
    recovered = reconstruct(list(bad.values())[:sim.k])
    caught = recovered != sim.secret_key
    return caught, recovered

def share_accumulation(sim, days=30, refresh_every=5):
    """Накопление долей во времени; proactive refresh обнуляет старые доли."""
    history = []
    for day in range(days):
        if day % refresh_every == 0:
            sim.distribute()            # refresh: новые доли
        history.append(len(sim.shares))
    return history

def replay_attack(sim, t_min):
    """Replay: повтор старого сообщения. Проверка nonce/счётчика (заглушка)."""
    nonce = secrets.token_bytes(12)
    seen = set()
    def send(n):
        if n in seen:
            return False                # replay поймали
        seen.add(n)
        return True
    ok1 = send(nonce)
    ok2 = send(nonce)                   # повтор
    return ok1, ok2


"""Трекер атакующего: накопление долей, счётчики, time-to-compromise."""
import math

class AttackerTracker:
    def __init__(self, sim, attacker_lat=-30.0, attacker_lon=-60.0, k_target=None):
        self.sim = sim
        self.lat = attacker_lat
        self.lon = attacker_lon
        self.k_target = k_target if k_target is not None else sim.k
        self.shares_collected = set()      # sid'ы, чьи доли уже утекли
        self.attempts = 0
        self.successes = 0                 # «успех» = утекла новая доля
        self.failures = 0                  # попытки, где не хватило до k
        self.history = []                  # (t, n_shares, n_visible)

    def step(self, t_min):
        """Один шаг времени: проверить, кто в зоне, обновить счётчики."""
        in_zone = self.sim.leo.visible_at(t_min, self.lat, self.lon, radius_km=COVER_RADIUS)
        # доли утекают с каждого спутника в зоне (один раз)
        new_shares = [sid for sid in in_zone if sid not in self.shares_collected]
        if in_zone:
            self.attempts += 1
        if new_shares:
            self.successes += len(new_shares)
            self.shares_collected.update(new_shares)
        if len(self.shares_collected) < self.k_target and in_zone:
            self.failures += 1
        self.history.append((t_min, len(self.shares_collected), len(in_zone)))
        return {
            "in_zone": in_zone,
            "n_visible": len(in_zone),
            "n_shares": len(self.shares_collected),
            "k": self.k_target,
            "compromised": len(self.shares_collected) >= self.k_target,
        }

    def time_to_compromise(self, times):
        """Минуты до набора k долей или inf, если не набирается."""
        for t, n_shares, _ in self.history:
            if n_shares >= self.k_target:
                return t
        return math.inf

    @property
    def success_rate(self):
        return self.successes / self.attempts if self.attempts else 0.0