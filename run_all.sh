#!/usr/bin/env bash
# Полный конвейер: данные -> модели -> отчёт -> сайт. Повторный запуск докачивает только недостающее.
# Переменные: START, END, KPO (код ОЭС, по умолчанию 840000 — Северо-Запад), CHRONOS_STEPS, DEVICE подбирается сам (cuda/mps/cpu).
set -euo pipefail
cd "$(dirname "$0")"
START=${START:-2021-01-01}; END=${END:-2026-09-29}; KPO=${KPO:-840000}; STEPS=${CHRONOS_STEPS:-600}
python -m pip install -q -r requirements.txt
python download.py --start "$START" --end "$END" --kpo "$KPO"
python weather/download_weather.py --start "$START" --end "$END"
python model/train_lgbm.py
python model/train_chronos.py --runs zs_uni,zs_cov --ctx 2048
python model/train_chronos.py --runs lora --ctx 1024 --batch 16 --steps "$STEPS" --lr 3e-5
python model/report.py
python model/export_dashboard.py --version-label "Облачный прогон"
echo "Готово: results/REPORT.md, dashboard/nw-load-forecast.html"
