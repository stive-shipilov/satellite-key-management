"""Plotly Dash: интерактивный анализ стойкости со слайдерами."""
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def run_dash(gs_lat=-30.0, gs_lon=-60.0, radius_km=2500, port=8050):
    from satellite_key_management.simulation.leo_model import LEOModel
    from satellite_key_management.simulation.session import SessionSimulator
    from satellite_key_management.attacks.attacks import AttackerTracker

    app = Dash(__name__)

    app.layout = html.Div(style={"backgroundColor": "#111", "color": "white",
                                 "fontFamily": "monospace", "padding": "10px"}, children=[
        html.H2("Анализ стойкости threshold-схемы"),
        html.Div([
            html.Label("n (спутников): "),
            dcc.Slider(id="n", min=12, max=48, step=6, value=36,
                       marks={i: str(i) for i in range(12, 49, 6)}),
        ]),
        html.Div([
            html.Label("k (порог): "),
            dcc.Slider(id="k", min=1, max=48, step=1, value=12,
                       marks={i: str(i) for i in range(1, 49, 6)}),
        ]),
        html.Div([
            html.Label("Участников с модельным раскрытием доли: "),
            dcc.Slider(id="attackers", min=1, max=48, step=1, value=6,
                       marks={i: str(i) for i in range(1, 49, 6)}),
        ]),
        html.Div([
            html.Label("refresh_every (мин, 0 = выкл): "),
            dcc.Slider(id="refresh", min=0, max=120, step=10, value=30,
                       marks={i: str(i) for i in range(0, 121, 20)}),
        ]),
        dcc.Graph(id="graph"),
    ])

    @app.callback(
        Output("graph", "figure"),
        Input("n", "value"), Input("k", "value"),
        Input("attackers", "value"), Input("refresh", "value"),
    )
    def update(n, k, attackers, refresh_every):
        leo = LEOModel(n_sats=n, seed=7, n_planes=max(1, n // 6))
        sim = SessionSimulator(leo, n=n, k=min(k, n))
        sim.distribute()

        tracker = AttackerTracker(sim)
        exposed = range(1, min(attackers, n) + 1)

        times = list(range(300))
        acc_m, zone_n = [], []
        for minute in times:
            if refresh_every and minute and minute % refresh_every == 0:
                sim.refresh()
            visible = sim.leo.visible_at(minute, gs_lat, gs_lon, radius_km=radius_km)
            sample = tracker.step(minute, visible, exposed)
            acc_m.append(sample.shares)
            zone_n.append(len(sample.visible))

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=times, y=acc_m, mode="lines",
                                 line=dict(color="red"), name="раскрыто долей"))
        fig.add_trace(go.Scatter(x=[0, times[-1]], y=[sim.k, sim.k], mode="lines",
                                 line=dict(color="green", dash="dash"), name=f"k={sim.k}"))
        fig.add_trace(go.Scatter(x=times, y=zone_n, mode="lines",
                                 line=dict(color="orange", shape="hv"),
                                 name="в зоне"), secondary_y=True)
        fig.update_layout(
            title=(f"n={n}, k={sim.k}, attackers={attackers}, refresh={refresh_every} | "
                   f"max долей={max(acc_m)} | "
                   f"{'кворум достигнут' if max(acc_m) >= sim.k else 'кворум не достигнут'}"),
            paper_bgcolor="#111", plot_bgcolor="#111", font=dict(color="white"),
            yaxis=dict(title="долей"), yaxis2=dict(title="в зоне", overlaying="y", side="right"),
        )
        return fig

    print(f"Dash: http://127.0.0.1:{port}")
    app.run(debug=False, port=port)
