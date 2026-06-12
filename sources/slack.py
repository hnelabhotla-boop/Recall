"""Slack indexer (read-only, from local app data).

Each workspace lives at:
    ~/Library/Application Support/Slack/<workspace-id>/

Inside that, there's a `storage/slack-{TEAMID}` directory holding the bulk of
the local data. The actual messages are in IndexedDB. We do a best-effort
text scan of the LevelDB files for lines that look like messages.

This is a *light* indexer — it finds Slack URLs and quoted snippets reliably
because those are stored as plain text. Full message body indexing is patchy
across Slack versions and isn't worth chasing for v1.
"""

from __future__ import annotations

import re
from pathlib import Path

from sources._util import now, safe_read_file, stable_id

SLACK_BASE = Path.home() / "Library/Application Support/Slack"

# slack message URL pattern
URL_RE = re.compile(r"https?://[a-zA-Z0-9.-]*slack\.com/archives/[A-Z0-9]+/p\d{10,16}", re.I)
# file paths in chat
PATH_RE = re.compile(r"(/Users/[^\s\"'<>]+)")


def iter_items(since_ts: float) -> list[dict]:
    if not SLACK_BASE.exists():
        return []
    out: list[dict] = []
    for workspace in SLACK_BASE.iterdir():
        if not workspace.is_dir():
            continue
        local_storage = workspace / "Local Storage" / "leveldb"
        storage = workspace / "storage" / f"slack-{workspace.name}"
        for scan in (local_storage, storage):
            if not scan.exists():
                continue
            for f in scan.iterdir():
                if not f.is_file():
                    continue
                if f.stat().st_size > 50 * 1024 * 1024:
                    continue
                data = safe_read_file(f)
                if not data:
                    continue
                for url in URL_RE.findall(data):
                    out.append({
                        "id": stable_id("slack", workspace.name, url),
                        "source": "slack",
                        "title": f"Slack ref in {workspace.name}",
                        "snippet": url,
                        "url": url,
                        "app": "Slack",
                        "ts": now(),
                    })
    # dedupe
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
