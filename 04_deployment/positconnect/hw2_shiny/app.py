# Posit Connect entrypoint for the HW2 Shiny app.
# Bundle layout (after manifestme.sh): this file lives next to HOMEWORK_1/ and HOMEWORK_2/
# so HW2_app.py’s repo-root logic (parent of HOMEWORK_2) stays valid.

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_root / "HOMEWORK_1"))
sys.path.insert(0, str(_root / "HOMEWORK_2"))

from HW2_app import app  # noqa: E402
