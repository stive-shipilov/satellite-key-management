"""Offline 3D viewer shared by the visibility and scheme comparison reports."""

from base64 import b64encode
from html import escape
from io import BytesIO
import json
from math import degrees
from pathlib import Path
from shutil import copyfile

from PIL import Image

from .report import copy_report_styles


DEFAULT_OBSERVER = {"lat": 55.0, "lon": 45.0}
DEMO_GROUPS = (
    {"n": 48, "planes": 6, "altitude": 550, "inclination": 53},
    {"n": 36, "planes": 2, "altitude": 570, "inclination": 84},
    {"n": 36, "planes": 2, "altitude": 510, "inclination": 25},
)


def orbit_config(leo, minutes, step, lat, lon, threshold, refresh=0, *, groups=None, rotation=60):
    if min(minutes, step) < 1:
        raise ValueError("Длительность и шаг должны быть положительными")
    config = {
        "n": len(leo.sats),
        "planes": len({sat.raan for sat in leo.sats}),
        "altitude": leo.sats[0].altitude,
        "inclination": round(degrees(leo.sats[0].inc), 3),
        "lat": lat, "lon": lon, "mask": 10,
        "k": threshold, "refresh": refresh, "rotation": rotation, "minutes": minutes,
    }
    if groups is not None:
        config["groups"] = groups
    return config


def _earth_texture():
    texture = Path(__file__).resolve().parents[1] / "earth.jpg"
    if not texture.is_file():
        return None
    with Image.open(texture) as source, BytesIO() as buffer:
        source.convert("RGB").resize((768, 384), Image.Resampling.LANCZOS).save(
            buffer, format="JPEG", quality=85
        )
        return "data:image/jpeg;base64," + b64encode(buffer.getvalue()).decode("ascii")


OBSERVER_CONTROLS = """<section class="orbit-panel orbit-observer" id="observer-settings">
  <div>
    <h2>Наземный радионаблюдатель</h2>
    <p id="observer-position"></p>
    <p>Для обеих точек действует одна маска угла места. Доли нарушителя задаются событиями раскрытия.</p>
  </div>
  <form id="observer-form">
    <label class="observer-toggle"><input name="enabled" type="checkbox" checked> Показывать наблюдателя</label>
    <div class="scenario-fields">
      <label>Широта наблюдателя, ° <input name="lat" type="number" min="-90" max="90" step="any" required></label>
      <label>Долгота наблюдателя, ° <input name="lon" type="number" min="-180" max="180" step="any" required></label>
    </div>
    <p class="scenario-note">Северная широта и восточная долгота задаются положительными числами.</p>
    <div class="scenario-actions">
      <button class="orbit-play" type="submit">Применить положение</button>
      <button type="button" id="show-observer">Показать на глобусе</button>
    </div>
    <output id="observer-message" aria-live="polite"></output>
  </form>
</section>"""


ORBIT_FORM = """<div>
    <h2>Параметры прогона</h2>
    <form id="scenario-config">
      <div class="scenario-fields">
        <label>Групп спутников <select name="group-count"><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></label>
        <label>Порог долей <input name="k" type="number" min="1" required></label>
        <label>Обновление долей, мин <input name="refresh" type="number" min="0" required></label>
        <label>Смена ключа, мин <input name="rotation" type="number" min="0" required></label>
      </div>
      <div id="orbit-groups"></div>
      <template id="orbit-group-template">
        <fieldset class="orbit-group scenario-fields">
          <legend></legend>
          <label>Спутников <input data-field="n" type="number" min="1" max="256" required></label>
          <label>Плоскостей <input data-field="planes" type="number" min="1" required></label>
          <label>Высота, км <input data-field="altitude" type="number" min="200" max="2000" required></label>
          <label>Наклонение, ° <input data-field="inclination" type="number" min="0" max="180" step="any" required></label>
          <small class="group-period"></small>
        </fieldset>
      </template>
      <details>
        <summary>Положение станции и длительность</summary>
        <div class="scenario-fields">
          <label>Широта, ° <input name="lat" type="number" min="-90" max="90" step="any" required></label>
          <label>Долгота, ° <input name="lon" type="number" min="-180" max="180" step="any" required></label>
          <label>Угол места от, ° <input name="mask" type="number" min="0" max="90" step="any" required></label>
          <label>Длительность, мин <input name="minutes" type="number" min="1" max="1440" required></label>
        </div>
      </details>
      <div class="scenario-actions">
        <button class="orbit-play" type="submit">Применить параметры</button>
        <output id="config-message" aria-live="polite"></output>
      </div>
      <p class="scenario-note">Ноль отключает соответствующее расписание. Новый ключ начинает новый сеанс и оба отсчёта.</p>
    </form>
  </div>"""


MANUAL_EVENTS = """<div id="scenario-events">
    <h2>События сценария</h2>
    <form id="scenario-event">
      <div class="scenario-fields event-fields">
        <label>Событие <select name="kind">
          <option value="reveal">Разовое раскрытие доли</option>
          <option value="persist">Сохраняющийся доступ к доле</option>
          <option value="isolate">Изолировать спутник</option>
          <option value="restore">Восстановить спутник</option>
          <option value="rotate">Сменить ключ</option>
          <option value="key">Раскрытие ключа целиком</option>
        </select></label>
        <label>Минута <input name="minute" type="number" min="0" required></label>
        <label id="event-node">Спутник <select name="sid" required></select></label>
      </div>
      <div class="scenario-actions">
        <button class="orbit-play" type="submit" id="save-event">Добавить событие</button>
        <button type="button" id="cancel-event" hidden>Отменить правку</button>
        <button type="button" id="event-now">Текущая минута</button>
      </div>
      <output id="event-message" aria-live="polite"></output>
    </form>
    <div class="scenario-actions presets" aria-label="Готовые сценарии">
      <button type="button" data-example="below">Пример ниже порога</button>
      <button type="button" data-example="quorum">Пример с раскрытием ключа</button>
      <button type="button" data-example="empty">Очистить события</button>
    </div>
    <ol class="scenario-log" id="event-log" aria-label="Журнал событий"></ol>
  </div>"""


CONTACT_SETTINGS = """<div id="contact-settings">
    <h2>Раскрытие долей при контакте</h2>
    <p class="scenario-note">Модель задаёт задержку и вероятность раскрытия доли при условной утечке в канале выдачи.</p>
    <form id="contact-form">
      <div class="scenario-fields">
        <label>Непрерывный контакт, мин <input name="duration" type="number" min="1" max="1440" required></label>
        <label>Вероятность раскрытия за окно, % <input name="probability" type="number" min="0" max="100" step="any" required></label>
        <label>Начальное число генератора <input name="seed" type="number" min="0" max="4294967295" required></label>
      </div>
      <div class="scenario-actions">
        <button class="orbit-play" type="submit">Применить параметры контакта</button>
        <output id="contact-message" aria-live="polite"></output>
      </div>
    </form>
    <div class="scenario-actions presets" aria-label="Готовые примеры радиоконтакта">
      <button type="button" data-contact-example="short">Пример: ключ раскрыт</button>
      <button type="button" data-contact-example="long">Пример: ключ защищён</button>
    </div>
    <p class="scenario-note">Примеры восстанавливают стартовую орбиту и положение наблюдателя. Вероятность 100% выбрана для сравнения длительности контакта.</p>
    <details class="contact-log-details">
      <summary>Журнал исходов контакта</summary>
      <ol class="scenario-log" id="contact-log" aria-label="Журнал исходов контакта"></ol>
    </details>
  </div>"""


METHOD_DETAILS = """<details class="orbit-panel orbit-method">
  <summary>Допущения и источники</summary>
  <p>Сферическая Земля, круговые орбиты и вращение Земли относительно орбит. Первая группа
  использует опубликованный профиль 550 км и 53°. Параметры второй и третьей группы заданы
  для демонстрации. В каждой группе узлы орбит и спутники распределены равномерно. Угол места задаёт геометрическую
  видимость. Предполагается, что за каждую минуту станция получает по одной подлинной доле от
  каждого видимого неизолированного спутника по защищённому каналу. При расчёте кворума накопление
  долей станцией между минутами отсутствует. Радиопотери, задержку и декодирование пакетов
  эта визуализация не моделирует.</p>
  <p>{disclosure_method}</p>
  <p><a href="https://docs.fcc.gov/public/attachments/fcc-21-48a1.pdf">Профиль 53°</a>
  · <a href="https://ssd.jpl.nasa.gov/astro_par.html">Параметры JPL</a>
  · <a href="https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html">Радиус Земли NASA</a>
  · <a href="https://pwg.gsfc.nasa.gov/stargaze/Srotfram1.htm">Вращение Земли</a></p>
</details>"""


MANUAL_METHOD = (
    "Раскрытия задаются вручную. Доступ к узлу даёт его текущую долю и доли следующих эпох "
    "до изоляции или восстановления. Прежние раскрытия учитываются до конца эпохи. В пределах одной "
    "минуты сначала происходят изоляция и восстановление, затем ротация или плановое обновление, "
    "затем раскрытия. Ротация начинает новый сеанс и новый интервал обновления. "
    "Старые доли считаются удалёнными на узлах после смены эпохи."
)

CONTACT_METHOD = (
    "Обмен, при котором доля может раскрыться, предполагается в каждом видимом окне. Контакт "
    "отсчитывается с первой видимой минуты. Каждая следующая минута засчитывается, пока спутник "
    "виден на последовательных отсчётах. В рамках одного такого окна в одной эпохе выполняется "
    "одна вероятностная проверка по достижении заданного времени. Потеря видимости или смена эпохи "
    "сбрасывает отсчёт. Наблюдатель может видеть несколько спутников одновременно. Доли разных эпох "
    "учитываются раздельно. Раскрытие сохраняется после обновления долей и сбрасывается при смене ключа. Параметры условные "
    "и служат для анализа риска. Модель работает с событиями на синтетической орбите."
)


def save_contact_risk_page(out, config, observer):
    write_orbit_page(
        out, "contact", "Риск раскрытия при радиоконтакте",
        "Сравните штатный сбор долей станцией и условное раскрытие долей наблюдателю "
        "при непрерывном контакте.",
        {
            "config": config, "observer": observer,
            "contact_presets": {
                "short": {"duration": 3, "probability": 1, "seed": 7},
                "long": {"duration": 15, "probability": 1, "seed": 7},
            },
        },
    )


def write_orbit_page(out_html, mode, title, description, data):
    out = Path(out_html)
    copy_report_styles(out.parent)
    for name in ("orbit-player.js", "orbit-player.css", "orbit-scenario.js"):
        source = Path(__file__).with_name(name)
        destination = out.parent / name
        if source.resolve() != destination.resolve():
            copyfile(source, destination)

    data.setdefault("observer", DEFAULT_OBSERVER)
    data.setdefault("group_presets", DEMO_GROUPS)
    data.update(mode=mode, texture=_earth_texture())
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    title = escape(title)
    other_page, other_title = (
        ("schemes_on_leo_live.html", "Сравнение пяти схем")
        if mode == "visibility" else ("simulation_3d.html", "Орбиты и зона видимости")
    )
    metrics_title = "Восстановление ключа" if mode == "schemes" else "Состояние сеанса"
    controls = ""
    settings_link = ""
    observer_controls = OBSERVER_CONTROLS
    if mode != "schemes":
        settings = MANUAL_EVENTS if mode == "visibility" else CONTACT_SETTINGS
        method = MANUAL_METHOD if mode == "visibility" else CONTACT_METHOD
        controls = (
            f'<section class="orbit-panel orbit-config" id="scenario-settings">{ORBIT_FORM}{settings}</section>'
            + METHOD_DETAILS.format(disclosure_method=method)
        )
        settings_link = '<a href="#scenario-settings">Настроить сценарий ↓</a>'
    if mode == "contact":
        observer_controls = observer_controls.replace(
            "Доли нарушителя задаются событиями раскрытия.",
            "Положение наблюдателя определяет непрерывные окна условного раскрытия.",
        )
        settings_link += '<a href="#contact-settings">Настроить радиоконтакт ↓</a>'
    page_class = "orbit-page orbit-contact" if mode == "contact" else "orbit-page"
    out.write_text(f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Спутниковая связь</title>
<link rel="stylesheet" href="report.css">
<link rel="stylesheet" href="orbit-player.css">
<script src="orbit-scenario.js" defer></script>
<script src="orbit-player.js" defer></script>
</head>
<body class="{page_class}">
<header class="topbar"><div class="shell wide"><a href="index.html">← К отчёту</a>
<a href="{other_page}">{other_title} →</a></div></header>
<main class="shell wide orbit-main">
  <header class="orbit-heading"><h1>{title}</h1><p>{escape(description)}</p>
  <nav aria-label="Настройки визуализации">{settings_link}<a href="#observer-settings">Настроить наблюдателя ↓</a></nav></header>
  <noscript><p>Для воспроизведения включите JavaScript.</p></noscript>
  <div id="orbit-error" role="alert" hidden>Не удалось открыть 3D-сцену.</div>
  <div class="orbit-layout">
    <section class="orbit-panel orbital-scene" aria-label="Трёхмерная сцена">
      <div class="orbit-stage">
        <canvas id="orbit-canvas" tabindex="0" aria-label="Орбиты спутников. Стрелки вращают Землю, плюс и минус меняют масштаб."></canvas>
        <div class="orbit-stage-header">
          <div><h2>Орбитальная сцена</h2><p id="constellation"></p></div>
          <button id="reset-view" type="button">Вернуть вид</button>
        </div>
        <span id="satellite-label" class="satellite-label" hidden></span>
      </div>
      <div class="orbit-scene-footer"><div id="orbit-legend" class="orbit-legend"></div>
        <div id="orbit-group-legend" class="orbit-legend orbit-link-legend" aria-label="Группы орбит"></div>
        <div id="orbit-link-legend" class="orbit-legend orbit-link-legend" aria-label="Линии связи и радиовидимости"></div>
        <p>Перетащите для вращения. Колесо меняет масштаб.</p>
      </div>
    </section>
    <section class="orbit-panel orbit-detail">
      <h2>{metrics_title}</h2>
      <div id="orbit-metrics"></div>
    </section>
    <section class="orbit-panel orbit-timeline" aria-label="Управление временем">
      <div class="orbit-controls">
        <button id="orbit-play" class="orbit-play" type="button">▶ Пуск</button>
        <output id="orbit-time" for="orbit-seek"></output>
        <label class="orbit-speed">Скорость
          <select id="orbit-speed"><option value="0.5">0,5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select>
        </label>
      </div>
      <input id="orbit-seek" type="range" min="0" step="1" value="0" aria-label="Минута симуляции">
      <div class="orbit-time-range"><span>0 мин</span><span id="orbit-duration"></span></div>
    </section>
  </div>
{controls}
{observer_controls}
</main>
<script id="orbit-data" type="application/json">{payload}</script>
</body>
</html>""", encoding="utf-8")
