# lab_multi_agent.py
# Multi-agent pipeline: Relevance Validator (parallel), Coverage Analyst, Report Writer.
# Uses HOMEWORK_1 NYT cache + GVA; Ollama for all agents. Test states: Ohio, Louisiana.

# 0. SETUP ###################################

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
import yaml

# Add HOMEWORK_1 so we can import HW1_* when run from LABS/prompt_design/
_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent.parent
_hw1_dir = _repo_root / "HOMEWORK_1"
if str(_hw1_dir) not in sys.path:
    sys.path.insert(0, str(_hw1_dir))

from HW1_nyt_cache import load_or_build_2025_cache
from HW1_state_analysis import (
    _assign_articles_to_events,
    _article_pub_date,
    load_gva_2025,
    run_state_analysis,
)

from functions import agent_run

# 1. CONFIGURATION ###################################

MODEL = "smollm2:1.7b"
STATE_A = "Ohio"
STATE_B = "Louisiana"
PORT = 11434
OLLAMA_HOST = f"http://localhost:{PORT}"

# 2. LOAD RULES FROM YAML ###################################

_rules_path = _script_dir / "lab_rules.yaml"
with open(_rules_path, "r", encoding="utf-8") as f:
    _rules_data = yaml.safe_load(f)

# Match 04_rules.yaml structure: rules.rules.<section>
_rules = _rules_data["rules"]
rules_relevance = _rules["relevance_validation"][0]
rules_coverage = _rules["coverage_analysis"][0]
rules_report = _rules["report_writing"][0]


def format_rules_for_prompt(ruleset):
    """Format a ruleset (dict with name, description, guidance) for the agent's system prompt."""
    return f"{ruleset['name']}\n{ruleset['description']}\n\n{ruleset['guidance']}"


# 3. OLLAMA REQUEST HELPERS ###################################

def get_request(content, prompt, model):
    """Build URL + request body for a local Ollama chat call."""
    url = f"{OLLAMA_HOST}/api/chat"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        "stream": False,
    }
    return url, body


def req_perform(content, prompt, model):
    """Send one POST request and return assistant text."""
    url, body = get_request(content=content, prompt=prompt, model=model)
    response = requests.post(url, json=body, timeout=120)
    response.raise_for_status()
    return response.json()["message"]["content"]


# 4. DATA PREPARATION ###################################

def _format_task_for_validator(task):
    """Build user message for Agent 1 from (article, city, date_str)."""
    article, city, date_str = task
    headline = (article.get("headline") or {}).get("main") or ""
    abstract = article.get("abstract") or ""
    return (
        f"Headline: {headline}\n\nAbstract: {abstract}\n\n"
        f"Matched shooting event: city={city}, date={date_str}"
    )


def _parse_relevance_response(response_text):
    """Defensive parse of Agent 1 JSON output. Returns dict with 'relevant' and 'reason'."""
    text = (response_text or "").strip()
    # Try direct parse
    try:
        out = json.loads(text)
        if isinstance(out, dict) and "relevant" in out:
            return {"relevant": bool(out["relevant"]), "reason": out.get("reason", "")}
    except json.JSONDecodeError:
        pass
    # Strip markdown code blocks
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                out = json.loads(m.group(1))
                return {"relevant": bool(out.get("relevant", False)), "reason": out.get("reason", "")}
            except json.JSONDecodeError:
                pass
    # Regex fallback for {"relevant": true/false, ...}
    m = re.search(r'"relevant"\s*:\s*(true|false)', text, re.IGNORECASE)
    if m:
        return {"relevant": m.group(1).lower() == "true", "reason": text[:200]}
    return {"relevant": False, "reason": "Could not parse response"}


def main():
    # Optional: check Ollama is running
    try:
        requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        print("Cannot connect to Ollama at localhost:11434. Start Ollama (e.g. ollama serve) and try again.")
        raise SystemExit(1) from e

    # Load cache and GVA; restrict GVA to cache date range
    print("Loading cache and GVA...")
    cache = load_or_build_2025_cache()
    gva = load_gva_2025()
    if gva.empty or not cache:
        print("No GVA 2025 data or empty cache. Exiting.")
        return
    cache_dates = [_article_pub_date(a) for a in cache if _article_pub_date(a) is not None]
    if not cache_dates:
        print("Cache has no valid dates. Exiting.")
        return
    cache_start = min(cache_dates)
    cache_end = max(cache_dates)
    gva["date_fixed"] = pd.to_datetime(gva["date_fixed"])
    gva = gva[(gva["date_fixed"].dt.date >= cache_start) & (gva["date_fixed"].dt.date <= cache_end)]
    assigned = _assign_articles_to_events(gva, cache)

    # Build tasks for Agent 1: (article, city, date_str) for Ohio and Louisiana only
    tasks = []
    for event_key, article_list in assigned.items():
        state, city, date_str, _ = event_key
        if state not in (STATE_A, STATE_B):
            continue
        for art in article_list:
            tasks.append((art, city, date_str))

    if not tasks:
        print("No article-event pairs for Ohio/Louisiana. Exiting.")
        return

    print(f"Agent 1: {len(tasks)} validation tasks (Ohio + Louisiana).")

    # ----- Agent 1: Relevance Validator (parallel) -----
    role1 = "You determine whether a news article actually covers a specific mass shooting event (city and date)."
    system_prompt_1 = f"{role1}\n\n{format_rules_for_prompt(rules_relevance)}"

    start = time.time()
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        responses = list(
            executor.map(
                lambda t: req_perform(_format_task_for_validator(t), system_prompt_1, MODEL),
                tasks,
            )
        )
    elapsed = time.time() - start
    print(f"Agent 1 completed in {elapsed:.2f} s for {len(tasks)} requests.")

    parsed = [_parse_relevance_response(r) for r in responses]
    validated_articles = [tasks[i][0] for i in range(len(tasks)) if parsed[i].get("relevant") is True]
    print(f"Agent 1: {len(validated_articles)} articles marked relevant (of {len(tasks)}).")
    print("\n=== Agent 1 results (all article checks) ===")
    for i in range(len(tasks)):
        art, city, date_str = tasks[i]
        headline = (art.get("headline") or {}).get("main") or "(no headline)"
        headline_short = (headline[:60] + "...") if len(headline) > 60 else headline
        p = parsed[i]
        rel = p.get("relevant", False)
        reason = p.get("reason", "")
        print(f"  [{i+1}] {city} {date_str} | relevant={rel} | {headline_short}")
        print(f"      reason: {reason}")

    # ----- Agent 2: Coverage Analyst (sequential) -----
    # Recompute stats using only validated articles
    result_analysis = run_state_analysis(STATE_A, STATE_B, cache_articles=validated_articles)
    if result_analysis.get("error"):
        print("Agent 2 input error:", result_analysis["error"])
        analysis_text = f"Validated articles: {len(validated_articles)}. Error: {result_analysis['error']}"
    else:
        sa = result_analysis["state_a"]
        sb = result_analysis["state_b"]
        analysis_text = (
            f"Validated articles count: {len(validated_articles)}.\n\n"
            f"State A ({STATE_A}): total_shootings={sa.get('total_shootings')}, "
            f"reported_count={sa.get('reported_count')}, pct_reported={sa.get('pct_reported')}%, "
            f"coverage_mean_days={sa.get('coverage_mean_days')}, coverage_median_days={sa.get('coverage_median_days')}.\n"
            f"State B ({STATE_B}): total_shootings={sb.get('total_shootings')}, "
            f"reported_count={sb.get('reported_count')}, pct_reported={sb.get('pct_reported')}%, "
            f"coverage_mean_days={sb.get('coverage_mean_days')}, coverage_median_days={sb.get('coverage_median_days')}.\n\n"
            f"Reported events (sample) Ohio: {[e.get('label') for e in (sa.get('reported_events') or [])[:5]]}.\n"
            f"Reported events (sample) Louisiana: {[e.get('label') for e in (sb.get('reported_events') or [])[:5]]}."
        )

    role2 = "Analyze NYT coverage patterns, gaps, and differences between the two states using the validated article list and stats above."
    system_prompt_2 = f"{role2}\n\n{format_rules_for_prompt(rules_coverage)}"
    result2 = agent_run(role=system_prompt_2, task=analysis_text, model=MODEL)
    print("\n=== Agent 2 Output (Coverage Analyst) ===")
    print(result2)

    # ----- Agent 3: Report Writer (sequential) -----
    role3 = "Write a press-release-style report (300-400 words) from the analyst's table and findings."
    system_prompt_3 = f"{role3}\n\n{format_rules_for_prompt(rules_report)}"
    result3 = agent_run(role=system_prompt_3, task=result2, model=MODEL)
    print("\n=== Agent 3 Output (Report Writer) ===")
    print(result3)


if __name__ == "__main__":
    main()
