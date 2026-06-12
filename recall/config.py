"""Configuration for recall.

Stores everything in `~/.recall/config.json`. Defaults are baked in.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ---- paths ----------------------------------------------------------------

RECALL_HOME: Path = Path(os.environ.get("RECALL_HOME", Path.home() / ".recall"))
INDEX_PATH: Path = RECALL_HOME / "index.db"
LOG_PATH: Path = RECALL_HOME / "recall.log"
CONFIG_PATH: Path = RECALL_HOME / "config.json"
WEB_DIR: Path = Path(__file__).resolve().parent.parent / "ui"

# ---- network / server -----------------------------------------------------

HOST: str = os.environ.get("RECALL_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("RECALL_PORT", "7331"))

# ---- indexing -------------------------------------------------------------

# How many days of history to keep. 0 = infinite.
RETENTION_DAYS: int = 0

# Per-source enable/disable. Anything not listed is auto-enabled if present.
SOURCE_DEFAULTS: dict = {
    "clipboard": True,
    "safari": True,
    "chrome": True,
    "brave": True,
    "arc": True,
    "edge": True,
    "notes": True,
    "shell": True,
    "recent_files": True,
    "mail": True,
    "slack": True,
    "discord": True,
}

# How often to poll each source (seconds) when running `recall watch`.
POLL_INTERVAL: int = 5


def load() -> dict:
    """Return the current config (loading from disk, falling back to defaults)."""
    base = {
        "retention_days": RETENTION_DAYS,
        "sources": dict(SOURCE_DEFAULTS),
        "poll_interval": POLL_INTERVAL,
        "port": PORT,
    }
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open() as f:
                user = json.load(f)
            # shallow merge: user overrides defaults
            for k, v in user.items():
                if k == "sources" and isinstance(v, dict):
                    base["sources"].update(v)
                else:
                    base[k] = v
        except Exception:
            pass
    return base


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        json.dump(cfg, f, indent=2)


def ensure_home() -> None:
    """Create ~/.recall/ if missing."""
    RECALL_HOME.mkdir(parents=True, exist_ok=True)
