#!/usr/bin/env bash
# Build manifest.json for Posit Connect / Posit Connect Cloud (Shiny for Python).
#
# Copies HOMEWORK_1 and HOMEWORK_2 into this folder (same layout as the repo root)
# so rsconnect can checksum every file. Run from repo root or this directory:
#   ./04_deployment/positconnect/hw2_shiny/manifestme.sh
#
# Re-run after changing Python deps (requirements.txt) or files under HOMEWORK_1 / HOMEWORK_2.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$SCRIPT_DIR"

rm -rf HOMEWORK_1 HOMEWORK_2
mkdir -p HOMEWORK_1 HOMEWORK_2
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude '*.docx' \
  "$REPO_ROOT/HOMEWORK_1/" "$SCRIPT_DIR/HOMEWORK_1/"
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'data/*.db' \
  "$REPO_ROOT/HOMEWORK_2/" "$SCRIPT_DIR/HOMEWORK_2/"

pip install -q rsconnect-python 2>/dev/null || pip install rsconnect-python

rsconnect write-manifest shiny . \
  --entrypoint "app:app" \
  --overwrite \
  -x "__pycache__" \
  -x "*.pyc" \
  -x ".DS_Store" \
  -x "HOMEWORK_1/__pycache__" \
  -x "HOMEWORK_2/__pycache__" \
  -x "HOMEWORK_2/data/*.db"

echo "Wrote manifest.json in $SCRIPT_DIR"
echo "Next: rsconnect deploy shiny .   (or Connect UI using this directory contents)"
