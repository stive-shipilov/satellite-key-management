"""Запуск: python -m satellite_key_management.analysis --out results"""
import argparse
import platform
from dataclasses import asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pandas as pd

from ..simulation.leo_model import LEOModel
from ..simulation.session import SessionSimulator
from .benchmark import measure
from .plots import bar_chart, radar_chart


def run(out: Path, repeats: int, number: int):
    if min(repeats, number) < 1:
        raise ValueError("Число серий и измерений должно быть положительным")
    out.mkdir(parents=True, exist_ok=True)
    rows, compromise = [], []
    for bits in (64, 128, 256):
        for n, k in ((4, 2), (6, 3), (6, 6), (10, 4)):
            group = measure(bits, n, k, repeats, number)
            rows.extend(group)
            for r in group:
                for m in range(n + 1):
                    compromise.append((r.scheme, bits, n, k, r.threshold, m, int(m >= r.threshold)))
            if (bits, n, k) == (128, 6, 3):
                bar_chart(group, out / "comparison.png")
                radar_chart(group, out / "radar.png")
    metrics = pd.DataFrame(asdict(row) for row in rows)
    metrics["repeats"], metrics["number"] = repeats, number
    metrics["python"], metrics["platform"] = platform.python_version(), platform.platform()
    metrics.to_csv(out / "benchmark.csv", index=False)
    pd.DataFrame(compromise, columns=["scheme", "bits", "n", "scenario_k", "threshold", "m",
                                      "full_recovery"]).to_csv(out / "compromise.csv", index=False)
    # Одна геометрия для всех уровней, открытые параметры опыта фиксированы.
    leo = LEOModel(n_sats=72, n_planes=6, seed=7)
    sim = SessionSimulator(leo, n=72, k=3)
    windows = []
    for t in range(0, 190, 2):
        visible = len(leo.visible_at(t))
        for threat in (0.0, 0.02, 0.05):
            k = sim.dynamic_k(t, threat)
            windows.append((t, visible, threat, k, int(k is not None)))
    visibility = pd.DataFrame(windows, columns=["minute", "visible", "threat", "k", "available"])
    visibility["k"] = visibility["k"].astype("Int64")
    visibility.to_csv(out / "visibility.csv", index=False)
    sample = metrics[(metrics.bits == 128) & (metrics.n == 6) & (metrics.scenario_k == 3)]
    print(sample[["scheme", "threshold", "share_bytes", "split_us", "recover_us"]].to_string(index=False))
    print("Доля окон с достижимым порогом по уровням угрозы:")
    print(visibility.groupby("threat")["available"].mean().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Сравнение схем управления ключами")
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--number", type=int, default=30)
    args = parser.parse_args()
    run(args.out, args.repeats, args.number)
