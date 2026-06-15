"""Search wrapper + result formatting."""

from __future__ import annotations

import datetime as _dt
import time

from recall import db


SOURCE_BADGES = {
    "clipboard":   "📋",
    "safari":      "🧭",
    "chrome":      "🌐",
    "brave":       "🦁",
    "arc":         "🌀",
    "edge":        "🟦",
    "notes":       "📝",
    "shell":       "⌨️ ",
    "recent_files":"📁",
    "mail":        "✉️ ",
    "slack":       "💬",
    "discord":     "🎮",
    "imessage":    "💚",
    "safari_tabs": "🗂 ",
}

# bias: more recent items get a small score boost (subtracted from BM25)
RECENCY_DECAY_SECONDS = 60 * 60 * 24 * 7  # 1 week


def search(query: str, limit: int = 20) -> list[dict]:
    rows = db.query_fts(query, limit=limit)
    now = time.time()
    for r in rows:
        # small recency nudge: more recent = lower (better) effective score
        age = max(0, now - r.get("ts", now))
        r["effective_score"] = r.get("score", 0) - (age / RECENCY_DECAY_SECONDS) * 0.1
    rows.sort(key=lambda r: (r["effective_score"], -r.get("ts", 0)))
    # Best-effort: if any URL-having row has a bare-URL title, swap in a
    # fetched page title (cached). Failures are silent.
    try:
        from recall import url_titles
        for r in rows:
            url = r.get("url")
            title = (r.get("title") or "").strip()
            if not url or not url.startswith(("http://", "https://")):
                continue
            # If the title looks like a URL (raw), try to upgrade
            if title.startswith(("http://", "https://")) or title == url:
                fetched = url_titles.fetch_title(url)
                if fetched:
                    r["title"] = fetched
    except Exception:
        pass
    return rows


def badge_for(source: str) -> str:
    return SOURCE_BADGES.get(source, "•")


def humanize_age(ts: float) -> str:
    if not ts:
        return "?"
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        m = int(delta // 60)
        return f"{m}m ago"
    if delta < 86400:
        h = int(delta // 3600)
        return f"{h}h ago"
    if delta < 86400 * 7:
        d = int(delta // 86400)
        return f"{d}d ago"
    if delta < 86400 * 30:
        w = int(delta // (86400 * 7))
        return f"{w}w ago"
    return _dt.date.fromtimestamp(ts).isoformat()
