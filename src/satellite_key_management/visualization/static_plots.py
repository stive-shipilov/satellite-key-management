"""Статичные графики: ступенька компрометации, зубчатая пила, динамика k, сравнение."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def plot_compromise_step(sim, out="compromise_step.png"):
    ms = list(range(0, sim.n + 1))
    results = []
    for m in ms:
        from attacks.attacks import compromise_m
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
    from attacks.attacks import share_accumulation
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

def plot_dynamic_k(sim, out="dynamic_k.png", t_total=120):
    ts = list(range(0, t_total, 2))
    ks = [sim.dynamic_k(t, threat_level=0.3) for t in ts]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(ts, ks, color="blue", linewidth=2)
    ax.set_xlabel("время, мин")
    ax.set_ylabel("динамический k")
    ax.set_title("Динамика порога k")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out

def plot_scheme_comparison(out="schemes_comparison.png"):
    """Заглушка: Участник 2 подставит реальные метрики."""
    schemes = ["Shamir", "Blakley", "XOR (N,N)"]
    share_size = [16, 32, 16]
    gen_time = [0.8, 1.2, 0.1]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].bar(schemes, share_size, color=["green", "blue", "orange"])
    ax[0].set_title("Размер доли, байт")
    ax[1].bar(schemes, gen_time, color=["green", "blue", "orange"])
    ax[1].set_title("Время генерации, мс")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out

def plot_attacker_accumulation(tracker, out="attacker_accumulation.png"):
    """Накопление долей у атакующего vs порог k."""
    import matplotlib.pyplot as plt
    ts = [h[0] for h in tracker.history]
    ns = [h[1] for h in tracker.history]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(ts, ns, color="red", linewidth=2, label="долей у атакующего")
    ax.axhline(tracker.k_target, color="green", linestyle="--", label=f"порог k={tracker.k_target}")
    ax.fill_between(ts, ns, tracker.k_target, where=[n < tracker.k_target for n in ns],
                    color="red", alpha=0.1)
    ax.set_xlabel("время, мин"); ax.set_ylabel("долей")
    ax.set_title("Накопление долей атакующим vs порог k")
    ax.legend(); fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    return out


def plot_attacker_zone_presence(tracker, out="attacker_zone_presence.png"):
    """Сколько спутников было в зоне атакующего по времени."""
    import matplotlib.pyplot as plt
    ts = [h[0] for h in tracker.history]
    nv = [h[2] for h in tracker.history]
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.step(ts, nv, where="post", color="orange")
    ax.set_xlabel("время, мин"); ax.set_ylabel("спутников в зоне")
    ax.set_title("Окна уязвимости: спутники в зоне атакующего")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    return out


def plot_attacker_metrics_summary(tracker, out="attacker_metrics.png"):
    """Сводка: попытки, успехи, провалы, success rate, time-to-compromise."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3))
    labels = ["попытки", "утекло долей", "провалов"]
    values = [tracker.attempts, tracker.successes, tracker.failures]
    ax.bar(labels, values, color=["gray", "red", "green"])
    ttc = tracker.time_to_compromise(None)
    ttc_str = "∞ (невозможно)" if ttc == float("inf") else f"{ttc} мин"
    ax.set_title(f"Метрики атакующего | success rate={tracker.success_rate:.0%} | "
                 f"time-to-compromise={ttc_str}")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    return out