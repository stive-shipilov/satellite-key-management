"""Сравнение доставки и раскрытия долей на общей трассе видимости."""

from dataclasses import dataclass
from random import Random

from satellite_key_management.attacks.attacks import AttackerTracker
from satellite_key_management.simulation.session import SessionSimulator


@dataclass(frozen=True)
class OrbitalResult:
    policy: str
    exposure_interval: int
    first_quorum_minute: int | None
    duration: int
    delivered: int
    longest_outage: int
    refreshes: int
    fixed_threshold: int | None
    threat: float | None
    refresh_interval: int | None
    active_key_exposed: bool


def compare_orbital_sessions(leo, minutes, *, k, threat, refresh_every=30):
    if min(minutes, refresh_every) < 1:
        raise ValueError("Длительность и период обновления должны быть положительными")
    trace = [leo.visible_at(minute) for minute in range(minutes)]
    n = len(leo.sats)

    # Это входные данные эксперимента. Каждое событие обозначает чтение доли
    # одного узла в данной эпохе и задаётся независимо от видимости станции.
    node_order = list(range(1, n + 1))
    Random(7).shuffle(node_order)
    schedules = {}
    for interval in (15, 8, 10, 20):
        schedules[interval] = {
            minute: (node_order[index % n],)
            for index, minute in enumerate(range(1, minutes, interval))
        }

    results = []
    for policy in ("fixed", "fixed_refresh", "adaptive_refresh"):
        adaptive = policy == "adaptive_refresh"
        refresh_interval = None if policy == "fixed" else refresh_every
        sim = SessionSimulator(leo, n=n, k=k)
        if not adaptive:
            sim.distribute()
        trackers = {interval: AttackerTracker(sim) for interval in schedules}
        delivered = outage = longest_outage = 0
        for minute, visible in enumerate(trace):
            previous_epoch = sim.epoch
            if adaptive:
                candidate = sim.threshold_for(visible, threat)
                if candidate is not None and (sim.shares is None or candidate != sim.k):
                    sim.distribute_adaptive(minute, threat, visible=visible)
            if (refresh_interval and sim.shares is not None and sim.epoch == previous_epoch
                    and minute and minute % refresh_interval == 0):
                sim.refresh()
            for interval, tracker in trackers.items():
                tracker.step(minute, visible, schedules[interval].get(minute, ()))

            message = f"telemetry/minute={minute}".encode()
            if sim.shares is not None and sim.receive(sim.seal(message), visible) == message:
                delivered += 1
                outage = 0
            else:
                outage += 1
                longest_outage = max(outage, longest_outage)

        for interval, tracker in trackers.items():
            results.append(OrbitalResult(
                policy, interval, tracker.time_to_compromise(), minutes,
                delivered, longest_outage, tracker.refreshes,
                None if adaptive else k, threat if adaptive else None, refresh_interval,
                tracker.history[-1].key_exposed,
            ))
        if policy == "fixed_refresh":
            reference_tracker = trackers[15]

    return results, reference_tracker
