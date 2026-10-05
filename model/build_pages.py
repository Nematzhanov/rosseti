"""Собирает сайт для GitHub Pages в папку docs/:
  docs/index.html   — лендинг: прогноз на завтра, прогноз и факт за прошедшие сутки, точность за год, автор;
  docs/results.html — полный сайт с результатами бэктеста (копия dashboard/nw-load-forecast.html).

Прогнозы берутся из файлов docs/_fc_<дата>.txt — это вывод model/predict.py:
  .venv/bin/python model/predict.py --date <дата> --update | sed -n '/RESULT_BEGIN/,/RESULT_END/p' > docs/_fc_<дата>.txt
Запуск: python3 model/build_pages.py [--check 2026-10-05] [--tomorrow 2026-10-07]
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def read_fc(path: Path):
    if not path.exists():
        return None
    meta, rows = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("meta "):
            k, _, v = line[5:].partition(" ")
            meta[k] = v
        elif line.startswith("row "):
            f = line.split()
            num = lambda x: None if x == "-" else float(x)
            rows.append([int(f[1]), float(f[2]), float(f[3]), float(f[4]), num(f[5]), num(f[6])])
    return {"meta": meta, "rows": rows} if len(rows) == 24 else None


def main():
    files = sorted(DOCS.glob("_fc_*.txt"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", help="сутки, для которых показать прогноз и факт")
    ap.add_argument("--tomorrow", help="сутки прогноза «на завтра»")
    args = ap.parse_args()
    fcs = {p.stem[4:]: read_fc(p) for p in files}
    with_fact = [d for d, f in fcs.items() if f and f["meta"].get("mape", "-") != "-"]
    without = [d for d, f in fcs.items() if f and f["meta"].get("mape", "-") == "-"]
    check = args.check or (max(with_fact) if with_fact else None)
    tomorrow = args.tomorrow or (max(without) if without else None)

    deck = json.loads((ROOT / "deck" / "data.json").read_text())
    y, best = deck["year"], deck["best_ft"]
    st = deck["stats"]
    data = {
        "year": {"best": y[best]["MAPE_%"], "naive": y["naive_week"]["MAPE_%"],
                 "lgb_now": y["lgb_noweather"]["MAPE_%"], "lgb_w": y["lgb_fcst"]["MAPE_%"]},
        "bars": [["Chronos-2 после дообучения", y[best]["MAPE_%"]], ["Ансамбль", y["ens_lgb_chronos"]["MAPE_%"]],
                 ["LightGBM + прогноз погоды", y["lgb_fcst"]["MAPE_%"]], ["LightGBM без погоды", y["lgb_noweather"]["MAPE_%"]],
                 ["Наивный: как неделю назад", y["naive_week"]["MAPE_%"]]],
        "test": f"{st['test_start']} – {st['test_end']}", "hours": st["test_days"] * 24,
        "tomorrow": fcs.get(tomorrow) if tomorrow else None, "check": fcs.get(check) if check else None,
        "built": datetime.now().strftime("%d.%m.%Y"),
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = (ROOT / "site" / "landing.html").read_text(encoding="utf-8")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    res = (ROOT / "dashboard" / "nw-load-forecast.html").read_text(encoding="utf-8")
    if "<html" not in res[:300]:  # страница собрана как фрагмент — оборачиваем для обычного хостинга
        res = '<!doctype html>\n<html lang="ru">\n<head>\n<meta name="viewport" content="width=device-width, initial-scale=1">\n' + res + "\n</html>\n"
    res = res.replace('<p class="foot">', '<p class="foot"><a href="index.html">← На главную</a> · ', 1)
    (DOCS / "results.html").write_text(res, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    print(f"docs/index.html: завтра={tomorrow}, прогноз и факт={check}; docs/results.html")


if __name__ == "__main__":
    main()
