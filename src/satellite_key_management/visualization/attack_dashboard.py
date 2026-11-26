"""Локальный экран сравнения орбитальных сценариев на общей шкале времени."""

import json
from pathlib import Path

from .report import ensure_plotly_assets


def save_attack_dashboard(trials, contacts, out: Path):
    cases = {}
    for trial in trials:
        result = trial.result
        timeline = []
        margins = []
        for sample, delivery in zip(trial.samples, trial.reception, strict=True):
            threshold = sample.threshold if sample.epoch else None
            if threshold is not None:
                margins.append(max(0, threshold - sample.shares))
            timeline.append({
                "minute": sample.minute,
                "epoch": sample.epoch,
                "threshold": threshold,
                "shares": sample.shares,
                "exposures": sample.new_exposures,
                "keyExposed": sample.key_exposed,
                "verified": delivery.valid_shares,
                "delivered": delivery.delivered,
                "event": delivery.key_event,
            })

        cases.setdefault(result.exposure_interval, {})[result.policy] = {
            "firstQuorum": result.first_quorum_minute,
            "duration": result.duration,
            "threat": result.threat,
            "refreshInterval": result.refresh_interval,
            "delivered": result.delivered,
            "longestOutage": result.longest_outage,
            "exposedMinutes": sum(sample.key_exposed for sample in trial.samples),
            "closestToQuorum": min(margins, default=None),
            "timeline": timeline,
        }

    replay = [{"minute": row.minute, "sequence": row.sequence, "reason": row.replay_reason}
              for row in contacts if row.replay_rejected]
    ensure_plotly_assets(out.parent)
    template = Path(__file__).with_name("attack_dashboard.html").read_text(encoding="utf-8")
    data = json.dumps({"cases": cases, "replay": replay}, separators=(",", ":"))
    html = template.replace("<!-- plotly-script -->", '<script src="plotly.min.js"></script>')
    out.write_text(html.replace("/* dashboard-data */ null", data), encoding="utf-8")
