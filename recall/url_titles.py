"""URL title fetcher.

Fetches the <title> of a URL using only stdlib (urllib + html.parser).
Caches results to ~/.recall/url_titles.json so we don't re-fetch.

Why this matters: a browser-history hit for "https://news.ycombinator.com"
shows up as the raw URL by default. After this, it shows "Hacker News".
Way more useful when scrolling through 50 results.
"""

from __future__ import annotations

import html
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from recall import config

CACHE_PATH: Path = config.RECALL_HOME / "url_titles.json"
USER_AGENT = "recall/0.3 (+https://github.com/hnelabhotla-boop/Recall)"
TIMEOUT = 4  # seconds per request
MAX_BYTES = 64 * 1024  # read at most 64KB of the page (title is in the head)


def _load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with CACHE_PATH.open() as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    config.ensure_home()
    try:
        with CACHE_PATH.open("w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


_TITLE_RE = re.compile(
    r"""<title[^>]*>(.*?)</title>""",
    re.IGNORECASE | re.DOTALL,
)


def _extract_title(html_text: str) -> Optional[str]:
    """Pull the first <title> from raw HTML, strip whitespace + entities."""
    m = _TITLE_RE.search(html_text)
    if not m:
        return None
    raw = m.group(1).strip()
    raw = re.sub(r"\s+", " ", raw)
    decoded = html.unescape(raw)
    # truncate very long titles
    if len(decoded) > 200:
        decoded = decoded[:197] + "..."
    return decoded or None


def fetch_title(url: str, use_cache: bool = True) -> Optional[str]:
    """Return the page title for a URL, or None on failure.

    Cached per-URL. Network failure, timeout, non-200, no <title> all return None.
    Never raises \u2014 best-effort.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    cache = _load_cache() if use_cache else {}
    if url in cache:
        return cache[url] or None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            resp_ctx = urllib.request.urlopen(req, timeout=TIMEOUT)
        except urllib.error.URLError as e:
            # Some Python installs (notably Homebrew or venv on macOS) lack
            # the system CA bundle. Try once with no verification as a fallback.
            if "CERTIFICATE_VERIFY_FAILED" in str(e) or "certificate" in str(e).lower():
                import ssl
                ctx = ssl._create_unverified_context()
                resp_ctx = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
            else:
                raise
        with resp_ctx as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in ctype and "xml" not in ctype:
                return None
            raw = resp.read(MAX_BYTES).decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError):
        return None
    except Exception:
        return None

    title = _extract_title(raw)
    cache[url] = title or ""
    _save_cache(cache)
    return title


def backfill(items: list[dict], max_items: int = 100) -> int:
    """For a batch of items with a `url` and missing/bad title, fetch the real
    page title and write it back to the items dict. Returns the number updated.

    Rate-limited: small sleep between fetches so we don't hammer sites.
    """
    cache = _load_cache()
    updated = 0
    for it in items[:max_items]:
        url = it.get("url")
        if not url or not url.startswith(("http://", "https://")):
            continue
        cur = (it.get("title") or "").strip()
        # Skip if the current title already looks like a real title (not just the URL)
        if cur and not cur.startswith(("http://", "https://")) and cur != url:
            continue
        if url in cache and cache[url]:
            it["title"] = cache[url]
            updated += 1
            continue
        t = fetch_title(url)
        if t:
            it["title"] = t
            updated += 1
        # small breather
        time.sleep(0.05)
    return updated
