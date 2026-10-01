"""Минималистичный сайт: результаты лучшей модели -> site/template.html -> dashboard/nw-load-forecast.html."""
import json
from datetime import datetime

import pandas as pd

from common import ROOT, load_calendar, load_weather, metrics
from report import load_preds

P = load_preds().asfreq("h")
FT = [k for k in ["chronos_ft_lora_cov_fcst", "chronos_ft_full_cov_fcst"] if k in P]
BF = min(FT, key=lambda k: metrics(P["actual"], P[k])["MAPE_%"])
days = pd.date_range(P.index.min().normalize(), P.index.max().normalize(), freq="D")
t = load_weather("actual")["temperature_2m"].reindex(P.index).resample("D").mean()
ints = lambda s: [None if pd.isna(v) else int(round(v)) for v in s]
m = lambda k: metrics(P["actual"], P[k])
bars = [("Chronos-2 после дообучения", BF), ("LightGBM + прогноз погоды", "lgb_fcst"),
        ("Chronos-2 без дообучения", "chronos_zs_cov_fcst"), ("LightGBM без погоды", "lgb_noweather"),
        ("Наивный: как неделю назад", "naive_week")]
data = {
    "start": P.index.min().strftime("%Y-%m-%d"),
    "actual": ints(P["actual"]), "pred": ints(P[BF]),
    "day_temp": [None if pd.isna(v) else round(float(v), 1) for v in t],
    "day_type": [int(v) if pd.notna(v) else 0 for v in load_calendar().reindex(days)],
    "bars": [[name, round(m(k)["MAPE_%"], 2)] for name, k in bars],
    "best": {k: round(v, 2) for k, v in m(BF).items()},
    "naive": round(m("naive_week")["MAPE_%"], 2),
    "lgb_now": round(m("lgb_noweather")["MAPE_%"], 2), "lgb_w": round(m("lgb_fcst")["MAPE_%"], 2),
    "built": datetime.now().strftime("%d.%m.%Y"),
}
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
tpl = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
out = ROOT / "dashboard" / "nw-load-forecast.html"
out.write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
print(out.name, f"{out.stat().st_size // 1024} КБ, лучшая модель {BF}, MAPE {data['best']['MAPE_%']}")
