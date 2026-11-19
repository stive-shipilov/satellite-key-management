"""Учебные проверки при пассивном чтении долей и наблюдении модельных окон."""
import math
from copy import copy


def compromise_m(sim, m):
    if not 0 <= m <= sim.n:
        raise ValueError("Число долей вне диапазона")
    key, count = sim.verified_key(range(1, m + 1))
    return key is not None and sim.vss.verify_reconstructed(key, sim.commitments), count


def evil_dealer(sim, tamper_sid=3):
    """Проверить контрольный отрицательный пример по публичным обязательствам."""
    i, value = sim.shares[tamper_sid]
    candidate = (i, (value + 1) % sim.vss.q)
    return not sim.vss.verify_share(candidate, sim.commitments), None


def share_accumulation(sim, days=30, refresh_every=5):
    """Одно наблюдение в день. Между эпохами набор наблюдений сбрасывается."""
    if refresh_every < 1 or days < 0:
        raise ValueError("Некорректный период")
    model = copy(sim)
    model.distribute()
    current = set()
    history = []
    for day in range(days):
        if day and day % refresh_every == 0:
            model.refresh()
            current.clear()
        current.add(day % model.n + 1)
        history.append(len(current))
    return history


def replay_attack(sim, t_min):
    packet = sim.seal(str(t_min).encode())
    members = range(1, sim.n + 1)
    ok = sim.receive(packet, members) is not None
    if not ok:
        return False, False
    try:
        sim.receive(packet, members)
    except ValueError:
        return True, False
    return True, True


class AttackerTracker:
    def __init__(self, sim, attacker_lat=-30.0, attacker_lon=-60.0,
                 k_target=None, refresh_every=None):
        self.sim = sim
        self.lat = attacker_lat
        self.lon = attacker_lon
        self.k_target = k_target if k_target is not None else sim.k
        self.refresh_every = refresh_every
        self.shares_collected = set()
        self.attempts = 0
        self.successes = 0
        self.failures = 0
        self.refreshes = 0
        self.history = []

    def step(self, t_min):
        # proactive refresh: обнуляем накопленные доли
        refreshed = False
        if self.refresh_every and self.history:
            crossed = t_min // self.refresh_every - self.history[-1][0] // self.refresh_every
            if crossed > 0:
                self.shares_collected.clear()
                self.refreshes += crossed
                refreshed = True

        in_zone = self.sim.leo.visible_at(t_min, self.lat, self.lon, radius_km=2500)
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
            "refreshed": refreshed,
        }

    def time_to_compromise(self, times):
        for t, n_shares, _ in self.history:
            if n_shares >= self.k_target:
                return t
        return math.inf

    @property
    def success_rate(self):
        """Доля отсчётов с контактом, в которых уже накоплен кворум."""
        return (self.attempts - self.failures) / self.attempts if self.attempts else 0.0
