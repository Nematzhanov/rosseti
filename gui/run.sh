#!/usr/bin/env bash
# Сборка и запуск интерфейса прогноза. Запускать из любой папки.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/gui/out"
javac -encoding UTF-8 -d "$ROOT/gui/out" "$ROOT/gui/src/ForecastApp.java"
exec java -Dfile.encoding=UTF-8 -cp "$ROOT/gui/out" ForecastApp "$ROOT"
