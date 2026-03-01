#!/bin/bash
# manifestme.sh — generate manifest.json for deploying this Shiny Python app to Posit Connect.
# Run from repo root or from this directory:
#   ./HOMEWORK_1/manifestme.sh
#   # or
#   cd HOMEWORK_1 && ./manifestme.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Optional: ensure rsconnect-python is available
pip install -q rsconnect-python 2>/dev/null || true

# Write manifest.json for this directory (entrypoint auto-detected from HW1_app.py)
rsconnect write-manifest shiny .

echo "Wrote manifest.json in $SCRIPT_DIR"
