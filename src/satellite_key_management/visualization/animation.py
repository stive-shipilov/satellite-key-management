"""3D-анимация LEO: Земля, конусы покрытия, атаки линками, сбор долей."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D  # noqa
import os

R_EARTH = 6371.0
COVER_RADIUS = 2500.0          # радиус пятна покрытия на сфере, км
ATTACK_COLOR = "#ff2b2b"
OK_COLOR = "#22cc55"
LINK_COLOR = "#ffd23f"

def _earth_surface(ax, texture_path="earth.jpg", n=60):
    """Сфера Земли: текстура, если есть файл, иначе процедурные пятна."""
    u = np.linspace(0, 2 * np.pi, n)
    v = np.linspace(0, np.pi, n)
    x = R_EARTH * np.outer(np.cos(u), np.sin(v))
    y = R_EARTH * np.outer(np.sin(u), np.sin(v))
    z = R_EARTH * np.outer(np.ones_like(u), np.cos(v))

    if os.path.exists(texture_path):
        img = plt.imread(texture_path)
        ax.plot_surface(x, y, z, rstride=1, cstride=1, facecolors=img,
                        shade=False, linewidth=0, antialiased=False)
    else:
        # процедурный «материковый» шум
        noise = (np.sin(3 * u)[:, None] * np.cos(2 * v)[None, :]
                 + 0.5 * np.sin(7 * u)[:, None] * np.sin(5 * v)[None, :])
        colors = np.empty(x.shape + (3,))
        land = noise > 0.1
        colors[..., 0] = np.where(land, 0.15, 0.05)
        colors[..., 1] = np.where(land, 0.55, 0.25)
        colors[..., 2] = np.where(land, 0.20, 0.65)
        ax.plot_surface(x, y, z, rstride=1, cstride=1, facecolors=colors,
                        shade=False, linewidth=0, antialiased=False)
    return x, y, z

def _coverage_ring(subpoint, radius=COVER_RADIUS, n=60):
    """Кольцо зоны покрытия вокруг подспутниковой точки на сфере."""
    up = subpoint / np.linalg.norm(subpoint)
    # два ортогональных вектора к up
    tmp = np.array([0, 0, 1.0]) if abs(up[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(up, tmp); e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    ang = radius / R_EARTH
    ring = []
    for a in np.linspace(0, 2 * np.pi, n):
        dirv = np.cos(ang) * up + np.sin(ang) * (np.cos(a) * e1 + np.sin(a) * e2)
        ring.append(dirv * R_EARTH)
    return np.array(ring)

def animate_simulation_3d(sim, t_total=120, step=2, out="simulation_3d.gif",
                          attackers=(3, 5, 7), gs_lat=55.0, gs_lon=37.0):
    """
    attackers — sid'ы спутников, которые «под контролем атакующих».
    Атакующие шлют линки к GS, пытаясь собрать доли, но k не набирается.
    """
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect([1, 1, 1])
    lim = R_EARTH * 2.0
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
    ax.set_axis_off()
    ax.set_title("LEO 3D: зоны покрытия, атаки и сбор долей", pad=0)

    _earth_surface(ax)

    # наземная станция
    gs = sim.leo._gs_vector(gs_lat, gs_lon)
    ax.scatter(*gs, color="white", s=60, marker="^", depthshade=False, label="GS")

    # артисты
    sat_pts, = ax.plot([], [], [], "o", color="silver", markersize=5)
    active_pts, = ax.plot([], [], [], "o", color=OK_COLOR, markersize=8)
    attack_pts, = ax.plot([], [], [], "o", color=ATTACK_COLOR, markersize=9)

    # заранее создаём линии покрытия/линков
    n_cover = len(sim.leo.sats)
    cover_lines = [ax.plot([], [], [], color=OK_COLOR, linewidth=1, alpha=0.6)[0]
                   for _ in range(n_cover)]
    attack_links = [ax.plot([], [], [], color=ATTACK_COLOR, linewidth=2, alpha=0.9,
                            linestyle="--")[0] for _ in attackers]
    ok_links = [ax.plot([], [], [], color=OK_COLOR, linewidth=1.5, alpha=0.7)[0]
                for _ in range(n_cover)]

    status = fig.text(0.02, 0.95, "", fontsize=12, family="monospace")

    def update(t):
        positions = np.array([s.position(t) for s in sim.leo.sats])
        sat_pts.set_data(positions[:, 0], positions[:, 1])
        sat_pts.set_3d_properties(positions[:, 2])

        visible = sim.leo.visible_at(t, gs_lat, gs_lon)
        vis_pos = positions[[sid - 1 for sid in visible]] if visible else np.empty((0, 3))
        active_pts.set_data(vis_pos[:, 0] if len(vis_pos) else [],
                            vis_pos[:, 1] if len(vis_pos) else [])
        active_pts.set_3d_properties(vis_pos[:, 2] if len(vis_pos) else [])

        # зоны покрытия — кольца вокруг подспутниковых точек
        for i, s in enumerate(sim.leo.sats):
            ring = _coverage_ring(s.subpoint(t))
            cover_lines[i].set_data(ring[:, 0], ring[:, 1])
            cover_lines[i].set_3d_properties(ring[:, 2])
            cover_lines[i].set_color(OK_COLOR if s.sid in visible else "gray")
            cover_lines[i].set_alpha(0.6 if s.sid in visible else 0.15)

        # атакующие: подмножество видимых спутников
        attack_vis = [sid for sid in attackers if sid in visible]
        att_pos = positions[[sid - 1 for sid in attack_vis]] if attack_vis else np.empty((0, 3))
        attack_pts.set_data(att_pos[:, 0] if len(att_pos) else [],
                            att_pos[:, 1] if len(att_pos) else [])
        attack_pts.set_3d_properties(att_pos[:, 2] if len(att_pos) else [])

        # линки атак: от атакующего спутника к GS
        for i, line in enumerate(attack_links):
            if i < len(attack_vis):
                p = positions[attack_vis[i] - 1]
                line.set_data([p[0], gs[0]], [p[1], gs[1]])
                line.set_3d_properties([p[2], gs[2]])
            else:
                line.set_data([], []); line.set_3d_properties([])

        # легитимные линки: видимые спутники -> GS
        for i, line in enumerate(ok_links):
            if i < len(visible):
                p = positions[visible[i] - 1]
                line.set_data([p[0], gs[0]], [p[1], gs[1]])
                line.set_3d_properties([p[2], gs[2]])
            else:
                line.set_data([], []); line.set_3d_properties([])

        # сбор долей
        ok, ncol = sim.collect_and_reconstruct(t)
        n_attack = len(attack_vis)
        if ncol < sim.k:
            status.set_text(f"t={t:3d} мин | видимых={len(visible):2d} | "
                            f"атакующих видимых={n_attack} | собрано={ncol}/{sim.k} "
                            f"→ АТАКА, ключ НЕ собран")
            status.set_color(ATTACK_COLOR)
        else:
            status.set_text(f"t={t:3d} мин | видимых={len(visible):2d} | "
                            f"атакующих видимых={n_attack} | собрано={ncol}/{sim.k} "
                            f"→ ключ собран (зелёный)")
            status.set_color(OK_COLOR)

        return [sat_pts, active_pts, attack_pts, status, *cover_lines, *attack_links, *ok_links]

    anim = FuncAnimation(fig, update, frames=range(0, t_total, step), interval=200)
    anim.save(out, writer="pillow", dpi=80)
    plt.close(fig)
    return out