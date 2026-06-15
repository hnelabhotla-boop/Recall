# recall
"""Main CLI entry point.

Subcommands:
    recall "query"     search and print results
    recall ui          open the local web UI
    recall watch       run the indexer in the foreground
    recall index       one-shot re-index
    recall status      show index stats
    recall config      print config
    recall uninstall   remove symlink + index
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Make sibling `recall` package importable when running as a flat script
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Import the package as a sub-module to avoid colliding with the script's own name
import importlib
pkg = importlib.import_module("recall")
config = importlib.import_module("recall.config")
db = importlib.import_module("recall.db")
search = importlib.import_module("recall.search")
ui = importlib.import_module("recall.ui")


BANNER = r"""
   ____  _____ ____ _   _    _    ____
  |  _ \| ____/ ___| | | |  / \  / ___|
  | |_) |  _|| |  _| |_| | / _ \ \___ \
  |  _ <| |__| |_| |  _  |/ ___ \ ___) |
  |_| \_\_____\____|_| |_/_/   \_\____/

  Local full-text search for everything you've seen.
"""


def cmd_search(args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    if not query.strip():
        print('Usage: recall "your search query"', file=sys.stderr)
        return 1

    # Live refresh: pull a fast incremental index of the cheap sources first
    try:
        from sources import clipboard
        clipboard.poll_once()
    except Exception:
        pass  # never let a source failure break search

    results = search.search(query, limit=args.limit)
    if not results:
        print(f'(no matches for "{query}")')
        return 0

    print(f'\n  {len(results)} result(s) for "{query}":\n')
    for i, r in enumerate(results, 1):
        badge = search.badge_for(r["source"])
        age = search.humanize_age(r.get("ts", 0))
        title = (r.get("title") or "").strip()[:80]
        snippet = (r.get("snippet") or "").strip().replace("\n", " ")[:140]
        print(f"  {i:>2}. {badge}  {r['source']:<10}  •  {age}")
        if title:
            print(f"      {title}")
        if snippet:
            print(f"      {snippet}")
        if r.get("url"):
            print(f"      \033[36m{r['url'][:100]}\033[0m")
        print()
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    print(BANNER)
    print(f"  opening http://localhost:{config.PORT}/")
    print("  (press Ctrl-C to stop)\n")
    # Ensure index has at least a baseline
    try:
        from recall import indexer
        indexer.index_once(silent=True)
    except Exception as e:
        print(f"  warning: initial index failed: {e}", file=sys.stderr)
    ui.serve()
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    print(BANNER)
    print("  watching for new content. Ctrl-C to stop.\n")
    from recall import indexer
    indexer.watch_forever()
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    print(BANNER)
    from recall import indexer
    started = time.time()
    counts = indexer.index_once(silent=False)
    elapsed = time.time() - started
    total = sum(counts.values())
    print(f"\n  indexed {total} new item(s) in {elapsed:.1f}s:")
    for src, n in sorted(counts.items()):
        print(f"    {src:<14} +{n}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    stats = db.stats()
    print(BANNER)
    print(f"  index:    {config.INDEX_PATH}")
    print(f"  size:     {stats['size_mb']:.2f} MB")
    print(f"  total:    {stats['total']:,} item(s)")
    print()
    print("  by source:")
    for src, n in sorted(stats["by_source"].items(), key=lambda kv: -kv[1]):
        bar = "█" * min(40, max(1, int(n / max(1, stats["total"]) * 40)))
        print(f"    {src:<14} {n:>7,}  {bar}")
    print()
    print(f"  last indexed:  {stats['last_index'] or '(never)'}")
    print(f"  sources live:  {', '.join(stats['live_sources']) or '(none)'}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    cfg = config.load()
    print(json.dumps(cfg, indent=2))
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    import shutil
    target = Path.home() / ".local" / "bin" / "recall"
    if target.is_symlink() or target.exists():
        try:
            target.unlink()
            print(f"  removed {target}")
        except Exception as e:
            print(f"  could not remove {target}: {e}", file=sys.stderr)
    answer = input("  also delete ~/.recall/ (the index)? [y/N] ").strip().lower()
    if answer == "y":
        if config.RECALL_HOME.exists():
            shutil.rmtree(config.RECALL_HOME)
            print(f"  removed {config.RECALL_HOME}")
    print("  done. recall is uninstalled.")
    return 0

def cmd_doctor(args: argparse.Namespace) -> int:
    from recall import doctor
    return doctor.cmd_doctor(args)


def cmd_setup(args: argparse.Namespace) -> int:
    from recall import setup as setup_mod
    return setup_mod.cmd_setup(args)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # If the first arg isn't a known subcommand or a flag, treat all of argv as
    # the search query. This makes `recall "kubernetes tips"` work as expected.
    KNOWN = {"ui", "watch", "index", "status", "config", "uninstall", "search", "doctor", "setup", "-h", "--help"}
    if argv and argv[0] not in KNOWN and not argv[0].startswith("-"):
        argv = ["search", *argv]

    p = argparse.ArgumentParser(
        prog="recall",
        description="Local full-text search across everything you've consumed on your Mac.",
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("search", help="search (default if no subcommand)")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", "-n", type=int, default=20)
    s.set_defaults(func=cmd_search)

    sub.add_parser("ui", help="open the local web UI").set_defaults(func=cmd_ui)
    sub.add_parser("watch", help="watch and incrementally index").set_defaults(func=cmd_watch)
    sub.add_parser("index", help="one-shot re-index").set_defaults(func=cmd_index)
    sub.add_parser("status", help="show index stats").set_defaults(func=cmd_status)
    sub.add_parser("doctor", help="diagnose what works and what doesn't").set_defaults(func=cmd_doctor)
    sub.add_parser("setup", help="walk through granting macOS permissions").set_defaults(func=cmd_setup)
    sub.add_parser("config", help="print config").set_defaults(func=cmd_config)
    sub.add_parser("uninstall", help="remove recall from your system").set_defaults(func=cmd_uninstall)

    args = p.parse_args(argv)

    # Ensure DB is initialized
    db.init()

    func = getattr(args, "func", None)
    if func is None:
        p.print_help()
        return 1
    return func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
