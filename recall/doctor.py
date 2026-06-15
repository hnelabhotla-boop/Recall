"""recall doctor — diagnose what's working and what's not.

Run: recall doctor
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

from recall import config, db
from sources.live_status import live_status, reset_cache


def _check(label: str, ok: bool, hint: str = "") -> bool:
    icon = "\u2705" if ok else "\u274c"
    line = f"  {icon}  {label}"
    if hint:
        line += f"   ({hint})"
    print(line)
    return ok


def _check_apple_notes_permission() -> bool:
    notes_db = Path.home() / "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
    if not notes_db.exists():
        return _check("Apple Notes", False, "no notes database found")
    try:
        conn = sqlite3.connect(f"file:{notes_db}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM ZICCLOUDSYNCINGOBJECT LIMIT 1")
        conn.close()
        return _check("Apple Notes", True, f"{notes_db.stat().st_size // 1024} KB")
    except sqlite3.OperationalError:
        return _check("Apple Notes", False, "Full Disk Access required (System Settings -> Privacy & Security)")
    except Exception as e:
        return _check("Apple Notes", False, str(e)[:60])


def _check_mail() -> bool:
    base = Path.home() / "Library/Mail"
    if not base.exists():
        return _check("Mail", False, "no ~/Library/Mail")
    mboxes = list(base.glob("V*/MailData/*.mbox"))
    if not mboxes:
        return _check("Mail", False, "no mbox files found")
    return _check("Mail", True, f"{len(mboxes)} mbox file(s)")


def _check_browser(db_path: Path, name: str, table: str) -> bool:
    if not db_path.exists():
        return _check(name, False, "not installed")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        conn.close()
        return _check(name, True)
    except Exception as e:
        return _check(name, False, str(e)[:60])


def cmd_doctor(args) -> int:
    print()
    print("  recall doctor -- checking your setup")
    print("  " + "-" * 40)
    print()

    _check(f"Python {sys.version.split()[0]}", True)
    fts_ok = False
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        fts_ok = True
        c.close()
    except Exception:
        pass
    _check("SQLite FTS5", fts_ok)

    _check("pbpaste (clipboard)", bool(shutil.which("pbpaste")), "macOS only")
    _check("osascript (foreground app)", bool(shutil.which("osascript")), "macOS only")

    config.ensure_home()
    _check("recall home", config.RECALL_HOME.exists(), str(config.RECALL_HOME))
    _check("index db", config.INDEX_PATH.exists(), str(config.INDEX_PATH))

    print()
    print("  sources:")
    reset_cache()
    live = live_status()
    for s in ("clipboard", "safari", "chrome", "brave", "arc", "edge",
              "notes", "shell", "recent_files", "mail", "slack", "discord"):
        _check(s, s in live)

    print()
    print("  permission-gated:")
    _check_apple_notes_permission()
    _check_mail()
    _check_browser(Path.home() / "Library/Application Support/Google/Chrome/Default/History", "Chrome history", "urls")
    _check_browser(Path.home() / "Library/Safari/History.db", "Safari history", "history_items")

    print()
    stats = db.stats()
    print(f"  index: {stats['total']:,} item(s) across {len(stats['by_source'])} source(s)")
    print(f"  size:  {stats['size_mb']:.2f} MB")
    print()
    return 0
xcvdg 