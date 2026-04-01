# HW2 System Documentation

Brief reference for the **multi-agent NYT coverage analysis** stack: Shiny app (`HW2_app.py`), pipeline (`HW2_multi_agent.py`), RAG (`rag_setup.py`), and supporting data in `HOMEWORK_1/`.

---

## 1. System architecture

### Overview

The system compares **New York Times** article coverage of **Gun Violence Archive (GVA)** mass-shooting incidents for two U.S. states, enriches with **U.S. Census ACS** demographics, optionally pulls **semantic context** from a local **RAG** index over the NYT cache, and produces **narrative reports** via OpenAI.

**Workflow (high level)**

1. **Data load** — GVA CSV + NYT JSON cache → per-event records with optional `matched_article_urls`, outlier flags, etc.
2. **Shiny app** — National choropleth, two-state comparison (HW1-style analysis), and **The Report** tab that runs the multi-agent pipeline.
3. **Agent pipeline** (`run_agent_pipeline`) — Agents 2 → 3 → 4 run in sequence; Agent 1-style validation is **simulated in the app** from GVA/NYT matches when generating the report (see `HW2_app._synthetic_validated_from_gva_events`).

### Agent roles

| Agent | Role | Primary implementation | Rules (YAML) |
|-------|------|------------------------|--------------|
| **Agent 1** | For each candidate article, judge if it truly covers the matched shooting (`relevant`, `reason`, `url`). | `agent1_validate_articles_parallel` (CLI); Shiny uses synthetic rows from cache matches for pipeline speed. | `relevance_validation` |
| **Agent 2** | Build a **structured two-state summary**: totals, covered counts, coverage rates, timing stats, **Census demographics** per state, high-profile event list. | `agent2_build_state_summary` (Python + `get_state_demographics`; LLM guided by rules). | `demographics_enrichment` |
| **Agent 3** | Turn **pre-computed** stats (markdown block from Python) into **3–5 bullets** only; may use **RAG** text as background. Must not recalculate numbers. | `agent3_format_bullets`, `compute_state_comparison_stats` | `pattern_analysis` |
| **Agent 4** | Write a **300–400 word** report from the stats block + Agent 3 bullets. | `agent4_write_report` | `report_writing` |

**Rules file:** `HOMEWORK_2/04_rules.yaml` — sections under `rules:` feed `format_rules_for_prompt()` for each agent’s system prompt.

**Model:** `gpt-4o-mini` (`OPENAI_MODEL` in `HW2_multi_agent.py`).

---

## 2. RAG data source and search

### Data source

- **Input:** `HOMEWORK_1/nyt_2025_shootings_cache.json` — NYT Article Search API–shaped documents (list or `{"docs": [...]}`).
- **Filtering:** `filter_articles_for_states()` keeps articles whose headline/abstract/snippet mention the requested state(s) (names or abbreviations) and, by default, contain at least one **event keyword** (e.g. shooting, killed, gunman — see `EVENT_KEYWORDS` in `rag_setup.py`).
- **Index:** Embeddings with **SentenceTransformers** `all-MiniLM-L6-v2` (384-dim), stored in **SQLite** under `HOMEWORK_2/data/`, filename derived from sorted state codes (e.g. `nyt_ak_al_..._embed.db`).

### Search function

| Function | Purpose |
|----------|---------|
| **`setup_rag(cache_path, states, state_name_to_abbr, data_dir, rebuild=False, ...)`** | Load JSON → filter → open/create DB → build or reuse vector index. Returns an **`sqlite3.Connection`**. |
| **`semantic_search(conn, query, top_k=5)`** | Embed `query`, rank articles by cosine similarity (sqlite-vec **or** NumPy fallback on embedding blobs). Returns list of dicts: `id`, `score`, `text`, `web_url`, `pub_date`, `headline`. |
| **`retrieve_context(conn, query, top_k=8, min_score=None, allowed_urls=None)`** | Runs semantic search, optionally **restricts to URLs** marked relevant by Agent 1 (`allowed_urls`), applies **`min_score`** (e.g. `RAG_MIN_SIMILARITY` in `HW2_multi_agent.py`), formats concatenated text blocks for the LLM. |

**App behavior:** At startup, `HW2_app.py` calls `setup_rag` for **all** tracked state abbreviations so Compare States / Report can share one index. The pipeline may open a **smaller** two-state index if `rag_conn` is unavailable.

---

## 3. Tool / function reference

### Pipeline & agents (`HW2_multi_agent.py`)

| Name | Purpose | Key parameters | Returns |
|------|---------|----------------|---------|
| `get_openai_client` | Lazy OpenAI client using `OPENAI_API_KEY`. | — | OpenAI client |
| `load_rules` / `format_rules_for_prompt` | Load YAML rules and format for prompts. | path / rules section | dict / str |
| `safe_parse_json` | Parse LLM JSON (with simple `{...}` fallback). | `text` | object or `None` |
| `req_perform` / `req_perform_openai` | Chat completion; accumulate token counts. | content, prompt, model, `total_tokens_used` | str |
| `get_state_demographics` | **Census ACS5** (2023) for a state: income, population, % white. | `state_abbr` | dict or `None` |
| `build_gva_events_for_states` | Build event list from GVA + NYT cache for given abbreviations. | state list, `max_articles` | `(events, articles)` |
| `build_real_cache_inputs` | Two-state mode: events + candidate articles for Agent 1. | `state_a`, `state_b`, `max_articles` | `(events, articles)` |
| `agent1_validate_articles_parallel` | Parallel relevance checks for many articles. | articles, `total_tokens_used` | validated list |
| `agent1_relevant_urls` | URLs with `relevant=True`. | validated list | `set` of str |
| `agent2_build_state_summary` | Per-state coverage + demographics + outliers metadata. | validated, `all_events`, `state_a`, `state_b`, tokens | dict |
| `compute_state_comparison_stats` | Markdown + debug dict for stats (table, flags, speed notes). | `state_summary` | `(stats_markdown, debug)` |
| `extract_bullets` | Parse `-` / `*` lines from Agent 3 text. | `agent3_text` | `list[str]` |
| `agent3_format_bullets` | LLM: bullets only from precomputed stats (+ optional RAG). | `stats_markdown`, tokens, `rag_context` | str |
| `agent4_write_report` | LLM: final narrative. | `stats_markdown`, `agent3_bullets`, tokens | str |
| `run_agent_pipeline` | End-to-end Agents 2–4 (+ RAG for Agent 3). | `validated_articles`, `all_events`, `state_a`, `state_b`, `rag_conn` | dict with `agent2`, `agent3`, `agent4`, `tokens`, `stats_data`, `outlier_events`, `agent3_bullets`, … |

### RAG (`rag_setup.py`)

| Name | Purpose | Key parameters | Returns |
|------|---------|----------------|---------|
| `load_articles` | Read NYT cache JSON. | `cache_path` | `list[dict]` |
| `filter_articles_for_states` | State + keyword filter. | articles, states, `state_name_to_abbr`, `strict_event_keywords` | `list[dict]` |
| `article_to_embed_text` | Concatenate fields for embedding. | `doc` | str |
| `get_embed_model` / `embed` | Load MiniLM; embed one string. | text | `list[float]` |
| `connect_db` / `init_schema` / `build_index` | SQLite + vectors + insert articles. | path / conn / articles | — |
| `article_count` | Rows in `articles` table. | `conn` | int |
| `semantic_search` | Vector similarity search. | `conn`, `query`, `top_k` | `list[dict]` |
| `get_db_path` | Deterministic DB filename for state set. | states, `data_dir` | `Path` |
| `retrieve_context` | Search + filter URLs + min score → prompt text. | `conn`, `query`, `top_k`, `min_score`, `allowed_urls` | str |
| `setup_rag` | Full build-or-load pipeline. | cache, states, map, `data_dir`, `rebuild` | `sqlite3.Connection` |

### Shiny app (`HW2_app.py`)

| Output / effect | Purpose |
|-----------------|--------|
| `national_map` | U.S. choropleth from preloaded `national_stats`. |
| `comparison_section` | Two-state metrics, table, takeaway cards after **Run NYT coverage analysis**. |
| `handle_generate_report` | **Generate Report →** calls `run_agent_pipeline`. |
| `report_stats_table` | Structured stats UI (no raw PRECOMPUTED prompt). |
| `download_report_hw2` | Word export with real table + findings (via `_write_hw2_pipeline_docx`). |

---

## 4. Technical details

### API keys and external services

| Secret / service | Where | Notes |
|------------------|-------|--------|
| **`OPENAI_API_KEY`** | Environment or repo-root **`.env`** (loaded by app / multi-agent). | Required for agents. |
| **`NYT_API_KEY`** | Environment or **`.env`** | Used by `HOMEWORK_1/HW1_nyt_cache.py` to build/refresh the article cache (not required every run if JSON exists). |
| **U.S. Census Data API** | No key for many **ACS5** endpoints. | `get_state_demographics` uses `https://api.census.gov/data/2023/acs/acs5`. |

### Endpoints (reference)

- OpenAI: default client base URL (standard API).
- Census: `GET .../data/2023/acs/acs5?get=B19013_001E,B01003_001E,B02001_002E&for=state:{FIPS}`

### Python packages (main)

- **App / HW1 path:** `shiny`, `pandas`, `plotly`, `python-docx`, `requests`, `python-dotenv`, `markdown`, … — see `HOMEWORK_1/requirements.txt`.
- **HW2 pipeline:** `openai`, `pyyaml`, `pandas`, `requests`, …
- **RAG:** `sentence-transformers`, `torch`, `numpy`, `sqlite-vec` (with NumPy cosine fallback if vec extension unavailable).

### File structure (HW2-focused)

```
HOMEWORK_2/
  HW2_app.py           # Shiny UI + server
  HW2_multi_agent.py   # Agents, GVA/NYT wiring, CLI
  rag_setup.py         # Embeddings, SQLite index, retrieve_context
  04_rules.yaml        # Agent prompt rules
  data/                # RAG *.db files (generated)
  run_hw2_app.sh       # Launch app with repo .venv
  SYSTEM_DOCUMENTATION.md

HOMEWORK_1/
  nyt_2025_shootings_cache.json   # NYT articles (build with HW1 cache script)
  gva_mass_shootings-*.csv        # GVA export (path set in HW1_state_analysis / multi-agent)
  HW1_state_analysis.py           # run_state_analysis for Compare tab
  HW1_nyt_cache.py
  requirements.txt
```

### Constants worth knowing

- `HIGH_PROFILE_ARTICLE_THRESHOLD` (default **5**) — “outlier” incidents by article count.
- `RAG_MIN_SIMILARITY` (e.g. **0.35**) — floor for RAG chunks passed to Agent 3.
- `GVA_ARTICLE_MATCH_WINDOW_DAYS` — date window for matching articles to incidents.

---

## 5. Usage instructions

### 1. Clone and create a virtual environment

```bash
cd /path/to/sysen5381-1
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r HOMEWORK_1/requirements.txt
pip install openai pyyaml sentence-transformers sqlite-vec
# torch is pulled in by sentence-transformers; use PyTorch install docs if needed for your OS/GPU.
```

### 2. Configure API keys

Create a **`.env`** file in the **repository root** (same folder as `HOMEWORK_1/`):

```env
OPENAI_API_KEY=sk-...
NYT_API_KEY=your-nyt-key
```

Or export in the shell:

```bash
export OPENAI_API_KEY="sk-..."
export NYT_API_KEY="..."
```

### 3. Data setup

1. Place **GVA** CSV where the code expects it (see `GVA_PATH` in `HOMEWORK_1/HW1_state_analysis.py` and matching logic in `HW2_multi_agent.py`).
2. Build or copy **`HOMEWORK_1/nyt_2025_shootings_cache.json`** (NYT article cache). If missing, run the HW1 cache workflow / `load_or_build_2025_cache` path you use in class.

### 4. Run the Shiny app (recommended)

Use the **project venv** so RAG (`torch`) and Shiny match:

```bash
cd HOMEWORK_2
../.venv/bin/python -m shiny run HW2_app.py:app --port 8001
```

Or:

```bash
chmod +x HOMEWORK_2/run_hw2_app.sh
./HOMEWORK_2/run_hw2_app.sh 8001
```

**Important:** If `which shiny` points at **Anaconda**, use **`python -m shiny`** with **`.venv/bin/python`** so the RAG index loads with the same interpreter that has working `torch`.

Open **http://127.0.0.1:8001**. First startup may build the RAG SQLite index under `HOMEWORK_2/data/` (can take several minutes).

### 5. Run the CLI pipeline (optional)

```bash
cd HOMEWORK_2
export OPENAI_API_KEY="sk-..."
python HW2_multi_agent.py --real-cache --state-a IL --state-b MS --max-articles 120
```

Use `--help` for flags.

### 6. Troubleshooting

| Issue | What to try |
|-------|-------------|
| `RAG index failed` / `Tensor` import error | Run the app with **`.venv/bin/python -m shiny`**, not Conda’s `shiny`. Reinstall `torch` + `sentence-transformers` in that venv. |
| Empty RAG context for Agent 3 | Agent 1 allow-list may be empty; in the Shiny path, synthetic validation supplies URLs from matched GVA events. |
| Census `None` demographics | Network blocked or FIPS mapping issue; pipeline still runs with null demographics. |
| Map blank | Plotly CDN blocked in browser; check network / ad blockers. |

---

*Generated for course / project handoff. Update paths and package lists if your fork differs.*
