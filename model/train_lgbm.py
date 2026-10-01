"""Бэктест базовых моделей и LightGBM для ОЭС Северо-Запада (прогноз на сутки вперёд).

Каждый тестовый месяц модель переобучается на всех данных, известных к его началу
(расширяющееся окно). Обучение — на фактической погоде; проверка:
  *_fcst   — честно: погода на целевые сутки = прогноз, выпущенный накануне (dayahead),
             погода прошлых дней = архив оперативного анализа (hist_fcst);
  *_oracle — на фактической погоде (недостижимая на практике верхняя граница).

Запуск: .venv/bin/python model/train_lgbm.py [--test-start 2025-10-01] [--test-end 2026-09-29]
"""
import argparse
import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

from common import ROOT, WEATHER_VARS, load_calendar, load_power, load_weather, make_features, metrics

WEATHER_FEATS = WEATHER_VARS + ["hdd", "temp_ema24", "temp_ema72", "temp_day_mean", "temp_day_min",
                                "temp_day_max", "temp_lag48", "temp_lag168", "temp_day_mean_lag2",
                                "temp_delta_vs_lag2"]
CAT_FEATS = ["hour", "dow", "month", "day_type", "day_type_prev", "day_type_next"]
LGB_PARAMS = dict(objective="l2", learning_rate=0.03, num_leaves=63, min_data_in_leaf=40,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                  verbose=-1, seed=42)
OUT = ROOT / "results"


def fit_lgb(X: pd.DataFrame, y: pd.Series, val_days: int = 56):
    cut = X.index.max() - pd.Timedelta(days=val_days)
    tr, va = X.index <= cut, X.index > cut
    dtr = lgb.Dataset(X[tr], y[tr])
    dva = lgb.Dataset(X[va], y[va], reference=dtr)
    m = lgb.train(LGB_PARAMS, dtr, 5000, valid_sets=[dva],
                  callbacks=[lgb.early_stopping(200, verbose=False)])
    n = max(200, int(m.best_iteration * 1.05))
    return lgb.train(LGB_PARAMS, lgb.Dataset(X, y), n)


def fit_ridge(X: pd.DataFrame, y: pd.Series):
    num = [c for c in X.columns if c not in CAT_FEATS]
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATS),
                             ("num", StandardScaler(), num)])
    return make_pipeline(pre, RidgeCV(alphas=np.logspace(-2, 3, 12))).fit(X, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-start", default="2025-10-01")
    ap.add_argument("--test-end", default="2026-09-29")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    cons = load_power()
    cal = load_calendar()
    w_act, w_hist, w_da = load_weather("actual"), load_weather("hist_fcst"), load_weather("dayahead")
    print(f"Потребление: {cons.index.min()} .. {cons.index.max()}, пропусков {int(cons.isna().sum())} ч.")

    X_act = make_features(cons, w_act, w_act, cal)       # обучение и «оракул»
    X_fcst = make_features(cons, w_da, w_hist, cal)      # честная проверка
    y = cons

    test_start, test_end = pd.Timestamp(args.test_start), pd.Timestamp(args.test_end) + pd.Timedelta(hours=23)
    months = pd.date_range(test_start, test_end, freq="MS")
    preds = {k: [] for k in ["naive_week", "ridge_fcst", "lgb_noweather", "lgb_fcst", "lgb_oracle",
                             "lgb_ratio_fcst"]}
    importances = []

    for m_start in months:
        m_end = min(m_start + pd.offsets.MonthEnd(0) + pd.Timedelta(hours=23), test_end)
        # к выпуску прогноза на первые сутки месяца полностью известны сутки до m_start-2
        train = (X_act.index < m_start - pd.Timedelta(days=1)) & y.notna()
        train &= X_act[["cons_lag336", "cons_last_known"]].notna().all(axis=1)
        test = (X_act.index >= m_start) & (X_act.index <= m_end)
        Xtr, ytr = X_act[train], y[train]
        noweather = [c for c in Xtr.columns if c not in WEATHER_FEATS]

        m_all = fit_lgb(Xtr, ytr)
        m_nw = fit_lgb(Xtr[noweather], ytr)
        # Цель — отношение к среднему потреблению за неделю: деревьям не нужно экстраполировать уровень
        m_ratio = fit_lgb(Xtr, ytr / Xtr["cons_week_mean"])
        ok = Xtr.notna().all(axis=1)
        m_ridge = fit_ridge(Xtr[ok], ytr[ok])

        idx = X_act.index[test]
        preds["naive_week"].append(X_act.loc[test, "cons_lag168"])
        preds["lgb_oracle"].append(pd.Series(m_all.predict(X_act[test]), idx))
        preds["lgb_fcst"].append(pd.Series(m_all.predict(X_fcst[test]), idx))
        preds["lgb_noweather"].append(pd.Series(m_nw.predict(X_act.loc[test, noweather]), idx))
        preds["lgb_ratio_fcst"].append(pd.Series(m_ratio.predict(X_fcst[test]) * X_fcst.loc[test, "cons_week_mean"], idx))
        preds["ridge_fcst"].append(pd.Series(m_ridge.predict(X_fcst[test].fillna(X_fcst[test].median())), idx))
        importances.append(pd.Series(m_all.feature_importance("gain"), Xtr.columns))
        mp = metrics(y[test], preds["lgb_fcst"][-1])["MAPE_%"]
        print(f"{m_start:%Y-%m}: обучение {int(train.sum())} ч., LightGBM (прогноз погоды) MAPE {mp:.2f}%", flush=True)

    P = pd.DataFrame({k: pd.concat(v) for k, v in preds.items()})
    P.insert(0, "actual", y.reindex(P.index))
    P.index.name = "datetime_msk"
    P.to_csv(OUT / "predictions_lgbm.csv")

    res = {k: metrics(P["actual"], P[k]) for k in preds}
    (OUT / "metrics_lgbm.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    imp = pd.concat(importances, axis=1).mean(axis=1).sort_values(ascending=False)
    imp.to_csv(OUT / "feature_importance_lgbm.csv", header=["gain"])
    print(pd.DataFrame(res).T.round(2).to_string())


if __name__ == "__main__":
    main()
