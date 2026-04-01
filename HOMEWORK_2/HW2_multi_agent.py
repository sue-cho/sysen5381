#!/usr/bin/env python3
"""
HW2_multi_agent.py

Command-line multi-agent pipeline (no Shiny integration yet).
Uses hardcoded test data and makes network calls to:
- OpenAI API (Agents 1-4)
- Census API for ACS5 demographics lookups (Agent 2 tool)

Install:
  pip install requests pandas pyyaml beautifulsoup4 openai

Run:
  export OPENAI_API_KEY='your-key-here'
  python HW2_multi_agent.py                    # hardcoded test data + LLM Agent 1
  python HW2_multi_agent.py --real-cache         # OH/LA default; same pipeline inputs as HW2_app.py Report tab
"""

from __future__ import annotations

import concurrent.futures
import argparse
import json
import os
import re
import statistics
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup  # noqa: F401  (installed dependency; not required for current pipeline)


# 0. IMPORTS AND SETUP
HOMEWORK_2_DIR = os.path.dirname(os.path.abspath(__file__))


def homework1_dir() -> str:
    """
    Development: ../HOMEWORK_1 next to HOMEWORK_2.
    Posit / packed deploy: rsync copies HOMEWORK_1 into HOMEWORK_2/HOMEWORK_1/.
    """
    h2 = Path(HOMEWORK_2_DIR).resolve()
    nested = h2 / "HOMEWORK_1"
    if nested.is_dir():
        return str(nested)
    return str(h2.parent / "HOMEWORK_1")

# OpenAI config (Agents 1-4)
OPENAI_MODEL = "gpt-4o-mini"
# GVA incident with this many matched NYT URLs (unique) is flagged for Agent 3/4 narrative.
HIGH_PROFILE_ARTICLE_THRESHOLD = 5
# Skip low-similarity RAG chunks. all-MiniLM-L6-v2 cosine scores for broad queries are often ~0.35–0.55.
# Agent 3 RAG only includes URLs Agent 1 already marked relevant=true (see retrieve_context allowed_urls).
RAG_MIN_SIMILARITY = 0.35
# NYT pub date must fall in [incident date, incident + N days] for GVA match (Agent 1 + RAG).
GVA_ARTICLE_MATCH_WINDOW_DAYS = 90
_openai_client: Any = None
total_tokens_used: Dict[str, int] = {"prompt": 0, "completion": 0}


def get_openai_client() -> Any:
    """
    Lazily create the OpenAI client so the script can run the Census preflight
    before requiring OPENAI_API_KEY. Import is deferred so HW2_app can import
    data helpers (e.g. build_gva_events_for_states) without installing openai.
    """
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    try:
        from openai import OpenAI
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "The openai package is required for the multi-agent pipeline. "
            "Install with: pip install openai"
        ) from e
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set.\n"
            "Run: export OPENAI_API_KEY='your-key-here'"
        )
    _openai_client = OpenAI(api_key=api_key)
    return _openai_client


STATE_FIPS: Dict[str, str] = {
    # 50 states + DC excluded (not needed for state abbreviations)
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
}

STATE_NAME_TO_ABBR: Dict[str, str] = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}


# 1. LOAD YAML RULES
RULES_PATH = os.path.join(HOMEWORK_2_DIR, "04_rules.yaml")


def load_rules(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_rules_for_prompt(rules_section: Any) -> str:
    """
    Convert a YAML rule section into a single system prompt string.
    We pick the first rule item (since HW2 YAML defines one per agent).
    """
    if not rules_section:
        return ""
    first = rules_section[0]
    guidance = first.get("guidance", "")
    return str(guidance).strip()


RULES = load_rules(RULES_PATH)


# 2. HELPER FUNCTIONS
def safe_parse_json(text: str) -> Optional[Any]:
    """
    Defensive JSON parsing for LLM outputs.
    Returns parsed JSON or None.
    """
    if text is None:
        return None
    raw = str(text).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    # Regex fallback: extract the first {...} block.
    # This is intentionally simple for robustness given small test data.
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw[start : end + 1]
            return json.loads(candidate)
    except Exception:
        return None
    return None


def req_perform(
    content: str,
    prompt: str,
    model: str = OPENAI_MODEL,
    total_tokens_used: Optional[Dict[str, int]] = None,
    token_lock: Optional[threading.Lock] = None,
) -> str:
    """
    Compatibility wrapper used by Agent 1.
    Uses OpenAI API to preserve the same system/user message shape.
    """
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        max_tokens=500,
    )

    if total_tokens_used is not None and response.usage:
        prompt_tokens = int(response.usage.prompt_tokens or 0)
        completion_tokens = int(response.usage.completion_tokens or 0)
        if token_lock is not None:
            with token_lock:
                total_tokens_used["prompt"] += prompt_tokens
                total_tokens_used["completion"] += completion_tokens
        else:
            total_tokens_used["prompt"] += prompt_tokens
            total_tokens_used["completion"] += completion_tokens

    return response.choices[0].message.content


def req_perform_openai(
    content: str, prompt: str, model: str = OPENAI_MODEL, total_tokens_used: Optional[Dict[str, int]] = None
) -> str:
    """
    Single OpenAI API call matching the structure you requested.
    Optionally updates total_tokens_used from response.usage.
    """
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        max_tokens=1000,
    )

    if total_tokens_used is not None and response.usage:
        total_tokens_used["prompt"] += int(response.usage.prompt_tokens or 0)
        total_tokens_used["completion"] += int(response.usage.completion_tokens or 0)

    return response.choices[0].message.content


_state_census_cache: Dict[str, Optional[Dict[str, Any]]] = {}


def get_state_demographics(state_abbr: str) -> Optional[Dict[str, Any]]:
    """
    Fetches state-level ACS5 demographics for a given state.
    Returns None on any failure.
    """
    if not state_abbr:
        return None
    state_code = state_abbr.strip().upper()
    fips = STATE_FIPS.get(state_code)
    if not fips:
        return None

    if state_code in _state_census_cache:
        return _state_census_cache[state_code]

    url = "https://api.census.gov/data/2023/acs/acs5"
    params = {
        "get": "B19013_001E,B01003_001E,B02001_002E",
        "for": f"state:{fips}",
    }

    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or len(data) < 2:
            _state_census_cache[state_code] = None
            return None

        row = data[1]
        income_raw = row[0]
        pop_raw = row[1]
        white_raw = row[2]

        income_val = float(income_raw) if income_raw not in (None, "", "null") else None
        pop_val = float(pop_raw) if pop_raw not in (None, "", "null") else None
        white_val = float(white_raw) if white_raw not in (None, "", "null") else None
        if income_val is None or pop_val in (None, 0) or white_val is None:
            _state_census_cache[state_code] = None
            return None

        out = {
            "state": state_code,
            "median_household_income": income_val,
            "population": int(pop_val),
            "pct_white": (white_val / pop_val) * 100.0,
            "acs_dataset": "acs5",
            "acs_year": 2023,
        }
        _state_census_cache[state_code] = out
        return out
    except Exception as e:
        print(f"[CENSUS_ERROR] state={state_code!r} err={e}", file=sys.stderr, flush=True)
        _state_census_cache[state_code] = None
        return None


# 3. TEST DATA
test_articles: List[Dict[str, Any]] = [
    {
        "url": "https://nytimes.com/example1",
        "headline": "3 Dead in Chicago Shooting",
        "abstract": "A shooting in Chicago's South Side left 3 dead Saturday.",
        "event": {"city": "Chicago", "state": "IL", "date": "2025-03-15", "victims": 3},
    },
    {
        "url": "https://nytimes.com/example2",
        "headline": "Bulls Win Fourth Straight Game",
        "abstract": "The Chicago Bulls defeated the Knicks 112-98 last night.",
        "event": {"city": "Chicago", "state": "IL", "date": "2025-03-15", "victims": 3},
    },
    {
        "url": "https://nytimes.com/example3",
        "headline": "Budget Hearing in Jackson Draws Protest",
        "abstract": "State officials discussed municipal budget priorities in Jackson, Mississippi.",
        "event": {"city": "Jackson", "state": "MS", "date": "2025-02-20", "victims": 4},
    },
]

test_uncovered_events: List[Dict[str, Any]] = [
    {"city": "Springfield", "state": "IL", "date": "2025-04-02", "victims": 2},
    {"city": "Jackson", "state": "MS", "date": "2025-02-20", "victims": 4},
    {"city": "Gulfport", "state": "MS", "date": "2025-02-28", "victims": 3},
]

all_events: List[Dict[str, Any]] = [
    {"city": "Chicago", "state": "IL", "date": "2025-03-15", "victims": 3},
    {"city": "Springfield", "state": "IL", "date": "2025-04-02", "victims": 2},
    {"city": "Jackson", "state": "MS", "date": "2025-02-20", "victims": 4},
    {"city": "Gulfport", "state": "MS", "date": "2025-02-28", "victims": 3},
]


def _victims_from_gva_row(row: Any) -> int:
    """
    Best-effort victim count from GVA row.
    """
    for col in ("killed", "n_killed", "victims"):
        val = row.get(col) if hasattr(row, "get") else None
        if isinstance(val, (int, float)):
            return int(val)
        try:
            if val is not None and str(val).strip() != "":
                return int(float(val))
        except Exception:
            continue
    return 0


def _parse_article_pub_date(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _build_gva_events_and_candidates(
    selected_states: Set[str],
    max_articles: int = 120,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Shared loader: GVA 2025 events for selected state abbreviations + optional Agent 1 URL cap.
    Each event includes is_outlier when ≥ HIGH_PROFILE_ARTICLE_THRESHOLD unique matched URLs.
    """
    home1_dir = homework1_dir()
    cache_path = os.path.join(home1_dir, "nyt_2025_shootings_cache.json")
    gva_path = os.path.join(home1_dir, "gva_mass_shootings-2026-02-08.csv")

    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"Cache file not found: {cache_path}")
    if not os.path.exists(gva_path):
        raise FileNotFoundError(f"GVA CSV not found: {gva_path}")

    gva = pd.read_csv(gva_path)

    def _to_state_abbr(value: Any) -> str:
        raw = str(value or "").strip().upper()
        if len(raw) == 2 and raw in STATE_FIPS:
            return raw
        return STATE_NAME_TO_ABBR.get(raw, "")

    gva["state_abbr"] = gva["state"].map(_to_state_abbr)
    if "year" in gva.columns:
        gva["year"] = pd.to_numeric(gva["year"], errors="coerce")
        gva = gva[gva["year"] == 2025]
    gva["date_fixed"] = pd.to_datetime(gva["date_fixed"], errors="coerce")
    gva_filtered = gva[
        (gva["state_abbr"].isin(selected_states)) & (gva["date_fixed"].notna())
    ].copy()

    print(f"GVA events found for {sorted(selected_states)}: {len(gva_filtered)}", flush=True)
    if len(gva_filtered) == 0:
        print("WARNING: No GVA events found. Check state abbreviations and year.", flush=True)
        return [], []

    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)

    parsed_articles: List[Dict[str, Any]] = []
    for article in cache:
        pub_dt = _parse_article_pub_date(article.get("pub_date"))
        if pub_dt is None:
            continue
        parsed_articles.append(
            {
                "pub_date": pub_dt,
                "url": article.get("web_url", ""),
                "headline": (article.get("headline") or {}).get("main", "") or "",
                "abstract": article.get("abstract", "") or "",
                "snippet": article.get("snippet", "") or "",
            }
        )
    print(f"NYT cache articles parsed: {len(parsed_articles)}", flush=True)

    all_events_real: List[Dict[str, Any]] = []
    articles_for_agent1: List[Dict[str, Any]] = []
    seen_urls: set = set()
    reached_cap = False

    for _, row in gva_filtered.iterrows():
        city = str(row.get("city_or_county") or "").strip()
        state = str(row.get("state_abbr") or "").strip().upper()
        if not city or not state:
            continue
        incident_dt = row["date_fixed"].to_pydatetime()
        incident_date = incident_dt.date()
        date_str = incident_dt.strftime("%Y-%m-%d")
        killed = int(pd.to_numeric(row.get("killed"), errors="coerce") or 0)
        injured = int(pd.to_numeric(row.get("injured"), errors="coerce") or 0)
        victims = killed + injured

        event = {
            "city": city,
            "state": state,
            "date": date_str,
            "victims": victims,
            "killed": killed,
            "injured": injured,
        }

        city_low = city.lower().strip()
        city_short = city_low.replace(" county", "").strip()
        matched_urls: List[str] = []
        matched_dates: List[datetime] = []

        for article in parsed_articles:
            pub_dt = article["pub_date"]
            if pub_dt.date() < incident_date:
                continue
            if pub_dt.date() > (incident_date + timedelta(days=GVA_ARTICLE_MATCH_WINDOW_DAYS)):
                continue

            text = f"{article['headline']} {article['abstract']} {article['snippet']}".lower()
            if city_low not in text and city_short not in text:
                continue

            art_url = article.get("url") or ""
            if art_url:
                matched_urls.append(art_url)
                matched_dates.append(pub_dt)
                if (
                    max_articles > 0
                    and not reached_cap
                    and art_url not in seen_urls
                ):
                    seen_urls.add(art_url)
                    articles_for_agent1.append(
                        {
                            "url": art_url,
                            "headline": article["headline"],
                            "abstract": article["abstract"],
                            "event": {
                                "city": city,
                                "state": state,
                                "date": date_str,
                                "victims": victims,
                                "killed": killed,
                                "injured": injured,
                            },
                        }
                    )
                    if len(articles_for_agent1) >= max_articles:
                        reached_cap = True

        days_to_first = None
        if matched_dates:
            days_to_first = (min(matched_dates).date() - incident_date).days

        event["matched_article_urls"] = matched_urls
        event["days_to_first_article"] = days_to_first
        nuniq = len({str(u).strip() for u in matched_urls if u})
        event["is_outlier"] = nuniq >= HIGH_PROFILE_ARTICLE_THRESHOLD
        all_events_real.append(event)

    covered_count = sum(1 for e in all_events_real if e.get("matched_article_urls"))
    uncovered_count = len(all_events_real) - covered_count
    event_dates = [e.get("date") for e in all_events_real if e.get("date")]
    cache_dates = [a["pub_date"].strftime("%Y-%m-%d") for a in parsed_articles if a.get("pub_date") is not None]

    print(f"Total events loaded: {len(all_events_real)}", flush=True)
    print(f"Covered events: {covered_count}", flush=True)
    print(f"Uncovered events: {uncovered_count}", flush=True)
    print(f"Candidate articles for Agent 1: {len(articles_for_agent1)}", flush=True)
    if event_dates:
        print(f"GVA event date range: {min(event_dates)} to {max(event_dates)}", flush=True)
    if cache_dates:
        print(f"NYT cache date range: {min(cache_dates)} to {max(cache_dates)}", flush=True)

    if max_articles > 0 and len(articles_for_agent1) == 0:
        print("NOTE: Zero candidate articles found. This means the NYT", flush=True)
        print("did not cover any of these shooting events - a valid and", flush=True)
        print("meaningful finding. Pipeline will continue with all events", flush=True)
        print("marked as uncovered.", flush=True)
    elif max_articles > 0 and len(articles_for_agent1) < 5:
        print(f"NOTE: Only {len(articles_for_agent1)} candidate article(s) found.", flush=True)
        print("Low coverage is a valid finding, not a pipeline error.", flush=True)

    return all_events_real, articles_for_agent1


def build_real_cache_inputs(state_a: str, state_b: str, max_articles: int = 120) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Build all GVA events + Agent 1 candidate articles from real HW1 cache/GVA data.
    Returns (all_events_for_states, articles_for_agent1).
    """
    return _build_gva_events_and_candidates(
        {state_a.upper(), state_b.upper()},
        max_articles=max_articles,
    )


def build_gva_events_for_states(
    state_codes: List[str],
    max_articles: int = 0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Same matching rules as build_real_cache_inputs, for any list of state abbreviations.
    Use max_articles=0 to skip collecting Agent 1 candidates (faster for national aggregates).
    """
    sel = {s.strip().upper() for s in state_codes if s}
    return _build_gva_events_and_candidates(sel, max_articles=max_articles)


def _synthetic_validated_from_gva_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Same as HW2_app: Agent 2 keys coverage off Agent-1-shaped rows derived from GVA events
    that already have matched NYT URLs (no LLM Agent 1).
    """
    out: List[Dict[str, Any]] = []
    for ev in events:
        urls = ev.get("matched_article_urls") or []
        if not isinstance(urls, list) or not urls:
            continue
        u0 = str(urls[0]).strip()
        if not u0:
            continue
        out.append(
            {
                "relevant": True,
                "url": u0,
                "reason": "GVA/NYT cache match",
                "event": {
                    "city": ev.get("city"),
                    "state": str(ev.get("state", "")).strip().upper(),
                    "date": ev.get("date"),
                },
            }
        )
    return out


def _load_rag_conn_like_app() -> Any:
    """
    Same RAG index as HW2_app startup: full-state NYT cache embedding DB under HOMEWORK_2/data.
    Returns sqlite3.Connection or None on failure.
    """
    try:
        from rag_setup import setup_rag

        cache_path = Path(homework1_dir()) / "nyt_2025_shootings_cache.json"
        data_dir = Path(HOMEWORK_2_DIR) / "data"
        return setup_rag(
            cache_path=cache_path,
            states=list(STATE_NAME_TO_ABBR.values()),
            state_name_to_abbr=STATE_NAME_TO_ABBR,
            data_dir=data_dir,
            rebuild=False,
        )
    except Exception as exc:
        print(f"[CLI] RAG load skipped (optional): {exc}", flush=True)
        return None


# 4. AGENT 1 - PARALLEL VALIDATION
def agent1_validate_articles_parallel(
    articles: List[Dict[str, Any]],
    total_tokens_used: Optional[Dict[str, int]] = None,
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Returns (validated_articles, elapsed_seconds).
    validated_articles includes only the required JSON fields,
    then we merge event info in later stages in Python.
    """
    system_prompt = format_rules_for_prompt(RULES.get("rules", {}).get("relevance_validation"))

    start = time.time()
    validated: List[Dict[str, Any]] = []
    token_lock = threading.Lock()

    def one_article(article: Dict[str, Any]) -> Dict[str, Any]:
        event = article.get("event", {}) or {}
        content = (
            f"headline: {article.get('headline','')}\n\n"
            f"abstract: {article.get('abstract','')}\n\n"
            f"url: {article.get('url','')}\n\n"
            f"matched_event: city={event.get('city')}, state={event.get('state')}, "
            f"date={event.get('date')}, victims={event.get('victims')}"
        )

        raw_out = req_perform(
            content=content,
            prompt=system_prompt,
            model=OPENAI_MODEL,
            total_tokens_used=total_tokens_used,
            token_lock=token_lock,
        )
        parsed = safe_parse_json(raw_out)

        if not isinstance(parsed, dict):
            # Default to non-relevant when we can't parse.
            return {
                "url": article.get("url"),
                "relevant": False,
                "reason": "Could not parse model output",
                "event": event,
            }

        url = parsed.get("url", article.get("url"))
        relevant = bool(parsed.get("relevant", False))
        reason = parsed.get("reason", "No reason provided")
        if not isinstance(reason, str):
            reason = "Invalid reason provided"
        return {"url": url, "relevant": relevant, "reason": reason, "event": event}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(one_article, a) for a in articles]
        for fut in concurrent.futures.as_completed(futures):
            validated.append(fut.result())

    elapsed = time.time() - start
    return validated, elapsed


def agent1_relevant_urls(validated_articles: List[Dict[str, Any]]) -> Set[str]:
    """URLs Agent 1 marked relevant=true — only these may appear in RAG context for Agent 3."""
    out: Set[str] = set()
    for v in validated_articles:
        if not isinstance(v, dict):
            continue
        if v.get("relevant") is not True:
            continue
        u = str(v.get("url") or "").strip()
        if u:
            out.add(u)
    return out


# 5. AGENT 2 - DEMOGRAPHICS ENRICHMENT (state-level summary)
def agent2_build_state_summary(
    validated_articles: List[Dict[str, Any]],
    all_events: List[Dict[str, Any]],
    state_a: str,
    state_b: str,
    total_tokens_used: Dict[str, int],
) -> Dict[str, Any]:
    """
    Build deterministic per-state summary for the two selected states.
    """
    # Build covered event keys from Agent 1 relevant outputs.
    covered_keys: set = set()
    for v in validated_articles:
        if not isinstance(v, dict) or not v.get("relevant"):
            continue
        event = v.get("event", {}) or {}
        covered_keys.add(
            (
                str(event.get("city", "")).strip().lower(),
                str(event.get("state", "")).strip().upper(),
                str(event.get("date", "")).strip(),
            )
        )

    def build_state_entry(state_code: str) -> Dict[str, Any]:
        state_code = state_code.upper()
        state_events = [ev for ev in all_events if str(ev.get("state", "")).upper() == state_code]
        total_events = len(state_events)
        covered_events = 0
        covered_state_events: List[Dict[str, Any]] = []
        for ev in state_events:
            key = (
                str(ev.get("city", "")).strip().lower(),
                str(ev.get("state", "")).strip().upper(),
                str(ev.get("date", "")).strip(),
            )
            if key in covered_keys:
                covered_events += 1
                covered_state_events.append(ev)
        coverage_rate = (covered_events / total_events * 100.0) if total_events else 0.0

        days_values = [
            ev.get("days_to_first_article")
            for ev in covered_state_events
            if isinstance(ev.get("days_to_first_article"), (int, float))
        ]
        avg_days_to_first = statistics.mean(days_values) if days_values else None
        same_day_coverage_pct = (
            (sum(1 for d in days_values if float(d) == 0.0) / len(days_values) * 100.0) if days_values else None
        )

        return {
            "state": state_code,
            "total_events": total_events,
            "covered_events": covered_events,
            "coverage_rate": coverage_rate,
            "avg_days_to_first_article": avg_days_to_first,
            "same_day_coverage_pct": same_day_coverage_pct,
            "demographics": get_state_demographics(state_code),
        }

    def high_profile_events_from_gva() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for ev in all_events:
            urls = ev.get("matched_article_urls") or []
            if not isinstance(urls, list):
                continue
            n = len({str(u).strip() for u in urls if u})
            if n >= HIGH_PROFILE_ARTICLE_THRESHOLD:
                out.append(
                    {
                        "city": ev.get("city"),
                        "state": str(ev.get("state", "")).strip().upper(),
                        "date": ev.get("date"),
                        "matched_article_count": n,
                    }
                )
        return out

    return {
        "state_a": build_state_entry(state_a),
        "state_b": build_state_entry(state_b),
        "high_profile_events": high_profile_events_from_gva(),
    }


# 6. AGENT 3 - PATTERN ANALYSIS (state-level precomputed comparisons)
def compute_state_comparison_stats(state_summary: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    state_a_data = state_summary["state_a"]
    state_b_data = state_summary["state_b"]
    state_a = state_a_data["state"]
    state_b = state_b_data["state"]

    def safe_num(x: Any) -> float:
        return float(x) if isinstance(x, (int, float)) else 0.0

    state_a_income = safe_num((state_a_data.get("demographics") or {}).get("median_household_income"))
    state_b_income = safe_num((state_b_data.get("demographics") or {}).get("median_household_income"))
    state_a_cov = safe_num(state_a_data.get("coverage_rate"))
    state_b_cov = safe_num(state_b_data.get("coverage_rate"))
    state_a_avg_days = state_a_data.get("avg_days_to_first_article")
    state_b_avg_days = state_b_data.get("avg_days_to_first_article")
    state_a_same_day = state_a_data.get("same_day_coverage_pct")
    state_b_same_day = state_b_data.get("same_day_coverage_pct")

    income_diff = state_a_income - state_b_income
    coverage_rate_diff = state_a_cov - state_b_cov
    higher_coverage_state = state_a if state_a_cov >= state_b_cov else state_b
    higher_income_state = state_a if state_a_income >= state_b_income else state_b

    if higher_income_state == higher_coverage_state:
        correlation_flag = "positive: higher income state also has higher coverage rate"
    else:
        correlation_flag = "negative: higher income state has LOWER coverage rate - notable anomaly"

    if state_a_avg_days is not None and state_b_avg_days is not None:
        faster_state = state_a if float(state_a_avg_days) < float(state_b_avg_days) else state_b
        speed_diff = abs(float(state_a_avg_days) - float(state_b_avg_days))
        speed_note = f"{faster_state} covered shootings {speed_diff:.1f} days faster on average"
    elif state_a_avg_days is None and state_b_avg_days is None:
        speed_note = "Neither state had covered events - speed comparison unavailable"
    elif state_a_avg_days is None:
        speed_note = f"Only {state_b} had covered events (avg {float(state_b_avg_days):.1f} days)"
    else:
        speed_note = f"Only {state_a} had covered events (avg {float(state_a_avg_days):.1f} days)"

    shootings_per_100_gap = abs(coverage_rate_diff)
    coverage_diff_text = (
        f"{higher_coverage_state} has {shootings_per_100_gap:.2f} more shootings covered per 100 events "
        f"than {state_b if higher_coverage_state == state_a else state_a}."
    )

    def fmt_currency(v: Any) -> str:
        if not isinstance(v, (int, float)) or v == 0:
            return "—"
        return f"${v:,.0f}"

    def fmt_pct(v: Any) -> str:
        if not isinstance(v, (int, float)):
            return "—"
        return f"{v:.2f}%"

    def fmt_int(v: Any) -> str:
        if not isinstance(v, (int, float)):
            return "—"
        return f"{int(v):,}"

    def fmt_days(v: Any) -> str:
        if not isinstance(v, (int, float)):
            return "N/A"
        return f"{float(v):.1f}"

    def fmt_same_day(v: Any) -> str:
        if not isinstance(v, (int, float)):
            return "N/A"
        return f"{float(v):.1f}%"

    table = (
        f"| Metric | {state_a} | {state_b} |\n"
        "|--------|-----------|-----------|\n"
        f"| Total Shootings | {state_a_data.get('total_events', 0)} | {state_b_data.get('total_events', 0)} |\n"
        f"| NYT Covered | {state_a_data.get('covered_events', 0)} | {state_b_data.get('covered_events', 0)} |\n"
        f"| Coverage Rate | {fmt_pct(state_a_cov)} | {fmt_pct(state_b_cov)} |\n"
        f"| Avg Days to First Article | {fmt_days(state_a_avg_days)} | {fmt_days(state_b_avg_days)} |\n"
        f"| Same-Day Coverage | {fmt_same_day(state_a_same_day)} | {fmt_same_day(state_b_same_day)} |\n"
        f"| Median Household Income | {fmt_currency(state_a_income)} | {fmt_currency(state_b_income)} |\n"
        f"| % White Population | {fmt_pct((state_a_data.get('demographics') or {}).get('pct_white'))} | {fmt_pct((state_b_data.get('demographics') or {}).get('pct_white'))} |\n"
        f"| State Population | {fmt_int((state_a_data.get('demographics') or {}).get('population'))} | {fmt_int((state_b_data.get('demographics') or {}).get('population'))} |\n"
    )

    high_profile = state_summary.get("high_profile_events") or []
    if high_profile:
        outlier_lines = [
            "OUTLIER_EVENTS (high-profile: 5+ matched NYT articles per GVA incident):",
        ]
        for e in high_profile:
            c = e.get("city") or "?"
            st = e.get("state") or "?"
            d = e.get("date") or "?"
            n = int(e.get("matched_article_count") or 0)
            outlier_lines.append(f"- {c}, {st}, {d}: {n} articles")
        outlier_block = "\n".join(outlier_lines)
    else:
        outlier_block = "OUTLIER_EVENTS: none (no incident with 5+ matched articles)."

    stats_text = (
        "PRECOMPUTED_2_STATE_STATS (do not recalculate)\n\n"
        + table
        + "\n"
        + f"Correlation flag: {correlation_flag}\n"
        + f"Coverage rate difference: {state_a} minus {state_b} = {coverage_rate_diff:.2f} percentage points.\n"
        + f"Income difference: {state_a} minus {state_b} = {income_diff:,.0f} dollars.\n"
        + f"Human interpretation: {coverage_diff_text}\n"
        + f"Coverage speed: {speed_note}\n"
        + f"Within-state note: {state_a} coverage rate is {state_a_cov:.2f}%; {state_b} coverage rate is {state_b_cov:.2f}%.\n"
        + "\n"
        + outlier_block
        + "\n"
    )
    debug = {
        "income_diff": income_diff,
        "coverage_rate_diff": coverage_rate_diff,
        "higher_coverage_state": higher_coverage_state,
        "higher_income_state": higher_income_state,
        "correlation_flag": correlation_flag,
        "speed_note": speed_note,
        "state_a_avg_days": state_a_avg_days,
        "state_b_avg_days": state_b_avg_days,
        "state_a_same_day": state_a_same_day,
        "state_b_same_day": state_b_same_day,
        "high_profile_events": high_profile,
    }
    return stats_text, debug


def extract_bullets(agent3_text: str) -> List[str]:
    """
    Extract just the bullet point lines from Agent 3 output.
    Returns list of strings, one per bullet.
    """
    lines = str(agent3_text or "").split("\n")
    bullets: List[str] = []
    for line in lines:
        line = line.strip()
        if line.startswith("*") or line.startswith("-"):
            bullets.append(line.lstrip("*- ").strip())
    return bullets


def agent3_format_bullets(
    stats_markdown: str,
    total_tokens_used: Dict[str, int],
    rag_context: str = "",
) -> str:
    """
    Formatter-only: Agent 3 outputs 3–5 bullet points only.
    It receives a markdown stats block and must not recalculate numbers.
    """
    yaml_prompt = format_rules_for_prompt(RULES.get("rules", {}).get("pattern_analysis"))
    # Ensure the constraint sentence is present verbatim in system prompt.
    system_prompt = (
        yaml_prompt
        + "\n\n"
        + "You are formatting pre-computed statistics into a markdown table. "
        "Do not recalculate or modify any numbers. "
        "Format exactly what is given to you."
        + "\n\n"
        + "Always refer to states by name, never as 'state_a' or 'state_b'. "
        "Your bullets should address: which state had more coverage, whether income correlates with coverage, "
        "and what the coverage gap means in human terms (X more shootings covered per 100 events). "
        "Note that data comes from a single national newspaper - avoid implying comprehensive coverage analysis."
        + "\n\n"
        + "Your output must be ONLY 3-5 bullet points (no tables)."
    )

    user_content = stats_markdown
    if rag_context:
        user_content = (
            "RETRIEVED_CONTEXT (NYT URLs already validated relevant=true by Agent 1; background only; "
            "do not override precomputed stats numbers):\n"
            f"{rag_context}\n\n"
            "PRECOMPUTED_STATS_INPUT:\n"
            f"{stats_markdown}"
        )
    raw_out = req_perform_openai(
        content=user_content, prompt=system_prompt, model=OPENAI_MODEL, total_tokens_used=total_tokens_used
    )

    # Accept as plain text; if it accidentally includes JSON, try extracting bullets.
    # We keep defensive parsing minimal since bullets are human-readable.
    return str(raw_out).strip()


# 7. AGENT 4 - REPORT WRITING
def agent4_write_report(
    stats_markdown: str,
    agent3_bullets: str,
    total_tokens_used: Dict[str, int],
) -> str:
    system_prompt = format_rules_for_prompt(RULES.get("rules", {}).get("report_writing"))
    system_prompt += "\n\nUse only the provided numbers and statements from the stats block."

    user_content = (
        "STATS_TABLE_AND_CONTEXT:\n"
        f"{stats_markdown}\n\n"
        "AGENT3_BULLETS:\n"
        f"{agent3_bullets}\n"
    )

    raw_out = req_perform_openai(
        content=user_content, prompt=system_prompt, model=OPENAI_MODEL, total_tokens_used=total_tokens_used
    )
    return str(raw_out).strip()


# 7.5 Wrapper Function
def run_agent_pipeline(
    validated_articles: List[Dict[str, Any]],
    all_events: List[Dict[str, Any]],
    state_a: str,
    state_b: str,
    rag_conn=None,
) -> Dict[str, Any]:
    """
    Wraps Agents 2, 3, and 4 into a single callable.
    Returns:
      {"agent2": ..., "agent3": ..., "agent4": ..., "tokens": total_tokens_used}
    """
    global total_tokens_used
    total_tokens_used = {"prompt": 0, "completion": 0}
    created_local_rag_conn = False
    from rag_setup import retrieve_context, setup_rag

    # Agent 2
    state_summary = agent2_build_state_summary(
        validated_articles=validated_articles,
        all_events=all_events,
        state_a=state_a,
        state_b=state_b,
        total_tokens_used=total_tokens_used,
    )
    print("\n=== AGENT 2 OUTPUT (state-level summary JSON) ===")
    print(json.dumps(state_summary, indent=2))

    if rag_conn is None:
        cache_path = Path(homework1_dir()) / "nyt_2025_shootings_cache.json"
        data_dir = Path(os.path.join(HOMEWORK_2_DIR, "data"))
        # Convert to title-case keys expected by setup_rag examples.
        name_map = {k.title(): v for k, v in STATE_NAME_TO_ABBR.items()}
        rag_conn = setup_rag(
            cache_path=cache_path,
            states=[state_a, state_b],
            state_name_to_abbr=name_map,
            data_dir=data_dir,
            rebuild=False,
            strict_event_keywords=True,
        )
        created_local_rag_conn = True

    rag_query_3 = (
        f"shooting coverage patterns demographics income race "
        f"{state_a} {state_b} media reporting disparities"
    )
    rag_context_3 = (
        retrieve_context(
            rag_conn,
            rag_query_3,
            top_k=5,
            min_score=RAG_MIN_SIMILARITY,
            allowed_urls=agent1_relevant_urls(validated_articles),
            per_state_fallback_codes=[state_a, state_b],
        )
        if rag_conn is not None
        else ""
    )

    # Agent 3 (stats computed in Python + bullets only from OpenAI)
    stats_markdown, debug = compute_state_comparison_stats(state_summary)
    agent3_bullets = agent3_format_bullets(
        stats_markdown=stats_markdown,
        total_tokens_used=total_tokens_used,
        rag_context=rag_context_3,
    )
    print("\n=== AGENT 3 OUTPUT (stats table + bullets) ===")
    print(stats_markdown)
    if rag_context_3:
        print("\n--- Agent 3 retrieved context ---")
        print(rag_context_3)
    print("\n--- Agent 3 bullets ---")
    print(agent3_bullets)

    # Agent 4 (300–400 word report)
    agent4_report = agent4_write_report(
        stats_markdown=stats_markdown,
        agent3_bullets=agent3_bullets,
        total_tokens_used=total_tokens_used,
    )
    print("\n=== AGENT 4 OUTPUT (final report) ===")
    print(agent4_report)

    outlier_events_display: List[Dict[str, Any]] = []
    for e in all_events:
        if not e.get("is_outlier"):
            continue
        urls = e.get("matched_article_urls") or []
        n = len(urls) if isinstance(urls, list) else 0
        outlier_events_display.append(
            {
                "city": e.get("city"),
                "state": e.get("state"),
                "date": e.get("date"),
                "article_count": n,
            }
        )

    stats_data: Dict[str, Any] = {
        "state_a": state_a,
        "state_b": state_b,
        "state_a_data": state_summary["state_a"],
        "state_b_data": state_summary["state_b"],
        "coverage_rate_diff": debug["coverage_rate_diff"],
        "income_diff": debug["income_diff"],
        "correlation_flag": debug["correlation_flag"],
        "speed_note": debug["speed_note"],
        "higher_coverage_state": debug["higher_coverage_state"],
    }

    result = {
        "agent2": state_summary,
        "agent3": {"stats_markdown": stats_markdown, "bullets": agent3_bullets, "rag_context": rag_context_3},
        "agent4": agent4_report,
        "tokens": dict(total_tokens_used),  # copy
        "cost": (int(total_tokens_used["prompt"]) + int(total_tokens_used["completion"])) / 1_000_000 * 0.60,
        "stats_data": stats_data,
        "outlier_events": outlier_events_display,
        "agent3_bullets": extract_bullets(agent3_bullets),
    }
    if created_local_rag_conn and rag_conn is not None:
        try:
            rag_conn.close()
        except Exception:
            pass
    return result


# 8. CLI ENTRY
def main() -> None:
    total_tokens_used: Dict[str, int] = {"prompt": 0, "completion": 0}
    parser = argparse.ArgumentParser(description="HW2 multi-agent 2-state pipeline")
    parser.add_argument("--state-a", default="OH", help="Two-letter state code for state A (default: Ohio)")
    parser.add_argument("--state-b", default="LA", help="Two-letter state code for state B (default: Louisiana)")
    parser.add_argument(
        "--real-cache",
        action="store_true",
        help="Use real HOMEWORK_1 cache + GVA events instead of hardcoded test data",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=120,
        help="Used only in non-real-cache flows; real-cache uses HW2_app parity (synthetic Agent 1, max_articles=0).",
    )
    args = parser.parse_args()
    state_a = args.state_a.strip().upper()
    state_b = args.state_b.strip().upper()

    # Preflight: verify Census connectivity for selected state A.
    print(f"=== Preflight Census Test: {state_a} state demographics ===", flush=True)
    demo = get_state_demographics(state_a)
    print("Census result:", demo, flush=True)
    if demo is None:
        print(
            f"ERROR: Census state lookup failed for {state_a}. Fix Census connectivity/mapping before proceeding.",
            flush=True,
        )
        sys.exit(1)

    rag_conn = None
    if args.real_cache:
        # Match HW2_app.handle_generate_report: same GVA event list + synthetic "Agent 1" + full-state RAG.
        print("\n=== DATA MODE: REAL CACHE (HW2_app parity) ===", flush=True)
        all_events_local, _ = build_gva_events_for_states([state_a, state_b], max_articles=0)
        print(
            f"Loaded {len(all_events_local)} GVA events for {state_a} and {state_b} "
            f"(max_articles=0; same scope as HW2_app filter on hw2_events_all).",
            flush=True,
        )
        if args.max_articles != 120:
            print(
                f"Note: --max-articles={args.max_articles} is ignored in real-cache mode "
                f"(app uses synthetic validation, not LLM Agent 1 on candidates).",
                flush=True,
            )
        validated_articles = _synthetic_validated_from_gva_events(all_events_local)
        rag_conn = _load_rag_conn_like_app()
        print(
            "\n=== AGENT 1 SKIPPED (synthetic validation from GVA/NYT cache matches, same as HW2_app.py) ===",
            flush=True,
        )
        print(f"Synthetic validated rows (one URL per covered event): {len(validated_articles)}", flush=True)
    else:
        print("\n=== DATA MODE: HARDCODED TEST ===", flush=True)
        test_articles_local = test_articles
        all_events_local = all_events
        print("\n=== AGENT 1 OUTPUT (parallel relevance validation via OpenAI) ===")
        validated_articles, elapsed = agent1_validate_articles_parallel(
            test_articles_local, total_tokens_used=total_tokens_used
        )
        validated_articles_for_print = [
            {"url": v.get("url"), "relevant": v.get("relevant"), "reason": v.get("reason")} for v in validated_articles
        ]
        print("Validated articles (url/relevant/reason):")
        print(json.dumps(validated_articles_for_print, indent=2))
        print(f"Agent 1 timing: {elapsed:.2f}s")

    pipeline_out = run_agent_pipeline(
        validated_articles=validated_articles,
        all_events=all_events_local,
        state_a=state_a,
        state_b=state_b,
        rag_conn=rag_conn,
    )

    pipeline_tokens = pipeline_out["tokens"]
    total_tokens_used["prompt"] += int(pipeline_tokens["prompt"])
    total_tokens_used["completion"] += int(pipeline_tokens["completion"])

    total_tokens = int(total_tokens_used["prompt"]) + int(total_tokens_used["completion"])
    cost = total_tokens / 1_000_000 * 0.60

    print("\n=== COST SUMMARY ===")
    if args.real_cache:
        print("Agent 1 (OpenAI): skipped (synthetic GVA/NYT rows; matches HW2_app.py)")
    else:
        print("Agent 1 (OpenAI): included (LLM relevance on hardcoded test articles)")
    print(f"Agents 2-4 (OpenAI): included")
    print(f"Total tokens:      {total_tokens:,}")
    print(f"Total cost:        ${cost:.4f}")

    state_a_summary = (pipeline_out.get("agent2") or {}).get("state_a", {})
    state_b_summary = (pipeline_out.get("agent2") or {}).get("state_b", {})
    state_a_avg_days = state_a_summary.get("avg_days_to_first_article")
    state_b_avg_days = state_b_summary.get("avg_days_to_first_article")
    state_a_same_day = state_a_summary.get("same_day_coverage_pct")
    state_b_same_day = state_b_summary.get("same_day_coverage_pct")

    print("=== COVERAGE SPEED SUMMARY ===")
    print(
        f"{state_a} avg days to first article: {state_a_avg_days:.1f}"
        if state_a_avg_days is not None
        else f"{state_a} avg days to first article: N/A"
    )
    print(
        f"{state_b} avg days to first article: {state_b_avg_days:.1f}"
        if state_b_avg_days is not None
        else f"{state_b} avg days to first article: N/A"
    )
    print(
        f"{state_a} same-day coverage: {state_a_same_day:.1f}%"
        if state_a_same_day is not None
        else f"{state_a} same-day coverage: N/A"
    )
    print(
        f"{state_b} same-day coverage: {state_b_same_day:.1f}%"
        if state_b_same_day is not None
        else f"{state_b} same-day coverage: N/A"
    )


if __name__ == "__main__":
    main()

