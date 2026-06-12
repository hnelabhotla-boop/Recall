"""Shell history indexer (zsh + bash)."""

from __future__ import annotations

import re
import time
from pathlib import Path

from sources._util import now, safe_read_file, stable_id

ZSH = Path.home() / ".zsh_history"
BASH = Path.home() / ".bash_history"


# zsh extended history format: ": <ts>:0;<command>"
ZSH_LINE = re.compile(r"^: (\d+):\d+;(.+)$")


def _iter_file(path: Path, since_ts: float) -> list[dict]:
    if not path.exists():
        return []
    text = safe_read_file(path)
    if not text:
        return []
    out: list[dict] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        m = ZSH_LINE.match(line)
        if m:
            ts = int(m.group(1))
            cmd = m.group(2).strip()
        else:
            ts = int(time.time() - (24 * 3600))  # unknown ts; treat as yesterday
            cmd = line
        if since_ts and ts < since_ts:
            continue
        if not cmd:
            continue
        out.append({
            "id": stable_id("shell", path.name, ts, cmd),
            "source": "shell",
            "title": cmd[:80],
            "snippet": cmd,
            "url": None,
            "app": "shell",
            "ts": float(ts),
        })
    return out


def iter_items(since_ts: float) -> list[dict]:
    out: list[dict] = []
    for p in (ZSH, BASH):
        out.extend(_iter_file(p, since_ts))
    return out


def poll_once() -> list[dict]:
    return []
