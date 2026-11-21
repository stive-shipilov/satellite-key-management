"""Стартовая страница локального отчёта, все ссылки относительны."""


def save_index(out, history):
    delivered = sum(row.delivered for row in history)
    handovers = sum(row.handover for row in history)
    html = f"""<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Спутниковая связь — результаты сеанса</title>
<style>
body{{max-width:58rem;margin:6vh auto;padding:0 1.4rem;font:18px/1.55 system-ui;color:#183247;background:#f8fafb}}
h1{{font-size:clamp(2rem,5vw,3.6rem);line-height:1.1}} h2{{margin-top:2rem;font-size:1.4rem}}
a{{color:#075b80}} li{{margin:.65rem 0}} .metric{{padding:1rem 1.3rem;border-left:4px solid #18836f;background:#eaf5f2}}
</style><main><h1>Спутниковая связь</h1>
<p class="metric">За {len(history)} модельных минут доставлено <b>{delivered} пакетов</b>.
Число переходов между обслуживающими спутниками — <b>{handovers}</b>.</p>
<h2>Связь наземной станции</h2><ul>
<li><a href="contacts.html">Видимость, кворум и смена узла</a> · синтетические окна от 6 до 12 минут, порог 2 из 6.</li>
<li><a href="contacts.csv">Журнал по минутам</a> · номер пакета, эпоха долей, результат доставки, проверки подписи и повтора.</li>
<li><a href="refresh.png">Обновление долей</a> · один новый наблюдаемый узел в день, новая эпоха каждые пять дней.</li></ul>
<h2>Геометрическая модель</h2><ul>
<li><a href="simulation_3d.html">Открыть анимацию орбит</a> · перемещайте ползунок времени или нажмите «Пуск».</li>
<li><a href="metrics_dashboard.html">Метрики наблюдения долей</a> · зона станции и достижение порога при накоплении.</li></ul></main></html>"""
    (out / "index.html").write_text(html, encoding="utf-8")
