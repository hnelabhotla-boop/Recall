"""Generic Chromium-based browser history indexer (Chrome/Brave/Arc/Edge).

All four store history in the same SQLite schema. The only thing that changes
is the file path. We use a `mode=ro` SQLite URI so the browser can keep
writing while we read.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from sources._util import now, stable_id


# We expect this module to be imported multiple times with different
# `__name__`, so we infer the source name from the file name.
SOURCE_NAME = Path(__file__).stem.replace("_history", "")


# Common path candidates per browser
CANDIDATES: dict[str, list[str]] = {
    "chrome": [
        "Library/Application Support/Google/Chrome/Default/History",
        "Library/Application Support/Google/Chrome/Profile 1/History",
        "Library/Application Support/Google/Chrome/Default/History",
    ],
    "brave": [
        "Library/Application Support/BraveSoftware/Brave-Browser/Default/History",
    ],
    "arc": [
        "Library/Application Support/Arc/User Data/Stable_Default/History",
        "Library/Application Support/Arc/User Data/Default/History",
    ],
    "edge": [
        "Library/Application Support/Microsoft Edge/Default/History",
    ],
}


def _find_db() -> Path | None:
    for rel in CANDIDATES.get(SOURCE_NAME, []):
        p = Path.home() / rel
        if p.exists():
            return p
    return None


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def iter_items(since_ts: float) -> list[dict]:
    db_path = _find_db()
    if not db_path:
        return []
    out: list[dict] = []
    try:
        # Chromium uses Windows epoch (1601-01-01) in microseconds
        # since_ts is unix epoch seconds, so convert: ts_chrome = (ts - epoch) * 1e6
        chrome_epoch_unix = -11644473600  # unix seconds of 1601-01-01
        since_chrome = max(0, int((since_ts + chrome_epoch_unix) * 1_000_000)) if since_ts else 0
        conn = _connect_ro(db_path)
        cur = conn.execute(
            """
            SELECT url, title, last_visit_time
            FROM urls
            WHERE last_visit_time > ?
            ORDER BY last_visit_time DESC
            LIMIT 5000
            """,
            (since_chrome,),
        )
        for url, title, lvt in cur:
            ts = (lvt / 1_000_000) - chrome_epoch_unix
            out.append({
                "id": stable_id(SOURCE_NAME, url, int(ts)),
                "source": SOURCE_NAME,
                "title": title or url,
                "snippet": title or url,
                "url": url,
                "app": SOURCE_NAME.capitalize(),
                "ts": float(ts),
            })
        conn.close()
    except Exception:
        pass
    return out


def poll_once() -> list[dict]:
    return []
