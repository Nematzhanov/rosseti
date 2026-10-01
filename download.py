#!/usr/bin/env python3
"""Скачивает почасовые генерацию и потребление ЕЭС/ОЭС с сайта СО ЕЭС (so-ups.ru).

Источник: https://www.so-ups.ru/functioning/ees/ees-indicators/ees-gen-consump-hour/
Страница отдаёт одни сутки для одной энергосистемы; ряды лежат в атрибутах
data-datay1 (мощность генерации, МВт) и data-datay (мощность потребления, МВт).

Запуск:  python3 download.py [--start 2025-09-28] [--end 2026-09-27]
Повторный запуск докачивает только недостающее (кэш в raw/cache.jsonl).
"""
import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

BASE = "https://www.so-ups.ru/functioning/ees/ees-indicators/ees-gen-consump-hour/"
KPO = {
    1019: "ЕЭС РОССИИ",
    530000: "ОЭС ЦЕНТРА",
    550000: "ОЭС ЮГА",
    600000: "ОЭС СР. ВОЛГИ",
    610000: "ОЭС СИБИРИ",
    630000: "ОЭС УРАЛА",
    840000: "ОЭС СЕВ.ЗАПАДА",
    540000: "ОЭС ВОСТОКА",
}
SLUG = {
    1019: "ees_russia", 530000: "oes_center", 550000: "oes_south",
    600000: "oes_mid_volga", 610000: "oes_siberia", 630000: "oes_ural",
    840000: "oes_northwest", 540000: "oes_east",
}
CHART_RE = re.compile(
    r'data-datax="([^"]*)"\s*data-datay="([^"]*)"\s*data-datay1="([^"]*)"'
    r'[^>]*data-source="([^"]*)"\s*data-date="([^"]*)"'
)

OUT = Path(__file__).resolve().parent
CACHE = OUT / "raw" / "cache.jsonl"


DELAY = 2.0  # пауза перед каждым запросом, сек (сайт отвечает 503 на частые запросы)


def fetch(day: date, kpo: int, retries: int = 8) -> dict:
    params = {
        "tx_mscdugraph_pi[controller]": "Graph",
        "tx_mscdugraph_pi[action]": "fullview",
        "tx_mscdugraph_pi[viewDate]": day.isoformat(),
        "tx_mscdugraph_pi[viewKpo]": str(kpo),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research data download)"})
    for attempt in range(retries):
        time.sleep(DELAY)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                html = r.read().decode("utf-8", errors="replace")
            m = CHART_RE.search(html)
            if not m:
                raise ValueError("chart data not found")
            xs, cons, gen, source, d = m.groups()
            if d != day.isoformat():
                raise ValueError(f"date mismatch: {d}")
            return {
                "date": d, "kpo": kpo, "source": source,
                "x": xs.split(",") if xs else [],
                "gen": gen.split(",") if gen else [],
                "cons": cons.split(",") if cons else [],
            }
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise RuntimeError(f"{day} {kpo}: {e}") from e
            throttled = isinstance(e, urllib.error.HTTPError) and e.code in (429, 503)
            time.sleep(30 * (attempt + 1) if throttled else 2 ** attempt)


def load_cache() -> dict:
    done = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done[(rec["date"], rec["kpo"])] = rec
    return done


def to_num(v: str):
    v = v.strip()
    if v in ("", "null", "NaN"):
        return ""
    return int(v) if re.fullmatch(r"-?\d+", v) else float(v)


def build_rows(records: dict) -> list:
    rows = []
    for (d, kpo), rec in sorted(records.items(), key=lambda kv: (kv[0][1] != 1019, kv[0][1], kv[0][0])):
        for i, x in enumerate(rec["x"]):
            day_s, hour_s = x.split(" ")
            hour = int(hour_s.split(":")[0])
            rows.append({
                "datetime_msk": f"{day_s} {hour:02d}:00",
                "date": day_s,
                "hour": hour,
                "kpo": kpo,
                "energy_system": KPO[kpo],
                "generation_mw": to_num(rec["gen"][i]) if i < len(rec["gen"]) else "",
                "consumption_mw": to_num(rec["cons"][i]) if i < len(rec["cons"]) else "",
            })
    return rows


def write_csv(path: Path, rows: list, fields: list):
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM, чтобы Excel открыл кириллицу
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    today = date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=(today - timedelta(days=365)).isoformat())
    ap.add_argument("--end", default=(today - timedelta(days=1)).isoformat())
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--kpo", default=",".join(map(str, KPO)), help="коды энергосистем через запятую")
    args = ap.parse_args()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    kpos = [int(k) for k in args.kpo.split(",")]

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    records = load_cache()
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    # сначала свежие даты: при прерывании остаётся непрерывный хвост истории, пригодный для обучения
    todo = [(d, k) for d in reversed(days) for k in kpos if (d.isoformat(), k) not in records]
    print(f"Период {start}..{end}: {len(days)} дн. x {len(kpos)} энергосистем; к загрузке {len(todo)}")

    failed = []
    with ThreadPoolExecutor(args.workers) as pool, CACHE.open("a", encoding="utf-8") as cache:
        futs = {pool.submit(fetch, d, k): (d, k) for d, k in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                rec = fut.result()
            except Exception as e:  # noqa: BLE001
                failed.append(str(e))
                continue
            records[(rec["date"], rec["kpo"])] = rec
            cache.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cache.flush()
            if n % 100 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)}", flush=True)

    in_range = {k: v for k, v in records.items() if start.isoformat() <= k[0] <= end.isoformat()}
    rows = build_rows(in_range)
    fields = ["datetime_msk", "date", "hour", "kpo", "energy_system", "generation_mw", "consumption_mw"]
    tag = f"{start}_{end}"

    write_csv(OUT / f"all_energy_systems_hourly_{tag}.csv", rows, fields)
    per_dir = OUT / "by_energy_system"
    per_dir.mkdir(exist_ok=True)
    for kpo, slug in SLUG.items():
        write_csv(per_dir / f"{slug}_{kpo}_hourly_{tag}.csv", [r for r in rows if r["kpo"] == kpo], fields)

    # Широкая таблица: одна строка = час, колонки = генерация/потребление по каждой энергосистеме
    wide = {}
    for r in rows:
        w = wide.setdefault(r["datetime_msk"], {"datetime_msk": r["datetime_msk"]})
        w[f"gen_{SLUG[r['kpo']]}"] = r["generation_mw"]
        w[f"cons_{SLUG[r['kpo']]}"] = r["consumption_mw"]
    wide_fields = ["datetime_msk"] + [f"{p}_{SLUG[k]}" for k in KPO for p in ("gen", "cons")]
    write_csv(OUT / f"wide_hourly_{tag}.csv", [wide[k] for k in sorted(wide)], wide_fields)

    print(f"Строк: {len(rows)}; ошибок: {len(failed)}")
    for e in failed[:20]:
        print("  FAIL", e)


if __name__ == "__main__":
    main()
