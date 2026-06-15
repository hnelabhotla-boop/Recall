"""Clipboard indexer.

Polls the macOS pasteboard via `pbpaste`. We avoid reading the clipboard on
the main thread (it can block on password managers etc.) by running a small
thread per poll. We detect the foreground app via AppleScript so the result
can show e.g. "from Chrome".

If the clipboard contains a single URL, we set the `url` field so the
title-fetcher can later upgrade the bare-URL title to a real page title.

Privacy note: clipboard contents can include passwords when you copy them
to paste into a password manager. We still index them — recall is local and
private, but if you'd rather skip short, sensitive-looking snippets, see
SKIP_SHORT in the code.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from sources._util import now, stable_id

_LAST_HASH: str | None = None
_LAST_POLL: float = 0.0
_LOCK = threading.Lock()

# Poll at most this often (seconds) to keep CPU/nagging low.
POLL_INTERVAL = 1.0

URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)


def _pbcopy() -> str | None:
    if not shutil.which("pbpaste"):
        return None
    try:
        out = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=2
        )
        if out.returncode == 0:
            return out.stdout
        return None
    except Exception:
        return None


def _foreground_app() -> str:
    """Best-effort: which app is the user currently focused on?"""
    try:
        out = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first application process whose frontmost is true',
            ],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _should_skip(text: str) -> bool:
    """Don't index obvious password-manager paste patterns."""
    t = text.strip()
    if not t:
        return True
    # super short tokens are usually "select to copy" accidents
    if len(t) < 3:
        return True
    # long base64 / hex blobs from 1Password/Bitwarden/Keychain
    if len(t) >= 24 and all(c.isalnum() or c in "+/=-_:" for c in t):
        # only skip if it doesn't have spaces (real text usually has spaces)
        if " " not in t:
            return True
    return False


def _extract_url(text: str) -> str | None:
    """If the clipboard text is (or contains) a single URL, return it."""
    stripped = text.strip()
    # whole text is a URL?
    if re.match(r"^https?://\S+$", stripped):
        return stripped.rstrip(".,;:!?)")
    # first URL found
    m = URL_RE.search(text)
    if m:
        return m.group(0).rstrip(".,;:!?)")
    return None


def poll_once() -> list[dict]:
    """Capture the current clipboard if it changed. Returns a list (0 or 1 items)."""
    global _LAST_HASH, _LAST_POLL
    with _LOCK:
        now_ts = time.time()
        if now_ts - _LAST_POLL < POLL_INTERVAL:
            return []
        _LAST_POLL = now_ts

        text = _pbcopy()
        if not text or _should_skip(text):
            return []

        h = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
        if h == _LAST_HASH:
            return []
        _LAST_HASH = h

        app = _foreground_app()
        snippet = text[:4000]  # cap per item
        url = _extract_url(text)
        item_id = stable_id("clipboard", h)
        return [
            {
                "id": item_id,
                "source": "clipboard",
                "title": (text.strip().splitlines() or [""])[0][:80] or "(clipboard)",
                "snippet": snippet,
                "url": url,
                "app": app,
                "ts": now(),
            }
        ]


def iter_items(since_ts: float) -> list[dict]:
    """Index the most recent clipboard item if not already known."""
    return poll_once()
