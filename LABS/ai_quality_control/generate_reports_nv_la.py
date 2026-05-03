#!/usr/bin/env python3
"""
Generate NV vs LA NYT comparison reports by reusing HW2 Agents 3–4 with OpenAI or Ollama Cloud.
Agent 2 + stats + RAG run once; only LLM calls repeat with varied temperature.

Requires: HOMEWORK_1 cache + GVA CSV, OPENAI_API_KEY, and for Ollama Cloud OLLAMA_API_KEY + OLLAMA_CLOUD_MODEL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Repo root → import HOMEWORK_2.HW2_multi_agent
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOMEWORK_2 = _REPO_ROOT / "HOMEWORK_2"
if str(_HOMEWORK_2) not in sys.path:
    sys.path.insert(0, str(_HOMEWORK_2))

from HW2_multi_agent import (  # noqa: E402
    RAG_MIN_SIMILARITY,
    agent1_relevant_urls,
    agent2_build_state_summary,
    agent3_format_bullets,
    agent4_write_report,
    build_gva_events_for_states,
    compute_state_comparison_stats,
    get_state_demographics,
    _load_rag_conn_like_app,
    _synthetic_validated_from_gva_events,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
GENERATED_JSON = DATA_DIR / "generated_reports_nv_la.json"
SOURCE_STATS_JSON = DATA_DIR / "source_stats_nv_la.json"

STATE_A = "NV"
STATE_B = "LA"

BASE_TEMP = 0.3
EPSILON = 0.05


def _structured_stats(state_summary: dict) -> dict:
    out = {}
    for key in ("state_a", "state_b"):
        s = state_summary.get(key) or {}
        out[key] = {
            "state": s.get("state"),
            "total_events": s.get("total_events"),
            "covered_events": s.get("covered_events"),
            "coverage_rate_pct": s.get("coverage_rate"),
            "avg_days_to_first_article": s.get("avg_days_to_first_article"),
            "same_day_coverage_pct": s.get("same_day_coverage_pct"),
            "demographics": s.get("demographics"),
        }
    return out


def generate_reports(
    n_runs: int,
    model: str,
    stats_markdown: str,
    rag_context: str,
    ollama_model: str | None = None,
    start_run_id: int = 1,
) -> list[dict]:
    """
    model: 'openai' or 'ollama'
    Each run varies temperature; Agent 3 then Agent 4 use the same temp for that run.
    run_id values are start_run_id, start_run_id+1, ... (use start_run_id > 1 when appending batches).
    """
    if model not in ("openai", "ollama"):
        raise ValueError("model must be 'openai' or 'ollama'")

    records: list[dict] = []
    total_tokens_used = {"prompt": 0, "completion": 0}
    llm_backend = model

    for offset in range(n_runs):
        run_id = start_run_id + offset
        temp = BASE_TEMP + (run_id * EPSILON)
        temp = min(max(temp, 0.2), 0.9)

        bullets = agent3_format_bullets(
            stats_markdown=stats_markdown,
            total_tokens_used=total_tokens_used,
            rag_context=rag_context,
            llm_backend=llm_backend,
            temperature=temp,
            ollama_model=ollama_model,
        )
        report_text = agent4_write_report(
            stats_markdown=stats_markdown,
            agent3_bullets=bullets,
            total_tokens_used=total_tokens_used,
            llm_backend=llm_backend,
            temperature=temp,
            ollama_model=ollama_model,
        )
        records.append(
            {
                "model": model,
                "run_id": run_id,
                "report_text": report_text,
                "temperature": temp,
            }
        )

    return records


def run_one_time_setup():
    """GVA + cached NYT, synthetic Agent 1, Agent 2 once, stats once, RAG once."""
    print(f"=== Preflight Census: {STATE_A} ===", flush=True)
    if get_state_demographics(STATE_A) is None:
        print(f"ERROR: Census lookup failed for {STATE_A}.", flush=True)
        sys.exit(1)

    all_events, _ = build_gva_events_for_states([STATE_A, STATE_B], max_articles=0)
    print(f"Loaded {len(all_events)} GVA events for {STATE_A}/{STATE_B}.", flush=True)

    validated_articles = _synthetic_validated_from_gva_events(all_events)
    print(f"Synthetic validated rows: {len(validated_articles)}", flush=True)

    rag_conn = _load_rag_conn_like_app()
    total_tokens_used = {"prompt": 0, "completion": 0}

    state_summary = agent2_build_state_summary(
        validated_articles=validated_articles,
        all_events=all_events,
        state_a=STATE_A,
        state_b=STATE_B,
        total_tokens_used=total_tokens_used,
    )
    stats_markdown, _debug = compute_state_comparison_stats(state_summary)

    # Only import rag_setup when RAG connected. Importing rag_setup loads sentence_transformers/torch;
    # if that stack is broken, _load_rag_conn_like_app returns None — avoid a second import crash.
    rag_context = ""
    if rag_conn is not None:
        from rag_setup import retrieve_context  # noqa: WPS433

        rag_query = (
            f"shooting coverage patterns demographics income race "
            f"{STATE_A} {STATE_B} media reporting disparities"
        )
        rag_context = retrieve_context(
            rag_conn,
            rag_query,
            top_k=5,
            min_score=RAG_MIN_SIMILARITY,
            allowed_urls=agent1_relevant_urls(validated_articles),
            per_state_fallback_codes=[STATE_A, STATE_B],
        )
        try:
            rag_conn.close()
        except Exception:
            pass
    else:
        print(
            "=== RAG skipped (no DB or embedding stack unavailable); Agent 3 runs on stats only. ===",
            flush=True,
        )

    source_payload = {
        "states": {"state_a": STATE_A, "state_b": STATE_B},
        "stats_markdown": stats_markdown,
        "structured": _structured_stats(state_summary),
    }

    return stats_markdown, rag_context, source_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate NV vs LA reports (OpenAI / Ollama Cloud)")
    parser.add_argument("--n-runs", type=int, default=2, help="Reports per backend (default 2)")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Add to existing generated_reports_nv_la.json; run_id continues per backend (default: overwrite file)",
    )
    parser.add_argument(
        "--backend",
        choices=("openai", "ollama", "both"),
        default="both",
        help="openai, ollama, or both (default: both)",
    )
    args = parser.parse_args()
    ollama_model = os.getenv("OLLAMA_CLOUD_MODEL", "").strip() or None

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    stats_markdown, rag_context, source_payload = run_one_time_setup()

    with open(SOURCE_STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(source_payload, f, indent=2, ensure_ascii=False)
    print(f"Wrote {SOURCE_STATS_JSON}", flush=True)

    all_records: list[dict] = []
    if args.append and GENERATED_JSON.is_file():
        with open(GENERATED_JSON, encoding="utf-8") as f:
            all_records = json.load(f)
        if not isinstance(all_records, list):
            all_records = []
        print(f"=== Appending to existing file ({len(all_records)} record(s)) ===", flush=True)

    max_run_by: defaultdict[str, int] = defaultdict(int)
    for r in all_records:
        m = r.get("model")
        if m in ("openai", "ollama"):
            try:
                max_run_by[m] = max(max_run_by[m], int(r.get("run_id", 0)))
            except (TypeError, ValueError):
                pass

    backends: list[str] = []
    if args.backend == "both":
        backends = ["openai", "ollama"]
    else:
        backends = [args.backend]

    for b in backends:
        if b == "ollama" and not ollama_model:
            print("ERROR: Set OLLAMA_CLOUD_MODEL for Ollama Cloud.", flush=True)
            sys.exit(1)
        start_id = max_run_by[b] + 1
        print(
            f"=== Generating {args.n_runs} report(s) with backend={b} (run_id {start_id}..{start_id + args.n_runs - 1}) ===",
            flush=True,
        )
        all_records.extend(
            generate_reports(
                n_runs=args.n_runs,
                model=b,
                stats_markdown=stats_markdown,
                rag_context=rag_context,
                ollama_model=ollama_model,
                start_run_id=start_id,
            )
        )

    with open(GENERATED_JSON, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(all_records)} record(s) to {GENERATED_JSON}", flush=True)


if __name__ == "__main__":
    main()
