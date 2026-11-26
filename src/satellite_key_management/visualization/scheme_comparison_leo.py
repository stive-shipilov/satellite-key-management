"""Сравнение пяти схем по доступности долей на общей орбитальной трассе."""
from __future__ import annotations

import secrets
from statistics import median
from timeit import repeat

from satellite_key_management.analysis.benchmark import byte_width, Measurement
from satellite_key_management.crypto.schemes import SCHEMES
from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.session import SessionSimulator

from .orbit_view import orbit_config, write_orbit_page


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


def _share_size(sim):
    """Размер полезной нагрузки доли при общих открытых параметрах."""
    scheme = sim.scheme
    label = byte_width(sim.n)
    if scheme.name == "crt":
        return label + sum(byte_width(modulus - 1) for modulus in scheme.impl.moduli) / sim.n
    word = byte_width(scheme.p - 1)
    return (sim.k + 1) * word if scheme.name == "blakley" else label + word


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
    *,
    orbit_groups=None,
) -> str:
    """Сравнить доступность ключа для пяти схем на каждой минуте трассы."""
    config = orbit_config(leo, minutes, step, gs_lat, gs_lon, k_shamir, groups=orbit_groups)
    sims = {}
    for name in SCHEMES:
        threshold = n if name in ("xor", "crt") else k_shamir
        try:
            sim = SessionSimulator(leo, n=n, k=threshold, scheme=name, bits=bits)
            sims[name] = sim
        except (ValueError, NotImplementedError) as error:
            print(f"[skip] {name}: {error}", flush=True)

    names = {"shamir": "Шамир", "blakley": "Блэкли", "feldman_vss": "Feldman VSS",
             "xor": "XOR", "crt": "CRT"}
    benchmark = {row.scheme: row for row in compare_schemes_on_leo(leo, bits=bits, n=n, k=k_shamir)}
    data = {
        "config": config,
        "observer": {"lat": attacker_lat, "lon": attacker_lon},
        "members": n,
        "schemes": [{
            "name": names[name],
            "threshold": sim.k,
            "size": round(_share_size(sim), 1),
            "recover_us": round(benchmark[name].recover_us, 1) if name in benchmark else None,
        } for name, sim in sims.items()],
    }
    write_orbit_page(
        out_html, "schemes", "Сравнение пяти схем",
        "Для всех схем используется одна орбитальная трасса. "
        "У станции и радионаблюдателя одинаковая маска угла места. Кворум рассчитывается для станции.",
        data,
    )
    print(f"Сохранено: {out_html}", flush=True)
    return out_html
