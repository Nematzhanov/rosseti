#!/usr/bin/env python3
"""Погода по Северо-Западу за прошлый год из Open-Meteo (бесплатно, без ключа).

Три набора, все почасовые и во времени МСК (как данные СО ЕЭС):
  actual       — фактическая погода (реанализ ERA5, archive-api)
  hist_fcst    — архив прогнозов погоды (historical-forecast-api: склейка первых часов
                 каждого прогона оперативных моделей)
  dayahead     — прогноз, каким он был за сутки до (previous-runs-api, *_previous_day1);
                 именно такой прогноз доступен при реальном прогнозе потребления на сутки вперёд

Кроме точек пишется средневзвешенная (по населению) погода ОЭС Северо-Запада.

Запуск:  python3 download_weather.py [--start 2025-09-28] [--end 2026-09-27]
"""
import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# name, регион, lat, lon, население (прибл., Росстат ~2024, млн), входит в ОЭС Северо-Запада
POINTS = [
    ("spb", "г. Санкт-Петербург", 59.9386, 30.3141, 5.60, True),
    ("gatchina", "Ленинградская обл.", 59.5667, 30.1333, 2.03, True),
    ("petrozavodsk", "Респ. Карелия", 61.7849, 34.3469, 0.52, True),
    ("murmansk", "Мурманская обл.", 68.9585, 33.0827, 0.65, True),
    ("arkhangelsk", "Архангельская обл.", 64.5393, 40.5187, 0.96, True),
    ("syktyvkar", "Респ. Коми", 61.6688, 50.8364, 0.72, True),
    ("veliky_novgorod", "Новгородская обл.", 58.5215, 31.2755, 0.58, True),
    ("pskov", "Псковская обл.", 57.8136, 28.3496, 0.58, True),
    ("kaliningrad", "Калининградская обл.", 54.7104, 20.4522, 1.03, True),
    # Вологодская обл. входит в СЗФО, но энергосистема — в ОЭС Центра
    ("vologda", "Вологодская обл.", 59.2181, 39.8886, 1.13, False),
]

VARS_FULL = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "dew_point_2m",
    "precipitation", "snowfall", "snow_depth", "cloud_cover", "shortwave_radiation",
    "wind_speed_10m", "surface_pressure",
]
VARS_DAYAHEAD = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "dew_point_2m",
    "precipitation", "cloud_cover", "shortwave_radiation", "wind_speed_10m",
]
SOURCES = {
    "actual": ("https://archive-api.open-meteo.com/v1/archive", VARS_FULL, ""),
    "hist_fcst": ("https://historical-forecast-api.open-meteo.com/v1/forecast", VARS_FULL, ""),
    "dayahead": ("https://previous-runs-api.open-meteo.com/v1/forecast", VARS_DAYAHEAD, "_previous_day1"),
}

OUT = Path(__file__).resolve().parent


def get_json(url: str, retries: int = 5) -> dict:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 400:  # неверный параметр — повтор не поможет
                raise RuntimeError(f"HTTP 400: {body}") from e
            err = f"HTTP {e.code}: {body[:200]}"
        except Exception as e:  # noqa: BLE001
            err = str(e)
        if attempt == retries - 1:
            raise RuntimeError(err)
        time.sleep(5 * (attempt + 1))


def download(source: str, start: str, end: str) -> list:
    url, variables, suffix = SOURCES[source]
    rows = []
    for name, region, lat, lon, pop, in_oes in POINTS:
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": ",".join(v + suffix for v in variables),
            "start_date": start, "end_date": end,
            "timezone": "Europe/Moscow",
            "wind_speed_unit": "ms",
        }
        data = get_json(url + "?" + urllib.parse.urlencode(params))
        h = data["hourly"]
        for i, t in enumerate(h["time"]):
            row = {"datetime_msk": t.replace("T", " "), "point": name, "region": region,
                   "in_oes_northwest": int(in_oes)}
            for v in variables:
                row[v] = h.get(v + suffix, [None] * len(h["time"]))[i]
            rows.append(row)
        print(f"  {source}: {name} ({len(h['time'])} ч.)", flush=True)
        time.sleep(1)
    return rows


def weighted(rows: list, variables: list) -> list:
    """Средневзвешенная по населению погода ОЭС Северо-Запада (только точки ОЭС)."""
    weights = {p[0]: p[4] for p in POINTS if p[5]}
    acc = {}
    for r in rows:
        if r["point"] not in weights:
            continue
        a = acc.setdefault(r["datetime_msk"], {v: [0.0, 0.0] for v in variables})
        for v in variables:
            if r[v] is not None:
                a[v][0] += r[v] * weights[r["point"]]
                a[v][1] += weights[r["point"]]
    out = []
    for t in sorted(acc):
        row = {"datetime_msk": t}
        for v in variables:
            s, w = acc[t][v]
            row[v] = round(s / w, 3) if w else ""
        out.append(row)
    return out


def write_csv(path: Path, rows: list, fields: list):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-09-28")
    ap.add_argument("--end", default="2026-09-27")
    ap.add_argument("--sources", default=",".join(SOURCES))
    args = ap.parse_args()
    tag = f"{args.start}_{args.end}"

    write_csv(OUT / "points.csv",
              [dict(point=p[0], region=p[1], lat=p[2], lon=p[3], population_mln=p[4],
                    in_oes_northwest=int(p[5])) for p in POINTS],
              ["point", "region", "lat", "lon", "population_mln", "in_oes_northwest"])

    for source in args.sources.split(","):
        variables = SOURCES[source][1]
        try:
            rows = download(source, args.start, args.end)
        except RuntimeError as e:
            print(f"ОШИБКА {source}: {e}")
            continue
        fields = ["datetime_msk", "point", "region", "in_oes_northwest"] + variables
        write_csv(OUT / f"{source}_points_hourly_{tag}.csv", rows, fields)
        write_csv(OUT / f"{source}_oes_northwest_weighted_hourly_{tag}.csv",
                  weighted(rows, variables), ["datetime_msk"] + variables)
        empty = sum(1 for r in rows if r["temperature_2m"] is None)
        print(f"{source}: {len(rows)} строк, пустых значений температуры: {empty}")


if __name__ == "__main__":
    main()
