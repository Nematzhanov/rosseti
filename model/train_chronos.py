"""Chronos-2 (Amazon): прогноз потребления ОЭС Северо-Запада на сутки вперёд — zero-shot и дообучение.

Та же постановка, что в train_lgbm.py: прогноз выпускается в D-1 09:00, известны данные до D-1 08:00;
модель прогнозирует 39 часов (D-1 09:00 .. D 23:00), в зачёт идут 24 часа суток D.
Ковариаты: погода (при проверке — прогноз, выпущенный накануне) и производственный календарь.
Дообучение — один раз на данных до начала теста.

Запуск: .venv/bin/python model/train_chronos.py --runs zs_uni,zs_cov,lora,full
"""
import argparse
import json
import time

import numpy as np
import pandas as pd
import torch
from chronos import Chronos2Pipeline
from chronos.chronos2.preprocess import from_list_of_dicts

from common import ISSUE_HOUR, ROOT, load_calendar, load_power, load_weather, metrics

COVS = ["temperature_2m", "wind_speed_10m", "cloud_cover", "shortwave_radiation", "nonwork", "short_day"]
PRED_LEN = (23 - ISSUE_HOUR) + 24  # 39 часов: D-1 09:00 .. D 23:00
OUT = ROOT / "results"
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"


def covariates(weather: pd.DataFrame, cal: pd.Series) -> pd.DataFrame:
    c = weather[COVS[:4]].copy().ffill().bfill()
    day_type = cal.reindex(c.index.normalize()).to_numpy()
    c["nonwork"] = (day_type == 1).astype(float)
    c["short_day"] = (day_type == 2).astype(float)
    return c


def build_inputs(cons, cov_past, cov_future, days, ctx, with_cov=True) -> list:
    items = []
    for d in days:
        last = d - pd.Timedelta(days=1) + pd.Timedelta(hours=ISSUE_HOUR)
        hist = pd.date_range(end=last, periods=ctx, freq="h")
        fut = pd.date_range(last + pd.Timedelta(hours=1), periods=PRED_LEN, freq="h")
        item = {"target": cons.reindex(hist).to_numpy(np.float32)}
        if with_cov:
            item["past_covariates"] = {c: cov_past[c].reindex(hist).to_numpy(np.float32) for c in COVS}
            item["future_covariates"] = {c: cov_future[c].reindex(fut).to_numpy(np.float32) for c in COVS}
        items.append(item)
    return items


def forecast(pipe, items, days) -> pd.Series:
    q, _ = pipe.predict_quantiles(items, prediction_length=PRED_LEN, quantile_levels=[0.1, 0.5, 0.9],
                                  batch_size=32)
    out = []
    for d, qi in zip(days, q):
        med = qi[0, -24:, 1].float().cpu().numpy()  # медиана, последние 24 часа = сутки D
        out.append(pd.Series(med, pd.date_range(d, periods=24, freq="h")))
    return pd.concat(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-start", default="2025-10-01")
    ap.add_argument("--test-end", default="2026-09-29")
    ap.add_argument("--runs", default="zs_uni,zs_cov,lora,full")
    ap.add_argument("--ctx", type=int, default=2048)
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=None, help="по умолчанию 1e-5 для LoRA и 1e-6 для полного")
    local = ROOT / "checkpoints" / "chronos-2"  # веса, скачанные напрямую (xet в этой сети не качает)
    ap.add_argument("--model", default=str(local) if (local / "model.safetensors").exists() else "amazon/chronos-2")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    runs = args.runs.split(",")

    cons, cal = load_power(), load_calendar()
    cov_act = covariates(load_weather("actual"), cal)
    cov_hist = covariates(load_weather("hist_fcst"), cal)
    cov_da = covariates(load_weather("dayahead"), cal)
    days = pd.date_range(args.test_start, args.test_end, freq="D")
    print(f"Устройство: {DEVICE}; тестовых суток: {len(days)}; контекст {args.ctx} ч.", flush=True)

    base = Chronos2Pipeline.from_pretrained(args.model, device_map=DEVICE, dtype=torch.float32)
    honest = build_inputs(cons, cov_hist, cov_da, days, args.ctx)
    preds, timing = {}, {}

    if "zs_uni" in runs:
        t = time.time()
        preds["chronos_zs_uni"] = forecast(base, build_inputs(cons, None, None, days, args.ctx, False), days)
        timing["chronos_zs_uni"] = time.time() - t
    if "zs_cov" in runs:
        t = time.time()
        preds["chronos_zs_cov_fcst"] = forecast(base, honest, days)
        timing["chronos_zs_cov_fcst"] = time.time() - t

    # Дообучение на всём, что известно к выпуску прогноза на первые тестовые сутки (фактическая погода)
    known_until = days[0] - pd.Timedelta(days=1) + pd.Timedelta(hours=ISSUE_HOUR)
    tr = cons.loc[:known_until].interpolate(limit=3).dropna()  # на сайте есть сутки из 23 часов
    tr = tr.loc[tr.index.to_series().diff().ne(pd.Timedelta(hours=1)).cumsum().pipe(
        lambda g: g == g.iloc[-1])]  # последний непрерывный кусок без пропусков
    train_inputs = from_list_of_dicts(
        [{"target": tr.to_numpy(np.float32),
          "past_covariates": {c: cov_act[c].reindex(tr.index).to_numpy(np.float32) for c in COVS}}],
        prediction_length=PRED_LEN, known_covariates_names=COVS)
    print(f"Обучающий ряд для дообучения: {tr.index.min()} .. {tr.index.max()} ({len(tr)} ч.)", flush=True)
    if DEVICE == "mps":  # SDPA на MPS не поддерживает dropout при обучении; fit() строит модель из конфига
        base.model.config.dropout_rate = 0.0

    for mode in [r for r in runs if r in ("lora", "full")]:
        t = time.time()
        lr = args.lr or (1e-5 if mode == "lora" else 1e-6)
        ft = base.fit(train_inputs, prediction_length=PRED_LEN, finetune_mode=mode, learning_rate=lr,
                      num_steps=args.steps, batch_size=args.batch, context_length=args.ctx,
                      output_dir=ROOT / "checkpoints" / f"chronos2-{mode}", min_past=args.ctx // 2,
                      logging_steps=100, save_strategy="no", report_to="none")
        timing[f"chronos_ft_{mode}_train"] = time.time() - t
        t = time.time()
        preds[f"chronos_ft_{mode}_cov_fcst"] = forecast(ft, honest, days)
        timing[f"chronos_ft_{mode}_cov_fcst"] = time.time() - t
        del ft
        if DEVICE == "mps":
            torch.mps.empty_cache()

    P = pd.DataFrame(preds)
    P.insert(0, "actual", cons.reindex(P.index))
    P.index.name = "datetime_msk"
    path = OUT / "predictions_chronos.csv"
    if path.exists():  # дописываем к прошлым прогонам, новые колонки заменяют старые
        old = pd.read_csv(path, parse_dates=["datetime_msk"], index_col="datetime_msk")
        P = old.drop(columns=[c for c in P.columns if c in old.columns]).join(P, how="outer") \
            if old.index.equals(P.index) else P
    P.to_csv(path)
    res = {k: metrics(P["actual"], P[k]) for k in P.columns if k != "actual"}
    (OUT / "metrics_chronos.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    (OUT / "timing_chronos.json").write_text(json.dumps(timing, indent=2))
    print(pd.DataFrame(res).T.round(2).to_string())
    print({k: round(v) for k, v in timing.items()})


if __name__ == "__main__":
    main()
