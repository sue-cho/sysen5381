# HW1_state_analysis.py
# State-level comparison: GVA 2025 mass shootings vs NYT cache coverage.
# Uses HW1_nyt_cache and GVA CSV; reuses filtering logic from LAB_api_query_2.

import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from HW1_nyt_cache import load_or_build_2025_cache

# GVA CSV path (same directory as this script: HOMEWORK_1)
HW1_DIR = Path(__file__).resolve().parent
GVA_PATH = HW1_DIR / "gva_mass_shootings-2026-02-08.csv"

KEYWORDS = ["shooting", "attack", "killed", "mass", "gunman", "victims"]


def _city_phrase_pattern(city: str):
    """
    Regex pattern so city matches as whole word(s). E.g. 'Mobile' -> \\bMobile\\b,
    'New Orleans' -> \\bNew\\s+Orleans\\b. Avoids matching 'mobile' in 'mobile unit' or 'New' alone.
    """
    if not city or not city.strip():
        return None
    words = city.strip().split()
    # Each word as escaped, with word boundaries; allow flexible whitespace between words
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def _contains_keywords(text: str) -> bool:
    """True if at least one keyword appears in text (case-insensitive)."""
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in KEYWORDS)


def filter_articles_by_city_and_keywords(
    articles: List[dict], city: str, state: Optional[str] = None
) -> List[dict]:
    """
    Filter articles: city must appear in headline or abstract as a whole word/phrase
    (avoids e.g. 'mobile' matching inside 'mobile unit'). State name is not required in headline.
    Keyword must appear in headline or abstract. Cache is 2025-only.
    """
    city_pattern = _city_phrase_pattern(city)
    if not city_pattern:
        return []

    def mentions_city_as_place(a):
        h = (a.get("headline") or {}).get("main") or ""
        ab = a.get("abstract") or ""
        combined = (h + " " + ab).strip()
        return bool(city_pattern.search(combined))

    def has_keyword(a):
        h = (a.get("headline") or {}).get("main") or ""
        ab = a.get("abstract") or ""
        return _contains_keywords(h) or _contains_keywords(ab)

    return [a for a in articles if mentions_city_as_place(a) and has_keyword(a)]


def _article_pub_date(article: dict) -> Optional[date]:
    """Article publication date as date, or None if missing/invalid."""
    raw = article.get("pub_date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def _assign_articles_to_events(gva: pd.DataFrame, cache_articles: List[dict]) -> dict:
    """
    Assign each article to at most one shooting so we do not double-count.
    Rule: an article is assigned to the matching shooting with the latest shooting_date
    such that article pub_date >= shooting_date (published on or after the shooting).
    Returns dict mapping event_key -> list of article dicts. event_key = (state, city, date_str, row_index).
    """
    from collections import defaultdict

    # Collect all (article_url, article, event_key, shooting_date) for valid event-article pairs
    candidates = []
    for idx, row in gva.iterrows():
        city = row.get("city_or_county") or ""
        if not city:
            continue
        state = row.get("state") or ""
        date_str = ""
        shooting_date = None
        try:
            dt = pd.to_datetime(row.get("date_fixed"))
            date_str = dt.strftime("%Y-%m-%d")
            shooting_date = dt.date()
        except Exception:
            date_str = str(row.get("date_fixed", ""))
        matched = filter_articles_by_city_and_keywords(cache_articles, city, state=state)
        matched = [
            a for a in matched
            if _article_pub_date(a) is not None and shooting_date is not None and _article_pub_date(a) >= shooting_date
        ]
        event_key = (state, city, date_str, idx)
        for a in matched:
            url = a.get("web_url")
            if url:
                candidates.append((url, a, event_key, shooting_date))

    # For each article (by url), assign to the event with max(shooting_date) (closest to pub_date)
    article_to_best = {}
    for url, a, event_key, shooting_date in candidates:
        pub = _article_pub_date(a)
        if pub is None:
            continue
        if url not in article_to_best:
            article_to_best[url] = (event_key, a, shooting_date)
        else:
            _, _, best_date = article_to_best[url]
            if shooting_date > best_date:
                article_to_best[url] = (event_key, a, shooting_date)

    # Build event_key -> list of assigned articles
    assigned = defaultdict(list)
    for url, (event_key, a, _) in article_to_best.items():
        assigned[event_key].append(a)
    return dict(assigned)


def coverage_days_for_articles(articles: List[dict]) -> Optional[int]:
    """Coverage duration in days (first to last pub date). Returns None if no articles."""
    if not articles:
        return None
    dates = [
        datetime.fromisoformat(a["pub_date"].replace("Z", "+00:00")).date()
        for a in articles
    ]
    first = min(dates)
    last = max(dates)
    return (last - first).days + 1


def load_gva_2025() -> pd.DataFrame:
    """Load GVA mass shootings and filter to year 2025."""
    try:
        gva = pd.read_csv(GVA_PATH)
        if "year" in gva.columns:
            gva = gva[gva["year"].astype(int) == 2025]
        elif "date_fixed" in gva.columns:
            gva["date_fixed"] = pd.to_datetime(gva["date_fixed"])
            gva = gva[gva["date_fixed"].dt.year == 2025]
        else:
            return pd.DataFrame()
        return gva.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def get_states_2025() -> List[str]:
    """Sorted list of states that have at least one 2025 mass shooting."""
    gva = load_gva_2025()
    if gva.empty:
        return []
    return sorted(gva["state"].dropna().unique().tolist())


def run_state_analysis(
    state_a: str,
    state_b: str,
    cache_articles: Optional[List[dict]] = None,
) -> dict:
    """
    Run comparison for two states. Uses cached NYT articles (or loads/builds cache if None).
    Returns dict with state stats and comparison table data. Clean error handling.
    """
    if cache_articles is None:
        try:
            cache_articles = load_or_build_2025_cache()
        except (ValueError, RuntimeError) as e:
            return {"error": str(e), "state_a": None, "state_b": None}

    gva = load_gva_2025()
    if gva.empty:
        return {"error": "No GVA 2025 data found.", "state_a": None, "state_b": None}

    # Restrict to shootings within the cache's article date range (pub_date min/max)
    cache_dates = [_article_pub_date(a) for a in cache_articles if _article_pub_date(a) is not None]
    if not cache_dates:
        return {"error": "Cache has no articles with valid dates.", "state_a": None, "state_b": None}
    cache_start_date = min(cache_dates)
    cache_end_date = max(cache_dates)
    gva["date_fixed"] = pd.to_datetime(gva["date_fixed"])
    gva_dates = gva["date_fixed"].dt.date
    gva = gva[(gva_dates >= cache_start_date) & (gva_dates <= cache_end_date)].reset_index(drop=True)
    if gva.empty:
        return {"error": "No GVA shootings in cache date range.", "state_a": None, "state_b": None}

    # Assign each article to at most one shooting (closest date: article pub_date on or after shooting;
    # among matching events, assign to the shooting with the latest date <= pub_date).
    assigned_articles = _assign_articles_to_events(gva, cache_articles)

    def stats_for_state(state: str) -> dict:
        events = gva[gva["state"] == state]
        if events.empty:
            return {
                "state": state,
                "total_shootings": 0,
                "reported_count": 0,
                "pct_reported": 0.0,
                "coverage_min_days": None,
                "coverage_max_days": None,
                "coverage_mean_days": None,
                "coverage_median_days": None,
                "reported_events": [],
                "not_reported_events": [],
            }
        total = len(events)
        reported_count = 0
        coverage_durations = []
        reported_events = []
        not_reported_events = []
        for idx, row in events.iterrows():
            city = row.get("city_or_county") or ""
            if not city:
                continue
            date_str = ""
            try:
                dt = pd.to_datetime(row.get("date_fixed"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = str(row.get("date_fixed", ""))
            label = f"{city}, {date_str}"
            event_key = (state, city, date_str, idx)
            matched = assigned_articles.get(event_key, [])
            if matched:
                reported_count += 1
                days = coverage_days_for_articles(matched)
                if days is not None:
                    coverage_durations.append(days)
                # Store all articles (url, headline, pub_date) for display
                articles_info = []
                for art in matched:
                    url = art.get("web_url") or ""
                    headline = (art.get("headline") or {}).get("main") or ""
                    pub_date_str = ""
                    try:
                        raw = art.get("pub_date") or ""
                        if raw:
                            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                            pub_date_str = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pub_date_str = str(art.get("pub_date", ""))[:10] if art.get("pub_date") else ""
                    if url or headline:
                        articles_info.append({"url": url, "headline": headline, "pub_date": pub_date_str})
                reported_events.append({"label": label, "articles": articles_info})
            else:
                not_reported_events.append((date_str, label))
        pct = (100.0 * reported_count / total) if total else 0.0
        # Sort not covered by date (chronological) for display
        not_reported_events.sort(key=lambda x: x[0])
        not_reported_list = [lb for _, lb in not_reported_events]
        out = {
            "state": state,
            "total_shootings": total,
            "reported_count": reported_count,
            "pct_reported": round(pct, 1),
            "coverage_min_days": None,
            "coverage_max_days": None,
            "coverage_mean_days": None,
            "coverage_median_days": None,
            "reported_events": reported_events,
            "not_reported_events": not_reported_list,
        }
        if coverage_durations:
            out["coverage_min_days"] = min(coverage_durations)
            out["coverage_max_days"] = max(coverage_durations)
            out["coverage_mean_days"] = round(sum(coverage_durations) / len(coverage_durations), 1)
            sorted_d = sorted(coverage_durations)
            n = len(sorted_d)
            out["coverage_median_days"] = round(
                (sorted_d[n // 2] if n % 2 else (sorted_d[n // 2 - 1] + sorted_d[n // 2]) / 2), 1
            )
        return out

    sa = stats_for_state(state_a)
    sb = stats_for_state(state_b)
    return {
        "error": None,
        "state_a": sa,
        "state_b": sb,
        "cache_article_count": len(cache_articles),
        "cache_start_date": cache_start_date.strftime("%Y-%m-%d"),
        "cache_end_date": cache_end_date.strftime("%Y-%m-%d"),
    }


def get_all_states_stats(cache_articles: Optional[List[dict]] = None) -> dict:
    """
    Compute stats for every state (same cache date range and logic as run_state_analysis).
    Returns dict with error or states: list of {state, total_shootings, reported_count, pct_reported, ...}.
    """
    if cache_articles is None:
        try:
            cache_articles = load_or_build_2025_cache()
        except (ValueError, RuntimeError) as e:
            return {"error": str(e), "states": []}

    gva = load_gva_2025()
    if gva.empty:
        return {"error": "No GVA 2025 data found.", "states": []}

    cache_dates = [_article_pub_date(a) for a in cache_articles if _article_pub_date(a) is not None]
    if not cache_dates:
        return {"error": "Cache has no articles with valid dates.", "states": []}
    cache_start_date = min(cache_dates)
    cache_end_date = max(cache_dates)
    gva["date_fixed"] = pd.to_datetime(gva["date_fixed"])
    gva_dates = gva["date_fixed"].dt.date
    gva = gva[(gva_dates >= cache_start_date) & (gva_dates <= cache_end_date)].reset_index(drop=True)
    if gva.empty:
        return {"error": "No GVA shootings in cache date range.", "states": []}

    assigned_articles = _assign_articles_to_events(gva, cache_articles)

    def stats_for_state(state: str) -> dict:
        events = gva[gva["state"] == state]
        if events.empty:
            return {"state": state, "total_shootings": 0, "reported_count": 0, "pct_reported": 0.0}
        total = len(events)
        reported_count = 0
        for idx, row in events.iterrows():
            city = row.get("city_or_county") or ""
            if not city:
                continue
            date_str = ""
            try:
                dt = pd.to_datetime(row.get("date_fixed"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = str(row.get("date_fixed", ""))
            event_key = (state, city, date_str, idx)
            matched = assigned_articles.get(event_key, [])
            if matched:
                reported_count += 1
        pct = (100.0 * reported_count / total) if total else 0.0
        return {
            "state": state,
            "total_shootings": total,
            "reported_count": reported_count,
            "pct_reported": round(pct, 1),
        }

    states = sorted(gva["state"].dropna().unique().tolist())
    return {
        "error": None,
        "states": [stats_for_state(s) for s in states],
        "cache_start_date": cache_start_date.strftime("%Y-%m-%d"),
        "cache_end_date": cache_end_date.strftime("%Y-%m-%d"),
    }
