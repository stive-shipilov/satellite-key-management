"""Статичные графики: ступенька компрометации, зубчатая пила, динамика k, сравнение."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def plot_compromise_step(sim, out="compromise_step.png"):
    ms = list(range(0, sim.n + 1))
    results = []
    for m in ms:
        from satellite_key_management.attacks.attacks import compromise_m
        ok, _ = compromise_m(sim, m)
        results.append(1 if ok else 0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.step(ms, results, where="post", color="red", linewidth=2)
    ax.axvline(sim.k, color="green", linestyle="--", label=f"порог k={sim.k}")
    ax.set_xlabel("скомпрометировано спутников m")
    ax.set_ylabel("ключ восстановлен (1/0)")
    ax.set_title("Ступенька компрометации")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out

def plot_refresh_sawtooth(sim, out="refresh_sawtooth.png"):
    from satellite_key_management.attacks.attacks import share_accumulation
    hist = share_accumulation(sim)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(hist, color="orange", linewidth=2)
    for d in range(0, len(hist), 5):
        ax.axvline(d, color="gray", linestyle=":", alpha=0.4)
    ax.set_xlabel("день")
    ax.set_ylabel("активных долей у атакующего")
    ax.set_title("Зубчатая пила proactive refresh")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out

def plot_dynamic_k(sim, out="dynamic_k.png", t_total=120, *, threat=0.3):
    ts = list(range(t_total))
    ks = [sim.dynamic_k(t, threat_level=threat) for t in ts]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.step(ts, [0 if k is None else k for k in ks], where="post", color="blue", linewidth=2)
    ax.set_xlabel("время, мин")
    ax.set_ylabel("порог k (0 — сессия отложена)")
    ax.set_title(f"Динамика порога k при уровне угрозы {threat:g}")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out

def plot_scheme_comparison(out="schemes_comparison.png"):
    """Сравнение по замерам при 128 битах и шести спутниках."""
    if __package__ == "visualization":
        from analysis.benchmark import measure
        from analysis.plots import bar_chart
    else:
        from ..analysis.benchmark import measure
        from ..analysis.plots import bar_chart
    return bar_chart(measure(), out)

def plot_attacker_accumulation(tracker, out="attacker_accumulation.png"):
    """Накопление долей у атакующего vs порог k."""
    import matplotlib.pyplot as plt
    ts = [sample.minute for sample in tracker.history]
    ns = [sample.shares for sample in tracker.history]
    thresholds = [sample.threshold for sample in tracker.history]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.step(ts, ns, where="post", color="red", linewidth=2, label="раскрыто долей по сценарию")
    ax.step(ts, thresholds, where="post", color="green", linestyle="--", label="порог k")
    ax.set_xlabel("время, мин"); ax.set_ylabel("долей")
    ax.set_title("Накопление долей атакующим vs порог k")
    ax.legend(); fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    return out


def plot_attacker_zone_presence(tracker, out="attacker_zone_presence.png"):
    """Сколько спутников было в зоне атакующего по времени."""
    import matplotlib.pyplot as plt
    ts = [sample.minute for sample in tracker.history]
    nv = [len(sample.visible) for sample in tracker.history]
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.step(ts, nv, where="post", color="orange")
    ax.set_xlabel("время, мин"); ax.set_ylabel("спутников в зоне")
    ax.set_title("Спутники в зоне наблюдения")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    return out


def plot_attacker_metrics_summary(tracker, out="attacker_metrics.png"):
    """Сводка по отсчётам модели и достигнутым кворумам."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3))
    labels = ["отсчётов", "с видимостью", "с кворумом"]
    values = [len(tracker.history), sum(bool(sample.visible) for sample in tracker.history),
              sum(sample.quorum_reached for sample in tracker.history)]
    ax.bar(labels, values, color=["gray", "red", "green"])
    ttc = tracker.time_to_compromise()
    ttc_str = "нет за время прогона" if ttc is None else f"{ttc} мин"
    ax.set_title(f"Первый кворум из раскрытых долей · {ttc_str}")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    return out
