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


def test_single_satellite_threshold():
    assert choose_threshold(1, 1, 1) == 1
    assert choose_threshold(1, 0, 0) is None
    with pytest.raises(ValueError):
        choose_threshold(1, 1, 0, minimum=2)


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


@pytest.mark.parametrize("name", ["xor", "crt"])
def test_all_party_schemes_keep_their_threshold(name):
    sim = SessionSimulator(None, n=3, k=3, scheme=name)
    sim.distribute()
    session_id = sim.session_id
    assert sim.distribute_adaptive(0, visible=[1, 2]) is None
    assert sim.session_id == session_id
    sim.distribute_adaptive(1, visible=[1, 2, 3])
    assert sim.session_id != session_id and sim.k == sim.scheme.k == 3
    assert sim.receive(sim.seal(b"message"), [1, 2, 3]) == b"message"


def test_failed_redistribution_leaves_active_session_usable(monkeypatch):
    from satellite_key_management.crypto.schemes import SchemeAdapter

    sim = SessionSimulator(None, n=3, k=2)
    sim.distribute()
    packet = sim.seal(b"existing session")
    session_id, epoch, scheme = sim.session_id, sim.epoch, sim.scheme

    def fail_new_distribution(self, key):
        raise ValueError("Раздача прервана")

    monkeypatch.setattr(SchemeAdapter, "split", fail_new_distribution)
    with pytest.raises(ValueError, match="Раздача прервана"):
        sim.distribute_adaptive(0, visible=[1, 2, 3])
    assert (sim.session_id, sim.epoch, sim.scheme) == (session_id, epoch, scheme)
    assert sim.receive(packet, [1, 2]) == b"existing session"


def test_orbital_comparison_pairs_exposures_and_measures_delivery(tmp_path):
    import json

    from satellite_key_management.simulation.orbital_experiment import simulate_orbital_sessions
    from satellite_key_management.visualization.attack_dashboard import save_attack_dashboard

    class Sky:
        sats = range(4)

        def visible_at(self, minute):
            return [1, 2, 3] if minute % 2 == 0 else [1, 2]

    trials, tracker = simulate_orbital_sessions(Sky(), 33, k=3, threat=0)
    cases = {trial.result.policy: trial.result for trial in trials if trial.result.exposure_interval == 15}
    assert cases["fixed"].first_quorum_minute == 31
    assert cases["fixed_refresh"].first_quorum_minute is None
    assert cases["fixed"].delivered == cases["fixed_refresh"].delivered == 17
    assert cases["adaptive_refresh"].delivered == 33
    assert cases["fixed"].longest_outage == 1 and cases["adaptive_refresh"].longest_outage == 0
    assert tracker.refreshes == 1 and tracker.history[30].epoch == 2

    dashboard = tmp_path / "metrics_dashboard.html"
    save_attack_dashboard(trials, [], dashboard)
    html = dashboard.read_text(encoding="utf-8")
    data, _ = json.JSONDecoder().raw_decode(html.split("const data = ", 1)[1])
    assert sum(len(group) for group in data["cases"].values()) == 12
    paired = data["cases"]["15"]
    assert paired["fixed"]["firstQuorum"] == 31
    assert paired["fixed_refresh"]["firstQuorum"] is None
    assert paired["fixed_refresh"]["timeline"][30]["event"] == "refresh"
    assert paired["fixed_refresh"]["timeline"][31]["verified"] == 2
    assert paired["fixed_refresh"]["timeline"][31]["delivered"] is False
    exposed = data["cases"]["8"]["fixed_refresh"]
    assert exposed["firstQuorum"] == 17 and exposed["timeline"][17]["exposures"]
    assert exposed["timeline"][30]["shares"] == 0 and exposed["timeline"][30]["keyExposed"]
    assert (tmp_path / "plotly.min.js").is_file()


def test_orbital_trace_distinguishes_start_rotation_and_refresh():
    from satellite_key_management.simulation.orbital_experiment import simulate_orbital_sessions

    class Sky:
        sats = range(5)

        def visible_at(self, minute):
            return ([], [1, 2], [1, 2, 3, 4, 5])[min(minute, 2)]

    trials, _ = simulate_orbital_sessions(Sky(), 5, k=3, threat=0, refresh_every=2)
    adaptive = next(trial for trial in trials if trial.result.policy == "adaptive_refresh")
    assert [row.key_event for row in adaptive.reception] == [None, "start", "rotate", None, "refresh"]
    assert [row.delivered for row in adaptive.reception] == [False, True, True, True, True]
