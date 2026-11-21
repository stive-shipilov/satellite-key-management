"""Стартовая страница локального отчёта, все ссылки относительны."""


def save_index(out, history, *, comparison_rows=None, bench_sample=None, tracker=None):
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
        ttc = tracker.time_to_compromise(None)
        ttc_str = "не достигнут" if ttc == float("inf") else f"{ttc} мин"
        tracker_html = f"""
<h2>Метрики атакующего (главный сценарий)</h2>
<ul>
<li>Успешность контакта: <b>{tracker.success_rate:.0%}</b></li>
<li>Time-to-compromise: <b>{ttc_str}</b></li>
<li>Попыток: {tracker.attempts}, утекло долей: {tracker.successes},
    провалов: {tracker.failures}, refresh: {tracker.refreshes}</li>
</ul>
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
    · двигайте слайдер: Shamir/Blakley собирают ключ при 2+ видимых, XOR/CRT — только при всех n.</li>


<h2>2. Геометрическая модель</h2><ul>
<li><a href="simulation_3d.html">Анимация орбит</a> · слайдер времени или «Пуск».</li>
<li><a href="metrics_dashboard.html">Метрики наблюдения долей</a> · зона станции, достижение порога.</li>
<li><a href="attacker_accumulation.png">Накопление долей атакующим</a> · vs k.</li>
</ul>

<h2>3. Атаки и стойкость</h2><ul>
<li><a href="compromise_step.png">Ступенька компрометации</a> · m ≥ k.</li>
<li><a href="dynamic_k.png">Динамический порог</a> · k(t) при threat=0.3.</li>
</ul>
{tracker_html}
{comparison_html}
{bench_html}



<h2>4. Демонстрация 4 схем (см. консоль)</h2>
<p>При запуске печатается <code>telemetry_demo()</code>: 4 схемы на одной видимости LEO
(AES-128-GCM + пороговая подпись). Это связывает <code>crypto/</code> с <code>simulation/</code>.</p>
</main></html>"""
    (out / "index.html").write_text(html, encoding="utf-8")