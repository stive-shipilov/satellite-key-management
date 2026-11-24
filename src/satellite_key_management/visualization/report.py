"""Страницы локального отчёта и общие ресурсы для визуализаций."""

from html import escape
from pathlib import Path
from shutil import copyfile


INTERACTIVE_VIEWS = (
    ("metrics_dashboard.html", "Исходы атак", "Сравните раскрытые доли, доставку и состояние ключа в двух сценариях."),
    ("simulation_3d.html", "Орбиты и зона видимости", "Проследите движение спутников, видимость станции и события раскрытия."),
    ("contacts.html", "Связь наземной станции", "Посмотрите кворум, смену обслуживающего спутника и результат проверки подписи."),
    ("schemes_on_leo_live.html", "Сравнение пяти схем", "Сопоставьте доступность кворума на общей орбитальной трассе."),
)

STATIC_VIEWS = (
    ("attacker_accumulation.png", "Накопление долей", "Раскрытые доли текущей эпохи и порог."),
    ("compromise_step.png", "Граница восстановления", "Зависимость восстановления ключа от числа подлинных долей."),
    ("refresh.png", "Обновление долей", "Смена эпох в учебной модели накопления."),
    ("dynamic_k.png", "Адаптивный порог", "Выбор порога по видимости и заданному уровню угрозы."),
    ("schemes_on_leo.png", "Характеристики пяти схем", "Размер долей и время вычислений."),
    ("radar.png", "Сводка бенчмарка", "Сравнение времени и размеров в одном сценарии."),
)

DATA_FILES = (
    ("contacts.csv", "Журнал контактов"),
    ("orbital_experiment.csv", "Орбитальный эксперимент"),
    ("schemes_on_leo.csv", "Сравнение пяти схем"),
    ("benchmark.csv", "Бенчмарк"),
)


def copy_report_styles(out: Path):
    source = Path(__file__).with_name("report.css")
    destination = out / source.name
    if source.resolve() != destination.resolve():
        copyfile(source, destination)


def ensure_plotly_assets(out: Path):
    from plotly.offline import get_plotlyjs

    copy_report_styles(out)
    script = out / "plotly.min.js"
    if not script.is_file():
        script.write_text(get_plotlyjs(), encoding="utf-8")


def write_plotly_page(figure, out, title: str, **options):
    out = Path(out)
    ensure_plotly_assets(out.parent)
    graph = figure.to_html(full_html=False, include_plotlyjs="directory", **options)
    page_title = escape(title)
    out.write_text(f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title} · Спутниковая связь</title>
<link rel="stylesheet" href="report.css">
</head>
<body>
<header class="topbar"><div class="shell wide"><a href="index.html">← К отчёту</a><strong>{page_title}</strong></div></header>
<main class="shell wide"><div class="plot-frame">{graph}</div></main>
</body>
</html>""", encoding="utf-8")


def _table(title, columns, records, *, introduction="", opened=False):
    headings = "".join(f'<th scope="col">{escape(label)}</th>' for label in columns)
    rows = []
    for record in records:
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in record)
        rows.append(f"<tr>{cells}</tr>")
    state = " open" if opened else ""
    note = f"<p>{escape(introduction)}</p>" if introduction else ""
    return f"""<details class="table-card"{state}>
<summary>{escape(title)}</summary>{note}
<div class="table-scroll"><table>
<thead><tr>{headings}</tr></thead><tbody>{''.join(rows)}</tbody>
</table></div>
</details>"""


def _orbital_table(results, threat):
    labels = {
        "fixed": "Фиксированный порог",
        "fixed_refresh": "Фиксированный порог с обновлением",
        "adaptive_refresh": "Адаптивный порог с обновлением",
    }
    rows = []
    for policy, label in labels.items():
        group = [row for row in results if row.policy == policy]
        if not group:
            continue
        first = group[0]
        quorum_times = [row.first_quorum_minute for row in group if row.first_quorum_minute is not None]
        earliest = f"{min(quorum_times)} мин" if quorum_times else "За время прогона не достигнут"
        rows.append((
            label, f"{first.delivered}/{first.duration} ({first.delivered / first.duration:.0%})",
            f"{first.longest_outage} мин", f"{len(quorum_times)}/{len(group)}", earliest,
        ))
    fixed_threshold = next((row.fixed_threshold for row in results if row.fixed_threshold), None)
    refresh_interval = next((row.refresh_interval for row in results if row.refresh_interval), None)
    description = f"Уровень угрозы для адаптивного порога {threat:g}."
    if fixed_threshold and refresh_interval:
        description = f"Фиксированный порог {fixed_threshold}, обновление раз в {refresh_interval} минут. {description}"
    return _table(
        "Орбитальный эксперимент",
        ("Режим", "Доставлено", "Макс. простой", "Сценариев с кворумом", "Самый ранний кворум"),
        rows, introduction=description, opened=True,
    )


def _cards(views, files, *, previews=False):
    cards = []
    for name, title, description in views:
        if name not in files:
            continue
        preview = f'<img src="{name}" alt="" loading="lazy">' if previews else ""
        cards.append(f'<a class="card" href="{name}">{preview}<strong>{title}</strong><span>{description}</span></a>')
    return "\n".join(cards)


def _section(identifier, title, content):
    return f'<section id="{identifier}"><h2>{title}</h2>{content}</section>' if content else ""


def save_index(out, history, *, comparison_rows=None, bench_sample=None, tracker=None,
               orbital_results=(), threat=0.3):
    out = Path(out)
    copy_report_styles(out)
    files = {path.name for path in out.iterdir() if path.is_file()}
    delivered = sum(row.delivered for row in history)
    handovers = sum(row.handover for row in history)

    interactive = _cards(INTERACTIVE_VIEWS, files)
    gallery = _cards(STATIC_VIEWS, files, previews=True)
    data_links = "".join(
        f'<li><a href="{name}">{label} · CSV</a></li>'
        for name, label in DATA_FILES if name in files
    )
    sections = [
        ("views", "Интерактивные визуализации", f'<div class="card-grid">{interactive}</div>' if interactive else ""),
        ("charts", "Графики", f'<div class="card-grid gallery">{gallery}</div>' if gallery else ""),
        ("data", "Данные", f'<ul class="data-links">{data_links}</ul>' if data_links else ""),
    ]
    tables = []
    if orbital_results:
        tables.append(_orbital_table(orbital_results, threat))
    if comparison_rows:
        rows = ((r.scheme, r.threshold, f"{r.share_bytes:.1f}", f"{r.split_us:.1f}", f"{r.recover_us:.1f}")
                for r in comparison_rows)
        tables.append(_table("Сравнение пяти схем", ("Схема", "k", "Доля, байт", "Выдача, мкс",
                                                      "Восстановление, мкс"), rows))
    if bench_sample:
        rows = ((r.scheme, r.bits, r.n, r.threshold, f"{r.share_bytes:.1f}", f"{r.split_us:.1f}",
                 f"{r.recover_us:.1f}") for r in bench_sample)
        tables.append(_table("Бенчмарк схем", ("Схема", "Бит", "n", "k", "Доля, байт", "Выдача, мкс",
                                              "Восстановление, мкс"), rows))
    if tracker is not None and tracker.history:
        minute = tracker.time_to_compromise()
        quorum = "За время прогона не достигнут" if minute is None else f"{minute} мин"
        state = "Раскрыт по модели" if tracker.history[-1].key_exposed else "Кворум ниже порога"
        contact_samples = any(sample.visible for sample in tracker.history)
        quorum_share = f"{tracker.success_rate:.0%}" if contact_samples else "Отсчётов с видимостью нет"
        tables.append(_table("Раскрытие долей в опорном сценарии", ("Показатель", "Результат"), (
            ("Первый кворум из раскрытых долей", quorum),
            ("Состояние ключа в конце", state),
            ("Доля отсчётов с видимостью и накопленным кворумом", quorum_share),
            ("Обновлений долей", tracker.refreshes),
        )))
    sections.append(("results", "Результаты эксперимента", "".join(tables)))

    navigation = "".join(f'<a href="#{identifier}">{label}</a>' for identifier, label, content in sections if content)
    body = "".join(_section(*section) for section in sections)
    primary = '<a class="primary" href="metrics_dashboard.html">Сравнить исходы атак →</a>' if "metrics_dashboard.html" in files else ""

    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Спутниковая связь · Отчёт симуляции</title>
<link rel="stylesheet" href="report.css">
</head>
<body>
<header class="topbar"><div class="shell">
<strong>Спутниковая связь</strong><nav aria-label="Разделы отчёта">{navigation}</nav>
</div></header>
<main class="shell report">
<header class="hero">
<div><h1>Устойчивость спутниковой связи</h1>
<p>Орбитальная модель, пороговое управление ключами и сценарии раскрытия долей.</p>{primary}</div>
<dl aria-label="Результаты синтетического сценария">
<div><dt>Длительность синтетического сценария</dt><dd>{len(history)} мин</dd></div>
<div><dt>Доставлено пакетов</dt><dd>{delivered} / {len(history)}</dd></div>
<div><dt>Смен обслуживающего узла</dt><dd>{handovers}</dd></div>
</dl>
</header>
{body}
</main>
</body>
</html>"""
    (out / "index.html").write_text(html, encoding="utf-8")
