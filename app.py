"""
Posit Connect Cloud — primary file (Git deploy).

Delegates to the Homework 2 Shiny app in HOMEWORK_2/. Keeps a single obvious
`app.py` at the repo root for the Connect file picker.
"""
import sys
from pathlib import Path

_hw2 = Path(__file__).resolve().parent / "HOMEWORK_2"
sys.path.insert(0, str(_hw2))

from HW2_app import app  # noqa: E402

__all__ = ["app"]
