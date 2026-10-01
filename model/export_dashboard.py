"""Собирает интерактивный дашборд: результаты -> JSON -> dashboard/nw-load-forecast.html.

Запуск: .venv/bin/python model/export_dashboard.py [--version-label "..."]
"""
import argparse
import json
from datetime import datetime

import pandas as pd

from common import ROOT, load_calendar, load_power, load_weather
from report import load_preds

# key, полное имя, короткое имя, семейство, слот категориальной палитры (0 — нейтральный), штрих
MODELS = [
    ("naive_week", "Наивный: тот же час неделю назад", "Наивный", "base", 0, ""),
    ("ridge_fcst", "Линейная регрессия + прогноз погоды", "Линейная", "base", 7, ""),
    ("lgb_noweather", "LightGBM без погоды", "LightGBM без погоды", "ml", 6, ""),
    ("lgb_fcst", "LightGBM + прогноз погоды", "LightGBM", "ml", 1, ""),
    ("lgb_ratio_fcst", "LightGBM, цель — доля от недельного среднего", "LightGBM (доля)", "ml", 1, "7 4"),
    ("lgb_oracle", "LightGBM + фактическая погода (оракул)", "LightGBM-оракул", "ml", 1, "2 3"),
    ("chronos_zs_uni", "Chronos-2 без дообучения, без погоды", "Chronos-2 ZS", "fm", 8, ""),
    ("chronos_zs_cov_fcst", "Chronos-2 без дообучения + прогноз погоды", "Chronos-2 ZS + погода", "fm", 4, ""),
    ("chronos_ft_lora_cov_fcst", "Chronos-2, дообучение LoRA + прогноз погоды", "Chronos-2 LoRA", "fm", 3, ""),
    ("chronos_ft_full_cov_fcst", "Chronos-2, полное дообучение + прогноз погоды", "Chronos-2 full FT", "fm", 2, ""),
    ("ens_lgb_chronos", "Ансамбль: среднее LightGBM и Chronos-2 ZS", "Ансамбль", "ens", 5, ""),
]
FEATURES = {
    "cons_lag48": "Потребление 2 суток назад, тот же час", "cons_lag72": "Потребление 3 суток назад",
    "cons_lag168": "Потребление неделю назад", "cons_lag336": "Потребление 2 недели назад",
    "cons_last_known": "Последний известный час (D−1, 08:00)", "cons_prev_morning": "Среднее D−1, 00–08 ч",
    "cons_day_lag2": "Среднесуточное потребление D−2", "cons_week_mean": "Среднее за неделю до D−2",
    "temperature_2m": "Температура", "apparent_temperature": "Ощущаемая температура",
    "relative_humidity_2m": "Влажность", "dew_point_2m": "Точка росы", "precipitation": "Осадки",
    "cloud_cover": "Облачность", "shortwave_radiation": "Солнечная радиация", "wind_speed_10m": "Ветер",
    "hdd": "Градусо-часы отопления (база 16 °C)", "temp_ema24": "Сглаженная температура, 24 ч",
    "temp_ema72": "Сглаженная температура, 72 ч", "temp_day_mean": "Среднесуточная температура D",
    "temp_day_min": "Минимум температуры D", "temp_day_max": "Максимум температуры D",
    "temp_lag48": "Температура 2 суток назад", "temp_lag168": "Температура неделю назад",
    "temp_day_mean_lag2": "Среднесуточная температура D−2", "temp_delta_vs_lag2": "Изменение температуры к D−2",
    "hour": "Час суток", "dow": "День недели", "month": "Месяц", "doy_sin": "День года (sin)",
    "doy_cos": "День года (cos)", "day_type": "Тип дня D (календарь)", "day_type_prev": "Тип дня D−1",
    "day_type_next": "Тип дня D+1", "day_type_lag2": "Тип дня D−2", "day_type_lag7": "Тип дня D−7",
}


def ints(s: pd.Series) -> list:
    return [None if pd.isna(v) else int(round(v)) for v in s]


def floats(s: pd.Series, nd: int = 1) -> list:
    return [None if pd.isna(v) else round(float(v), nd) for v in s]


SHOW = ["BEST_FT", "ens_lgb_chronos", "lgb_fcst"]  # лучшая модель каждого подхода (BEST_FT — лучший вариант дообучения)
REFS = ["naive_week", "lgb_noweather"]  # не рисуются, нужны только для сводных цифр


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version-label", default="")
    ap.add_argument("--models", default=",".join(SHOW))
    args = ap.parse_args()

    P = load_preds().asfreq("h")
    idx = P.index
    days = pd.date_range(idx.min().normalize(), idx.max().normalize(), freq="D")
    ft = [k for k in ["chronos_ft_lora_cov_fcst", "chronos_ft_full_cov_fcst"] if k in P]
    best_ft = min(ft, key=lambda k: abs(P[k] - P["actual"]).div(P["actual"]).mean())
    show = [best_ft if k == "BEST_FT" else k for k in args.models.split(",")]
    show = [k for k in show if k in P]
    slots = {k: i + 1 for i, k in enumerate(show)}  # цвета по порядку палитры, без пропусков
    meta_by_key = {k: (n, s, f, d) for k, n, s, f, _, d in MODELS}
    models = [dict(key=k, name=meta_by_key[k][0], short=meta_by_key[k][1], family=meta_by_key[k][2],
                   slot=slots[k], dash="") for k in show]

    cons = load_power()
    t_act = load_weather("actual")["temperature_2m"]
    t_fc = load_weather("dayahead")["temperature_2m"]
    hist = pd.DataFrame({"c": cons.resample("D").mean(), "t": t_act.resample("D").mean()}).dropna()
    hist = hist.loc[:idx.max()]

    imp = pd.read_csv(ROOT / "results" / "feature_importance_lgbm.csv", index_col=0)["gain"]
    imp = (imp / imp.sum() * 100).head(12)
    timing_p = ROOT / "results" / "timing_chronos.json"

    data = {
        "meta": {
            "start": idx.min().strftime("%Y-%m-%dT%H:%M"),
            "hours": len(idx),
            "built": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "version": args.version_label,
            "hist_start": hist.index.min().strftime("%Y-%m-%d"),
            "n_tested": sum(1 for k, *_ in MODELS if k in P and k != "lgb_oracle"),
        },
        "models": models,
        "actual": ints(P["actual"]),
        "pred": {m["key"]: ints(P[m["key"]]) for m in models},
        "refs": {k: ints(P[k]) for k in REFS if k in P},
        "temp_fcst": floats(t_fc.reindex(idx)),
        "temp_act": floats(t_act.reindex(idx)),
        "day_type": [int(v) if pd.notna(v) else 0 for v in load_calendar().reindex(days)],
        "hist": {"start": hist.index.min().strftime("%Y-%m-%d"),
                 "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                 "cons": ints(hist["c"]), "temp": floats(hist["t"])},
        "importance": [[FEATURES.get(k, k), round(float(v), 1)] for k, v in imp.items()],
        "timing": json.loads(timing_p.read_text()) if timing_p.exists() else {},
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
    out = ROOT / "dashboard" / "nw-load-forecast.html"
    out.write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"{out} — {out.stat().st_size / 1024:.0f} КБ, моделей {len(models)}, часов {len(idx)}")


if __name__ == "__main__":
    main()
