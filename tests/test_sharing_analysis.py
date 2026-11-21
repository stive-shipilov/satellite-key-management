from itertools import product
from types import SimpleNamespace

import pytest

from satellite_key_management.analysis.benchmark import measure
from satellite_key_management.analysis.threshold import choose_threshold
from satellite_key_management.simulation.session import SessionSimulator


def test_measured_sizes_and_actual_thresholds():
    rows = measure(bits=128, n=6, k=3, repeats=1, number=1)
    assert [r.threshold for r in rows] == [3, 3, 6, 6]
    assert [r.share_bytes for r in rows] == [33, 128, 17, 26]
    assert [r.safe_shares for r in rows] == [2, 2, 5, 5]
    assert all(min(r.split_us, r.recover_us) > 0 for r in rows)


def test_decimal_threat_on_exact_budget_boundary():
    assert choose_threshold(51, 8, 0.14) == 8


def test_policy_is_feasible_and_monotone():
    for n in range(2, 16):
        for visible in range(n + 1):
            choices = [choose_threshold(n, visible, i / 10) for i in range(11)]
            # Недостижимый порог сортируем после любого допустимого.
            ordered = [n + 1 if k is None else k for k in choices]
            assert sorted(ordered) == ordered
            for k in choices:
                assert k is None or 2 <= k <= visible
    assert choose_threshold(6, 5, 1) is None
    assert choose_threshold(6, 6, 1) == 6
    for visible, threat in product((-1, 7), (-0.1, 1.1)):
        with pytest.raises(ValueError):
            choose_threshold(6, visible, threat)


def test_session_reissues_for_new_threshold_and_waits_without_quorum(monkeypatch):
    class Sky:
        def visible_at(self, t, lat, lon):
            assert (lat, lon) == (55.0, 37.0)
            return [1, 2, 2, 3, 7] if t == 0 else [1]

    keys = iter([7, 9, 8])
    monkeypatch.setattr("satellite_key_management.simulation.session.secrets",
                        SimpleNamespace(randbelow=lambda p: next(keys)))
    sim = SessionSimulator(Sky(), n=6, k=4)
    sim.distribute()
    assert sim.dynamic_k(0, 0.2) == 2
    assert sim.k == sim.current_k == 4
    assert sim.collect_and_reconstruct(0) == (False, 3)
    sim.distribute_adaptive(0, 0.2)
    assert sim.secret_key == 9 and sim.k == sim.current_k == 2
    assert sim.collect_and_reconstruct(0) == (True, 3)
    active_shares = sim.shares
    assert sim.distribute_adaptive(1) is None
    assert sim.shares is active_shares and sim.current_k == sim.k == 2
    assert sim.secret_key == 9 and sim.collect_and_reconstruct(0) == (True, 3)
    sim.distribute_adaptive(0, 0.4)
    assert sim.secret_key == 8 and sim.k == 3 and sim.collect_and_reconstruct(0)[0]
