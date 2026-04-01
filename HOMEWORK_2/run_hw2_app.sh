#!/usr/bin/env bash
# Run HW2 Shiny app with the repo .venv (avoids conda `shiny` using Anaconda Python).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
PORT="${1:-8001}"
exec "$PY" -m shiny run "$HERE/HW2_app.py:app" --port "$PORT"
