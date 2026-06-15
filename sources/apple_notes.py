"""Apple Notes indexer (read-only).

Reads the local NoteStore.sqlite. The DB schema is undocumented and has
shifted across macOS releases, but the ZICCLOUDSYNCINGOBJECT and ZICCLOUDSYNCINGOBJECT.ZBODY
fields have been stable since macOS 10.15. We do best-effort.

Requires Full Disk Access on modern macOS. Without it, the read will fail
with a SQLITE_READONLY_DBMOVED / unable-to-open error. We surface that
clearly via `log_indexer_error()` so the user knows what to do.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sources._util import now, stable_id

NOTES_DB = Path.home() / "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _permission_error() -> str:
    return (
        "Apple Notes can't be read. On macOS this almost always means "
        "Full Disk Access isn't granted to your terminal. "
        "Run `recall setup` for click-by-step instructions, or open "
        "System Settings \u2192 Privacy & Security \u2192 Full Disk Access and add your terminal app."
    )


def iter_items(since_ts: float) -> list[dict]:
    if not NOTES_DB.exists():
        return []
    out: list[dict] = []
    try:
        conn = _connect_ro(NOTES_DB)
        # try modern schema first
        try:
            cur = conn.execute(
                """
                SELECT
                    n.Z_PK,
                    n.ZTITLE1,
                    COALESCE(c.Z_FOK_CONTENT, '') AS body,
                    COALESCE(n.ZMODIFICATIONDATE1, n.ZCREATIONDATE1, 0) AS mod_ts
                FROM ZICCLOUDSYNCINGOBJECT n
                LEFT JOIN ZICCLOUDSYNCINGOBJECT c
                  ON c.Z_PK = (
                      SELECT Z_PK FROM ZICCLOUDSYNCINGOBJECT
                      WHERE ZNOTE = n.Z_PK
                        AND ZISPASSWORDPROTECTED = 0
                        AND ZCRYPTEDCOMMENT ISNULL
                        AND ZTYPEUTI = 'com.apple.notes.richtext'
                      ORDER BY Z_PK DESC LIMIT 1
                  )
                WHERE n.ZISPASSWORDPROTECTED = 0
                  AND n.ZCRYPTEDCOMMENT ISNULL
                  AND n.ZTITLE1 IS NOT NULL
                ORDER BY mod_ts DESC
                LIMIT 5000
                """
            )
            for pk, title, body, mod_ts in cur:
                # Apple uses Mac epoch (2001-01-01) in seconds
                ts = float(mod_ts) + 978307200 if mod_ts else now()
                if since_ts and ts < since_ts:
                    continue
                snippet = (body or "").strip()
                # the body is RTF-XML; pull the readable text via a light strip
                snippet = _strip_rtfxml(snippet)
                out.append({
                    "id": stable_id("notes", "n", int(pk)),
                    "source": "notes",
                    "title": title or "(untitled)",
                    "snippet": snippet[:8000] or title or "",
                    "url": None,
                    "app": "Notes",
                    "ts": ts,
                })
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "unable to open" in msg or "authorization" in msg or "permission" in msg:
                # Permission denied \u2014 surface to the user
                import logging
                logging.getLogger("recall").warning("notes: " + _permission_error())
            else:
                # older macOS schema (pre-Catalina-ish)
                cur = conn.execute(
                    "SELECT Z_PK, ZTITLE1, ZBODY, ZMODIFICATIONDATE FROM ZNOTE ORDER BY ZMODIFICATIONDATE DESC LIMIT 5000"
                )
                for pk, title, body, mod_ts in cur:
                    ts = float(mod_ts) + 978307200 if mod_ts else now()
                    if since_ts and ts < since_ts:
                        continue
                    out.append({
                        "id": stable_id("notes", "n", int(pk)),
                        "source": "notes",
                        "title": title or "(untitled)",
                        "snippet": (body or title or "")[:8000],
                        "url": None,
                        "app": "Notes",
                        "ts": ts,
                    })
        conn.close()
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "unable to open" in msg or "authorization" in msg or "permission" in msg:
            import logging
            logging.getLogger("recall").warning("notes: " + _permission_error())
    except Exception:
        pass
    return out


def _strip_rtfxml(s: str) -> str:
    """Cheap RTF-XML stripper: remove tags, decode entities, collapse whitespace."""
    if not s:
        return ""
    import re
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def poll_once() -> list[dict]:
    return []
