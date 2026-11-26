from html.parser import HTMLParser
from types import SimpleNamespace

from satellite_key_management.visualization.report import save_index


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = set()
        self.anchors = set()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        self.references.update(attrs[key] for key in ("src", "href") if key in attrs)
        if "id" in attrs:
            self.anchors.add(f"#{attrs['id']}")


def test_index_links_all_available_report_outputs(tmp_path):
    outputs = {
        "metrics_dashboard.html", "simulation_3d.html", "contact_risk.html",
        "contacts.html", "schemes_on_leo_live.html",
        "attacker_accumulation.png", "compromise_step.png", "refresh.png", "dynamic_k.png",
        "schemes_on_leo.png", "radar.png", "contacts.csv", "orbital_experiment.csv",
        "schemes_on_leo.csv", "benchmark.csv",
    }
    for name in outputs:
        (tmp_path / name).touch()
    history = [SimpleNamespace(delivered=True, handover=False)]
    save_index(tmp_path, history)

    page = PageLinks()
    page.feed((tmp_path / "index.html").read_text(encoding="utf-8"))
    assert page.references - page.anchors == outputs | {"report.css"}
    assert (tmp_path / "report.css").is_file()

    (tmp_path / "radar.png").unlink()
    save_index(tmp_path, history)
    updated = PageLinks()
    updated.feed((tmp_path / "index.html").read_text(encoding="utf-8"))
    assert "radar.png" not in updated.references
