# Прогноз электропотребления ОЭС Северо-Запада

Почасовой прогноз потребления мощности объединённой энергосистемы Северо-Запада на сутки вперёд с учётом погоды. Сравниваются базовые модели, градиентный бустинг LightGBM и предобученная модель временных рядов Chronos-2 (Amazon) с дообучением.

## Результаты

Проверка на целом годе (01.10.2025 – 29.09.2026, 8 736 часов). Прогноз выпускается накануне в 09:00 МСК, на целевые сутки используется **прогноз** погоды, а не факт.

| Модель | MAPE, % |
|---|---|
| Chronos-2, дообучение LoRA | **0,84** |
| Chronos-2, полное дообучение | 0,85 |
| Ансамбль LightGBM + Chronos-2 | 0,86 |
| LightGBM + прогноз погоды | 0,97 |
| LightGBM без погоды | 1,39 |
| Наивный прогноз (неделю назад) | 2,81 |

- Лучшая модель в 3,3 раза точнее наивного прогноза.
- Прогноз погоды снижает ошибку LightGBM на 30 %.
- В самую холодную неделю (−14,9 °C) Chronos-2 ошибается на ~0,5 %, LightGBM — на 1,08 %: деревья решений не экстраполируют пики.

## Данные

- Потребление — АО «СО ЕЭС», раздел «Генерация (час)», 2021–2026.
- Погода — Open-Meteo: реанализ ERA5, архив прогнозов и прогноз за сутки; 9 городов ОЭС, веса по населению.
- Производственный календарь — isdayoff.ru.

## Структура

| Папка / файл | Что внутри |
|---|---|
| `download.py` | загрузка почасовых данных СО ЕЭС (с паузами, сайт ограничивает частоту) |
| `weather/download_weather.py` | загрузка погоды из Open-Meteo |
| `model/common.py` | загрузка данных, признаки, метрики |
| `model/train_lgbm.py` | бэктест базовых моделей и LightGBM (ежемесячное переобучение) |
| `model/train_chronos.py` | Chronos-2: zero-shot, LoRA и полное дообучение |
| `model/report.py` | сводный отчёт и графики → `results/REPORT.md` |
| `model/export_dashboard.py`, `dashboard/` | интерактивный сайт с результатами |
| `deck/` | презентация (PptxGenJS + постобработка: переход «Трансформация», анимации) |
| `article/` | статья в формате .docx и рисунки к ней |
| `PLAN.md` | план исследования |

## Запуск

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python pandas numpy pyarrow lightgbm scikit-learn matplotlib "chronos-forecasting>=2.0"
python3 download.py --start 2021-01-01 --end 2026-09-29 --kpo 840000
python3 weather/download_weather.py --start 2021-01-01 --end 2026-09-29
.venv/bin/python model/train_lgbm.py
.venv/bin/python model/train_chronos.py --runs zs_uni,zs_cov --ctx 2048
.venv/bin/python model/train_chronos.py --runs lora --ctx 1024 --batch 16 --steps 600 --lr 3e-5
.venv/bin/python model/report.py
```

## Автор

Мухаммадзохид Нематжанов — студент Политехнического института НовГУ имени Ярослава Мудрого.
[GitHub](https://github.com/Nematzhanov) · [Telegram](https://t.me/nematzhonov) · [Instagram](https://www.instagram.com/nematzhanov_) · nematzhanov.m@gmail.com
