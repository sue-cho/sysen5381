#!/usr/bin/env python3
"""
AI quality control for NYT state comparison reports: faithfulness, formality, and clarity (1–5).

Default evaluator: Ollama Cloud (api.ollama.com). Override with --evaluator openai for gpt-4o-mini.

Scores can be saved to CSV for statistics, similar to LABS/09_text_analysis/data/prompt_comparison_scores.csv.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# --- Config (match lab + HW2) ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

# Ollama Cloud QC (https://docs.ollama.com/api/authentication)
OLLAMA_CHAT_URL = "https://api.ollama.com/api/chat"
OLLAMA_CLOUD_MODEL = os.getenv("OLLAMA_CLOUD_MODEL", "")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DEFAULT_SOURCE = DATA_DIR / "source_stats_nv_la.json"
DEFAULT_REPORTS = DATA_DIR / "generated_reports_nv_la.json"
DEFAULT_SCORES_CSV = DATA_DIR / "qc_scores_nv_la.csv"

N_RUNS_QC = 2
QC_SLEEP_SEC = 0.5
DEFAULT_EVALUATOR = "ollama"
PROMPT_ID_PREFIX = "NV_LA"


def query_ai_quality_control(prompt: str, provider: str = DEFAULT_EVALUATOR) -> str:
    """OpenAI chat or Ollama Cloud /api/chat; return raw text (JSON inside)."""
    if provider == "ollama":
        api_key = os.getenv("OLLAMA_API_KEY")
        if not api_key:
            raise ValueError("OLLAMA_API_KEY not set (required for Ollama Cloud).")
        model = OLLAMA_CLOUD_MODEL.strip()
        if not model:
            raise ValueError("Set OLLAMA_CLOUD_MODEL for Ollama Cloud QC.")
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a quality control validator. Always return valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(OLLAMA_CHAT_URL, json=body, headers=headers, timeout=300)
        response.raise_for_status()
        response_data = response.json()
        return response_data["message"]["content"]

    if provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found in environment.")
        url = "https://api.openai.com/v1/chat/completions"
        body = {
            "model": OPENAI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a quality control validator. Always return your responses as valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=body, timeout=120)
        response.raise_for_status()
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]

    raise ValueError("Invalid provider. Use 'ollama' (Ollama Cloud) or 'openai'.")


def create_nyt_qc_prompt(report_text: str, source_data: str | None = None) -> str:
    instructions = (
        "You are a quality control validator for AI-generated NYT state comparison reports. "
        "Score faithfulness, formality, and clarity. Return valid JSON."
    )
    data_context = f"\n\nSource Data (ground truth for faithfulness):\n{source_data}\n" if source_data else ""
    criteria = """
Quality Control Criteria:

1. **faithfulness** (1-5 Likert scale): Rank the paragraph on a 5-point Likert scale, where
   1 = makes grandiose claims not supported by the data vs. 5 = makes claims directly related to the data.

2. **formality** (1-5 Likert scale): Rank the paragraph on a 5-point Likert scale, where
   1 = casual writing vs. 5 = government report writing.

3. **clarity** (1-5): 1 = confusing or poorly structured; 5 = clear and easy to follow.

Return JSON exactly in this shape:
{
  "faithfulness": <integer 1-5>,
  "formality": <integer 1-5>,
  "clarity": <integer 1-5>,
  "details": "<brief explanation>"
}
"""
    return f"{instructions}{data_context}\n\nReport Text to Validate:\n{report_text}{criteria}"


def parse_nyt_qc_results(json_response: str) -> pd.DataFrame:
    m = re.search(r"\{.*\}", json_response, re.DOTALL)
    if m:
        json_response = m.group(0)
    data = json.loads(json_response)
    faith = int(data["faithfulness"])
    formal = int(data["formality"])
    clar = int(data["clarity"])
    details = str(data.get("details", ""))
    overall = (faith + formal + clar) / 3.0
    return pd.DataFrame(
        {
            "faithfulness": [faith],
            "formality": [formal],
            "clarity": [clar],
            "details": [details],
            "overall_score": [round(overall, 2)],
        }
    )


def run_qc_evaluations(
    report_text: str,
    source_data: str | None,
    n_runs: int,
    provider: str = DEFAULT_EVALUATOR,
) -> pd.DataFrame:
    """Repeated QC runs with the chosen evaluator (Ollama Cloud or OpenAI)."""
    rows: list[pd.DataFrame] = []
    for run in range(1, n_runs + 1):
        prompt = create_nyt_qc_prompt(report_text, source_data)
        raw = query_ai_quality_control(prompt, provider=provider)
        df = parse_nyt_qc_results(raw)
        df.insert(0, "report_id", run)
        rows.append(df)
        if run < n_runs:
            time.sleep(QC_SLEEP_SEC)
    return pd.concat(rows, ignore_index=True)


def summarize_evaluations(df: pd.DataFrame) -> pd.DataFrame:
    """Mean/std for faithfulness, formality, clarity."""
    return pd.DataFrame(
        [
            {
                "avg_faithfulness": df["faithfulness"].mean(),
                "avg_formality": df["formality"].mean(),
                "avg_clarity": df["clarity"].mean(),
                "avg_overall_score": df["overall_score"].mean(),
                "std_faithfulness": df["faithfulness"].std(ddof=0),
                "std_formality": df["formality"].std(ddof=0),
                "std_clarity": df["clarity"].std(ddof=0),
                "std_overall_score": df["overall_score"].std(ddof=0),
            }
        ]
    )


def scores_to_csv_rows(
    prompt_id: str,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Wide row layout comparable to prompt_comparison_scores.csv (ids + numeric scores)."""
    out = df[["report_id", "overall_score", "faithfulness", "formality", "clarity"]].copy()
    out.insert(0, "prompt_id", prompt_id)
    return out


def load_source_stats(path: Path | None = None) -> str:
    p = path or DEFAULT_SOURCE
    with open(p, encoding="utf-8") as f:
        src = json.load(f)
    return str(src.get("stats_markdown", "") or "")


def load_generated_reports(path: Path | None = None) -> list[dict]:
    p = path or DEFAULT_REPORTS
    with open(p, encoding="utf-8") as f:
        reports = json.load(f)
    if not reports:
        raise FileNotFoundError(f"No entries in {p}")
    return reports


def _evaluator_label(provider: str) -> str:
    if provider == "openai":
        return f"OpenAI ({OPENAI_MODEL})"
    return f"Ollama Cloud ({OLLAMA_CLOUD_MODEL or 'set OLLAMA_CLOUD_MODEL'})"


def grade_one_report(
    report_text: str,
    source_data: str | None,
    n_runs: int,
    provider: str = DEFAULT_EVALUATOR,
    heading: str | None = None,
) -> pd.DataFrame:
    """Run QC; print table + summary. Returns per-run DataFrame (incl. details)."""
    if heading:
        print(heading)

    print(f"--- Evaluator: {_evaluator_label(provider)} ---")
    df = run_qc_evaluations(report_text, source_data, n_runs, provider=provider)
    print(df.drop(columns=["details"], errors="ignore").to_string(index=False))
    print()
    print("--- Summary (mean / std) ---")
    print(summarize_evaluations(df).to_string(index=False))
    print()
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Grade NV/LA reports with AI QC (faithfulness, formality, clarity). "
            "Default evaluator is Ollama Cloud (OLLAMA_API_KEY + OLLAMA_CLOUD_MODEL); "
            "use --evaluator openai for OpenAI. "
            "Writes a CSV in the same spirit as prompt_comparison_scores.csv."
        )
    )
    parser.add_argument(
        "--evaluator",
        choices=("ollama", "openai"),
        default=DEFAULT_EVALUATOR,
        help="ollama = Ollama Cloud; openai = gpt-4o-mini (default: ollama)",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        default=N_RUNS_QC,
        help=f"Repeated QC calls per generated report (default {N_RUNS_QC})",
    )
    parser.add_argument(
        "--reports",
        choices=("first", "all"),
        default="all",
        help="Grade only the first saved report, or every entry in generated_reports_nv_la.json (default: all)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help=f"Override path to source_stats JSON (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--generated",
        type=Path,
        default=None,
        help=f"Override path to generated_reports JSON (default: {DEFAULT_REPORTS})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SCORES_CSV,
        help=f"CSV path for scores (default: {DEFAULT_SCORES_CSV})",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print results only; do not write CSV",
    )
    args = parser.parse_args()

    source_data = load_source_stats(args.source)
    reports = load_generated_reports(args.generated)
    if args.reports == "first":
        reports = reports[:1]

    csv_chunks: list[pd.DataFrame] = []

    for rec in reports:
        author = rec.get("model", "?")
        gen_run_id = rec.get("run_id", "?")
        report_text = rec.get("report_text", "")
        if not report_text:
            continue
        prompt_id = f"{PROMPT_ID_PREFIX}_{author}"
        print(f"========== Grading: report author={author!r} gen_run_id={gen_run_id} ==========")
        df = grade_one_report(
            report_text, source_data, args.n_runs, provider=args.evaluator
        )
        csv_chunks.append(scores_to_csv_rows(prompt_id, df))

    if csv_chunks:
        combined = pd.concat(csv_chunks, ignore_index=True)
        # Column order: ids, overall, then Likert dimensions (cf. prompt_comparison_scores.csv)
        cols = ["prompt_id", "report_id", "overall_score", "faithfulness", "formality", "clarity"]
        combined = combined[[c for c in cols if c in combined.columns]]
        if not args.no_save:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            combined.to_csv(args.output, index=False)
            print(f"Saved scores CSV: {args.output}")


if __name__ == "__main__":
    main()
