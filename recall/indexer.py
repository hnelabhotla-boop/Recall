"""One-shot and watch-mode index orchestration."""

from __future__ import annotations

import logging
import time
from typing import Callable

from recall import config, db

log = logging.getLogger("recall")


# Ordered list of source modules. Each exposes a `iter_items(since_ts)` function
# that yields item dicts and an optional `poll_once()` for cheap live updates.

SOURCE_MODULES: list[str] = [
    "sources.clipboard",
    "sources.shell_history",
    "sources.recent_files",
    "sources.safari_history",
    "sources.chrome_history",
    "sources.brave_history",
    "sources.arc_history",
    "sources.edge_history",
    "sources.apple_notes",
    "sources.mail",
    "sources.slack",
    "sources.discord",
]


def _last_index_ts() -> float:
    row = db.conn().execute("SELECT value FROM meta WHERE key = 'last_index_ts'").fetchone()
    if not row:
        return 0.0
    try:
        import datetime
        return datetime.datetime.fromisoformat(row[0]).timestamp()
    except Exception:
        return 0.0


def _safe(modname: str, fn_name: str, *args, **kwargs):
    """Import and call a source function; never let one bad source break the run."""
    try:
        mod = __import__(modname, fromlist=["_"])
        fn = getattr(mod, fn_name, None)
        if fn is None:
            return iter(())
        return fn(*args, **kwargs)
    except Exception as e:
        log.warning("%s.%s failed: %s", modname, fn_name, e)
        return iter(())


def index_once(silent: bool = False) -> dict[str, int]:
    """Re-index all sources. Returns {source_name: new_items_count}."""
    db.init()
    since = _last_index_ts() or 0.0
    counts: dict[str, int] = {}
    for modname in SOURCE_MODULES:
        src_name = modname.split(".")[-1]
        try:
            items = list(_safe(modname, "iter_items", since))
            n = db.upsert_many(items) if items else 0
            counts[src_name] = n
            if not silent and n:
                print(f"    {src_name:<14} +{n}")
        except Exception as e:
            log.warning("%s failed: %s", modname, e)
            counts[src_name] = 0
    db.mark_indexed(sum(counts.values()))
    db.prune(config.load().get("retention_days", 0))
    return counts


def watch_forever() -> None:
    """Continuously poll the cheap sources (clipboard etc.)."""
    import signal

    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("  running initial index...")
    counts = index_once(silent=False)
    print(f"  initial: {sum(counts.values())} new items")
    print(f"  watching (poll every {config.POLL_INTERVAL}s)...")

    interval = max(1, int(config.load().get("poll_interval", config.POLL_INTERVAL)))
    tick = 0
    while not stop:
        time.sleep(interval)
        tick += 1
        # every tick: poll cheap sources
        for modname in ("sources.clipboard",):
            try:
                items = list(_safe(modname, "poll_once"))
                if items:
                    db.upsert_many(items)
                    if items:
                        print(f"  [{_ts()}] +{len(items)} from {modname}")
            except Exception:
                pass
        # every 12 ticks (~1 min): re-poll history sources
        if tick % 12 == 0:
            since = time.time() - 3600  # last hour
            for modname in SOURCE_MODULES:
                if modname == "sources.clipboard":
                    continue
                try:
                    items = list(_safe(modname, "iter_items", since))
                    if items:
                        n = db.upsert_many(items)
                        if n:
                            print(f"  [{_ts()}] +{n} from {modname}")
                except Exception:
                    pass
        # every 720 ticks (~1 hour): full re-index of slow sources
        if tick % 720 == 0:
            print(f"  [{_ts()}] full re-index")
            index_once(silent=True)


def _ts() -> str:
    import datetime
    return datetime.datetime.now().strftime("%H:%M:%S")
