"""Safari history indexer (read-only)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from sources._util import now, stable_id

HISTORY = Path.home() / "Library/Safari/History.db"


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Open a SQLite DB in read-only mode so Safari can keep writing."""
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def iter_items(since_ts: float) -> list[dict]:
    if not HISTORY.exists():
        return []
    out: list[dict] = []
    try:
        conn = _connect_readonly(HISTORY)
        cur = conn.execute(
            """
            SELECT hi.id, hi.url, COALESCE(hi.title, ''), hv.visit_time
            FROM history_items hi
            JOIN history_visits hv ON hv.history_item = hi.id
            WHERE hv.visit_time > ?
            ORDER BY hv.visit_time DESC
            LIMIT 5000
            """,
            (since_ts or 0,),
        )
        seen = set()
        for row_id, url, title, vt in cur:
            # dedupe by URL, keep most recent visit
            if url in seen:
                continue
            seen.add(url)
            # Safari stores visit_time as seconds since 2001-01-01 (Mac epoch)
            ts = vt + 978307200
            out.append({
                "id": stable_id("safari", url, int(ts)),
                "source": "safari",
                "title": title or url,
                "snippet": title or url,
                "url": url,
                "app": "Safari",
                "ts": float(ts),
            })
        conn.close()
    except Exception:
        pass
    return out


def poll_once() -> list[dict]:
    return []
