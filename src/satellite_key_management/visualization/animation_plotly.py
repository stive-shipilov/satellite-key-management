"""Интерактивный орбитальный сценарий с редактором раскрытий."""

from .orbit_view import orbit_config, write_orbit_page


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
    scenario_leo=None,
):
    """Открыть новый сценарий; параметры конуса оставлены для прежних вызовов."""
    from satellite_key_management.attacks.attacks import track_visibility

    config = orbit_config(scenario_leo if scenario_leo is not None else sim.leo, t_total, step, gs_lat, gs_lon, sim.k, refresh_every)
    if tracker is None:
        tracker = track_visibility(sim, t_total, gs_lat, gs_lon, refresh_every=refresh_every or None)

    write_orbit_page(
        out_html, "visibility", "Орбиты и зона видимости",
        "Меняйте созвездие и порог, задавайте события раскрытия и сравнивайте доступность долей "
        "у наземной станции и у нарушителя.",
        {"config": config},
    )
    print(f"Сохранено: {out_html}", flush=True)
    return out_html, tracker
