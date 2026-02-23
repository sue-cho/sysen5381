# HOMEWORK_1 — NYT State Comparison

Compare mass-shooting events (GVA data) with New York Times coverage by state. Shiny app for two-state comparison and Top 10 rankings; DOCX analysis report.

### Repository links

| Content | Link |
|---------|------|
| API query script | [HW1_api_query.py](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/HW1_api_query.py) |
| Shiny app code | [HW1_app.py](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/HW1_app.py) |
| AI reporting script | [HW1_data_reporter.py](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/HW1_data_reporter.py) |
| NYT article cache | [nyt_2025_shootings_cache.json](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/nyt_2025_shootings_cache.json) |

---

## Data Summary

**GVA mass shootings CSV** (`gva_mass_shootings-2026-02-08.csv`) — columns:

| Column | Data type | Description |
|--------|-----------|-------------|
| `incident_id` | integer | Unique incident ID. |
| `incident_date` | string | Human-readable date (e.g. "April 1, 2017"). |
| `incident_time` | string | Time of incident or "N/A". |
| `updated_date` | integer | Unix timestamp of record update. |
| `state` | string | U.S. state name. |
| `city_or_county` | string | City or county where incident occurred. |
| `address` | string | Street address or block. |
| `business_location_name` | string | Venue name or "N/A". |
| `latitude` | float | Latitude. |
| `longitude` | float | Longitude. |
| `killed` | integer | Number killed. |
| `injured` | integer | Number injured. |
| `victims_killed` | integer | Victims killed. |
| `victims_injured` | integer | Victims injured. |
| `suspects_killed` | integer | Suspects killed. |
| `suspects_injured` | integer | Suspects injured. |
| `suspects_arrested` | integer | Suspects arrested. |
| `incident_characteristics` | string | R-style list of tags (e.g. mass shooting, location type). |
| `sources` | string | Source URL(s) for the incident. |
| `date_fixed` | string | Normalized date (YYYY-MM-DD). |
| `year` | integer | Year (used to filter to 2025). |

The app filters to **year 2025** and matches events to cached NYT articles by city and headline/abstract keywords.

**NYT Article Search API** — cached in `nyt_2025_shootings_cache.json`. Each cached item is one article from the [NYT Article Search API](https://developer.nytimes.com/docs/article-search-api/overview). Key fields used for matching to GVA events:

| Field | Data type | Description |
|-------|-----------|-------------|
| `web_url` | string | Article URL on nytimes.com. |
| `pub_date` | string | Publication date/time (ISO 8601, e.g. `2025-03-03T10:00:35Z`). |
| `headline` | object | `main` (string): main headline; used for city/keyword matching. |
| `abstract` | string | Short summary; used for city/keyword matching. |
| `snippet` | string | Search-result snippet. |
| `_id` | string | NYT internal ID (e.g. `nyt://article/...`). |
| `document_type` | string | e.g. `"article"`. |
| `byline` | object | e.g. `original`: author byline. |
| `keywords` | array | Subjects, persons, locations. |
| `lead_paragraph` | string | First paragraph when present. |
| `type_of_material` | string | e.g. News, Editorial. |

Matching to GVA events uses `headline.main`, `abstract`, `pub_date`, and `web_url`. The city must appear in headline or abstract, and shooting-related keywords must appear there as well.

---

## Technical Details

### API keys

| Variable | Required | Purpose |
|----------|----------|---------|
| `NYT_API_KEY` | Yes | NYT Article Search API (build/load article cache). |
| `OPENAI_API_KEY` | No | AI sections in DOCX report. |

- Set in a **`.env` file in the repo root** (parent of `HOMEWORK_1`), or as environment variables.
- **NYT**: [NYT Developer](https://developer.nytimes.com/) → Create App → Article Search API.
- **OpenAI**: [OpenAI API keys](https://platform.openai.com/api-keys). Omit if you don’t need AI report sections.

### Endpoints

- **NYT Article Search**: `https://api.nytimes.com/svc/search/v2/articlesearch.json`  
  Params: `api-key`, `q`, `begin_date`, `end_date`, `page`, `sort`.
- **OpenAI**: `https://api.openai.com/v1/chat/completions` (Bearer token), used by the reporter.

### Packages

- `pandas` — GVA CSV and analysis.
- `requests` — NYT and OpenAI API calls.
- `python-dotenv` — Load keys from `.env`.
- `shiny` — Web app.
- `python-docx` — DOCX report generation.

### File structure (HOMEWORK_1)

| File | Purpose |
|------|--------|
| `gva_mass_shootings-2026-02-08.csv` | GVA mass-shooting data (filtered to 2025 in app). |
| `HW1_app.py` | Shiny app: compare two states or view Top 10 rankings. |
| `HW1_nyt_cache.py` | Load or build NYT article cache (`nyt_2025_shootings_cache.json`). |
| `HW1_state_analysis.py` | State stats, % reported, coverage duration, reported/not-reported lists. |
| `HW1_data_reporter.py` | Generate DOCX comparison report (with AI-generated sections). |
| `HW1_api_query.py` | Script to pre-build the NYT cache. |
| `HW1_nyt_test.py` | Quick NYT API connectivity test. |
| `nyt_2025_shootings_cache.json` | Cached NYT articles (created on first run or by `HW1_api_query.py`). |

---

## Usage Instructions

### 1. Install dependencies

```bash
pip install pandas requests python-dotenv shiny python-docx
```

### 2. Set up API key

Create a `.env` file in the **repo root** (one level above `HOMEWORK_1`):

```bash
# From repo root
echo "NYT_API_KEY=your_key_here" > .env
```

Get a key at [NYT Developer](https://developer.nytimes.com/) (Article Search API).  
Add `OPENAI_API_KEY=...` to `.env` for AI-generated sections in the DOCX report.  
Do not commit `.env` (keep it in `.gitignore`).

### 3. Run the app

```bash
cd HOMEWORK_1
shiny run HW1_app.py
```

- The app loads or builds the NYT cache on first run.
- Choose State A and State B, click **Run NYT coverage analysis** to compare.
- Use **Top 10 Statistics** for nationwide rankings.
- Use **Generate comparison document (.docx)** to download a report.

### Optional: pre-build cache or test API

```bash
cd HOMEWORK_1
python HW1_api_query.py    # Build cache before first run
python HW1_nyt_test.py     # Test NYT API connectivity
```

### Optional: generate DOCX from command line

```bash
cd HOMEWORK_1
python HW1_data_reporter.py "Ohio" "Louisiana"
```

Output: `HW1_NYT_Comparison_Ohio_vs_Louisiana.docx` in `HOMEWORK_1`.
