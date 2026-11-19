"""Детерминированный сценарий связи с окнами 6–12 минут и одним сеансом AES."""

import csv
from dataclasses import asdict, dataclass
from random import Random

from ..crypto.threshold_sig import generate_key, sign_share, combine_signs, verify
from .session import SessionSimulator


class ContactSchedule:
    """Шесть узлов по очереди входят в зону. Длительность прохода фиксируется seed."""

    def __init__(self, seed=7):
        rng = Random(seed)
        self.durations = tuple(rng.randint(6, 12) for _ in range(6))

    def visible_at(self, minute, *_):
        return [
            sid
            for sid, duration in enumerate(self.durations, 1)
            if (minute - 3 * (sid - 1)) % 18 < duration
        ]


@dataclass(frozen=True)
class Contact:
    minute: int
    visible: int
    relay: int | None
    handover: bool
    epoch: int
    sequence: int
    delivered: bool
    signature_verified: bool
    replay_rejected: bool


def session_history(minutes, refresh_every=30):
    """AES-GCM для каждого пакета, пороговая подпись первого доступного пакета."""
    if min(minutes, refresh_every) < 1:
        raise ValueError("Длительность и период должны быть положительными")
    schedule = ContactSchedule()
    sim = SessionSimulator(schedule, n=6, k=2)
    sim.distribute()
    public, shares = generate_key(sim.n, sim.k)
    signed = False
    history = []
    for t in range(minutes):
        if t and t % refresh_every == 0:
            sim.refresh()
        visible = schedule.visible_at(t)
        previous = sim.relay
        message = f"telemetry/minute={t}".encode()
        signature = None
        if not signed and len(visible) >= sim.k:
            partials = [sign_share(shares[i - 1], message) for i in visible[: sim.k]]
            signature = combine_signs(partials, message, public)
        packet = sim.seal(message + (signature or b""))
        received = sim.receive(packet, visible)
        checked = rejected = False
        if received is not None:
            if signature is not None:
                checked = verify(received[:-96], received[-96:], public.public_key)
                if not checked:
                    raise ValueError("Подпись телеметрии не прошла проверку")
                signed = True
                try:
                    sim.receive(packet, visible)
                except ValueError:
                    rejected = True
                if not rejected:
                    raise RuntimeError("Приёмник повторно принял пакет")
        relay = sim.relay if received is not None else None
        history.append(
            Contact(
                t,
                len(visible),
                relay,
                previous is not None and relay is not None and relay != previous,
                sim.epoch,
                packet[0],
                received is not None,
                checked,
                rejected,
            )
        )
    return history


def save_contact_history(history, out):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    with (out / "contacts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(history[0])))
        writer.writeheader()
        writer.writerows(map(asdict, history))
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=("Видимость и кворум", "Доставка и смена обслуживающего узла"),
    )
    t = [r.minute for r in history]
    fig.add_trace(
        go.Scatter(
            x=t,
            y=[r.visible for r in history],
            mode="lines",
            line_shape="hv",
            name="Видимые спутники",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=2, line_dash="dash", annotation_text="Кворум 2", row=1, col=1)
    fig.add_trace(
        go.Scatter(
            x=t,
            y=[r.relay or 0 for r in history],
            mode="lines",
            line_shape="hv",
            name="Номер узла (0 — ожидание)",
        ),
        row=2,
        col=1,
    )
    for name, events, marker in (
        ("Handover", [r for r in history if r.handover], "diamond"),
        ("Подпись проверена", [r for r in history if r.signature_verified], "star"),
    ):
        fig.add_trace(
            go.Scatter(
                x=[r.minute for r in events],
                y=[r.relay for r in events],
                mode="markers",
                marker=dict(symbol=marker, size=10),
                name=name,
            ),
            row=2,
            col=1,
        )
    boundaries = [b.minute for a, b in zip(history, history[1:]) if a.epoch != b.epoch]
    for minute in boundaries[:50]:
        fig.add_vline(x=minute, line_dash="dot", line_color="gray", row=2, col=1)
    fig.update_yaxes(dtick=1)
    fig.update_xaxes(title_text="Время, мин", row=2, col=1)
    fig.update_layout(
        title="Синтетические окна 6–12 мин · пунктир отмечает обновление долей",
        template="plotly_white",
        height=640,
        legend=dict(orientation="h", y=-0.15),
    )
    fig.write_html(out / "contacts.html", include_plotlyjs="directory")
