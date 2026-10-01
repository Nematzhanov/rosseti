"""Рисунки для статьи (Times New Roman, читаемы в чёрно-белой печати)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
D = json.loads((HERE.parent / "deck" / "data.json").read_text())
plt.rcParams.update({
    "font.family": "Times New Roman", "font.size": 12, "axes.edgecolor": "#333333", "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#d9d9d9", "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "savefig.dpi": 220, "savefig.bbox": "tight", "legend.frameon": False,
})


def comma(x, _=None, nd=0):
    return f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")


# Рисунок 1: потребление и температура
x = np.array([v for v in D["scatter"]["x"]], dtype=float)
c = np.array([a if a is not None else b for a, b in zip(D["scatter"]["train"], D["scatter"]["test"])], dtype=float)
ok = ~np.isnan(x) & ~np.isnan(c)
x, c = x[ok], c[ok]
k = np.polyfit(x, c, 2)
xs = np.linspace(x.min(), x.max(), 200)
fig, ax = plt.subplots(figsize=(6.6, 3.0))
ax.scatter(x, c, s=6, color="#4d4d4d", alpha=0.45, linewidths=0, label="среднесуточные значения")
ax.plot(xs, np.polyval(k, xs), color="black", lw=2, label="квадратичный тренд")
ax.set_xlabel("Среднесуточная температура воздуха, °C")
ax.set_ylabel("Потребление, МВт")
ax.yaxis.set_major_formatter(plt.FuncFormatter(comma))
ax.legend(loc="upper right")
fig.savefig(HERE / "fig1_temp.png")
plt.close(fig)

# Рисунок 2: самая холодная неделя
wk = D["week"]
best = D["best_ft"]
n = len(wk["series"]["actual"])
h = np.arange(n)
fig, ax = plt.subplots(figsize=(6.6, 2.9))
ax.plot(h, wk["series"]["actual"], color="black", lw=2.2, label="факт")
ax.plot(h, wk["series"][best], color="#1f4e9c", lw=1.8, ls=(0, (4, 2)),
        label="прогноз Chronos-2 (дообучение LoRA)" if "lora" in best else "прогноз Chronos-2")
days = [i for i, t in enumerate(wk["labels"]) if t]
ax.set_xticks([d + 12 for d in days])
ax.set_xticklabels([wk["labels"][d] for d in days])
for d in days[1:]:
    ax.axvline(d, color="#bfbfbf", lw=0.6)
ax.set_xlim(0, n - 1)
ax.set_ylabel("Потребление, МВт")
ax.yaxis.set_major_formatter(plt.FuncFormatter(comma))
ax.grid(axis="x", visible=False)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=11)
fig.savefig(HERE / "fig2_cold_week.png")
plt.close(fig)
print("ok", sorted(p.name for p in HERE.glob("fig*.png")))
