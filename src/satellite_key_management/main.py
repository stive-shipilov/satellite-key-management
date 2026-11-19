"""Общий запуск симуляции и панели метрик."""
import argparse
from pathlib import Path

from satellite_key_management.simulation.contact_session import session_history, save_contact_history
from satellite_key_management.visualization.report import save_index
from satellite_key_management.visualization.static_plots import plot_refresh_sawtooth

from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.session import SessionSimulator
from satellite_key_management.visualization.animation_plotly import animate_with_metrics
from satellite_key_management.visualization.metrics_dashboard import build_metrics_dashboard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("."), help="каталог для двух HTML и Plotly")
    parser.add_argument("--minutes", type=int, default=300, help="длительность сценария")
    parser.add_argument("--step", type=int, default=3, help="минут между кадрами")
    args = parser.parse_args()
    if min(args.minutes, args.step) < 1:
        parser.error("Длительность и шаг должны быть положительными")
    args.out.mkdir(parents=True, exist_ok=True)
    leo = LEOModel(n_sats=36, seed=7, n_planes=6)
    sim = SessionSimulator(leo, n=36, k=12)
    sim.distribute()
    print("Проверка телеметрии, подписи и повторной доставки…", flush=True)
    history = session_history(args.minutes)
    save_contact_history(history, args.out)
    plot_refresh_sawtooth(sim, args.out / "refresh.png")
    print(f"Доставлено {sum(r.delivered for r in history)}/{len(history)} пакетов. "
          f"Смен обслуживающего узла: {sum(r.handover for r in history)}. Строю орбиты…", flush=True)
    animate_with_metrics(sim, t_total=args.minutes, step=args.step,
                         out_html=args.out / "simulation_3d.html",
                         gs_lat=-30.0, gs_lon=-60.0, refresh_every=30, contact_history=history)
    build_metrics_dashboard(sim, t_total=args.minutes, step=args.step,
                            out_html=args.out / "metrics_dashboard.html", refresh_every=30)
    save_index(args.out, history)
    print(f"Откройте {args.out / 'index.html'}", flush=True)


if __name__ == "__main__":
    main()
