"""Plotly 3D: Земля, кольца покрытия, линки атак, сбор долей, ползунок времени.

Одна наземная станция (GS) — она же атакующий.
Спутники, попадающие в её зону видимости, подсвечиваются красным:
  * точка спутника — красный ореол + жёлтое ядро с красной обводкой;
  * линк спутник↔GS — широкий полупрозрачный + яркий красный слой.
"""
from pathlib import Path
import numpy as np
import plotly.graph_objects as go
from PIL import Image

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
    U, V = np.meshgrid(u, v)                    # (n, 2n)
    X = R_EARTH * np.cos(U) * np.sin(V)
    Y = R_EARTH * np.sin(U) * np.sin(V)
    Z = R_EARTH * np.cos(V)

    if tex is not None:
        img = Image.open(tex).convert("RGB").resize((2 * n, n))
        arr = np.asarray(img, dtype=float) / 255.0
        surfacecolor = 0.3 * arr[..., 0] + 0.5 * arr[..., 1] + 0.2 * arr[..., 2]
        colorscale = [
            [0.0, "rgb(5,20,60)"], [0.35, "rgb(20,80,140)"],
            [0.55, "rgb(40,130,70)"], [0.75, "rgb(150,140,90)"],
            [1.0, "rgb(240,240,240)"],
        ]
    else:
        noise = np.sin(3 * U) * np.cos(2 * V) + 0.5 * np.sin(7 * U) * np.sin(5 * V)
        surfacecolor = (noise + 1.0) / 2.0
        colorscale = [[0, "rgb(10,40,90)"], [0.5, "rgb(40,120,60)"], [1, "rgb(200,200,200)"]]

    return go.Surface(
        x=X, y=Y, z=Z,
        surfacecolor=surfacecolor,
        colorscale=colorscale,
        cmin=float(surfacecolor.min()), cmax=float(surfacecolor.max()),
        showscale=False,
        lighting=dict(ambient=0.8, diffuse=0.9, specular=0.05, roughness=0.9),
        lightposition=dict(x=10000, y=10000, z=10000),
        name="Earth", hoverinfo="skip",
    )


def _coverage_ring(subpoint, radius=COVER_RADIUS, n=48):
    up = subpoint / np.linalg.norm(subpoint)
    tmp = np.array([0, 0, 1.0]) if abs(up[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(up, tmp); e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    ang = radius / R_EARTH
    ring = [ (np.cos(ang)*up + np.sin(ang)*(np.cos(a)*e1 + np.sin(a)*e2)) * R_EARTH
             for a in np.linspace(0, 2*np.pi, n) ]
    return np.array(ring)


def _is_in_zone(sat, in_zone):
    """Устойчивая проверка попадания спутника в зону.

    Работает и если visible_at() возвращает sid'ы, и если индексы 0..n-1.
    """
    if not in_zone:
        return False
    return (sat.sid in in_zone) or ((sat.sid - 1) in in_zone)


def animate_simulation_plotly(sim, t_total=120, step=2,
                              out_html="simulation_3d.html",
                              gs_lat=-30.0, gs_lon=-60.0,
                              cone_deg=60, cone_rays=32):
    """
    Одна наземная станция — она же атакующий.
    Спутники в её зоне подсвечиваются красным свечением (точки + линки).
    Число трейсов в каждом кадре строго одинаково.
    """
    from attacks.attacks import AttackerTracker

    times = list(range(0, t_total, step))
    gs = sim.leo._gs_vector(gs_lat, gs_lon)
    n_sats = len(sim.leo.sats)
    tracker = AttackerTracker(sim, gs_lat, gs_lon)
    earth = earth_surface("earth.jpg")

    # постоянное кольцо зоны GS (на поверхности)
    zone_ring = _coverage_ring(gs, radius=COVER_RADIUS)

    # постоянный конус видимости от GS вверх к орбите
    up = gs / np.linalg.norm(gs)
    tmp = np.array([0, 0, 1.0]) if abs(up[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(up, tmp); e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    cone_ang = np.radians(cone_deg)
    cone_tips = []
    for a in np.linspace(0, 2 * np.pi, cone_rays):
        d = np.cos(cone_ang) * up + np.sin(cone_ang) * (np.cos(a) * e1 + np.sin(a) * e2)
        cone_tips.append(gs + d * 2000.0)

    frames = []
    for t in times:
        positions = np.array([s.position(t) for s in sim.leo.sats])
        in_zone = sim.leo.visible_at(t, gs_lat, gs_lon, radius_km=COVER_RADIUS)
        st = tracker.step(t)

        traces = [earth]

        # 1) все спутники
        traces.append(go.Scatter3d(
            x=positions[:, 0], y=positions[:, 1], z=positions[:, 2],
            mode="markers", marker=dict(size=3, color="silver"), name="спутники",
        ))

        # 2) точки: на КАЖДЫЙ спутник — ореол + ядро (пустые, если не в зоне)
        for s in sim.leo.sats:
            p = positions[s.sid - 1]
            if s.sid in in_zone:
                traces.append(go.Scatter3d(
                    x=[p[0]], y=[p[1]], z=[p[2]], mode="markers",
                    marker=dict(size=16, color="rgba(255,0,0,0.35)", symbol="circle"),
                    showlegend=False, hoverinfo="skip",
                ))
                traces.append(go.Scatter3d(
                    x=[p[0]], y=[p[1]], z=[p[2]], mode="markers",
                    marker=dict(size=8, color="yellow", symbol="circle",
                                line=dict(color="red", width=1)),
                    showlegend=False, hoverinfo="skip",
                ))
            else:
                traces.append(go.Scatter3d(
                    x=[], y=[], z=[], mode="markers",
                    marker=dict(size=16, color="rgba(255,0,0,0.35)", symbol="circle"),
                    showlegend=False, hoverinfo="skip",
                ))
                traces.append(go.Scatter3d(
                    x=[], y=[], z=[], mode="markers",
                    marker=dict(size=8, color="yellow", symbol="circle",
                                line=dict(color="red", width=1)),
                    showlegend=False, hoverinfo="skip",
                ))

        # 3) кольца покрытия спутников (ровно одно на спутник)
        for s in sim.leo.sats:
            ring = _coverage_ring(s.subpoint(t))
            is_zone = s.sid in in_zone
            traces.append(go.Scatter3d(
                x=ring[:, 0], y=ring[:, 1], z=ring[:, 2], mode="lines",
                line=dict(color="rgba(255,80,80,0.9)" if is_zone else "gray",
                          width=3 if is_zone else 1),
                opacity=0.8 if is_zone else 0.12, showlegend=False, hoverinfo="skip",
            ))

        # 4) постоянная зона GS: толстое кольцо
        traces.append(go.Scatter3d(
            x=zone_ring[:, 0], y=zone_ring[:, 1], z=zone_ring[:, 2], mode="lines",
            line=dict(color="red", width=6), opacity=1.0,
            showlegend=True, name="зона GS",
        ))

        # 5) постоянный конус видимости
        for tip in cone_tips:
            traces.append(go.Scatter3d(
                x=[gs[0], tip[0]], y=[gs[1], tip[1]], z=[gs[2], tip[2]],
                mode="lines", line=dict(color="rgba(255,0,0,0.25)", width=1),
                showlegend=False, hoverinfo="skip",
            ))

        # 6) линки: на КАЖДЫЙ спутник — ореол + ядро (пустые, если не в зоне)
        for s in sim.leo.sats:
            p = positions[s.sid - 1]
            if s.sid in in_zone:
                traces.append(go.Scatter3d(
                    x=[p[0], gs[0]], y=[p[1], gs[1]], z=[p[2], gs[2]],
                    mode="lines",
                    line=dict(color="rgba(255,0,0,0.25)", width=10),
                    showlegend=False, hoverinfo="skip",
                ))
                traces.append(go.Scatter3d(
                    x=[p[0], gs[0]], y=[p[1], gs[1]], z=[p[2], gs[2]],
                    mode="lines",
                    line=dict(color="rgba(255,40,40,1)", width=4),
                    showlegend=False, hoverinfo="skip",
                ))
            else:
                traces.append(go.Scatter3d(
                    x=[], y=[], z=[], mode="lines",
                    line=dict(color="rgba(255,0,0,0.25)", width=10),
                    showlegend=False, hoverinfo="skip",
                ))
                traces.append(go.Scatter3d(
                    x=[], y=[], z=[], mode="lines",
                    line=dict(color="rgba(255,40,40,1)", width=4),
                    showlegend=False, hoverinfo="skip",
                ))

        # 7) маркер GS: точка на поверхности + короткий штырь наружу
        tip_gs = gs + up * 250
        traces.append(go.Scatter3d(
            x=[gs[0], tip_gs[0]], y=[gs[1], tip_gs[1]], z=[gs[2], tip_gs[2]],
            mode="lines", line=dict(color="red", width=4), showlegend=False,
        ))
        traces.append(go.Scatter3d(
            x=[tip_gs[0]], y=[tip_gs[1]], z=[tip_gs[2]], mode="markers",
            marker=dict(size=7, color="red", symbol="circle"),
            name="GS атакующего",
        ))

        # 8) статус-панель
        text = (
            f"t={t} мин<br>"
            f"в зоне GS: {st['n_visible']} спутников<br>"
            f"долей у GS: {st['n_shares']}/{st['k']}<br>"
            f"{'✓ ПРОРЫВ: ключ собран' if st['compromised'] else '✗ провал: долей < k'}<br>"
            f"попыток={tracker.attempts}, утекло={tracker.successes}, "
            f"провалов={tracker.failures}, success={tracker.success_rate:.0%}"
        )
        traces.append(go.Scatter3d(
            x=[None], y=[None], z=[None], mode="text", text=[text],
            textposition="top center", showlegend=False,
        ))

        frames.append(go.Frame(name=str(t), data=traces))

    # проверка согласованности числа трейсов
    counts = {len(f.data) for f in frames}
    assert len(counts) == 1, f"число трейсов в кадрах разное: {counts}"

    fig = go.Figure(data=frames[0].data, frames=frames)

    slider_steps = [dict(
        method="animate",
        args=[[str(t)], dict(mode="immediate", frame=dict(duration=200, redraw=True),
                             transition=dict(duration=0))],
        label=str(t),
    ) for t in times]

    fig.update_layout(
        title="LEO 3D: спутники в зоне GS подсвечены красным; долей < k → провал",
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            aspectmode="data", bgcolor="black",
            camera=dict(eye=dict(x=-1.8, y=-1.8, z=1.0)),
        ),
        sliders=[dict(active=0, steps=slider_steps, currentvalue=dict(prefix="t = "))],
        updatemenus=[dict(
            type="buttons", showactive=False,
            buttons=[
                dict(label="▶ Play", method="animate",
                     args=[None, dict(frame=dict(duration=200, redraw=True),
                                      fromcurrent=True, transition=dict(duration=0))]),
                dict(label="⏸ Pause", method="animate",
                     args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
            ],
        )],
        paper_bgcolor="black", plot_bgcolor="black", font=dict(color="white"),
    )

    fig.write_html(out_html, include_plotlyjs="cdn", auto_play=False)
    print(f"Сохранено: {out_html}")
    return out_html, tracker