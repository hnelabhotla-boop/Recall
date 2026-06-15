"""recall setup — walk the user through granting permissions.

Some sources (Apple Notes, Mail) require macOS Full Disk Access before they
can be read. This command prints step-by-step instructions and, where possible,
deep-links into the right System Settings pane.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _print_header(title: str) -> None:
    print()
    print("  " + title)
    print("  " + "\u2500" * len(title))


def _try_open_settings() -> bool:
    """Try to open System Settings \u2192 Privacy & Security \u2192 Full Disk Access."""
    try:
        # macOS Ventura+
        subprocess.run(
            ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"],
            check=False, timeout=3,
        )
        return True
    except Exception:
        return False


def _detect_terminal() -> str:
    """Return the friendly name of the terminal app the user is likely running."""
    import os
    program = os.environ.get("TERM_PROGRAM", "")
    if "iTerm" in program:
        return "iTerm"
    if "Apple" in program or "Terminal" in program:
        return "Terminal"
    if "Warp" in program:
        return "Warp"
    if "VS Code" in program:
        return "Visual Studio Code"
    # fallback: check what apps exist
    if Path("/Applications/iTerm.app").exists():
        return "iTerm"
    if Path("/Applications/Warp.app").exists():
        return "Warp"
    return "Terminal"


def cmd_setup(args) -> int:
    print()
    print("  recall setup \u2014 grant permissions for the sources that need them")
    print()
    print("  This command helps you give recall access to:")
    print("    \u2022 Apple Notes    (Full Disk Access)")
    print("    \u2022 Local Mail      (Full Disk Access)")
    print("    \u2022 Browser history (usually works without extra steps)")
    print()

    if platform.system() != "Darwin":
        print("  \u26a0  recall is built for macOS. On other systems, only the")
        print("     shell history + recent-files sources will work.")
        print()
        return 0

    print("  macOS protects Notes, Mail, and some browser data behind")
    print("  'Full Disk Access'. Without it, recall can see the file but")
    print("  the OS blocks the read. The fix is one-time, ~30 seconds.")
    print()
    print("  " + "\u2500" * 60)
    print()

    # --- Terminal permission ---
    _print_header("Step 1: grant Full Disk Access to your terminal")
    print()
    print("  recall is run from your terminal, so the terminal app needs the")
    print("  permission (not recall itself).")
    print()
    term = _detect_terminal()
    print(f"  If you use {term}:")
    print()
    print("    1. Click the button below to open the right System Settings pane")
    print("    2. Click the + button under 'Allow applications to access")
    print("       files on removable media' (or 'Full Disk Access' in older macOS)")
    print(f"    3. Navigate to /Applications and pick '{term}.app'")
    print("    4. Make sure the toggle next to it is ON")
    print("    5. **Quit and reopen your terminal** (this part matters!)")
    print()

    if _try_open_settings():
        print("  \u2192 Opening System Settings \u2026")
    else:
        print("  \u2192 Open System Settings \u2192 Privacy & Security \u2192 Full Disk Access manually")
    print()

    # --- Quick re-test ---
    _print_header("Step 2: verify it works")
    print()
    print("  After granting access and reopening your terminal, run:")
    print()
    print("    recall doctor")
    print()
    print("  Look for \u2705 next to 'Apple Notes'. If you still see \u274c, the")
    print("  most common reason is forgetting to fully quit + reopen the")
    print("  terminal (the permission only applies to new processes).")
    print()

    # --- Source-by-source detail ---
    _print_header("What gets indexed once Notes is unlocked")
    print()
    print("  \u2022 Every note's title and full body text")
    print("  \u2022 Updates as you edit (run `recall watch` to keep it fresh)")
    print("  \u2022 Search is local + private \u2014 nothing leaves your Mac")
    print()

    # --- If they just want a 1-line answer ---
    _print_header("If you only have 30 seconds")
    print()
    print("  Open System Settings \u2192 Privacy & Security \u2192 Full Disk Access")
    print("  \u2192 add your Terminal app \u2192 quit and reopen terminal \u2192 done.")
    print()
    return 0
