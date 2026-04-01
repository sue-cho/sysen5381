"""
Posit Connect / Connect Cloud entry shim.

The UI often only offers `app.py` as the Shiny script. The real UI and server live in
`HW2_app.py`; this file re-exports the same `app` object (`app:app`).
"""
from HW2_app import app

__all__ = ["app"]
