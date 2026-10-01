"""Цифры и ряды для презентации -> deck/data.json."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "model"))
from common import load_calendar, load_power, load_weather, metrics  # noqa: E402
from report import load_preds  # noqa: E402

OUT = Path(__file__).resolve().parent / "data.json"
WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
KEYS = ["naive_week", "ridge_fcst", "lgb_noweather", "lgb_fcst", "lgb_oracle", "chronos_zs_uni",
        "chronos_zs_cov_fcst", "chronos_ft_lora_cov_fcst", "chronos_ft_full_cov_fcst", "ens_lgb_chronos"]
SEASONS = {"Осень": [9, 10, 11], "Зима": [12, 1, 2], "Весна": [3, 4, 5], "Лето": [6, 7, 8]}


def r(x, nd=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


P = load_preds().asfreq("h")
m = P.index.month
year = {k: {kk: r(v) for kk, v in metrics(P["actual"], P[k]).items()} for k in KEYS if k in P}
seasons = {s: {k: r(metrics(P[m.isin(ms)]["actual"], P[m.isin(ms)][k])["MAPE_%"])
               for k in KEYS if k in P} for s, ms in SEASONS.items()}

# Самая холодная неделя теста (понедельник–воскресенье)
t_act = load_weather("actual")["temperature_2m"]
dt = t_act.reindex(P.index).resample("D").mean()
weekly = dt.rolling(7).mean()
mondays = [d for d in weekly.index if d.dayofweek == 6 and d - pd.Timedelta(days=6) >= P.index.min()]
end = min(mondays, key=lambda d: weekly[d])
W = P.loc[end - pd.Timedelta(days=6): end + pd.Timedelta(hours=23)]
labels = [f"{WD[t.dayofweek]} {t:%d.%m}" if t.hour == 0 else "" for t in W.index]
FT = [k for k in ["chronos_ft_lora_cov_fcst", "chronos_ft_full_cov_fcst"] if k in P]
best_ft = min(FT, key=lambda k: year[k]["MAPE_%"])  # лучший вариант дообучения Chronos-2 за год
week = {"labels": labels, "start": f"{W.index.min():%d.%m.%Y}", "end": f"{W.index.max():%d.%m.%Y}",
        "temp_mean": r(dt.loc[W.index.min():end].mean(), 1),
        "series": {k: [int(round(v)) for v in W[k]] for k in ["actual", *FT, "lgb_fcst"]},
        "mape": {k: r(metrics(W["actual"], W[k])["MAPE_%"]) for k in [*FT, "lgb_fcst"]}}

# Связь потребления и температуры по всей истории
cons = load_power()
hist = pd.DataFrame({"c": cons.resample("D").mean(), "t": t_act.resample("D").mean()}).dropna()
hist = hist.loc[:P.index.max()]
test_start = P.index.min()
scatter = {"x": [r(v, 1) for v in hist["t"]],
           "train": [int(round(c)) if d < test_start else None for d, c in hist["c"].items()],
           "test": [int(round(c)) if d >= test_start else None for d, c in hist["c"].items()]}
stats = {
    "corr": r(hist["c"].corr(hist["t"])),
    "cold_mean": int(hist.loc[hist["t"] < -10, "c"].mean()),
    "warm_mean": int(hist.loc[hist["t"] > 15, "c"].mean()),
    "n_days_hist": len(hist), "hist_start": f"{hist.index.min():%Y}", "hist_end": f"{hist.index.max():%Y}",
    "hours_total": int(cons.loc[:P.index.max()].notna().sum()),
    "test_days": len(P) // 24, "test_start": f"{P.index.min():%d.%m.%Y}", "test_end": f"{P.index.max():%d.%m.%Y}",
    "max_load": int(cons.loc[:P.index.max()].max()), "min_load": int(cons.loc[:P.index.max()].min()),
}
monthly = {k: [r(metrics(g["actual"], g[k])["MAPE_%"]) for _, g in P.groupby(P.index.to_period("M"))]
           for k in [best_ft, "ens_lgb_chronos", "lgb_fcst"]}
months = [p.strftime("%m.%y") for p in P.index.to_period("M").unique()]
timing_p = Path(__file__).resolve().parents[1] / "results" / "timing_chronos.json"
data = {"best_ft": best_ft, "year": year, "seasons": seasons, "week": week, "scatter": scatter, "stats": stats,
        "monthly": monthly, "months": months,
        "timing": json.loads(timing_p.read_text()) if timing_p.exists() else {}}
OUT.write_text(json.dumps(data, ensure_ascii=False))
print(json.dumps({"year": {k: v["MAPE_%"] for k, v in year.items()}, "seasons": seasons, "stats": stats,
                  "week": {k: week[k] for k in ["start", "end", "temp_mean", "mape"]}}, ensure_ascii=False, indent=1))
