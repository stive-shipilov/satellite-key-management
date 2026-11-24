"""Plotly 3D: геометрия видимости станции и события раскрытия долей."""

from pathlib import Path
import numpy as np
import plotly.graph_objects as go
from PIL import Image
from plotly.subplots import make_subplots

from .report import write_plotly_page

R_EARTH = 6371.0
COVER_RADIUS = 2500.0
ATTACK_COLOR = "red"
OK_COLOR = "lime"


def _find_texture(name="earth.jpg"):
    here = Path(__file__).resolve().parent
    for p in [Path(name), here / name, here.parent / name, Path.cwd() / name]:
        if p.exists():
            return p
    return None


def earth_surface(texture_path="earth.jpg", n=120):
    """Сфера Земли: текстура (n,2n) → intensity → surfacecolor той же формы."""
    tex = _find_texture(texture_path)

    u = np.linspace(0, 2 * np.pi, 2 * n)
    v = np.linspace(0, np.pi, n)
    U, V = np.meshgrid(u, v)  # (n, 2n)
    X = R_EARTH * np.cos(U) * np.sin(V)
    Y = R_EARTH * np.sin(U) * np.sin(V)
    Z = R_EARTH * np.cos(V)

    if tex is not None:
        img = Image.open(tex).convert("RGB").resize((2 * n, n))
        arr = np.asarray(img, dtype=float) / 255.0
        surfacecolor = 0.3 * arr[..., 0] + 0.5 * arr[..., 1] + 0.2 * arr[..., 2]
        colorscale = [
            [0.0, "rgb(5,20,60)"],
            [0.35, "rgb(20,80,140)"],
            [0.55, "rgb(40,130,70)"],
            [0.75, "rgb(150,140,90)"],
            [1.0, "rgb(240,240,240)"],
        ]
    else:
        noise = np.sin(3 * U) * np.cos(2 * V) + 0.5 * np.sin(7 * U) * np.sin(5 * V)
        surfacecolor = (noise + 1.0) / 2.0
        colorscale = [
            [0, "rgb(10,40,90)"],
            [0.5, "rgb(40,120,60)"],
            [1, "rgb(200,200,200)"],
        ]

    return go.Surface(
        x=X,
        y=Y,
        z=Z,
        surfacecolor=surfacecolor,
        colorscale=colorscale,
        cmin=float(surfacecolor.min()),
        cmax=float(surfacecolor.max()),
        showscale=False,
        lighting=dict(ambient=0.8, diffuse=0.9, specular=0.05, roughness=0.9),
        lightposition=dict(x=10000, y=10000, z=10000),
        name="Earth",
        hoverinfo="skip",
    )


def _coverage_ring(subpoint, radius=COVER_RADIUS, n=48):
    up = subpoint / np.linalg.norm(subpoint)
    tmp = np.array([0, 0, 1.0]) if abs(up[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(up, tmp)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    ang = radius / R_EARTH
    ring = [
        (np.cos(ang) * up + np.sin(ang) * (np.cos(a) * e1 + np.sin(a) * e2)) * R_EARTH
        for a in np.linspace(0, 2 * np.pi, n)
    ]
    return np.array(ring)


def animate_with_metrics(
    sim,
    t_total=120,
    step=2,
    out_html="simulation_3d.html",
    gs_lat=-30.0,
    gs_lon=-60.0,
    cone_deg=60,
    cone_rays=32,
    refresh_every=30,
    *,
    tracker=None,
):
    """Анимация орбит. Все спутники одного статуса находятся в одном слое."""
    from satellite_key_management.attacks.attacks import track_visibility

    if min(step, t_total) <= 0:
        raise ValueError("Длительность и шаг должны быть положительными")
    if tracker is None:
        tracker = track_visibility(sim, t_total, gs_lat, gs_lon, refresh_every=refresh_every)
    gs = sim.leo._gs_vector(gs_lat, gs_lon)
    times = range(0, t_total, step)
    stride = max(1, (len(times) + 179) // 180)
    event_times = {sample.minute for sample in tracker.history[:t_total] if sample.new_exposures}
    frame_times = sorted(set(times[::stride]) | event_times | {times[-1]})
    frames = []
    for t in frame_times:
        sample = tracker.history[t]
        visible = set(sample.visible)
        exposed = set(sample.new_exposures)
        points = np.array([sat.position(t) for sat in sim.leo.sats])
        links = [[], [], []]
        for sat, point in zip(sim.leo.sats, points):
            if sat.sid in visible:
                for axis in range(3):
                    links[axis].extend([point[axis], gs[axis], None])
        layers = [
            go.Scatter3d(
                x=points[:, 0],
                y=points[:, 1],
                z=points[:, 2],
                mode="markers",
                text=[f"Спутник {sat.sid} · {'виден' if sat.sid in visible else 'вне видимости'}"
                      + (" · раскрыта доля" if sat.sid in exposed else "") for sat in sim.leo.sats],
                hoverinfo="text",
                marker=dict(
                    size=[8 if sat.sid in exposed else 4 for sat in sim.leo.sats],
                    symbol=["diamond" if sat.sid in exposed else "circle" for sat in sim.leo.sats],
                    color=["#ffb450" if sat.sid in exposed else "#52a8ff" if sat.sid in visible
                           else "#8798a9" for sat in sim.leo.sats],
                ),
                name="Спутники",
            ),
            go.Scatter3d(
                x=links[0],
                y=links[1],
                z=links[2],
                mode="lines",
                line=dict(color="#52a8ff", width=3),
                name="В зоне станции",
            ),
            go.Scatter(
                x=[t],
                y=[sample.shares],
                mode="markers",
                marker=dict(size=11),
                name="Текущий момент",
            ),
        ]
        title = (f"Орбиты и модель раскрытия долей · {t} мин · эпоха {sample.epoch}"
                 f" · видимых узлов {len(visible)} · раскрыто долей {sample.shares}/{sample.threshold}")
        if sample.key_exposed:
            title += " · ключ раскрыт по модели"
        frames.append(
            go.Frame(
                name=str(t),
                data=layers,
                traces=[3, 4, 5],
                layout=go.Layout(title_text=title),
            )
        )
    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "scene"}, {"type": "xy"}]],
        column_widths=[0.64, 0.36],
        subplot_titles=[
            "Вид сверху на орбиты",
            "Раскрытые по сценарию доли текущей эпохи",
        ],
    )
    fig.add_trace(earth_surface(n=48), row=1, col=1)
    fig.add_trace(
        go.Scatter3d(
            x=[gs[0]],
            y=[gs[1]],
            z=[gs[2]],
            mode="markers",
            marker=dict(size=6, color="white"),
            name="Станция",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=list(range(t_total)), y=[sample.shares for sample in tracker.history[:t_total]],
            mode="lines", name="Раскрыто долей", line_shape="hv"
        ),
        row=1,
        col=2,
    )
    for i, layer in enumerate(frames[0].data):
        fig.add_trace(layer, row=1, col=2 if i == 2 else 1)
    fig.frames = frames
    fig.add_trace(go.Scatter3d(x=[None], y=[None], z=[None], mode="markers",
                              marker=dict(color="#ffb450", symbol="diamond", size=8),
                              name="Раскрыта доля"), row=1, col=1)
    fig.add_trace(
        go.Scatter(
            x=[0, t_total],
            y=[sim.k, sim.k],
            mode="lines",
            line=dict(dash="dash"),
            name=f"Порог {sim.k}",
        ),
        row=1,
        col=2,
    )
    ring = _coverage_ring(gs)
    fig.add_trace(
        go.Scatter3d(
            x=ring[:, 0], y=ring[:, 1], z=ring[:, 2], mode="lines", name=f"Кольцо {COVER_RADIUS:g} км"
        ),
        row=1,
        col=1,
    )
    if cone_rays > 0:
        up = gs / np.linalg.norm(gs)
        axis = (
            np.array([1.0, 0.0, 0.0]) if abs(up[2]) > 0.9 else np.array([0.0, 0.0, 1.0])
        )
        east = np.cross(up, axis)
        east /= np.linalg.norm(east)
        north = np.cross(up, east)
        angle = np.radians(cone_deg)
        rays = [[], [], []]
        for azimuth in np.linspace(0, 2 * np.pi, cone_rays, endpoint=False):
            direction = np.cos(azimuth) * east + np.sin(azimuth) * north
            tip = gs + 2000 * (np.cos(angle) * up + np.sin(angle) * direction)
            for j in range(3):
                rays[j].extend([gs[j], tip[j], None])
        fig.add_trace(
            go.Scatter3d(
                x=rays[0],
                y=rays[1],
                z=rays[2],
                mode="lines",
                line=dict(color="gray", width=1),
                name="Конус станции",
            ),
            row=1,
            col=1,
        )
    fig.update_layout(
        template="plotly_dark",
        title=frames[0].layout.title,
        scene=dict(
            aspectmode="cube",
            **{a: dict(visible=False) for a in ("xaxis", "yaxis", "zaxis")},
        ),
        xaxis_title="Минуты",
        yaxis_title="Доли",
        legend=dict(orientation="h", y=-0.22),
        sliders=[
            dict(
                currentvalue=dict(prefix="Минута "),
                steps=[
                    dict(
                        label=f.name,
                        method="animate",
                        args=[
                            [f.name],
                            dict(
                                mode="immediate",
                                frame=dict(duration=0, redraw=True),
                                transition=dict(duration=0),
                            ),
                        ],
                    )
                    for f in frames
                ],
            )
        ],
        updatemenus=[
            dict(
                type="buttons",
                buttons=[dict(label="Пуск", method="skip"), dict(label="Пауза", method="skip")],
            )
        ],
    )
    # Ставим в очередь один кадр. Пауза завершает текущий кадр без отмены очереди Plotly.
    playback = """
const chart = document.getElementById('{plot_id}');
let generation = 0;
chart.on('plotly_sliderstart', () => { generation++; });
chart.on('plotly_buttonclicked', async ({button}) => {
    const run = ++generation;
    if (button.label !== 'Пуск') return;
    const slider = chart.layout.sliders[0];
    const active = slider.active ?? 0;
    const start = active >= slider.steps.length - 1 ? 0 : active + 1;
    for (let i = start; i < slider.steps.length && run === generation; i++) {
        try {
            await Plotly.animate(chart, [slider.steps[i].label], {
                mode: 'afterall', frame: {duration: 160, redraw: true}, transition: {duration: 0}
            });
        } catch (error) {
            if (run === generation) console.error('Ошибка воспроизведения кадра', error);
            return;
        }
    }
});
"""
    write_plotly_page(fig, out_html, "Орбиты и зона видимости", auto_play=False, post_script=playback)
    print(f"Сохранено: {out_html}", flush=True)
    return out_html, tracker
