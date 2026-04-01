#!/usr/bin/env bash
# Local run: syncs HOMEWORK_1 / HOMEWORK_2 like manifestme, then Shiny.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$SCRIPT_DIR"
mkdir -p HOMEWORK_1 HOMEWORK_2
rsync -a --delete --exclude '__pycache__' "$REPO_ROOT/HOMEWORK_1/" "$SCRIPT_DIR/HOMEWORK_1/"
rsync -a --delete --exclude '__pycache__' --exclude 'data/*.db' "$REPO_ROOT/HOMEWORK_2/" "$SCRIPT_DIR/HOMEWORK_2/"
PORT="${1:-8001}"
exec python -m shiny run app.py:app --host 127.0.0.1 --port "$PORT"
