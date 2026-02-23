# HW1_nyt_cache.py
# NYT 2025 shooting-article cache: load from JSON or build by querying per GVA 2025 city.
# Only fetches articles that include a 2025 shooting city in the query (title/headline match via API).
# Pairs with HOMEWORK_1 API query and Shiny app.

import json
import os
import re
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

# Paths: cache and .env relative to this file (HOMEWORK_1)
HW1_DIR = Path(__file__).resolve().parent
CACHE_PATH = HW1_DIR / "nyt_2025_shootings_cache.json"
REPO_ROOT = HW1_DIR.parent
GVA_PATH = REPO_ROOT / "01_query_api" / "gva_mass_shootings-2026-02-08.csv"
ENV_PATH = REPO_ROOT / ".env"

# Check for existing env var (would override .env)
if os.environ.get("NYT_API_KEY"):
    print(f"WARNING: NYT_API_KEY already set in environment. It will override .env file.", flush=True)

load_dotenv(ENV_PATH, override=False)
NYT_API_KEY = os.getenv("NYT_API_KEY")
NYT_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

if NYT_API_KEY:
    print(f"Loaded NYT_API_KEY from {ENV_PATH} (first 8: {NYT_API_KEY[:8]}..., last 4: ...{NYT_API_KEY[-4:]})", flush=True)
else:
    print(f"WARNING: NYT_API_KEY not found in {ENV_PATH}", flush=True)

# NYT API allows page 0–99 only (100 pages max per query)
MAX_PAGE = 99
# Timeout in seconds (same order as notebook; notebook uses no timeout)
REQUEST_TIMEOUT = 30
# Rate limiting: NYT allows 10 requests/minute, 4000/day
# Track request timestamps to stay under limit
_request_times = deque(maxlen=10)  # Keep last 10 request times

# Keywords for filtering articles (must appear in headline or abstract)
KEYWORDS = ["shooting", "attack", "killed", "mass", "gunman", "victims"]


def _contains_keywords(text: str) -> bool:
    """True if at least one keyword appears in text (case-insensitive)."""
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in KEYWORDS)


def _city_phrase_pattern(city: str):
    """Regex so city matches as whole word(s). Avoids 'Mobile' matching 'mobile unit' in New Orleans articles."""
    if not city or not city.strip():
        return None
    words = city.strip().split()
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def _filter_articles_by_city_and_keywords(
    articles: List[dict], city: str, state: Optional[str] = None
) -> List[dict]:
    """
    Filter articles: city must appear in headline or abstract as a whole word/phrase.
    State is not required in headline. Keyword must appear in headline or abstract.
    """
    city_pattern = _city_phrase_pattern(city)
    if not city_pattern:
        return []
    filtered = []
    for a in articles:
        headline = (a.get("headline") or {}).get("main") or ""
        abstract = a.get("abstract") or ""
        combined = (headline + " " + abstract).strip()
        if not city_pattern.search(combined):
            continue
        if not (_contains_keywords(headline) or _contains_keywords(abstract)):
            continue
        filtered.append(a)
    return filtered


def _rate_limit_wait() -> None:
    """
    Enforce 10 requests/minute limit. If we've made 10 requests in the last 60 seconds,
    wait until the oldest request is >60 seconds ago.
    """
    now = time.time()
    if len(_request_times) >= 10:
        oldest = _request_times[0]
        elapsed = now - oldest
        if elapsed < 60:
            wait_time = 60 - elapsed + 0.5  # Add 0.5 sec buffer
            time.sleep(wait_time)
    _request_times.append(time.time())


def _preflight_nyt() -> None:
    """One minimal request to check API reachability. Handles 429 (rate limit) with wait and retry.
    Uses plain requests.get (no Session) to match LAB_api_query_2.ipynb."""
    print("  Checking NYT API reachability (timeout 30 sec)...", flush=True)
    params = {"api-key": NYT_API_KEY, "q": "the", "begin_date": "20250101", "end_date": "20250101", "page": 0}
    for attempt in range(2):
        try:
            r = requests.get(NYT_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as e:
            raise RuntimeError(
                "NYT API did not respond within 15 seconds. Check internet, VPN, and firewall; or try again later."
            ) from e
        except requests.RequestException as e:
            raise RuntimeError(f"Cannot reach NYT API: {e}") from e
        if r.status_code == 429:
            if attempt == 0:
                wait = 60
                retry_after = r.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = min(int(retry_after), 120)
                print(f"  Rate limited (429). Waiting {wait} sec, then retrying...", flush=True)
                time.sleep(wait)
                continue
            print("  Still rate limited. Proceeding; event queries will wait when needed.", flush=True)
            break
        r.raise_for_status()
        break
    print("  API reachable. Starting event queries.", flush=True)


def _load_gva_2025_events(
    start_date: str = "2025-01-01", end_date: str = "2025-03-31"
) -> List[Tuple[str, str, str]]:
    """
    Load GVA 2025 events and return list of (city, state, shooting_date_yyyymmdd) tuples.
    start_date, end_date: YYYY-MM-DD strings. Defaults to Jan–Mar 2025.
    """
    try:
        gva = pd.read_csv(GVA_PATH)
        # Keep only 2025 rows
        if "year" in gva.columns:
            gva = gva[gva["year"].astype(int) == 2025]
        elif "date_fixed" in gva.columns:
            gva["date_fixed"] = pd.to_datetime(gva["date_fixed"])
            gva = gva[gva["date_fixed"].dt.year == 2025]
        else:
            return []
        # Ensure date_fixed is datetime and restrict to date range
        gva["date_fixed"] = pd.to_datetime(gva["date_fixed"])
        mask = (gva["date_fixed"] >= pd.Timestamp(start_date)) & (
            gva["date_fixed"] <= pd.Timestamp(end_date)
        )
        gva = gva[mask]
        events = []
        for _, row in gva.iterrows():
            city = str(row.get("city_or_county", "")).strip()
            if not city:
                continue
            state = str(row.get("state", "")).strip()
            date_fixed = row.get("date_fixed")
            if pd.isna(date_fixed):
                continue
            dt = pd.to_datetime(date_fixed)
            shooting_date_yyyymmdd = dt.strftime("%Y%m%d")
            events.append((city, state, shooting_date_yyyymmdd))
        return events
    except Exception:
        return []


def _fetch_pages_for_query(
    q: str,
    begin_date: str,
    end_date: str,
    progress_callback: Optional[Callable[..., None]] = None,
    city_label: str = "",
) -> List[dict]:
    """
    Fetch up to MAX_PAGE+1 pages for one NYT query. Handles 400 (page limit), 429 (rate limit).
    Uses plain requests.get (no Session) to match LAB_api_query_2.ipynb.
    begin_date, end_date: YYYYMMDD strings (e.g., "20250101").
    progress_callback(len_articles_this_event, page_index) called after each page.
    Returns list of article dicts (no dedup here).
    """
    params = {
        "q": q,
        "begin_date": begin_date,
        "end_date": end_date,
        "sort": "oldest",
        "api-key": NYT_API_KEY,
    }
    articles = []
    page = 0
    while page <= MAX_PAGE:
        params["page"] = page
        _rate_limit_wait()  # Enforce 10 requests/minute before each request
        try:
            response = requests.get(NYT_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise RuntimeError(f"NYT API request failed: {e}") from e
        if response.status_code == 429:
            # Rate limited: wait longer and clear recent request times
            wait = 60
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = min(int(retry_after), 120)
            print(f"    Rate limited (429). Waiting {wait} sec...", flush=True)
            _request_times.clear()  # Reset counter after rate limit
            time.sleep(wait)
            continue
        if response.status_code == 400:
            try:
                msg = (response.json() or {}).get("fault", {}).get("faultstring", "") or response.text
            except Exception:
                msg = response.text
            if "page" in msg.lower() and "100" in msg:
                break
            raise RuntimeError(f"NYT API error 400: {response.text[:300]}")
        if response.status_code != 200:
            raise RuntimeError(f"NYT API error {response.status_code}: {response.text[:300]}")
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise RuntimeError(f"NYT API returned invalid JSON: {e}") from e
        if "response" not in data:
            raise RuntimeError("Unexpected NYT API response structure.")
        docs = data["response"].get("docs", [])
        if not docs:
            break
        articles.extend(docs)
        if progress_callback:
            try:
                progress_callback(len(articles), page)
            except TypeError:
                progress_callback(len(articles), 0)
        page += 1
        # Small delay between pages (rate limiting handles the main throttling)
        if page <= MAX_PAGE:  # Don't sleep after last page
            time.sleep(0.5)
    return articles


def _write_cache(path: Path, articles: List[dict]) -> None:
    """Write article list to JSON cache file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=0, ensure_ascii=False)


def _build_cache_by_event(
    cache_path: Path,
    progress_callback: Optional[Callable[..., None]] = None,
    existing_articles: Optional[List[dict]] = None,
    start_date: str = "2025-01-01",
    end_date: str = "2025-03-31",
) -> List[dict]:
    """
    Build cache by querying NYT once per GVA 2025 event: city + (shooting OR attack OR killed),
    with begin_date = shooting_date, end_date = shooting_date + 60 days (matches notebook logic).
    Only stores articles where city appears as whole word/phrase in headline or abstract
    and keywords in headline/abstract. State name is not required in headline.
    Deduplicates by web_url. Writes cache to cache_path after each event (incremental save).
    existing_articles: optional list to merge with (deduplicated by web_url).
    start_date, end_date: YYYY-MM-DD strings for event date range.
    progress_callback(current_articles, total_articles, event_i, total_events): total_articles=0 until done.
    """
    if not NYT_API_KEY:
        raise ValueError("NYT_API_KEY not found in .env. Obtain a key from https://developer.nytimes.com/")
    events = _load_gva_2025_events(start_date=start_date, end_date=end_date)
    if not events:
        raise RuntimeError("No GVA 2025 events found. Check path and CSV columns (year or date_fixed).")
    print(f"Found {len(events)} events ({start_date} to {end_date}). Querying NYT (60-day window per event)...", flush=True)
    seen_urls = set()
    all_articles = []
    # Start with existing articles if provided
    if existing_articles:
        for a in existing_articles:
            url = a.get("web_url")
            if url:
                seen_urls.add(url)
                all_articles.append(a)
        print(f"  Merging with {len(existing_articles)} existing articles from cache.", flush=True)
    total_events = len(events)
    _preflight_nyt()
    for i, (city, state, shooting_date_yyyymmdd) in enumerate(events):
        if i == 0:
            print(f"  Sending first event request (timeout {REQUEST_TIMEOUT} sec)...", flush=True)
        dt = datetime.strptime(shooting_date_yyyymmdd, "%Y%m%d").date()
        end_dt = dt + timedelta(days=60)
        # Ensure we only search for reports published in 2025
        if end_dt.year > 2025:
            end_dt = datetime(2025, 12, 31).date()
        begin_date = shooting_date_yyyymmdd
        end_date = end_dt.strftime("%Y%m%d")
        q = f'"{city}" (shooting OR attack OR killed)'
        def make_page_cb(ei: int, te: int, cname: str, sdate: str):
            def _page_cb(n: int, page: int):
                print(f"  Event {ei} of {te} ({cname}, {sdate}) — {n} articles this event, page {page + 1}", flush=True)
            return _page_cb
        page_cb = make_page_cb(i + 1, total_events, city, shooting_date_yyyymmdd)
        try:
            batch = _fetch_pages_for_query(q, begin_date, end_date, progress_callback=page_cb, city_label=city)
        except RuntimeError:
            raise
        # Filter: city as whole word/phrase and state in text (avoids Mobile AL matching "mobile" in other articles)
        filtered_batch = _filter_articles_by_city_and_keywords(batch, city, state=state)
        for a in filtered_batch:
            url = a.get("web_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(a)
        try:
            _write_cache(cache_path, all_articles)
        except OSError:
            pass
        if progress_callback:
            try:
                progress_callback(len(all_articles), 0, i + 1, total_events)
            except TypeError:
                progress_callback(len(all_articles), 0)
        # Small delay between events (rate limiting handles main throttling)
        if i < total_events - 1:  # Don't sleep after last event
            time.sleep(0.5)
    if progress_callback and all_articles:
        try:
            progress_callback(len(all_articles), len(all_articles), total_events, total_events)
        except TypeError:
            progress_callback(len(all_articles), len(all_articles))
    return all_articles


def load_or_build_2025_cache(
    cache_path: Path = None,
    progress_callback: Optional[Callable[..., None]] = None,
    query_date_range: Optional[Tuple[str, str]] = None,
) -> list:
    """
    Load 2025 NYT shooting-article cache from JSON, or build and save it.
    Build queries per GVA 2025 event: city + (shooting OR attack OR killed), with begin_date = shooting_date,
    end_date = shooting_date + 60 days (matches notebook logic). Only stores articles where city is in headline/title.
    Cache is written after each event during build (incremental), so partial progress is saved if interrupted.
    If cache_path is None, uses HOMEWORK_1/nyt_2025_shootings_cache.json.
    query_date_range: optional (start_date, end_date) tuple as "YYYY-MM-DD" strings. If None and cache exists,
    returns cache without querying. If None and no cache, queries Jan–Mar 2025. If provided, queries that range
    and merges with existing cache (if any).
    progress_callback(current_articles, total_articles, event_i=None, total_events=None): when loading, called once
    with (n, n); when building, called after each event with (articles_so_far, 0, event_i, total_events).
    Returns list of raw article dicts (each with pub_date, headline, abstract, etc.).
    """
    path = cache_path if cache_path is not None else CACHE_PATH
    path = Path(path)
    # Load existing cache if it exists
    existing_articles = []
    if path.exists():
        print("Cache file found. Loading (may take a minute for large files)...", flush=True)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                existing_articles = data
            elif isinstance(data, dict) and "docs" in data:
                existing_articles = data["docs"]
            else:
                existing_articles = data if isinstance(data, list) else []
            print(f"Loaded {len(existing_articles)} articles from cache.", flush=True)
            # If no query_date_range specified, just return existing cache
            if query_date_range is None:
                if progress_callback and existing_articles:
                    try:
                        progress_callback(len(existing_articles), len(existing_articles), None, None)
                    except TypeError:
                        progress_callback(len(existing_articles), len(existing_articles))
                return existing_articles
            print(f"  Will query and merge events from {query_date_range[0]} to {query_date_range[1]}.", flush=True)
        except (json.JSONDecodeError, OSError):
            print("Cache invalid or unreadable. Will rebuild.", flush=True)
            pass
    # Determine date range for querying
    if query_date_range:
        start_date, end_date = query_date_range
    else:
        # Default: Jan–Mar 2025
        start_date, end_date = "2025-01-01", "2025-03-31"
    print("Building cache. Loading GVA 2025 events...", flush=True)
    articles = _build_cache_by_event(
        cache_path=path,
        progress_callback=progress_callback,
        existing_articles=existing_articles if existing_articles else None,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        _write_cache(path, articles)
    except OSError as e:
        raise RuntimeError(f"Could not write cache file {path}: {e}") from e
    return articles
