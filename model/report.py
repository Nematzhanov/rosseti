"""Сводный отчёт по моделям: метрики, разбивка по сезонам, графики -> results/REPORT.md."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from common import ROOT, load_power, load_weather, metrics

OUT = ROOT / "results"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # категориальная палитра, фиксированный порядок
NAMES = {
    "naive_week": "Наивный (неделю назад)",
    "ridge_fcst": "Линейная регрессия",
    "lgb_noweather": "LightGBM без погоды",
    "lgb_fcst": "LightGBM + прогноз погоды",
    "lgb_oracle": "LightGBM + факт. погода (оракул)",
    "lgb_ratio_fcst": "LightGBM (цель — доля от недельного среднего) + прогноз погоды",
    "chronos_zs_uni": "Chronos-2 zero-shot, без погоды",
    "chronos_zs_cov_fcst": "Chronos-2 zero-shot + прогноз погоды",
    "chronos_ft_lora_cov_fcst": "Chronos-2 LoRA + прогноз погоды",
    "chronos_ft_full_cov_fcst": "Chronos-2 полное дообучение + прогноз погоды",
    "ens_lgb_chronos": "Ансамбль: LightGBM + Chronos-2 zero-shot (среднее)",
}
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 130, "savefig.bbox": "tight", "lines.linewidth": 2})


def load_preds() -> pd.DataFrame:
    P = pd.read_csv(OUT / "predictions_lgbm.csv", parse_dates=["datetime_msk"], index_col="datetime_msk")
    ch = OUT / "predictions_chronos.csv"
    if ch.exists():
        C = pd.read_csv(ch, parse_dates=["datetime_msk"], index_col="datetime_msk").drop(columns="actual")
        P = P.join(C, how="left")
        if "chronos_zs_cov_fcst" in P:  # состав ансамбля зафиксирован заранее, без подбора по тесту
            P["ens_lgb_chronos"] = (P["lgb_fcst"] + P["chronos_zs_cov_fcst"]) / 2
    return P


def table(P: pd.DataFrame, mask=None) -> pd.DataFrame:
    Q = P if mask is None else P[mask]
    rows = {NAMES.get(c, c): metrics(Q["actual"], Q[c]) for c in P.columns if c != "actual" and P[c].notna().any()}
    return pd.DataFrame(rows).T[["MAPE_%", "MAE_MW", "RMSE_MW", "peak_MAE_MW", "bias_MW"]].sort_values("MAPE_%")


def md(df: pd.DataFrame) -> str:
    cols = ["Модель", "MAPE, %", "MAE, МВт", "RMSE, МВт", "MAE в пиковый час, МВт", "Смещение, МВт"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for name, r in df.iterrows():
        lines.append(f"| {name} | {r['MAPE_%']:.2f} | {r['MAE_MW']:.0f} | {r['RMSE_MW']:.0f} | "
                     f"{r['peak_MAE_MW']:.0f} | {r['bias_MW']:+.0f} |")
    return "\n".join(lines)


def main():
    P = load_preds()
    temp = load_weather("actual")["temperature_2m"]
    m = P.index.month
    daily_t = temp.resample("D").mean()
    cold = daily_t.reindex(P.index.normalize()).to_numpy() < -10

    overall = table(P)
    parts = {"Весь тестовый год": overall, "Зима (дек–фев)": table(P, m.isin([12, 1, 2])),
             "Лето (июн–авг)": table(P, m.isin([6, 7, 8])), "Морозные дни (t < −10 °C)": table(P, cold)}
    best_ch = [c for c in P.columns if c.startswith("chronos")]
    best_ch = min(best_ch, key=lambda c: metrics(P["actual"], P[c])["MAPE_%"]) if best_ch else None

    # 1. Потребление vs температура (вся история)
    cons = load_power()
    d = pd.DataFrame({"t": daily_t, "c": cons.resample("D").mean()}).dropna()
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.scatter(d["t"], d["c"] / 1000, s=9, color=SERIES[0], alpha=0.55, linewidths=0)
    ax.set_xlabel("Среднесуточная температура, °C (средневзвешенная по ОЭС)")
    ax.set_ylabel("Потребление, тыс. МВт")
    ax.set_title(f"ОЭС Северо-Запада: потребление и температура, {d.index.min():%Y}–{d.index.max():%Y}",
                 loc="left", color=INK)
    fig.savefig(OUT / "fig_temp_vs_load.png"); plt.close(fig)

    # 2. MAPE по месяцам
    keys = [k for k in ["naive_week", "lgb_fcst", best_ch, "ens_lgb_chronos"] if k and k in P]
    monthly = {k: P.groupby(P.index.to_period("M")).apply(lambda g: metrics(g["actual"], g[k])["MAPE_%"])
               for k in keys}
    fig, ax = plt.subplots(figsize=(8, 4.2))
    colors = iter(SERIES)
    for k in keys:
        s = monthly[k]
        c = "#a3a29c" if k == "naive_week" else next(colors)  # базовая линия — нейтральным серым
        ax.plot(s.index.to_timestamp(), s.values, color=c, marker="o", ms=4, label=NAMES[k])
    ax.set_ylabel("MAPE, %"); ax.set_ylim(bottom=0)
    ax.set_title("Ошибка прогноза на сутки вперёд по месяцам", loc="left", color=INK)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(1, 1))
    fig.savefig(OUT / "fig_monthly_mape.png"); plt.close(fig)

    # 3. Самая холодная неделя теста
    wk = daily_t.reindex(P.index.normalize().unique()).rolling(7).mean().idxmin()
    W = P.loc[wk - pd.Timedelta(days=6): wk + pd.Timedelta(hours=23)]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(W.index, W["actual"] / 1000, color=INK, lw=2.2, label="Факт")
    for i, k in enumerate([k for k in ["lgb_fcst", best_ch] if k]):
        ax.plot(W.index, W[k] / 1000, color=SERIES[i], lw=1.8, ls="--" if i else "-", label=NAMES[k])
    ax.set_ylabel("Потребление, тыс. МВт")
    ax.set_title(f"Самая холодная неделя теста: {W.index.min():%d.%m} – {W.index.max():%d.%m.%Y}",
                 loc="left", color=INK)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)
    fig.savefig(OUT / "fig_cold_week.png"); plt.close(fig)

    # 4. Вклад погоды (LightGBM), зима
    abl = ["lgb_noweather", "lgb_fcst", "lgb_oracle"]
    wint = P[m.isin([12, 1, 2])]
    vals = [metrics(wint["actual"], wint[k])["MAPE_%"] for k in abl]
    fig, ax = plt.subplots(figsize=(7, 2.6))
    ax.barh([NAMES[k] for k in abl][::-1], vals[::-1], color=SERIES[0], height=0.55)
    for y, v in enumerate(vals[::-1]):
        ax.text(v, y, f" {v:.2f}%", va="center", color=INK, fontsize=9)
    ax.set_xlabel("MAPE зимой, %"); ax.grid(axis="y", visible=False)
    ax.set_title("Что даёт погода (LightGBM, декабрь–февраль)", loc="left", color=INK)
    fig.savefig(OUT / "fig_weather_effect.png"); plt.close(fig)

    imp = pd.read_csv(OUT / "feature_importance_lgbm.csv", index_col=0)["gain"]
    imp = (imp / imp.sum() * 100).head(12)

    timing = json.loads((OUT / "timing_chronos.json").read_text()) if (OUT / "timing_chronos.json").exists() else {}
    lines = [
        "# Прогноз потребления ОЭС Северо-Запада на сутки вперёд — результаты",
        "",
        f"Тест: {P.index.min():%d.%m.%Y} – {P.index.max():%d.%m.%Y}, {len(P) // 24} суток, почасово. "
        "Прогноз выпускается накануне в 09:00 МСК; на целевые сутки используется **прогноз** погоды, "
        "выпущенный за сутки (кроме строки «оракул»). LightGBM и линейная регрессия переобучаются "
        "каждый месяц на всех прошлых данных; Chronos-2 дообучается один раз на данных до начала теста.",
        "",
    ]
    for title, t in parts.items():
        lines += [f"## {title}", "", md(t), ""]
    lines += ["## Графики", "", "![](fig_temp_vs_load.png)", "", "![](fig_monthly_mape.png)", "",
              "![](fig_cold_week.png)", "", "![](fig_weather_effect.png)", "",
              "## Важность признаков LightGBM (доля gain, %)", "",
              "| Признак | % |", "|---|---|"] + [f"| {k} | {v:.1f} |" for k, v in imp.items()]
    if timing:
        lines += ["", "## Время работы Chronos-2 (Apple M3, MPS), сек", "",
                  "| Этап | сек |", "|---|---|"] + [f"| {k} | {v:.0f} |" for k, v in timing.items()]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(overall.round(2).to_string())
    print("\nЗима:\n" + parts["Зима (дек–фев)"].round(2).to_string())


if __name__ == "__main__":
    main()
