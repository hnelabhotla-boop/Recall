"""Live status of which sources are usable on this machine.

Returns a list of source names that have the data they need to index.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

CACHE: list[str] | None = None


def _has_safari_history() -> bool:
    return Path.home().joinpath("Library/Safari/History.db").exists()


def _has_chrome_history() -> bool:
    candidates = [
        "Library/Application Support/Google/Chrome/Default/History",
        "Library/Application Support/Google/Chrome/Profile 1/History",
    ]
    base = Path.home()
    return any((base / c).exists() for c in candidates)


def _has_brave_history() -> bool:
    candidates = [
        "Library/Application Support/BraveSoftware/Brave-Browser/Default/History",
    ]
    base = Path.home()
    return any((base / c).exists() for c in candidates)


def _has_arc_history() -> bool:
    base = Path.home()
    return any((base / "Library/Application Support/Arc/User Data/Stable_Default/History").exists()
               for _ in [0]) or (base / "Library/Application Support/Arc").exists()


def _has_edge_history() -> bool:
    return (Path.home() / "Library/Application Support/Microsoft Edge/Default/History").exists()


def _has_apple_notes() -> bool:
    return Path.home().joinpath(
        "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
    ).exists()


def _has_mail() -> bool:
    base = Path.home() / "Library/Mail"
    if not base.exists():
        return False
    return any(base.glob("V*/MailData/*.mbox"))


def _has_slack() -> bool:
    base = Path.home() / "Library/Application Support/Slack"
    return base.exists() and any(base.glob("*/"))


def _has_discord() -> bool:
    return (Path.home() / "Library/Application Support/discord").exists()


def live_status() -> list[str]:
    global CACHE
    if CACHE is not None:
        return CACHE
    out: list[str] = []
    if shutil.which("pbpaste"):
        out.append("clipboard")
    if _has_safari_history():
        out.append("safari")
    if _has_chrome_history():
        out.append("chrome")
    if _has_brave_history():
        out.append("brave")
    if _has_arc_history():
        out.append("arc")
    if _has_edge_history():
        out.append("edge")
    if _has_apple_notes():
        out.append("notes")
    if Path.home().joinpath(".zsh_history").exists() or Path.home().joinpath(".bash_history").exists():
        out.append("shell")
    if Path.home().joinpath("Library/Application Support/com.apple.sharedfilelist").exists():
        out.append("recent_files")
    if _has_mail():
        out.append("mail")
    if _has_slack():
        out.append("slack")
    if _has_discord():
        out.append("discord")
    CACHE = out
    return out


def reset_cache() -> None:
    global CACHE
    CACHE = None
