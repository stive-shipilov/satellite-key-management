"""Plotly: 5 схем разделения секрета на одной LEO-видимости.

Слайдер времени гоняет общую LEO-модель. На каждом кадре:
    * слева — позиции видимых/невидимых спутников;
    * справа — 5 панелей (shamir, blakley, feldman_vss, xor, crt), на каждой
      «видно X / нужно k → ключ собран: да/нет» + размер доли, время recover.
"""
from __future__ import annotations

import secrets
from statistics import median
from timeit import repeat

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from satellite_key_management.analysis.benchmark import byte_width, Measurement
from satellite_key_management.analysis.threshold import choose_threshold
from satellite_key_management.crypto.schemes import SCHEMES
from satellite_key_management.simulation.leo_model import LEOModel, R_EARTH
from satellite_key_management.simulation.session import SessionSimulator

from .report import write_plotly_page

SCHEME_COLORS = {
    "shamir":       "#2b7bba",
    "blakley":      "#d1712f",
    "feldman_vss":  "#2ca58d",
    "xor":          "#8e5fa8",
    "crt":          "#b23b3b",
}

# 4-цветная схема для спутников на сцене.
COLOR_BOTH = "#b04fc9"      # виден и жертве, и атакующему
COLOR_VICTIM = "#2b7bba"    # виден только жертве
COLOR_ATTACKER = "#d1495b"  # виден только атакующему
COLOR_NONE = "#777777"      # не виден никому


# ---------------------------------------------------------------------------
# Сравнение 5 схем на фиксированных n, k (видимость LEO не нужна)
# ---------------------------------------------------------------------------
def compare_schemes_on_leo(leo, bits: int = 128, n: int = 6, k: int = 3):
    """Прогнать shamir/blakley/feldman_vss/xor/crt на одних n, k.

    XOR/CRT требуют k = n, поэтому для них берём threshold = n.
    Возвращает список Measurement, совместимый с analysis.plots.bar_chart.
    """
    rows = []
    for scheme_name, kk in (
        ("shamir", k), ("blakley", k), ("feldman_vss", k),
        ("xor", n), ("crt", n),
    ):
        try:
            sim = SessionSimulator(leo, n=n, k=kk, scheme=scheme_name, bits=bits)
        except (ValueError, NotImplementedError):
            continue
        sim.secret_key = secrets.randbits(bits)

        # Оценка размера доли (как в benchmark.measure).
        p = sim.scheme.p
        word = byte_width(p - 1) if p > 1 else 16
        if scheme_name in ("blakley", "feldman_vss"):
            size = (kk + 1) * word
        else:
            size = byte_width(n) + word

        # Время split.
        try:
            split_samples = [
                t * 1e6 / 10
                for t in repeat(
                    lambda: sim.scheme.split(sim.secret_key), repeat=5, number=10
                )
            ]
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] split {scheme_name}: {exc}", flush=True)
            continue

        # Время recover.
        try:
            ss = sim.scheme.split(sim.secret_key)
            selected = list(ss.shares.items())[:kk]  # ← было list(ss.shares.values())[:kk]
            recover_samples = [
                t * 1e6 / 10
                for t in repeat(
                    lambda: sim.scheme.reconstruct(selected), repeat=5, number=10
                )
            ]
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] recover {scheme_name}: {exc}", flush=True)
            continue

        rows.append(Measurement(
            scheme=scheme_name, bits=bits, n=n, scenario_k=kk, threshold=kk,
            share_bytes=size,
            split_us=median(split_samples),
            recover_us=median(recover_samples),
            split_mad_us=0.0, recover_mad_us=0.0,
        ))
    return rows




def build_scheme_comparison_leo(
    leo: LEOModel,
    gs_lat: float = 55.0,
    gs_lon: float = 37.0,
    attacker_lat: float = -30.0,
    attacker_lon: float = -60.0,
    minutes: int = 120,
    step: int = 3,
    bits: int = 128,
    n: int = 12,
    k_shamir: int = 3,
    out_html: str = "schemes_on_leo_live.html",
) -> str:
    """Сгенерировать интерактивное сравнение 5 схем на одной LEO-модели."""
    # 1. Один общий секрет — чтобы сравнение было честным.
    common_secret = secrets.randbits(bits)

    sims: dict[str, SessionSimulator] = {}
    for scheme in SCHEMES:
        kk = n if scheme in ("xor", "crt") else k_shamir
        try:
            sim = SessionSimulator(leo, n=n, k=kk, scheme=scheme, bits=bits)
            sim.secret_key = common_secret
            sim.distribute()
            sims[scheme] = sim
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {scheme}: {exc}", flush=True)

    # 2. Статический benchmark: размер доли и время recover.
    bench = {r.scheme: r for r in compare_schemes_on_leo(leo, bits=bits, n=n, k=k_shamir)}

    # 3. Точки GS: жертва и атакующий.
    gs_victim = leo._gs_vector(gs_lat, gs_lon)
    gs_attacker = leo._gs_vector(attacker_lat, attacker_lon)

    # 4. Кадры.
    times = list(range(0, minutes, step))
    frames = []
    first_title = "Нет кадров"

    for t in times:
        visible_victim = set(leo.visible_at(t, gs_lat, gs_lon))
        visible_attacker = set(leo.visible_at(t, attacker_lat, attacker_lon,
                                             radius_km=4000))

        # 4-цветная раскраска спутников.
        points = np.array([s.position(t) for s in leo.sats])
        colors = []
        for s in leo.sats:
            in_v = s.sid in visible_victim
            in_a = s.sid in visible_attacker
            if in_v and in_a:
                colors.append(COLOR_BOTH)
            elif in_v:
                colors.append(COLOR_VICTIM)
            elif in_a:
                colors.append(COLOR_ATTACKER)
            else:
                colors.append(COLOR_NONE)

        # Слой спутников.
        sat_layer = go.Scatter3d(
            x=points[:, 0], y=points[:, 1], z=points[:, 2],
            mode="markers",
            marker=dict(size=5, color=colors),
            text=[f"Спутник {s.sid}" for s in leo.sats],
            hoverinfo="text",
            name="Спутники",
        )
        # GS-жертва (белый треугольник).
        gs_victim_layer = go.Scatter3d(
            x=[gs_victim[0]], y=[gs_victim[1]], z=[gs_victim[2]],
            mode="markers",
            marker=dict(symbol="diamond", size=10, color="white"),
            name="GS-жертва",
        )
        # GS-атакующий (красный ромб).
        gs_attacker_layer = go.Scatter3d(
            x=[gs_attacker[0]], y=[gs_attacker[1]], z=[gs_attacker[2]],
            mode="markers",
            marker=dict(symbol="diamond", size=10, color=COLOR_ATTACKER),
            name="GS-атакующий",
        )

        # 5 панелей справа.
        scheme_layers = []
        for idx, scheme in enumerate(SCHEMES):
            sim = sims.get(scheme)
            if sim is None:
                continue
            # Схемы сравниваем по видимости жертвы (это «легитимный» сценарий).
            # Если хочешь показать атаку — замени visible_victim на visible_attacker.
            key, count = sim.verified_key(visible_victim)
            ok = key is not None
            b = bench.get(scheme)
            size = f"{b.share_bytes:.0f} Б" if b else "?"
            rec = f"{b.recover_us:.1f} мкс" if b else "?"
            label = (f"<b>{scheme}</b><br>"
                     f"видно {count}/{sim.k}  →  "
                     f"{'✅ ключ собран' if ok else '❌ кворум не набран'}<br>"
                     f"доля {size} · recover {rec}")
            scheme_layers.append(go.Scatter(
                x=[0.12], y=[len(SCHEMES) - idx - 0.5],
                mode="markers+text",
                marker=dict(size=40, color=SCHEME_COLORS[scheme],
                            line=dict(color="white" if ok else "gray", width=2)),
                text=[label],
                textposition="middle right",
                textfont=dict(size=11, color="white"),
                showlegend=False,
                hoverinfo="skip",
            ))

        # Заголовок кадра.
        title_str = (
            f"5 схем на одной видимости · t={t} мин · "
            f"видимых для жертвы={len(visible_victim)} · "
            f"видимых для атакующего={len(visible_attacker)}"
        )
        if not frames:
            first_title = title_str

        frames.append(go.Frame(
            name=str(t),
            data=[sat_layer, gs_victim_layer, gs_attacker_layer, *scheme_layers],
            traces=list(range(3 + len(scheme_layers))),
            layout=go.Layout(title_text=title_str),
        ))

    # 5. Сборка фигуры.
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "scene"}, {"type": "xy"}]],
        column_widths=[0.55, 0.45],
        subplot_titles=[
            f"Орбиты (n={n}, жертва {gs_lat}°/{gs_lon}°, "
            f"атакующий {attacker_lat}°/{attacker_lon}°)",
            "Схемы разделения секрета на видимости жертвы",
        ],
    )
    if frames:
        for index, layer in enumerate(frames[0].data):
            fig.add_trace(layer, row=1, col=1 if index < 3 else 2)

    fig.frames = frames
    fig.update_layout(
        template="plotly_dark",
        scene=dict(
            aspectmode="cube",
            **{a: dict(visible=False) for a in ("xaxis", "yaxis", "zaxis")},
        ),
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, len(SCHEMES)]),
        title=first_title,
        sliders=[dict(
            active=0,
            currentvalue=dict(prefix="Минута "),
            steps=[dict(
                label=f.name,
                method="animate",
                args=[[f.name], dict(mode="immediate",
                                     frame=dict(duration=0, redraw=True),
                                     transition=dict(duration=0))],
            ) for f in frames],
        )],
        height=650,
        legend=dict(orientation="h", y=-0.05),
    )
    write_plotly_page(fig, out_html, "Сравнение пяти схем", auto_play=False)
    print(f"Сохранено: {out_html}", flush=True)
    return out_html
