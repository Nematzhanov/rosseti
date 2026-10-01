"""Загрузка данных и признаки для прогноза потребления на сутки вперёд.

Схема прогноза (как у диспетчера): прогноз на сутки D (24 часа) выпускается в D-1 в 09:00 МСК.
На этот момент известно потребление до D-1 08:00 включительно и прогноз погоды на D.
Все признаки строятся только из этой информации.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ISSUE_HOUR = 8  # последний известный час потребления в D-1

KPO_NW = 840000
WEATHER_VARS = ["temperature_2m", "apparent_temperature", "relative_humidity_2m", "dew_point_2m",
                "precipitation", "cloud_cover", "shortwave_radiation", "wind_speed_10m"]


def load_power(kpo: int = KPO_NW, column: str = "cons") -> pd.Series:
    """Почасовое потребление (или генерация) энергосистемы из кэша загрузчика, МВт."""
    vals = {}
    with (ROOT / "raw" / "cache.jsonl").open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:  # недописанная строка, пока идёт загрузка
                continue
            if rec["kpo"] != kpo:
                continue
            for x, v in zip(rec["x"], rec[column]):
                d, h = x.split(" ")
                vals[pd.Timestamp(d) + pd.Timedelta(hours=int(h.split(":")[0]))] = float(v)
    s = pd.Series(vals).sort_index()
    return s.asfreq("h")


def load_weather(source: str) -> pd.DataFrame:
    """Средневзвешенная погода ОЭС Северо-Запада; склеивает все скачанные периоды."""
    parts = [pd.read_csv(p, parse_dates=["datetime_msk"], encoding="utf-8-sig")
             for p in sorted((ROOT / "weather").glob(f"{source}_oes_northwest_weighted_hourly_*.csv"))]
    df = pd.concat(parts).drop_duplicates("datetime_msk", keep="last").set_index("datetime_msk").sort_index()
    return df.asfreq("h")


def load_calendar() -> pd.Series:
    """Производственный календарь (isdayoff.ru): 0 — рабочий, 1 — нерабочий, 2 — сокращённый."""
    codes = {}
    for p in sorted((ROOT / "calendar").glob("isdayoff_*.txt")):
        year = int(p.stem.split("_")[1])
        for i, c in enumerate(p.read_text().strip()):
            codes[pd.Timestamp(year, 1, 1) + pd.Timedelta(days=i)] = int(c)
    return pd.Series(codes).sort_index()


def _daily(s: pd.Series, how: str = "mean") -> pd.Series:
    return s.resample("D").agg(how)


def make_features(cons: pd.Series, w_target: pd.DataFrame, w_past: pd.DataFrame,
                  cal: pd.Series) -> pd.DataFrame:
    """Таблица признаков, одна строка = целевой час.

    w_target — погода на целевые сутки (при честной проверке — прогноз, выпущенный накануне);
    w_past   — погода прошлых дней (на момент прогноза известна как анализ/факт).
    """
    idx = cons.index
    day = idx.normalize()
    X = pd.DataFrame(index=idx)
    X["hour"] = idx.hour
    X["dow"] = idx.dayofweek
    X["month"] = idx.month
    doy = idx.dayofyear.to_numpy()
    X["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    X["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    # Календарь: тип дня для D, соседних дней и дней, с которых берутся лаги
    for name, shift in [("day_type", 0), ("day_type_prev", -1), ("day_type_next", 1),
                        ("day_type_lag2", -2), ("day_type_lag7", -7)]:
        X[name] = cal.reindex(day + pd.Timedelta(days=shift)).to_numpy()

    # Лаги потребления, известные в D-1 09:00
    for lag in (48, 72, 168, 336):
        X[f"cons_lag{lag}"] = cons.shift(lag).to_numpy()
    X["cons_last_known"] = cons.reindex(day - pd.Timedelta(days=1) + pd.Timedelta(hours=ISSUE_HOUR)).to_numpy()
    morning = cons[cons.index.hour <= ISSUE_HOUR].resample("D").mean()
    X["cons_prev_morning"] = morning.reindex(day - pd.Timedelta(days=1)).to_numpy()
    daily = _daily(cons)
    X["cons_day_lag2"] = daily.reindex(day - pd.Timedelta(days=2)).to_numpy()
    X["cons_week_mean"] = daily.rolling(7).mean().reindex(day - pd.Timedelta(days=2)).to_numpy()

    # Погода на целевой час и сутки
    wt = w_target.reindex(idx)
    for v in WEATHER_VARS:
        X[v] = wt[v].to_numpy()
    t = w_target["temperature_2m"]
    X["hdd"] = np.clip(16 - X["temperature_2m"], 0, None)
    X["temp_ema24"] = t.ewm(halflife=24).mean().reindex(idx).to_numpy()  # тепловая инерция зданий
    X["temp_ema72"] = t.ewm(halflife=72).mean().reindex(idx).to_numpy()
    X["temp_day_mean"] = _daily(t).reindex(day).to_numpy()
    X["temp_day_min"] = _daily(t, "min").reindex(day).to_numpy()
    X["temp_day_max"] = _daily(t, "max").reindex(day).to_numpy()

    # Погода в дни, с которых взяты лаги: модель учится на разнице «было — будет»
    tp = w_past["temperature_2m"]
    X["temp_lag48"] = tp.shift(48).reindex(idx).to_numpy()
    X["temp_lag168"] = tp.shift(168).reindex(idx).to_numpy()
    X["temp_day_mean_lag2"] = _daily(tp).reindex(day - pd.Timedelta(days=2)).to_numpy()
    X["temp_delta_vs_lag2"] = X["temp_day_mean"] - X["temp_day_mean_lag2"]
    return X


def metrics(y_true: pd.Series, y_pred: pd.Series) -> dict:
    y_true, y_pred = y_true.align(y_pred, join="inner")
    ok = y_true.notna() & y_pred.notna()
    e = (y_pred - y_true)[ok]
    yt = y_true[ok]
    peak = yt.groupby(yt.index.normalize()).transform("max") == yt
    return {
        "MAPE_%": float((e.abs() / yt).mean() * 100),
        "MAE_MW": float(e.abs().mean()),
        "RMSE_MW": float(np.sqrt((e ** 2).mean())),
        "peak_MAE_MW": float(e[peak].abs().mean()),
        "bias_MW": float(e.mean()),
        "n_hours": int(ok.sum()),
    }
