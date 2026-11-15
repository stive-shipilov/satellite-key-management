from simulation.leo_model import LEOModel
from simulation.session import SessionSimulator
from visualization.animation_plotly import animate_with_metrics
from visualization.metrics_dashboard import build_metrics_dashboard


def main():
    leo = LEOModel(n_sats=36, seed=7, n_planes=6)
    sim = SessionSimulator(leo, n=36, k=12)
    sim.distribute()

    # 3D + 2D панель + refresh-вспышки
    out_html, tracker = animate_with_metrics(
        sim, t_total=300, step=3,
        out_html="simulation_3d.html",
        gs_lat=-30.0, gs_lon=-60.0,
        refresh_every=30,
    )

    # отдельный 2D-дашборд
    build_metrics_dashboard(sim, t_total=300, step=3,
                            out_html="metrics_dashboard.html")

    # интерактивный Dash (отдельный процесс)
    # from visualization.dash_app import run_dash
    # run_dash(port=8050)


if __name__ == "__main__":
    main()