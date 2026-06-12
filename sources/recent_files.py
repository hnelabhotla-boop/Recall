"""Recent files indexer (macOS shared file list + Finder recents)."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from sources._util import now, stable_id

RECENT_PLIST = Path.home() / "Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.RecentApplications.sfl2"
DOCS_PLIST   = Path.home() / "Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.RecentDocuments.sfl2"
SERVERS_PLIST= Path.home() / "Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.RecentServers.sfl2"
HOSTS_PLIST  = Path.home() / "Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.RecentHosts.sfl2"


def _read_sfl2(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
    except Exception:
        return []
    items = data.get("items", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for entry in items:
        try:
            name = entry.get("name") or ""
            if not name:
                # try to extract from bookmark
                bm = entry.get("Bookmark")
                if isinstance(bm, bytes):
                    name = f"(bookmark {len(bm)}b)"
            ts = entry.get("last-used") or now()
            if hasattr(ts, "timestamp"):
                ts = ts.timestamp()
            out.append({
                "id": stable_id("recent_files", path.name, name, ts),
                "source": "recent_files",
                "title": name or "(unnamed)",
                "snippet": name,
                "url": None,
                "app": "Finder",
                "ts": float(ts),
            })
        except Exception:
            continue
    return out


def iter_items(since_ts: float) -> list[dict]:
    out: list[dict] = []
    for p in (RECENT_PLIST, DOCS_PLIST, SERVERS_PLIST, HOSTS_PLIST):
        for it in _read_sfl2(p):
            if since_ts and it["ts"] < since_ts:
                continue
            out.append(it)
    return out


def poll_once() -> list[dict]:
    return []
