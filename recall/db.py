"""SQLite index with FTS5.

Schema is intentionally minimal: one `items` table with a contentless FTS5 mirror
for full-text search. All source-specific enrichment lives in a `meta` blob.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from recall import config

# Items table: stable id (source:hash) so re-indexing is idempotent.
SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT,
    snippet     TEXT,
    url         TEXT,
    app         TEXT,
    ts          REAL NOT NULL,
    extra       TEXT
);

CREATE INDEX IF NOT EXISTS items_source_ts ON items(source, ts DESC);
CREATE INDEX IF NOT EXISTS items_ts         ON items(ts DESC);

-- FTS5 mirror. content='items' (contentless) keeps it fast; we manage sync.
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title, snippet, url, content='items', content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, snippet, url)
    VALUES (new.rowid, new.title, new.snippet, new.url);
END;
CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, snippet, url)
    VALUES ('delete', old.rowid, old.title, old.snippet, old.url);
END;
CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, snippet, url)
    VALUES ('delete', old.rowid, old.title, old.snippet, old.url);
    INSERT INTO items_fts(rowid, title, snippet, url)
    VALUES (new.rowid, new.title, new.snippet, new.url);
END;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    config.ensure_home()
    # check_same_thread=False so the HTTP server's thread pool can share the
    # connection safely; we serialize writes via SQLite's own locking.
    conn = sqlite3.connect(str(config.INDEX_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # safer concurrent access when watch is running and UI is open
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init() -> None:
    """Create tables if missing. Idempotent."""
    global _conn
    _conn = _connect()
    _conn.executescript(SCHEMA)
    _conn.commit()


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        init()
    assert _conn is not None
    return _conn


def upsert(item: dict) -> bool:
    """Insert-or-replace one item by id. Returns True if newly inserted."""
    c = conn()
    cur = c.execute("SELECT 1 FROM items WHERE id = ?", (item["id"],))
    exists = cur.fetchone() is not None
    c.execute(
        """INSERT OR REPLACE INTO items
           (id, source, title, snippet, url, app, ts, extra)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item["id"],
            item.get("source", ""),
            item.get("title"),
            item.get("snippet"),
            item.get("url"),
            item.get("app"),
            float(item.get("ts", time.time())),
            json.dumps(item.get("extra", {})) if item.get("extra") else None,
        ),
    )
    c.commit()
    return not exists


def upsert_many(items: Iterable[dict]) -> int:
    """Bulk insert. Returns count of new items."""
    n_new = 0
    c = conn()
    for it in items:
        cur = c.execute("SELECT 1 FROM items WHERE id = ?", (it["id"],))
        if cur.fetchone() is None:
            n_new += 1
    c.executemany(
        """INSERT OR REPLACE INTO items
           (id, source, title, snippet, url, app, ts, extra)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            (
                it["id"],
                it.get("source", ""),
                it.get("title"),
                it.get("snippet"),
                it.get("url"),
                it.get("app"),
                float(it.get("ts", time.time())),
                json.dumps(it.get("extra", {})) if it.get("extra") else None,
            )
            for it in items
        ),
    )
    c.commit()
    return n_new


def query_fts(query: str, limit: int = 20) -> list[dict]:
    """Run a full-text query. Returns rows ordered by BM25 + recency tiebreak."""
    c = conn()
    fts_q = _build_fts_query(query)
    rows = c.execute(
        """
        SELECT items.*, bm25(items_fts) AS score
        FROM items_fts
        JOIN items ON items.rowid = items_fts.rowid
        WHERE items_fts MATCH ?
        ORDER BY score ASC, items.ts DESC
        LIMIT ?
        """,
        (fts_q, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    if d.get("extra"):
        try:
            d["extra"] = json.loads(d["extra"])
        except Exception:
            d["extra"] = {}
    return d


def _build_fts_query(q: str) -> str:
    """Convert a user query into a safe FTS5 MATCH expression.

    We tokenize on whitespace, append '*' for prefix match, and quote any token
    that has special chars. AND-combined.
    """
    import re

    tokens = [t for t in re.split(r"\s+", q.strip()) if t]
    if not tokens:
        return '""'
    out: list[str] = []
    for t in tokens:
        # escape internal quotes
        clean = t.replace('"', '""')
        # if user already used operators, leave as-is; otherwise prefix-match
        if re.search(r"[*:^\(\)]", t):
            out.append(f'"{clean}"')
        else:
            out.append(f'"{clean}"*')
    return " ".join(out)


def stats() -> dict:
    c = conn()
    total = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    by_src = dict(
        c.execute("SELECT source, COUNT(*) FROM items GROUP BY source").fetchall()
    )
    last = c.execute("SELECT value FROM meta WHERE key = 'last_index_ts'").fetchone()
    size = config.INDEX_PATH.stat().st_size if config.INDEX_PATH.exists() else 0

    from sources.live_status import live_status as _live  # avoid cycle at import
    return {
        "total": total,
        "by_source": by_src,
        "last_index": last[0] if last else None,
        "size_mb": size / (1024 * 1024),
        "live_sources": _live(),
    }


def mark_indexed(n: int) -> None:
    import datetime
    c = conn()
    c.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_index_ts', ?)",
        (datetime.datetime.now().isoformat(timespec="seconds"),),
    )
    c.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_index_count', ?)",
        (str(n),),
    )
    c.commit()


def prune(retention_days: int) -> int:
    """Delete items older than retention_days. 0 = keep all. Returns deleted count."""
    if retention_days <= 0:
        return 0
    cutoff = time.time() - retention_days * 86400
    c = conn()
    cur = c.execute("DELETE FROM items WHERE ts < ?", (cutoff,))
    c.commit()
    return cur.rowcount
