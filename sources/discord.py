"""Discord indexer (read-only). Light: scans LevelDB for URLs/quotes."""

from __future__ import annotations

import re
from pathlib import Path

from sources._util import now, safe_read_file, stable_id

DISCORD_BASE = Path.home() / "Library/Application Support/discord"

URL_RE = re.compile(r"https?://(?:discord\.gg|discord\.com|discordapp\.com)[^\s\"'<>]+", re.I)


def iter_items(since_ts: float) -> list[dict]:
    if not DISCORD_BASE.exists():
        return []
    out: list[dict] = []
    for leveldb in DISCORD_BASE.glob("*/Local Storage/leveldb"):
        for f in leveldb.iterdir():
            if not f.is_file() or f.stat().st_size > 50 * 1024 * 1024:
                continue
            data = safe_read_file(f)
            if not data:
                continue
            for url in URL_RE.findall(data):
                out.append({
                    "id": stable_id("discord", url),
                    "source": "discord",
                    "title": "Discord ref",
                    "snippet": url,
                    "url": url,
                    "app": "Discord",
                    "ts": now(),
                })
    seen = set()
    deduped = []
    for it in out:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        deduped.append(it)
    return deduped


def poll_once() -> list[dict]:
    return []
