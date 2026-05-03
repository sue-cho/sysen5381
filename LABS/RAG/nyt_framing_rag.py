# nyt_framing_rag.py
# NYT metadata RAG: embed headline/abstract/snippet/keywords (no full text),
# semantic search (sqlite-vec + sentence-transformers), framing analysis via Ollama Cloud.
#
# pip install sentence-transformers sqlite-vec requests python-dotenv
# Set OLLAMA_API_KEY in repo .env for the analysis step.

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sqlite_vec import load as sqlite_vec_load, serialize_float32

# --- Paths & config ----------------------------------------------------------

RAG_DIR = Path(__file__).resolve().parent
REPO_ROOT = RAG_DIR.parent.parent
DEFAULT_CACHE_PATH = REPO_ROOT / "HOMEWORK_1" / "nyt_2025_shootings_cache.json"
ENV_PATH = REPO_ROOT / ".env"
DATA_DIR = RAG_DIR / "data"
DB_PATH = DATA_DIR / "nyt_nola_90d_embed.db"

ANCHOR_DATE = date(2025, 1, 1)
WINDOW_DAYS = 90
END_EXCLUSIVE = ANCHOR_DATE + timedelta(days=WINDOW_DAYS)  # 2025-04-01; keep d < this

EMBED_MODEL = "all-MiniLM-L6-v2"
VEC_DIM = 384
OLLAMA_CLOUD_MODEL = "gpt-oss:20b-cloud"
OLLAMA_CHAT_URL = "https://ollama.com/api/chat"

EVENT_KEYWORDS = (
    "attack",
    "shooting",
    "bourbon",
    "french quarter",
    "terror",
    "killed",
    "gunman",
    "vehicle",
    "truck",
    "crowd",
    "mass shooting",
)

_embed_model: Optional[SentenceTransformer] = None

# True after connect_db() if sqlite-vec extension loaded; else NumPy cosine on BLOBs.
_SQLITE_VEC_ACTIVE = False


# =============================================================================
# Step 1: Load JSON, filter corpus, build one string per article for embedding
# =============================================================================


def load_articles(cache_path: Path) -> List[dict]:
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "docs" in data:
        return list(data["docs"])
    if isinstance(data, list):
        return data
    raise ValueError("Cache must be a JSON list of articles or {\"docs\": [...]}")


def _parse_pub_date(doc: dict) -> Optional[date]:
    raw = doc.get("pub_date")
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _combined_headline_abstract_snippet(doc: dict) -> str:
    h = (doc.get("headline") or {}).get("main") or ""
    ab = doc.get("abstract") or ""
    sn = doc.get("snippet") or ""
    return f"{h} {ab} {sn}"


def _matches_event_keywords(blob: str) -> bool:
    low = blob.lower()
    return any(kw in low for kw in EVENT_KEYWORDS)


def filter_new_orleans_90d_from_2025_01_01(
    articles: List[dict],
    strict_event_keywords: bool = True,
) -> List[dict]:
    out: List[dict] = []
    for a in articles:
        d = _parse_pub_date(a)
        if d is None or d < ANCHOR_DATE or d >= END_EXCLUSIVE:
            continue
        blob = _combined_headline_abstract_snippet(a)
        if "new orleans" not in blob.lower():
            continue
        if strict_event_keywords and not _matches_event_keywords(blob):
            continue
        out.append(a)
    return out


def _format_keywords(doc: dict) -> str:
    kws = doc.get("keywords")
    if not kws or not isinstance(kws, list):
        return ""
    seen: set = set()
    parts: List[str] = []
    for item in kws:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        value = (item.get("value") or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        if name:
            parts.append(f"{name}: {value}")
        else:
            parts.append(value)
    return "; ".join(parts)


def article_to_embed_text(doc: dict) -> str:
    headline = (doc.get("headline") or {}).get("main") or ""
    abstract = doc.get("abstract") or ""
    snippet = doc.get("snippet") or ""
    keywords = _format_keywords(doc)
    pub = doc.get("pub_date") or ""
    lines = [
        f"Headline: {headline}",
        f"Abstract: {abstract}",
        f"Snippet: {snippet}",
        f"Keywords: {keywords}",
        f"Date: {pub}",
    ]
    lead = doc.get("lead_paragraph")
    if isinstance(lead, str) and lead.strip():
        lines.append(f"Lead paragraph: {lead.strip()}")
    return "\n".join(lines)


# =============================================================================
# Step 2: Embeddings + sqlite-vec index + semantic_search
# =============================================================================


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def embed(text: str) -> List[float]:
    m = get_embed_model()
    vec = m.encode(text)
    return vec.tolist()


def connect_db(path: Path) -> sqlite3.Connection:
    global _SQLITE_VEC_ACTIVE
    _SQLITE_VEC_ACTIVE = False
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    if not hasattr(conn, "enable_load_extension"):
        return conn
    try:
        conn.enable_load_extension(True)
        sqlite_vec_load(conn)
        _SQLITE_VEC_ACTIVE = True
    except Exception:
        _SQLITE_VEC_ACTIVE = False
    finally:
        try:
            conn.enable_load_extension(False)
        except AttributeError:
            pass
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS vec_chunks")
    conn.execute("DROP TABLE IF EXISTS articles")
    if _SQLITE_VEC_ACTIVE:
        conn.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                embed_text TEXT NOT NULL,
                web_url TEXT,
                pub_date TEXT,
                headline TEXT
            )
            """
        )
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE vec_chunks USING vec0(
                embedding float[{VEC_DIM}] distance_metric=cosine
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                embed_text TEXT NOT NULL,
                web_url TEXT,
                pub_date TEXT,
                headline TEXT,
                embedding BLOB NOT NULL
            )
            """
        )
    conn.commit()


def article_count(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) FROM articles").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _db_has_vec_chunks(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'vec_chunks'"
    ).fetchone()
    return row is not None


def _db_articles_have_embedding_blob(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA table_info(articles)").fetchall()
    return any(r[1] == "embedding" for r in rows)


def build_index(conn: sqlite3.Connection, articles: List[dict]) -> None:
    mode = "sqlite-vec" if _SQLITE_VEC_ACTIVE else "numpy-fallback (no SQLite extension)"
    print(f"Embedding {len(articles)} articles with {EMBED_MODEL} [{mode}]...")
    for i, doc in enumerate(articles):
        text_body = article_to_embed_text(doc)
        vec = embed(text_body)
        blob = serialize_float32(vec)
        headline = (doc.get("headline") or {}).get("main") or ""
        web_url = doc.get("web_url") or ""
        pub_date = doc.get("pub_date") or ""
        if _SQLITE_VEC_ACTIVE:
            conn.execute(
                "INSERT INTO articles (id, embed_text, web_url, pub_date, headline) VALUES (?, ?, ?, ?, ?)",
                (i, text_body, web_url, pub_date, headline),
            )
            conn.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (i, blob),
            )
        else:
            conn.execute(
                "INSERT INTO articles (id, embed_text, web_url, pub_date, headline, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                (i, text_body, web_url, pub_date, headline, blob),
            )
    conn.commit()
    print("Index built.")


def semantic_search(conn: sqlite3.Connection, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    query_vec = embed(query)
    use_vec_sql = _db_has_vec_chunks(conn) and _SQLITE_VEC_ACTIVE
    use_numpy = _db_articles_have_embedding_blob(conn)

    if use_vec_sql:
        query_blob = serialize_float32(query_vec)
        cur = conn.execute(
            """
            SELECT rowid, distance
            FROM vec_chunks
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (query_blob, top_k),
        )
        rows = cur.fetchall()
        if not rows:
            return []
        out: List[Dict[str, Any]] = []
        for rowid, distance in rows:
            r = conn.execute(
                "SELECT embed_text, web_url, pub_date, headline FROM articles WHERE id = ?",
                (rowid,),
            ).fetchone()
            if not r:
                continue
            embed_text, web_url, pub_date, headline = r
            out.append(
                {
                    "id": rowid,
                    "score": 1 - distance,
                    "text": embed_text,
                    "web_url": web_url,
                    "pub_date": pub_date,
                    "headline": headline,
                }
            )
        return out

    if _db_has_vec_chunks(conn) and not _SQLITE_VEC_ACTIVE:
        raise RuntimeError(
            "This database was built with sqlite-vec, but SQLite cannot load extensions in this Python build. "
            "Run again with: python nyt_framing_rag.py --rebuild"
        )

    if not use_numpy:
        return []

    q = np.asarray(query_vec, dtype=np.float32)
    qn = float(np.linalg.norm(q)) + 1e-12
    rows = conn.execute(
        "SELECT id, embed_text, web_url, pub_date, headline, embedding FROM articles"
    ).fetchall()
    if not rows:
        return []
    scored: List[tuple] = []
    for rowid, embed_text, web_url, pub_date, headline, blob in rows:
        v = np.frombuffer(blob, dtype=np.float32)
        vn = float(np.linalg.norm(v)) + 1e-12
        sim = float(np.dot(q, v) / (qn * vn))
        scored.append((sim, rowid, embed_text, web_url, pub_date, headline))
    scored.sort(key=lambda x: -x[0])
    out = []
    for sim, rowid, embed_text, web_url, pub_date, headline in scored[:top_k]:
        out.append(
            {
                "id": rowid,
                "score": sim,
                "text": embed_text,
                "web_url": web_url,
                "pub_date": pub_date,
                "headline": headline,
            }
        )
    return out


# =============================================================================
# Step 3: Ollama Cloud RAG framing analysis
# =============================================================================


def agent_run(role: str, task: str, model: str = OLLAMA_CLOUD_MODEL) -> str:
    key = os.getenv("OLLAMA_API_KEY")
    if not key:
        raise ValueError("OLLAMA_API_KEY not found in environment (.env).")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": role},
            {"role": "user", "content": task},
        ],
        "stream": False,
    }
    response = requests.post(
        OLLAMA_CHAT_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


FRAMING_SYSTEM_PROMPT = """You are a communications scholar analyzing New York Times coverage using only the metadata supplied (headlines, abstracts, snippets, and keywords). Write in a neutral, academic research tone.

Your task is to identify cross-cutting patterns across the retrieved items: recurring themes, framing choices, and emphasis (for example crime or law enforcement, policy or reform, victims or community, security or infrastructure, political or institutional actors). Note differences in narrative focus where the metadata permits comparison.

Rules:
- Ground every claim in the provided text only. Do not invent facts, unnamed sources, or motives not supported by the metadata.
- Do not summarize each article in sequence. Synthesize across the set.
- If the metadata is too thin to support a point, say so briefly rather than speculating.

Required output structure (use these headings):
## Framing overview
One paragraph synthesizing dominant framing patterns across the coverage.

## Key themes
- Bullet points listing distinct themes supported by the metadata.

## Observed patterns in coverage
One paragraph describing how emphasis, framing, or narrative focus varies or converges across pieces."""


def rag_framing_analysis(
    user_query: str,
    conn: sqlite3.Connection,
    retrieve_k: int = 8,
    model: str = OLLAMA_CLOUD_MODEL,
) -> str:
    hits = semantic_search(conn, user_query, top_k=retrieve_k)
    if not hits:
        return "No retrieved articles; index may be empty or the query matched nothing."

    blocks = []
    for i, h in enumerate(hits, start=1):
        blocks.append(f"--- Retrieved item {i} (similarity score {h['score']:.4f}) ---\n{h['text']}")
    corpus = "\n\n".join(blocks)

    user_message = (
        f"User analytical focus / query:\n{user_query}\n\n"
        f"Retrieved NYT article metadata (use only this as evidence):\n\n{corpus}"
    )
    return agent_run(FRAMING_SYSTEM_PROMPT, user_message, model=model)


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    load_dotenv(ENV_PATH, override=False)

    parser = argparse.ArgumentParser(description="NYT metadata RAG: embed, search, framing analysis.")
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="Path to nyt_2025_shootings_cache.json",
    )
    parser.add_argument("--rebuild", action="store_true", help="Drop and rebuild the embedding database.")
    parser.add_argument(
        "--no-strict-keywords",
        action="store_true",
        help="Disable event-keyword filter (keep all NOLA articles in the 90-day window).",
    )
    parser.add_argument("--query", type=str, default="", help="User query for framing analysis (Ollama Cloud).")
    parser.add_argument("--search", type=str, default="", help="Run semantic search only; print JSON-like results.")
    parser.add_argument("--top-k", type=int, default=5, help="top_k for semantic search (default 5).")
    parser.add_argument("--retrieve-k", type=int, default=8, help="Articles to retrieve for RAG (default 8).")
    parser.add_argument("--model", type=str, default=OLLAMA_CLOUD_MODEL, help="Ollama Cloud model name.")
    args = parser.parse_args()

    strict_kw = not args.no_strict_keywords
    all_docs = load_articles(args.cache)
    filtered = filter_new_orleans_90d_from_2025_01_01(all_docs, strict_event_keywords=strict_kw)
    print(f"Loaded {len(all_docs)} articles from cache; {len(filtered)} after NOLA + 90-day window filter (strict_event_keywords={strict_kw}).")

    if args.rebuild and DB_PATH.exists():
        DB_PATH.unlink()

    conn = connect_db(DB_PATH)
    try:
        n = article_count(conn)
        if args.rebuild or n == 0:
            init_schema(conn)
            build_index(conn, filtered)
            print(f"Indexed {article_count(conn)} articles -> {DB_PATH}")

        if args.search:
            results = semantic_search(conn, args.search, top_k=args.top_k)
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if args.query:
            text = rag_framing_analysis(
                args.query,
                conn,
                retrieve_k=args.retrieve_k,
                model=args.model,
            )
            print(text)
            return

        print("No --query or --search given. Example:\n"
              f"  python {Path(__file__).name} --search \"victims and policy\" --top-k 5\n"
              f"  python {Path(__file__).name} --query \"How is policy versus crime emphasized?\" --retrieve-k 8")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
