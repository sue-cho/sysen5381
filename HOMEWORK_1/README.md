# HOMEWORK_1 — NYT 2025 State Comparison

Compare 2025 mass-shooting events (GVA data) with New York Times coverage by state. Includes a Shiny app for two-state comparison and a DOCX report (with optional AI-generated sections).

### Repository links (GitHub)

| File | Link |
|------|------|
| `HW1_api_query.py` | [HW1_api_query.py](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/HW1_api_query.py) |
| `HW1_app.py` | [HW1_app.py](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/HW1_app.py) |
| `HW1_data_reporter.py` | [HW1_data_reporter.py](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/HW1_data_reporter.py) |
| `nyt_2025_shootings_cache.json` | [nyt_2025_shootings_cache.json](https://github.com/sue-cho/sysen5381/blob/main/HOMEWORK_1/nyt_2025_shootings_cache.json) |

---

## Data summary

### NYT Article Search API — article document fields

Cached data comes from the [NYT Article Search API](https://developer.nytimes.com/docs/article-search-api/overview). Each cached item is one article **doc**. Key fields:

| Column / field      | Data type   | Description |
|---------------------|------------|-------------|
| `web_url`           | string     | URL of the article on nytimes.com. |
| `pub_date`          | string     | Publication date/time in ISO 8601 (e.g. `2025-03-03T10:00:35Z`). |
| `headline`          | object     | `main` (string): main headline; `kicker`, `print_headline` optional. |
| `abstract`          | string     | Short summary of the article. |
| `snippet`           | string     | Snippet used in search results (often same as abstract). |
| `_id`               | string     | NYT internal ID (e.g. `nyt://article/...`). |
| `document_type`     | string     | e.g. `"article"`. |
| `byline`            | object     | e.g. `original`: author byline text. |
| `keywords`          | array      | List of `{name, value, rank}` (subjects, persons, locations, etc.). |
| `multimedia`        | object     | Image info: `url`, `caption`, `credit`, dimensions. |
| `lead_paragraph`    | string     | First paragraph (when present). |
| `source`            | string     | Source of the article. |
| `type_of_material`  | string     | e.g. News, Editorial. |

Matching to GVA events uses `headline.main`, `abstract`, `pub_date`, and `web_url`. City must appear in headline or abstract; shooting-related keywords must appear there as well.

### GVA data

- **File**: `01_query_api/gva_mass_shootings-2026-02-08.csv`, filtered to **year 2025**.
- **Relevant columns**: `state`, `city_or_county`, `date_fixed` (shooting date). An event is “reported” if at least one cached NYT article matches by city, keywords in headline/abstract, and publication date in 2025. Coverage duration = days from first to last matching article for that event.

---

## Technical details

### API keys

| Variable           | Required | Where to set | Purpose |
|-------------------|----------|--------------|---------|
| `NYT_API_KEY`     | Yes      | Repo root `.env` or environment | NYT Article Search API (cache build and load). |
| `OPENAI_API_KEY`  | No       | Repo root `.env` or environment | Optional: AI-generated sections in the DOCX report. If unset, report uses non-AI summaries. |

- **NYT key**: [NYT Developer](https://developer.nytimes.com/) → Create App → Article Search API. Put in repo root `.env` as `NYT_API_KEY=your_key`.
- **OpenAI key**: [OpenAI API keys](https://platform.openai.com/api-keys). Put in same `.env` as `OPENAI_API_KEY=your_key`.

Environment variables override values in `.env`.

### Endpoints

- **NYT Article Search**: `https://api.nytimes.com/svc/search/v2/articlesearch.json`  
  Params: `api-key`, `q`, `begin_date`, `end_date`, `page`, `sort`.
- **OpenAI** (optional, in reporter): `https://api.openai.com/v1/chat/completions` (Bearer token).

### Packages

Install with:

```bash
pip install pandas requests python-dotenv shiny python-docx
```

| Package         | Use |
|----------------|-----|
| `pandas`       | GVA CSV and state/cache analysis. |
| `requests`     | NYT API and (if used) OpenAI API. |
| `python-dotenv`| Load `NYT_API_KEY` and `OPENAI_API_KEY` from repo root `.env`. |
| `shiny`        | Shiny for Python app (`HW1_app.py`). |
| `python-docx`  | Generate DOCX reports. |

### File structure (HOMEWORK_1)

| File | Purpose |
|------|--------|
| `HW1_nyt_cache.py` | `load_or_build_2025_cache()` — load from `nyt_2025_shootings_cache.json` or fetch 2025 shooting articles from NYT API and save. |
| `HW1_api_query.py` | Script to load or build the cache (run before first app run if you want cache pre-built). |
| `HW1_state_analysis.py` | GVA 2025 + cache: state stats, % reported, coverage duration (min/max/mean/median), reported/not-reported event lists. |
| `HW1_app.py` | Shiny app: two state dropdowns, “Run state analysis”, comparison table, optional DOCX export. |
| `HW1_data_reporter.py` | DOCX report: title (two states), executive summary, statistical table; optional OpenAI sections. |
| `HW1_nyt_test.py` | Minimal NYT API connectivity test. |
| `nyt_2025_shootings_cache.json` | Cached NYT article docs (created by `HW1_api_query.py` or on first app run). |

GVA path (used by cache and state analysis): `01_query_api/gva_mass_shootings-2026-02-08.csv`.

---

## Usage instructions

### 1. Install dependencies

From repo root or `HOMEWORK_1`:

```bash
pip install pandas requests python-dotenv shiny python-docx
```

### 2. Set up API keys

1. Create a `.env` file in the **repo root** (parent of `HOMEWORK_1`), e.g.:

   ```bash
   cd /path/to/dsai
   touch .env
   ```

2. Add your NYT key (required for cache):

   ```
   NYT_API_KEY=your_nyt_api_key_here
   ```

3. (Optional) For AI sections in the report:

   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. Do not commit `.env`; keep it in `.gitignore`.

### 3. Build or load the cache

From `HOMEWORK_1`:

```bash
cd HOMEWORK_1
python HW1_api_query.py
```

This creates or updates `nyt_2025_shootings_cache.json`. The app can also build the cache on first run if the file is missing.

### 4. Run the Shiny app

```bash
cd HOMEWORK_1
shiny run HW1_app.py
```

Select State A and State B, click “Run state analysis”, then view the comparison table and (optionally) generate the DOCX report from the app.

### 5. Generate the DOCX report from the command line

```bash
cd HOMEWORK_1
python HW1_data_reporter.py "California" "Texas"
```

Output: `HW1_NYT_Comparison_California_vs_Texas.docx` (use any two state names that appear in GVA 2025).

### 6. Test NYT API connectivity

If the cache build hangs or fails:

```bash
cd HOMEWORK_1
python HW1_nyt_test.py
```

You should see either “OK — got N docs” or a clear error (timeout, 429, missing key, etc.).

---

## Cache behavior

- **File**: `nyt_2025_shootings_cache.json` in `HOMEWORK_1`.
- **When**: Loaded at app start or when running `HW1_api_query.py`. Fetched from the NYT API only if the file does not exist (or when explicitly building).
- **Query**: Articles in 2025 matching GVA 2025 cities and `(shooting OR attack OR killed)`; stored as a list of article docs.
