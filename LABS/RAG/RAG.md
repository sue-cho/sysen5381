# NYT metadata RAG (`nyt_framing_rag.py`)

This folder includes a small RAG pipeline for **framing analysis** of New York Times coverage using **metadata only** (headline, abstract, snippet, keywords, date, and lead paragraph when present). There is **no full article body** in the cache.

The implementation follows the same embedding stack as [`05_embed.py`](05_embed.py) (sentence-transformers `all-MiniLM-L6-v2`, 384-dimensional vectors). Retrieval uses either **sqlite-vec** KNN inside SQLite or a **NumPy cosine-similarity** fallback when your Python build cannot load SQLite extensions (common on some Python 3.14 installs).

---

## Corpus and what gets embedded

1. **Source**: [`HOMEWORK_1/nyt_2025_shootings_cache.json`](../HOMEWORK_1/nyt_2025_shootings_cache.json) (list of NYT Article Search API `docs`).
2. **Filter** (`filter_new_orleans_90d_from_2025_01_01`):
   - `pub_date` on or after **2025-01-01** and **before** **2025-01-01 + 90 days** (through **2025-03-31** inclusive).
   - **“New Orleans”** must appear in headline, abstract, or snippet (case-insensitive).
   - By default, at least one **event** keyword must appear in that combined text (e.g. attack, terror, French Quarter, Bourbon, killed). Use CLI `--no-strict-keywords` to disable that extra filter.
3. **One text field per article** (`article_to_embed_text`) used both for **embedding** and as **LLM context**:

```text
Headline: ...
Abstract: ...
Snippet: ...
Keywords: ...
Date: ...
```

If the API included a lead paragraph, a final line `Lead paragraph: ...` is appended.

Keywords are deduplicated and formatted as `Name: value` pairs joined with `; `.

Indexed rows are stored in `data/nyt_nola_90d_embed.db` (see `DB_PATH` in the script).

---

## Search function: `semantic_search(conn, query, top_k=5)`

**Purpose**: Turn the user’s natural-language string into an embedding, compare it to every stored article embedding, and return the **top_k** most similar articles.

**Steps**

1. Encode `query` with the same `SentenceTransformer` model as the index (`embed()`).
2. **If** the database has a `vec_chunks` sqlite-vec table **and** the sqlite-vec extension loaded successfully at connect time:
   - Serialize the query vector as float32 and run `WHERE embedding MATCH ?` with `ORDER BY distance` and `LIMIT top_k` (cosine distance in the virtual table).
   - Each result’s **`score`** is `1 - distance` (higher = more similar).
3. **Else**, if the `articles` table has an **`embedding` BLOB** column (fallback index):
   - Load all stored vectors, compute **cosine similarity** in NumPy between the query vector and each row, sort descending, take **top_k**.
   - **`score`** is that cosine similarity (roughly comparable as “higher = more similar,” but not identical numerically to the sqlite-vec branch).

**Return value**: A list of dictionaries, each with:

| Field       | Meaning                                      |
|------------|-----------------------------------------------|
| `id`       | Integer row id (build order in the index)     |
| `score`    | Similarity (see above)                        |
| `text`     | Full metadata block used for embedding/RAG    |
| `web_url`  | Article URL when present                      |
| `pub_date` | ISO timestamp string when present             |
| `headline` | Main headline when present                    |

**CLI**: `python nyt_framing_rag.py --search "your words here" --top-k 5`  
Prints **JSON** (pretty-printed) of that list.

---

## Query (user input) in the RAG step

For **framing analysis**, the “query” is your **analytical focus**: what you want the model to emphasize when comparing retrieved pieces (e.g. victims vs policy, security, terrorism framing, timing of coverage).

**CLI**: `python nyt_framing_rag.py --query "..." --retrieve-k 8`

- **`--retrieve-k`**: How many articles `semantic_search` passes into the LLM (default **8**). Increase if you want a wider slice of the corpus; decrease for a tighter, more homogeneous context.
- **`--model`**: Ollama Cloud model name (default **`gpt-oss:20b-cloud`**).

**API flow** (`rag_framing_analysis`):

1. `hits = semantic_search(conn, user_query, top_k=retrieve_k)`.
2. Build a **user message** containing:
   - The **user analytical focus / query** verbatim.
   - A **retrieved corpus**: each hit as a block  
     `--- Retrieved item i (similarity score ...) ---`  
     followed by the metadata `text` for that article.
3. Send one chat request to **Ollama Cloud** (`https://ollama.com/api/chat`) with:
   - **system** = framing prompt below,
   - **user** = that combined message.

**Authentication**: Set **`OLLAMA_API_KEY`** in the repository [`.env`](../../.env) (loaded via `python-dotenv` from repo root).

---

## System prompt (role)

The system message instructs the model to act as a **communications scholar**, use **only** the supplied metadata, avoid **per-article sequential summaries**, avoid **speculation** beyond the text, and produce **three sections**:

1. **`## Framing overview`** — one paragraph on dominant cross-article framing.
2. **`## Key themes`** — bullet list of themes grounded in the metadata.
3. **`## Observed patterns in coverage`** — one paragraph on convergence or variation in emphasis and narrative focus.

The exact string is in the script as `FRAMING_SYSTEM_PROMPT` in [`nyt_framing_rag.py`](nyt_framing_rag.py).

---

## Results

### After `--search`

- **Format**: JSON array of objects (`id`, `score`, `text`, `web_url`, `pub_date`, `headline`).
- **Use**: Inspect which articles the retriever associates with your wording; tune the query or `top_k` before running the LLM.

### After `--query`

- **Format**: **Markdown-style** prose with the three required headings (model output may include minor formatting variation).
- **Content**: Synthesis across the retrieved set, **not** a digest of each article. Quality depends on how informative the metadata is; the prompt explicitly allows saying when evidence is thin.

If retrieval returns no rows, the script prints a short message instead of calling the API.

---

## Setup and rebuild

```bash
cd LABS/RAG
pip install sentence-transformers sqlite-vec requests python-dotenv
python nyt_framing_rag.py --rebuild
python nyt_framing_rag.py --search "French Quarter and victims" --top-k 5
python nyt_framing_rag.py --query "How is terrorism framing balanced against local impact?" --retrieve-k 8
```

- **`--rebuild`**: Deletes the existing SQLite file (if present) and re-embeds the filtered corpus.
- If the DB was built with sqlite-vec but you open it from a Python that cannot load extensions, rebuild with the same interpreter you use for queries (`--rebuild`), or use an environment where `enable_load_extension` works.

---

## Relation to `05_embed.py`

| Piece | `05_embed.py` | `nyt_framing_rag.py` |
|--------|----------------|----------------------|
| Chunks | Sentences from one `.txt` file | One row per filtered NYT article |
| Search | `search_embed_sql` | `semantic_search` (+ NumPy fallback) |
| LLM | `agent_run` + custom `role` | `agent_run` + `FRAMING_SYSTEM_PROMPT` |
| Local Ollama | Often started via `01_ollama.py` | Not required; cloud API only for this script |

For the generic lab exercise description, see [`LAB_custom_rag_query.md`](LAB_custom_rag_query.md).
