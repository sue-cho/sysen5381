#!/usr/bin/env bash
# Same role as HOMEWORK_1/manifestme.sh, but HW2 needs HOMEWORK_1 data next to the repo layout.
# This rsyncs ../HOMEWORK_1 into ./HOMEWORK_1/ (gitignored) so Posit’s bundle includes cache + GVA CSV.
#
# Run from repo root or this directory:
#   ./HOMEWORK_2/manifestme.sh
#   cd HOMEWORK_2 && ./manifestme.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

mkdir -p HOMEWORK_1
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude '*.docx' \
  --exclude 'manifest.json' \
  --exclude 'manifestme.sh' \
  "$REPO_ROOT/HOMEWORK_1/" "$SCRIPT_DIR/HOMEWORK_1/"

pip install -q rsconnect-python 2>/dev/null || pip install rsconnect-python

rsconnect write-manifest shiny . \
  --entrypoint "app:app" \
  --overwrite \
  -x "__pycache__" \
  -x "*.pyc" \
  -x ".DS_Store" \
  -x "HOMEWORK_1/__pycache__" \
  -x "data/*.db"

echo "Wrote manifest.json in $SCRIPT_DIR"
