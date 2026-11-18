"""Сравнение одного сценария. Все данные берутся из результата measure()."""
import matplotlib.pyplot as plt
import numpy as np

COLORS = ["#285d85", "#cc6137", "#31816c", "#76579b"]


def bar_chart(rows, out):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.1), layout="constrained")
    for ax, field, title in zip(
        axes, ("share_bytes", "split_us", "recover_us"),
        ("Размер доли, байт", "Выдача всех долей, мкс", "Восстановление, мкс")
    ):
        values = [getattr(r, field) for r in rows]
        bars = ax.bar([r.scheme for r in rows], values, color=COLORS)
        ax.bar_label(bars, labels=[f"{v:.3g}" for v in values], padding=3)
        ax.set_ylim(0, max(values) * 1.2)
        ax.set_title(title)
        ax.spines[["top", "right"]].set_visible(False)
    row = rows[0]
    fig.suptitle(f"Ключ {row.bits} бит, n = {row.n}   •   Шамир и Блэкли k = {row.scenario_k}, XOR и CRT k = n")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def radar_chart(rows, out):
    costs = np.array([[r.share_bytes, r.split_us, r.recover_us] for r in rows])
    efficiency = costs.min(axis=0) / costs
    angles = np.linspace(0, 2 * np.pi, 5, endpoint=False)
    cycle = np.append(angles, angles[0])
    fig, ax = plt.subplots(figsize=(7.8, 5.6), subplot_kw={"projection": "polar"})
    fig.subplots_adjust(left=.19, right=.80, top=.82, bottom=.17)
    for r, ratios, color in zip(rows, efficiency, COLORS):
        scores = [*ratios, r.safe_shares / r.n, (r.n - r.threshold) / r.n]
        ax.plot(cycle, [*scores, scores[0]], marker="o", label=r.scheme, color=color)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles, ["Компактность", "Скорость\nвыдачи", "Скорость\nсборки",
                           "Доля узлов до\nраскрытия ключа", "Допустимая доля\nнедоступных узлов"])
    ax.tick_params(axis="x", pad=18)
    ax.set_ylim(0, 1)
    ax.set_yticks([.25, .5, .75, 1], ["0,25", "0,5", "0,75", "1"])
    ax.legend(loc="lower center", bbox_to_anchor=(.5, -.27), ncol=4, frameon=False)
    r = rows[0]
    fig.suptitle(f"Сравнение при {r.bits} бит, n = {r.n}, k = {r.scenario_k} (XOR и CRT требуют n)")
    fig.savefig(out, dpi=150, bbox_inches="tight", pad_inches=.25)
    plt.close(fig)
    return out
