# HW1_nyt_test.py
# Minimal NYT API connectivity test — same pattern as 01_query_api/LAB_api_query_2.ipynb.
# Run from HOMEWORK_1: python HW1_nyt_test.py
# If this works, the cache script should work; if it hangs/fails, the issue is network or key.

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Same as notebook: repo root .env
REPO_ROOT = Path(__file__).resolve().parent.parent
env_path = REPO_ROOT / ".env"

# Check if env var already set (would override .env)
env_var_key = os.environ.get("NYT_API_KEY")
if env_var_key:
    print(f"WARNING: NYT_API_KEY already set in environment (first 8: {env_var_key[:8]}...).", flush=True)
    print("  This will override .env file. Unset it with: unset NYT_API_KEY", flush=True)

# Load .env
load_dotenv(env_path, override=False)  # Don't override existing env vars
NYT_API_KEY = os.getenv("NYT_API_KEY")
URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

if not NYT_API_KEY:
    print(f"Error: NYT_API_KEY not found in .env file at {env_path}")
    print("Make sure .env exists in the repo root and contains: NYT_API_KEY=your_key_here")
    if env_path.exists():
        print(f"  .env file exists. Contents (first 200 chars):")
        try:
            with open(env_path, "r") as f:
                content = f.read(200)
                print(f"  {content}")
        except Exception as e:
            print(f"  Could not read .env: {e}")
    else:
        print(f"  .env file does not exist at {env_path}")
    sys.exit(1)

print(f"Loaded API key from .env (first 8 chars: {NYT_API_KEY[:8]}..., last 4: ...{NYT_API_KEY[-4:]})", flush=True)
print(f"  .env file path: {env_path}", flush=True)
print(f"  Key length: {len(NYT_API_KEY)} characters", flush=True)

# One request, same style as notebook (no timeout to match notebook; use timeout=30 for safety)
params = {
    "api-key": NYT_API_KEY,
    "q": '"New Orleans" (shooting OR attack OR killed)',
    "begin_date": "20250101",
    "end_date": "20251231",
    "sort": "oldest",
    "page": 0,
}
print("Sending one NYT API request (timeout 30 sec)...", flush=True)
try:
    r = requests.get(URL, params=params, timeout=30)
except requests.exceptions.Timeout:
    print("TIMEOUT after 30 sec. NYT API not responding in time.")
    sys.exit(1)
except requests.RequestException as e:
    print(f"REQUEST ERROR: {e}")
    sys.exit(1)

print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    docs = data.get("response", {}).get("docs", [])
    print(f"OK — got {len(docs)} docs in response.")
    if docs:
        print(f"First headline: {(docs[0].get('headline') or {}).get('main', '')[:60]}...")
elif r.status_code == 401:
    print("401 Unauthorized — API key not approved.")
    # Extract key from URL to compare
    request_url = r.request.url if hasattr(r, "request") else ""
    if "api-key=" in request_url:
        url_key_part = request_url.split("api-key=")[1].split("&")[0] if "&" in request_url.split("api-key=")[1] else request_url.split("api-key=")[1]
        print(f"  Key used in request (from URL): {url_key_part[:8]}...{url_key_part[-4:] if len(url_key_part) > 12 else ''}")
        print(f"  Key from .env: {NYT_API_KEY[:8]}...{NYT_API_KEY[-4:]}")
        if url_key_part != NYT_API_KEY:
            print("  MISMATCH: URL key differs from .env key!")
            print("  This suggests .env wasn't loaded or was overridden by environment variable.")
    print("New NYT API keys can take 5–15 minutes to activate after creation.")
    print("Check:")
    print("  1. Key is correct in .env file (no extra spaces/quotes)")
    print("  2. Key is activated in NYT Developer Portal (https://developer.nytimes.com/)")
    print("  3. Wait 5–15 minutes after creating the key, then try again")
    print("  4. If keys don't match, check for NYT_API_KEY environment variable: echo $NYT_API_KEY")
    try:
        err_data = r.json()
        print(f"  API error detail: {err_data}")
    except Exception:
        print(f"  Response: {r.text[:300]}")
    sys.exit(1)
elif r.status_code == 429:
    print("429 Too Many Requests — rate limited.")
    print("Wait 10–15 minutes, then run this test again or run HW1_api_query.py (it will wait and retry on 429).")
    sys.exit(1)
else:
    print(f"Response: {r.text[:300]}")
sys.exit(0)
