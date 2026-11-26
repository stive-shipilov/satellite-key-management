"""Единый отчёт: орбиты + 5 схем + атаки + benchmark + demo.

Запуск:
    satellite-key-management --out results
"""
from __future__ import annotations

import argparse
import platform
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from satellite_key_management.analysis.benchmark import measure
from satellite_key_management.analysis.demo import telemetry_demo
from satellite_key_management.analysis.plots import bar_chart, radar_chart
from satellite_key_management.simulation.contact_session import (
    save_contact_history,
    session_history,
)
from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.orbital_experiment import simulate_orbital_sessions
from satellite_key_management.simulation.session import SessionSimulator
from satellite_key_management.visualization.animation_plotly import animate_with_metrics
from satellite_key_management.visualization.attack_dashboard import save_attack_dashboard
from satellite_key_management.visualization.orbit_view import (
    DEFAULT_OBSERVER, DEMO_GROUPS, orbit_config, save_contact_risk_page,
)
from satellite_key_management.visualization.report import save_index
from satellite_key_management.visualization.scheme_comparison_leo import build_scheme_comparison_leo, \
    compare_schemes_on_leo
from satellite_key_management.visualization.static_plots import (
    plot_attacker_accumulation,
    plot_compromise_step,
    plot_dynamic_k,
    plot_refresh_sawtooth,
)


# ---------------------------------------------------------------------------
# Общий запуск
# ---------------------------------------------------------------------------
def run(out: Path, minutes: int, step: int, threat: float = 0.3):
    if min(minutes, step) < 1:
        raise ValueError("Длительность и шаг должны быть положительными")
    if not 0 <= threat <= 1:
        raise ValueError("Уровень угрозы должен быть в диапазоне [0, 1]")
    out.mkdir(parents=True, exist_ok=True)

    # -------- 1. Единая LEO-модель и главный SessionSimulator -------------
    leo = LEOModel(n_sats=72, seed=7, n_planes=6)
    sim = SessionSimulator(leo, n=len(leo.sats), k=3)
    sim.distribute()

    # -------- 2. Синтетические окна 6–12 мин ------------------------------
    history = session_history(minutes)
    save_contact_history(history, out)

    # -------- 3. Кворум, защищённая доставка и раскрытие долей ------------
    trials, tracker = simulate_orbital_sessions(leo, minutes, k=sim.k, threat=threat)
    orbital_results = [trial.result for trial in trials]
    pd.DataFrame([asdict(row) for row in orbital_results]).convert_dtypes().to_csv(
        out / "orbital_experiment.csv", index=False
    )
    plot_compromise_step(sim, out / "compromise_step.png")
    plot_refresh_sawtooth(sim, out / "refresh.png")
    plot_dynamic_k(sim, out / "dynamic_k.png", t_total=minutes, threat=threat)

    # -------- 4. Орбиты и метрики атакующего ------------------------------
    # Demonstration profile with both contact and outage at k=3.
    demo_leo = LEOModel(n_sats=120, n_planes=6)
    animate_with_metrics(
        sim, t_total=minutes, step=step,
        out_html=str(out / "simulation_3d.html"),
        gs_lat=55.0, gs_lon=37.0, tracker=tracker, scenario_leo=demo_leo, orbit_groups=DEMO_GROUPS,
    )
    contact_demo = orbit_config(demo_leo, 120, 1, 55.0, 37.0, sim.k, 30, groups=DEMO_GROUPS)
    save_contact_risk_page(out / "contact_risk.html", contact_demo, DEFAULT_OBSERVER)
    save_attack_dashboard(trials, history, out / "metrics_dashboard.html")
    build_scheme_comparison_leo(
        demo_leo,
        gs_lat=55.0, gs_lon=37.0,
        attacker_lat=DEFAULT_OBSERVER["lat"], attacker_lon=DEFAULT_OBSERVER["lon"],
        minutes=minutes,
        step=1,
        n=len(demo_leo.sats),
        k_shamir=sim.k,
        out_html=str(out / "schemes_on_leo_live.html"),
        orbit_groups=DEMO_GROUPS,
    )
    plot_attacker_accumulation(tracker, out / "attacker_accumulation.png")

    # -------- 5. Сравнение 5 схем на фиксированных n, k -------------------
    comparison_rows = compare_schemes_on_leo(leo, bits=128, n=6, k=3)
    if comparison_rows:
        comparison_df = pd.DataFrame([asdict(r) for r in comparison_rows])
        comparison_df["python"] = platform.python_version()
        comparison_df["platform"] = platform.platform()
        comparison_df.to_csv(out / "schemes_on_leo.csv", index=False)
        try:
            bar_chart(comparison_rows, out / "schemes_on_leo.png")
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] bar_chart(schemes_on_leo): {exc}", flush=True)
    else:
        print("[warn] compare_schemes_on_leo вернул пусто — пропускаю раздел", flush=True)

    # -------- 6. Классический benchmark (bits × (n,k)) --------------------
    bench_rows = []
    for bits in (64, 128, 256):
        for n, k in ((4, 2), (6, 3), (6, 6), (10, 4)):
            try:
                bench_rows.extend(measure(bits, n, k, repeats=7, number=30))
            except Exception as exc:  # noqa: BLE001
                print(f"[skip] measure({bits},{n},{k}): {exc}", flush=True)
    if bench_rows:
        bench_df = pd.DataFrame([asdict(r) for r in bench_rows])
        bench_df.to_csv(out / "benchmark.csv", index=False)
        sample = [
            r for r in bench_rows
            if (r.bits, r.n, r.scenario_k) == (128, 6, 3)
        ]
        if sample:
            try:
                radar_chart(sample, out / "radar.png")
            except Exception as exc:  # noqa: BLE001
                print(f"[skip] radar_chart: {exc}", flush=True)
    else:
        sample = []
        print("[warn] benchmark пуст", flush=True)

    # -------- 7. Demo: 4 схемы на одной видимости ------------------------
    print("=== Демонстрация 4 схем на одной видимости LEO ===", flush=True)
    try:
        telemetry_demo()
    except Exception as exc:  # noqa: BLE001
        print(f"[skip] telemetry_demo: {exc}", flush=True)

    # -------- 8. Единый index.html ---------------------------------------
    save_index(
        out, history,
        comparison_rows=comparison_rows,
        bench_sample=sample,
        tracker=tracker,
        orbital_results=orbital_results,
        threat=threat,
    )
    print(f"\nГотово. Откройте {out / 'index.html'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--minutes", type=int, default=120)
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--threat", type=float, default=0.3)
    args = parser.parse_args()
    run(args.out, args.minutes, args.step, args.threat)


if __name__ == "__main__":
    main()
