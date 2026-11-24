"""Учебные проверки при пассивном чтении долей и наблюдении модельных окон."""
from copy import copy
from dataclasses import dataclass

from satellite_key_management.simulation.session import ReplayRejected


def compromise_m(sim, m):
    if not 0 <= m <= sim.n:
        raise ValueError("Число долей вне диапазона")
    key, count = sim.verified_key(range(1, m + 1))
    return key is not None, count


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
    tracker = AttackerTracker(model)
    for day in range(days):
        if day and day % refresh_every == 0:
            model.refresh()
        tracker.step(day, (), (day % model.n + 1,))
    return [row.shares for row in tracker.history]


def replay_attack(sim, t_min):
    packet = sim.seal(str(t_min).encode())
    members = range(1, sim.n + 1)
    ok = sim.receive(packet, members) is not None
    if not ok:
        return False, False
    try:
        sim.receive(packet, members)
    except ReplayRejected:
        return True, False
    return True, True


@dataclass(frozen=True)
class ExposureSample:
    minute: int
    visible: tuple[int, ...]
    shares: int
    threshold: int
    epoch: int
    quorum_reached: bool
    key_exposed: bool


class AttackerTracker:
    """Учёт заданных сценарием событий раскрытия долей без доступа к значениям."""

    def __init__(self, sim):
        self.sim = sim
        self.observations: dict[tuple[bytes, int], set[int]] = {}
        self.exposed_keys: set[bytes] = set()
        self._session_id = sim.session_id
        self._epoch = sim.epoch
        self.refreshes = 0
        self.history: list[ExposureSample] = []

    def step(self, minute, visible, exposed=()):
        session_id, epoch = self.sim.session_id, self.sim.epoch
        if session_id == self._session_id and self._epoch:
            self.refreshes += epoch - self._epoch
        self._session_id, self._epoch = session_id, epoch

        current = self.observations.setdefault((session_id, epoch), set())
        if self.sim.shares is not None:
            current.update(sid for sid in exposed if 1 <= sid <= self.sim.n)
        quorum = len(current) >= self.sim.k
        if quorum:
            self.exposed_keys.add(session_id)
        sample = ExposureSample(
            minute, tuple(sorted(set(visible))), len(current), self.sim.k,
            epoch, quorum, session_id in self.exposed_keys,
        )
        self.history.append(sample)
        return sample

    def time_to_compromise(self):
        return next((sample.minute for sample in self.history if sample.quorum_reached), None)

    @property
    def success_rate(self):
        """Доля отсчётов с контактом, в которых уже накоплен кворум."""
        contact_samples = [sample for sample in self.history if sample.visible]
        if not contact_samples:
            return 0.0
        return sum(sample.quorum_reached for sample in contact_samples) / len(contact_samples)


def track_visibility(sim, minutes, lat, lon, *, radius_km=None, refresh_every=None):
    """Трасса видимости для автономного графика, без событий раскрытия долей."""
    model = copy(sim)
    tracker = AttackerTracker(model)
    for minute in range(minutes):
        if model.shares is not None and refresh_every and minute and minute % refresh_every == 0:
            model.refresh()
        visible = model.leo.visible_at(minute, lat, lon, radius_km=radius_km)
        tracker.step(minute, visible)
    return tracker
