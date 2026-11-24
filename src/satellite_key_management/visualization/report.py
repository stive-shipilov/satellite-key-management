"""Стартовая страница локального отчёта, все ссылки относительны."""


def save_index(out, history, *, comparison_rows=None, bench_sample=None, tracker=None,
               orbital_results=(), threat=0.3):
    delivered = sum(row.delivered for row in history)
    handovers = sum(row.handover for row in history)

    comparison_html = ""
    if comparison_rows:
        rows = "".join(
            f"<tr><td>{r.scheme}</td><td>{r.threshold}</td>"
            f"<td>{r.share_bytes:.1f}</td>"
            f"<td>{r.split_us:.1f}</td><td>{r.recover_us:.1f}</td></tr>"
            for r in comparison_rows
        )
        comparison_html = f"""
<h2>Сравнение 5 схем на LEO-модели (одна видимость)</h2>
<table border="1" cellpadding="6" style="border-collapse:collapse">
<tr><th>схема</th><th>k</th><th>доля, байт</th><th>split, мкс</th><th>recover, мкс</th></tr>
{rows}
</table>
<p><a href="schemes_on_leo.png">Гистограмма</a> · <a href="schemes_on_leo.csv">CSV</a></p>
"""

    bench_html = ""
    if bench_sample:
        rows = "".join(
            f"<tr><td>{r.scheme}</td><td>{r.bits}</td><td>{r.n}</td><td>{r.threshold}</td>"
            f"<td>{r.share_bytes:.1f}</td><td>{r.split_us:.1f}</td>"
            f"<td>{r.recover_us:.1f}</td></tr>"
            for r in bench_sample
        )
        bench_html = f"""
<h2>Классический benchmark (128 бит, n=6, k=3)</h2>
<table border="1" cellpadding="6" style="border-collapse:collapse">
<tr><th>схема</th><th>бит</th><th>n</th><th>k</th><th>доля, байт</th>
<th>split, мкс</th><th>recover, мкс</th></tr>
{rows}
</table>
<p><a href="benchmark.csv">Полный CSV</a> · <a href="radar.png">Radar</a></p>
"""

    tracker_html = ""
    if tracker is not None:
        minute = tracker.time_to_compromise()
        quorum_time = "не достигнут за время прогона" if minute is None else f"{minute} мин"
        contact_samples = sum(bool(sample.visible) for sample in tracker.history)
        quorum_share = f"{tracker.success_rate:.0%}" if contact_samples else "нет отсчётов с видимостью"
        key_exposed = "раскрыт" if tracker.history[-1].key_exposed else "кворум не накоплен"
        tracker_html = f"""
<h2>Раскрытие долей в опорном сценарии</h2>
<p>Фиксированный порог, обновление каждые 30 минут, модельное раскрытие одной доли каждые 15 минут.</p>
<ul>
<li>Доля отсчётов с видимостью, в которых собран кворум раскрытых долей: <b>{quorum_share}</b></li>
<li>Первый кворум из раскрытых долей: <b>{quorum_time}</b></li>
<li>Состояние ключа в конце прогона по модели: <b>{key_exposed}</b></li>
<li>Обновлений долей: {tracker.refreshes}</li>
</ul>
"""

    orbital_html = ""
    if orbital_results:
        labels = {
            "fixed": "Фиксированный порог",
            "fixed_refresh": "Фиксированный порог с обновлением",
            "adaptive_refresh": "Адаптивный порог с обновлением",
        }
        rows = []
        fixed_threshold = orbital_results[0].fixed_threshold
        refresh_interval = next(row.refresh_interval for row in orbital_results if row.refresh_interval)
        for policy, label in labels.items():
            group = [row for row in orbital_results if row.policy == policy]
            first = group[0]
            quorum_times = [row.first_quorum_minute for row in group
                            if row.first_quorum_minute is not None]
            earliest = f"{min(quorum_times)} мин" if quorum_times else "За время прогона не достигнут"
            rows.append(
                f"<tr><td>{label}</td><td>{first.delivered}/{first.duration} "
                f"({first.delivered / first.duration:.0%})</td><td>{first.longest_outage} мин</td>"
                f"<td>{len(quorum_times)}/{len(group)}</td><td>{earliest}</td></tr>"
            )
        orbital_html = f"""
<h2>Эксперимент на общей орбитальной трассе</h2>
<p>Фиксированный порог {fixed_threshold}, обновление раз в {refresh_interval} минут, уровень угрозы для адаптивного порога {threat:g}.
Каждый режим проверен с четырьмя одинаковыми расписаниями модельного раскрытия долей.</p>
<table border="1" cellpadding="6" style="border-collapse:collapse">
<tr><th>Режим</th><th>Доставлено</th><th>Макс. простой</th>
<th>Сценариев с кворумом раскрытых долей</th><th>Самый ранний кворум</th></tr>
{''.join(rows)}
</table>
<p><a href="orbital_experiment.csv">Результаты по каждому расписанию (CSV)</a></p>
"""

    html = f"""<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Спутниковая связь — итоговый отчёт</title>
<style>
body{{max-width:58rem;margin:6vh auto;padding:0 1.4rem;font:18px/1.55 system-ui;color:#183247;background:#f8fafb}}
h1{{font-size:clamp(2rem,5vw,3.6rem);line-height:1.1}} h2{{margin-top:2rem;font-size:1.4rem}}
a{{color:#075b80}} li{{margin:.65rem 0}} .metric{{padding:1rem 1.3rem;border-left:4px solid #18836f;background:#eaf5f2}}
table{{font:14px monospace;margin:.6rem 0}} th{{background:#eaf5f2}}
</style><main><h1>Спутниковая связь: единый отчёт</h1>
<p class="metric">За {len(history)} модельных минут доставлено <b>{delivered} пакетов</b>.
Смен обслуживающего спутника — <b>{handovers}</b>.</p>

<h2>1. Связь наземной станции</h2><ul>
<li><a href="contacts.html">Видимость, кворум и смена узла</a> · синтетические окна 6–12 мин, порог 2 из 6.</li>
<li><a href="contacts.csv">Журнал по минутам</a> · номер пакета, эпоха, доставка, подпись, повтор.</li>
<li><a href="refresh.png">Proactive refresh (зубчатая пила)</a> · VSS-нулевая раздача каждые 5 дней.</li>
</ul>

<li><a href="schemes_on_leo_live.html">Живое сравнение 5 схем на одной видимости LEO</a>
    · двигайте слайдер, чтобы увидеть кворум каждой схемы.</li>


<h2>2. Геометрическая модель</h2><ul>
<li><a href="simulation_3d.html">Анимация орбит</a> · слайдер времени или «Пуск».</li>
<li><a href="metrics_dashboard.html">Видимость станции и модельное раскрытие долей</a>.</li>
<li><a href="attacker_accumulation.png">Раскрытые доли текущей эпохи и порог</a>.</li>
</ul>

<h2>3. Атаки и стойкость</h2><ul>
<li><a href="compromise_step.png">Ступенька компрометации</a> · m ≥ k.</li>
<li><a href="dynamic_k.png">Динамический порог</a> · k(t) при threat={threat:g}.</li>
</ul>
{tracker_html}
{orbital_html}
{comparison_html}
{bench_html}



<h2>4. Демонстрация 4 схем (см. консоль)</h2>
<p><code>telemetry_demo()</code> сравнивает доставку AES-128-GCM для четырёх схем на одной видимости LEO.
Пороговая подпись используется для первого пакета синтетического сценария.</p>
</main></html>"""
    (out / "index.html").write_text(html, encoding="utf-8")
