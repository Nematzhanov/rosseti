"""Локальный веб-сервер интерфейса прогноза: отдаёт webapp/index.html и считает прогноз через model/predict.py.

Запуск: python3 webapp/server.py [порт]   → открыть http://localhost:8790
API: GET /api/forecast?date=ГГГГ-ММ-ДД&model=chronos-lora|chronos-zs&update=1
"""
import json
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "bin" / "python"
LOCK = threading.Lock()  # модель занимает много памяти — считаем по одному прогнозу
NOISE = ("Warning", "warnings.warn", "MallocStackLogging", "Loading weights")


def forecast(date: str, model: str, update: bool) -> dict:
    cmd = [str(PY), "model/predict.py", "--date", date, "--model", model] + (["--update"] if update else [])
    with LOCK:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    meta, rows, log, inside = {}, [], [], False
    for line in (p.stdout + "\n" + p.stderr).splitlines():
        if line == "RESULT_BEGIN":
            inside = True
        elif line == "RESULT_END":
            inside = False
        elif inside and line.startswith("meta "):
            k, _, v = line[5:].partition(" ")
            meta[k] = v
        elif inside and line.startswith("row "):
            f = line.split()
            num = lambda x: None if x == "-" else float(x)
            rows.append({"hour": int(f[1]), "fc": float(f[2]), "p10": float(f[3]), "p90": float(f[4]), "actual": num(f[5]), "temp": num(f[6])})
        elif line.strip() and not any(n in line for n in NOISE):
            log.append(line)
    ok = p.returncode == 0 and len(rows) == 24
    return {"ok": ok, "meta": meta, "rows": rows, "log": log, "error": None if ok else (log[-1] if log else "ошибка расчёта")}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "webapp"), **kw)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/api/forecast":
            return super().do_GET()
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        model = q.get("model", "chronos-lora")
        if model not in ("chronos-lora", "chronos-zs") or len(q.get("date", "")) != 10:
            self.send_error(400, "bad parameters")
            return
        body = json.dumps(forecast(q["date"], model, q.get("update") == "1"), ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    print(f"Интерфейс прогноза: http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
