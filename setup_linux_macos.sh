#!/usr/bin/env bash
set -euo pipefail

echo "== KYC Job Radar: setup Linux/macOS =="
PYTHON="$(command -v python3 || command -v python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.11+ no está instalado o no está en PATH." >&2
  exit 1
fi

[[ -d .venv ]] || "$PYTHON" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m compileall -q job_radar radar.py
python -m unittest discover -s tests -v

echo "Primera búsqueda. Puede tardar unos minutos..."
python radar.py scan
python radar.py health

echo "Dashboard: $PWD/public/index.html"
