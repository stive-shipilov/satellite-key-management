"""2D-дашборд метрик стойкости в одном HTML (Plotly)."""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_metrics_dashboard(sim, gs_lat=-30.0, gs_lon=-60.0,
                            t_total=300, step=3, radius_km=2500,
                            out_html="metrics_dashboard.html", refresh_every=None):
    from satellite_key_management.attacks.attacks import AttackerTracker

    times = list(range(0, t_total, step))
    tracker = AttackerTracker(sim, gs_lat, gs_lon, refresh_every=refresh_every)

    # прогон по времени
    acc_t, acc_m, zone_t, zone_n = [], [], [], []
    for t in times:
        st = tracker.step(t)
        acc_t.append(t); acc_m.append(st["n_shares"])
        zone_t.append(t); zone_n.append(st["n_visible"])

    max_in_zone = max(zone_n) if zone_n else 0
    ttc = tracker.time_to_compromise(None)

    # success rate vs k
    ks = list(range(1, sim.n + 1))
    peak = max(acc_m, default=0)
    reached = [int(peak >= k) for k in ks]

    # heatmap (k, m)
    n = sim.n
    heat = np.zeros((n + 1, n + 1))
    for k in range(1, n + 1):
        for m in range(0, n + 1):
            heat[m, k] = 1.0 if m >= k else 0.0

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Накопление долей vs k",
            "Бюджет атакующего: max в зоне vs k",
            "Достигнут ли порог за весь прогон (1/0)",
            "Граница стойкости: m ≥ k",
        ),
        specs=[[{"type": "xy"}, {"type": "xy"}],
               [{"type": "xy"}, {"type": "heatmap"}]],
    )

    # 1) накопление
    fig.add_trace(go.Scatter(x=acc_t, y=acc_m, mode="lines+markers",
                             line=dict(color="red"), marker=dict(size=3),
                             name="долей у GS"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[0, t_total], y=[sim.k, sim.k], mode="lines",
                             line=dict(color="green", dash="dash"),
                             name=f"k={sim.k}"), row=1, col=1)

    # 2) бюджет
    fig.add_trace(go.Scatter(x=zone_t, y=zone_n, mode="lines",
                             line=dict(color="orange", shape="hv"),
                             name="в зоне"), row=1, col=2)
    fig.add_trace(go.Scatter(x=[0, t_total], y=[sim.k, sim.k], mode="lines",
                             line=dict(color="green", dash="dash"),
                             name=f"k={sim.k}"), row=1, col=2)
    fig.add_annotation(
        x=t_total, y=sim.k, row=1, col=2, showarrow=False,
        text=f"Одновременно в зоне: до {max_in_zone}. Накоплено в одной эпохе: до {peak}.",
        font=dict(color="white", size=10), yshift=12,
    )

    # 3) success rate vs k
    fig.add_trace(go.Scatter(x=ks, y=reached, mode="lines+markers",
                             line=dict(color="crimson"),
                             marker=dict(size=4), name="порог достигнут"),
                  row=2, col=1)

    # 4) heatmap
    fig.add_trace(go.Heatmap(z=heat, x=list(range(0, n + 1)), y=list(range(0, n + 1)),
                             colorscale=[[0, "green"], [1, "red"]], showscale=False,
                             name="стойкость"), row=2, col=2)

    ttc_str = "за время прогона порог не достигнут" if ttc == float("inf") else f"{ttc} мин"
    fig.update_layout(
        title=(f"Метрики стойкости | success rate={tracker.success_rate:.0%} | "
               f"time-to-compromise={ttc_str} | попыток={tracker.attempts}, "
               f"утекло={tracker.successes}, провалов={tracker.failures}"),
        paper_bgcolor="black", plot_bgcolor="black", font=dict(color="white"),
        showlegend=False, height=800,
    )
    fig.update_xaxes(color="white"); fig.update_yaxes(color="white")
    fig.write_html(out_html, include_plotlyjs="directory")
    print(f"Сохранено: {out_html}")
    return out_html, tracker
