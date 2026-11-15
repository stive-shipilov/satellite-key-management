from simulation.leo_model import LEOModel
from simulation.session import SessionSimulator
from attacks.attacks import AttackerTracker, compromise_m, evil_dealer, replay_attack
from visualization.static_plots import (
    plot_compromise_step, plot_refresh_sawtooth, plot_dynamic_k,
    plot_scheme_comparison, plot_attacker_accumulation,
    plot_attacker_zone_presence, plot_attacker_metrics_summary,
)
from visualization.animation_plotly import animate_simulation_plotly


def main():
    # 36 спутников, 6 плоскостей, k=12
    leo = LEOModel(n_sats=36, seed=7, n_planes=6)
    sim = SessionSimulator(leo, n=36, k=12)
    sim.distribute()

    print("=== Компрометация m ===")
    for m in [5, 10, 12, 18, 24, 36]:
        ok, mm = compromise_m(sim, m)
        print(f"m={mm}: {'ВОССТАНОВЛЕН' if ok else 'не восстановлен'}")

    print("\n=== Злой дилер ===")
    caught, _ = evil_dealer(sim)
    print("VSS", "поймал" if caught else "НЕ поймал")

    print("\n=== Replay ===")
    ok1, ok2 = replay_attack(sim, t_min=10)
    print(f"первое={ok1}, повтор={ok2} (False = поймали)")

    # анимация + трекер атакующего
    print("\n=== Plotly 3D + атака из зоны вражеской GS ===")
    out_html, tracker = animate_simulation_plotly(
        sim, t_total=120, step=2,
        out_html="simulation_3d.html",
        gs_lat=-30.0, gs_lon=-60.0,  # единственная GS — она же атакующий
    )

    # графики метрик атакующего
    print(plot_attacker_accumulation(tracker))
    print(plot_attacker_zone_presence(tracker))
    print(plot_attacker_metrics_summary(tracker))

    # старые графики
    print(plot_compromise_step(sim))
    print(plot_refresh_sawtooth(sim))
    print(plot_dynamic_k(sim))
    print(plot_scheme_comparison())

    ttc = tracker.time_to_compromise(None)
    print(f"\nTime-to-compromise: {'∞ (невозможно)' if ttc == float('inf') else f'{ttc} мин'}")
    print(f"Success rate атакующего: {tracker.success_rate:.0%}")


if __name__ == "__main__":
    main()