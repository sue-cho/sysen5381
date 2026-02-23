# HW1_api_query.py
# Run to load or build the 2025 NYT shooting-article cache.
# Call load_or_build_2025_cache(); cache is used by HW1_app and HW1_data_reporter.
# Usage: python HW1_api_query.py [start_date] [end_date]
#   Example: python HW1_api_query.py 2025-03-01 2025-12-31  (to query March–December and merge with existing cache)

import sys
from HW1_nyt_cache import load_or_build_2025_cache, CACHE_PATH


def main():
    query_range = None
    if len(sys.argv) >= 3:
        query_range = (sys.argv[1], sys.argv[2])
        print(f"Querying events from {query_range[0]} to {query_range[1]} (will merge with existing cache if present)...")
    else:
        print("Loading or building 2025 NYT shootings cache...")
        print("  (To query specific date range: python HW1_api_query.py 2025-03-01 2025-12-31)")
    def progress(current: int, total: int, event_i=None, total_events=None):
        if total > 0:
            print(f"  Done: {current} articles.")
        elif event_i is not None and total_events is not None:
            print(f"  Event {event_i} of {total_events} — {current} articles so far", flush=True)
        else:
            print(f"  Fetched {current} articles...", end="\r", flush=True)
    try:
        articles = load_or_build_2025_cache(progress_callback=progress, query_date_range=query_range)
        if articles:
            print(f"  Done: {len(articles)} articles.")
        print(f"Cache ready: {len(articles)} articles.")
        print(f"Cache file: {CACHE_PATH}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
