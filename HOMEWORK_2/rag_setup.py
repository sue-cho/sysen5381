from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional, Set

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlite_vec import load as sqlite_vec_load, serialize_float32

EMBED_MODEL = "all-MiniLM-L6-v2"
VEC_DIM = 384

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
_SQLITE_VEC_ACTIVE = False


def load_articles(cache_path: Path) -> List[dict]:
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "docs" in data:
        return list(data["docs"])
    if isinstance(data, list):
        return data
    raise ValueError('Cache must be a JSON list of articles or {"docs": [...]}')


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


def filter_articles_for_states(
    articles: List[dict],
    states: List[str],
    state_name_to_abbr: dict,
    strict_event_keywords: bool = True,
) -> List[dict]:
    """
    Filter NYT cache articles to those mentioning selected states.
    """
    states_norm = [s.strip().upper() for s in states if str(s).strip()]
    abbr_to_name = {str(v).upper(): str(k) for k, v in state_name_to_abbr.items()}
    state_names = [abbr_to_name.get(s, s).lower() for s in states_norm]
    state_abbrs = [s.lower() for s in states_norm]

    out: List[dict] = []
    for a in articles:
        blob = _combined_headline_abstract_snippet(a)
        blob_lower = blob.lower()
        if not any(token in blob_lower for token in (state_names + state_abbrs)):
            continue
        if strict_event_keywords and not _matches_event_keywords(blob_lower):
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
    # Be explicit and resilient across reruns.
    conn.execute("DROP TABLE IF EXISTS vec_chunks")
    conn.execute("DROP TABLE IF EXISTS articles")
    conn.commit()
    if _SQLITE_VEC_ACTIVE:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
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
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                embedding float[{VEC_DIM}] distance_metric=cosine
            )
            """
        )
        conn.execute("DELETE FROM vec_chunks")
        conn.execute("DELETE FROM articles")
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                embed_text TEXT NOT NULL,
                web_url TEXT,
                pub_date TEXT,
                headline TEXT,
                embedding BLOB NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM articles")
    conn.commit()


def article_count(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) FROM articles").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _db_has_vec_chunks(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'vec_chunks'").fetchone()
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
            conn.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)", (i, blob))
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
              AND k = ?
            ORDER BY distance
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
            "Rebuild the index from this module with sqlite-vec unavailable, or run in an environment with extension support."
        )

    if not use_numpy:
        return []

    q = np.asarray(query_vec, dtype=np.float32)
    qn = float(np.linalg.norm(q)) + 1e-12
    rows = conn.execute("SELECT id, embed_text, web_url, pub_date, headline, embedding FROM articles").fetchall()
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


def get_db_path(states: List[str], data_dir: Path) -> Path:
    state_key = "_".join(sorted([s.upper() for s in states])).lower()
    return data_dir / f"nyt_{state_key}_embed.db"


def _rag_url_key(url: Optional[str]) -> str:
    return (url or "").strip()


def retrieve_context(
    conn: sqlite3.Connection,
    query: str,
    top_k: int = 8,
    min_score: Optional[float] = None,
    allowed_urls: Optional[Collection[str]] = None,
) -> str:
    """
    allowed_urls: When set, only indexed articles whose web_url is in this set are eligible
    (use Agent 1 relevant=true URLs). Results are ranked by embedding similarity to `query`.
    When None, no URL filter (e.g. standalone RAG smoke test).
    """
    n_articles = article_count(conn)
    use_allow = allowed_urls is not None
    allowed: Set[str] = {_rag_url_key(u) for u in (allowed_urls or ()) if u}

    if use_allow:
        if not allowed:
            print(
                "[RAG] allowed_urls is empty (no Agent 1 relevant=true); no RAG context for Agent 3.",
                flush=True,
            )
            return ""
        pool_k = max(n_articles, 1)
    else:
        pool_k = top_k

    hits = semantic_search(conn, query, top_k=pool_k)
    if not hits:
        return ""

    if use_allow:
        before_n = len(hits)
        hits = [h for h in hits if _rag_url_key(h.get("web_url")) in allowed]
        if before_n and not hits:
            print(
                f"[RAG] None of {before_n} ranked article(s) appear in the Agent 1 relevant=true allow-list.",
                flush=True,
            )
            return ""

    if min_score is not None:
        best = max(float(h.get("score") or 0.0) for h in hits)
        filtered = [h for h in hits if float(h.get("score") or 0.0) >= float(min_score)]
        if not filtered:
            print(
                f"[RAG] min_score={min_score} dropped all {len(hits)} hit(s); "
                f"best similarity was {best:.3f} (lower threshold or None to include chunks).",
                flush=True,
            )
            return ""
        hits = filtered

    hits = hits[:top_k]
    blocks: List[str] = []
    for i, h in enumerate(hits, start=1):
        pub = str(h.get("pub_date") or "")
        pub_short = pub[:10] if pub else "unknown"
        blocks.append(
            f"--- Retrieved item {i} (similarity: {h['score']:.3f}, date: {pub_short}) ---\n{h['text']}"
        )
    return "\n\n".join(blocks)


def setup_rag(
    cache_path: Path,
    states: List[str],
    state_name_to_abbr: dict,
    data_dir: Path,
    rebuild: bool = False,
    strict_event_keywords: bool = True,
) -> sqlite3.Connection:
    all_docs = load_articles(cache_path)
    filtered = filter_articles_for_states(all_docs, states, state_name_to_abbr, strict_event_keywords)
    print(f"[RAG] {len(all_docs)} total articles -> {len(filtered)} after state+keyword filter")

    db_path = get_db_path(states, data_dir)
    if rebuild and db_path.exists():
        db_path.unlink()
        print(f"[RAG] Dropped existing index at {db_path}")

    conn = connect_db(db_path)
    n = article_count(conn)
    if rebuild or n == 0:
        print(f"[RAG] Building new index for {states}...")
        init_schema(conn)
        build_index(conn, filtered)
        print(f"[RAG] Indexed {article_count(conn)} articles -> {db_path}")
    else:
        print(f"[RAG] Loaded existing index: {n} articles from {db_path}")
    return conn


if __name__ == "__main__":
    import sys

    CACHE = Path("HOMEWORK_1/nyt_2025_shootings_cache.json")
    DATA = Path("HOMEWORK_2/data")

    STATE_NAME_TO_ABBR = {
        "Ohio": "OH",
        "Louisiana": "LA",
    }

    print("=== RAG STANDALONE TEST ===")
    conn = setup_rag(
        cache_path=CACHE,
        states=["OH", "LA"],
        state_name_to_abbr=STATE_NAME_TO_ABBR,
        data_dir=DATA,
        rebuild=True,
    )
    try:
        query = "shooting violence coverage patterns Ohio Louisiana"
        print(f"\nSemantic search: '{query}'")
        context = retrieve_context(conn, query, top_k=3)
        print(context if context else "No results returned.")
    finally:
        conn.close()
    print("\n=== TEST COMPLETE ===")
