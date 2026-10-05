"""Прогноз потребления ОЭС Северо-Запада на сутки D моделью Chronos-2 (для графического интерфейса).

Прогноз выпускается так же, как в бэктесте: по данным до D-1 08:00 и прогнозу погоды на D.
Если данных не хватает (дата свежее архива), с --update докачиваются потребление с сайта СО ЕЭС
и погода из Open-Meteo (прогноз + последние дни).

Вывод для интерфейса — строки между RESULT_BEGIN и RESULT_END:
  meta <ключ> <значение>
  row <час> <прогноз> <p10> <p90> <факт|-> <температура|->
Журнал пишется в stderr.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "weather"))
from common import ISSUE_HOUR, ROOT, load_calendar, load_power, load_weather  # noqa: E402

MODELS = {"chronos-lora": ("checkpoints/chronos2-lora/finetuned-ckpt", 1024, "Chronos-2, дообучение LoRA"),
          "chronos-zs": ("checkpoints/chronos-2", 2048, "Chronos-2 без дообучения")}
VARS = ["temperature_2m", "wind_speed_10m", "cloud_cover", "shortwave_radiation"]
RECENT = ROOT / "weather" / "recent_forecast_weighted.csv"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def recent_weather(max_age_h=3) -> pd.DataFrame:
    """Свежая погода (последние 60 дней + прогноз на 3 дня), средневзвешенная по городам ОЭС."""
    if RECENT.exists() and time.time() - RECENT.stat().st_mtime < max_age_h * 3600:
        return pd.read_csv(RECENT, parse_dates=["datetime_msk"], index_col="datetime_msk")
    from download_weather import POINTS
    acc, wsum = None, 0.0
    for name, _, lat, lon, pop, in_oes in POINTS:
        if not in_oes:
            continue
        q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "hourly": ",".join(VARS), "past_days": 60,
                                    "forecast_days": 3, "timezone": "Europe/Moscow", "wind_speed_unit": "ms"})
        with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=60) as r:
            h = json.load(r)["hourly"]
        df = pd.DataFrame({v: h[v] for v in VARS}, index=pd.to_datetime(h["time"])) * pop
        acc = df if acc is None else acc.add(df, fill_value=0)
        wsum += pop
        log(f"  погода: {name}")
    out = (acc / wsum).round(3)
    out.index.name = "datetime_msk"
    out.to_csv(RECENT)
    return out


def fetch_power(cons: pd.Series, until: pd.Timestamp) -> pd.Series:
    """Докачать с сайта СО ЕЭС сутки после конца архива до `until` (в память, без записи в кэш)."""
    import download  # загрузчик проекта
    start = (cons.dropna().index.max() + pd.Timedelta(hours=1)).normalize().date()
    extra = {}
    for d in pd.date_range(start, until.normalize(), freq="D"):
        log(f"  СО ЕЭС: {d:%d.%m.%Y}")
        try:
            rec = download.fetch(d.date(), 840000, retries=2)
        except RuntimeError:  # у СО ЕЭС ещё нет данных за эти сутки (например, текущие сутки ночью)
            log("    данных ещё нет, пропускаю")
            continue
        for x, v in zip(rec["x"], rec["cons"]):
            dd, hh = x.split(" ")
            if v.strip():
                extra[pd.Timestamp(dd) + pd.Timedelta(hours=int(hh.split(":")[0]))] = float(v)
    if extra:
        cons = pd.concat([cons, pd.Series(extra)]).groupby(level=0).last().sort_index().asfreq("h")
    return cons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=(date.today() + timedelta(days=1)).isoformat(), help="сутки D, ГГГГ-ММ-ДД")
    ap.add_argument("--model", default="chronos-lora", choices=list(MODELS))
    ap.add_argument("--update", action="store_true", help="докачать недостающие данные с сайтов")
    args = ap.parse_args()
    D = pd.Timestamp(args.date)
    last_needed = D - pd.Timedelta(days=1) + pd.Timedelta(hours=ISSUE_HOUR)
    path, ctx, title = MODELS[args.model]

    t0 = time.time()
    log("Загрузка данных…")
    cons = load_power().interpolate(limit=3)
    if cons.dropna().index.max() < D + pd.Timedelta(hours=23) and args.update:
        cons = fetch_power(cons, min(D, pd.Timestamp(date.today())))
    if cons.dropna().index.max() < last_needed:
        raise SystemExit(f"Нет данных о потреблении до {last_needed:%d.%m.%Y %H:%M}. Включите «Обновить данные с сайтов».")

    hist, da = load_weather("hist_fcst")[VARS], load_weather("dayahead")[VARS]
    if D + pd.Timedelta(hours=23) > hist.dropna().index.max():
        if not args.update:
            raise SystemExit("Для этой даты нет погоды в архиве. Включите «Обновить данные с сайтов».")
        rec = recent_weather()
        past, future = hist.combine_first(rec), da.combine_first(rec).combine_first(hist)
    else:
        past, future = hist, da.combine_first(hist)

    from train_chronos import COVS, PRED_LEN, build_inputs, covariates, DEVICE
    import torch
    from chronos import Chronos2Pipeline
    cal = load_calendar()
    log(f"Загрузка модели «{title}» ({DEVICE})…")
    pipe = Chronos2Pipeline.from_pretrained(str(ROOT / path), device_map=DEVICE, dtype=torch.float32)
    items = build_inputs(cons, covariates(past, cal), covariates(future, cal), [D], ctx)
    log("Прогноз…")
    q, _ = pipe.predict_quantiles(items, prediction_length=PRED_LEN, quantile_levels=[0.1, 0.5, 0.9])
    qd = q[0][0, -24:, :].float().cpu().numpy()

    hours = pd.date_range(D, periods=24, freq="h")
    actual = cons.reindex(hours)
    temp = future["temperature_2m"].reindex(hours)
    ok = actual.notna().to_numpy()
    mape = float(np.mean(np.abs(qd[ok, 1] - actual.to_numpy()[ok]) / actual.to_numpy()[ok]) * 100) if ok.any() else None
    day_type = {0: "рабочий", 1: "нерабочий", 2: "сокращённый"}.get(int(cal.get(D, 0)), "рабочий")

    print("RESULT_BEGIN")
    meta = {"date": f"{D:%d.%m.%Y}", "model": title, "day_type": day_type, "issued": f"{last_needed + pd.Timedelta(hours=1):%d.%m.%Y %H:%M}",
            "peak": f"{qd[:, 1].max():.0f}", "peak_hour": str(int(qd[:, 1].argmax())), "energy": f"{qd[:, 1].sum() / 1000:.1f}",
            "temp_mean": f"{temp.mean():.1f}" if temp.notna().any() else "-", "actual_hours": str(int(ok.sum())),
            "mape": f"{mape:.2f}" if mape is not None else "-", "seconds": f"{time.time() - t0:.0f}", "device": DEVICE}
    for k, v in meta.items():
        print(f"meta {k} {v}")
    for h in range(24):
        a = actual.iloc[h]
        tv = temp.iloc[h]
        print(f"row {h} {qd[h, 1]:.0f} {qd[h, 0]:.0f} {qd[h, 2]:.0f} {'-' if pd.isna(a) else f'{a:.0f}'} {'-' if pd.isna(tv) else f'{tv:.1f}'}")
    print("RESULT_END", flush=True)
    log(f"Готово за {time.time() - t0:.0f} с")


if __name__ == "__main__":
    main()
