"""Единый отчёт: орбиты + 5 схем + атаки + benchmark + demo.

Запуск:
    python -m satellite_key_management --out results
"""
from __future__ import annotations

import argparse
import platform
import secrets
from dataclasses import asdict
from pathlib import Path
from statistics import median
from timeit import repeat

import pandas as pd

from satellite_key_management.analysis.benchmark import Measurement, byte_width, measure
from satellite_key_management.analysis.demo import telemetry_demo
from satellite_key_management.analysis.plots import bar_chart, radar_chart
from satellite_key_management.attacks.attacks import AttackerTracker
from satellite_key_management.simulation.contact_session import (
    save_contact_history,
    session_history,
)
from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.session import SessionSimulator
from satellite_key_management.visualization.animation_plotly import animate_with_metrics
from satellite_key_management.visualization.metrics_dashboard import build_metrics_dashboard
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
    out.mkdir(parents=True, exist_ok=True)

    # -------- 1. Единая LEO-модель и главный SessionSimulator -------------
    leo = LEOModel(n_sats=36, seed=7, n_planes=6)
    sim = SessionSimulator(leo, n=36, k=12, scheme="feldman_vss")
    sim.distribute()

    # -------- 2. Синтетические окна 6–12 мин ------------------------------
    history = session_history(minutes)
    save_contact_history(history, out)

    # -------- 3. Атаки на главный sim ------------------------------------
    # AttackerTracker в текущем attacks.py принимает attacker_lat/attacker_lon.
    tracker = AttackerTracker(
        sim, attacker_lat=-30.0, attacker_lon=-60.0, refresh_every=30
    )
    try:
        plot_compromise_step(sim, out / "compromise_step.png")
    except Exception as exc:  # noqa: BLE001
        print(f"[skip] compromise_step: {exc}", flush=True)
    try:
        plot_refresh_sawtooth(sim, out / "refresh.png")
    except Exception as exc:  # noqa: BLE001
        print(f"[skip] refresh_sawtooth: {exc}", flush=True)
    try:
        plot_dynamic_k(sim, out / "dynamic_k.png", t_total=minutes)
    except Exception as exc:  # noqa: BLE001
        print(f"[skip] dynamic_k: {exc}", flush=True)

    # -------- 4. Орбиты и метрики атакующего ------------------------------
    _, tracker_anim = animate_with_metrics(
        sim, t_total=minutes, step=step,
        out_html=str(out / "simulation_3d.html"),
        gs_lat=-30.0, gs_lon=-60.0, refresh_every=30,
    )
    leo_vis = LEOModel(n_sats=72, seed=7, n_planes=12)
    build_scheme_comparison_leo(
        leo_vis,
        gs_lat=0.0, gs_lon=0.0,  # жертва — экватор, Гвинейский залив
        attacker_lat=5.0, attacker_lon=10.0,  # атакующий — ~800 км от жертвы
        minutes=minutes,
        step=1,
        n=72,
        k_shamir=6,
        out_html=str(out / "schemes_on_leo_live.html"),
    )
    try:
        plot_attacker_accumulation(tracker_anim, out / "attacker_accumulation.png")
    except Exception as exc:  # noqa: BLE001
        print(f"[skip] attacker_accumulation: {exc}", flush=True)

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
        tracker=tracker_anim,
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