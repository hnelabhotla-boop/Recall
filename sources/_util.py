"""Helpers shared by source modules."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path


def stable_id(source: str, *parts) -> str:
    """Build a stable, dedup-friendly primary key from source + parts."""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8", "ignore")).hexdigest()[:16]
    return f"{source}:{h}"


def now() -> float:
    return time.time()


def safe_read_file(path: Path, max_bytes: int = 50 * 1024 * 1024) -> str:
    """Read a text file with size limit + encoding fallback."""
    try:
        if not path.exists():
            return ""
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(errors="replace")
    except Exception:
        return ""
