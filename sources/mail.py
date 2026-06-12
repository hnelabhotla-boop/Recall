"""Local Mail indexer (mbox files in ~/Library/Mail)."""

from __future__ import annotations

import email
import mailbox
from pathlib import Path

from sources._util import now, stable_id

MAIL_BASE = Path.home() / "Library/Mail"


def _find_mboxes() -> list[Path]:
    if not MAIL_BASE.exists():
        return []
    return list(MAIL_BASE.glob("V*/MailData/*.mbox"))


def iter_items(since_ts: float) -> list[dict]:
    boxes = _find_mboxes()
    if not boxes:
        return []
    out: list[dict] = []
    for path in boxes:
        try:
            mbox = mailbox.mbox(str(path))
            for key, msg in mbox.iteritems():
                try:
                    d = email.utils.parsedate_tz(msg.get("Date"))
                    if d:
                        import calendar, time as _t
                        ts = _t.mktime(_t.struct_time(d[:9])) - (d[9] or 0)
                    else:
                        ts = now()
                except Exception:
                    ts = now()
                if since_ts and ts < since_ts:
                    continue
                subj = msg.get("Subject") or "(no subject)"
                frm  = msg.get("From") or ""
                body = _extract_body(msg)
                snippet = f"{subj}\n{frm}\n{body}".strip()[:4000]
                out.append({
                    "id": stable_id("mail", path.name, key, subj, ts),
                    "source": "mail",
                    "title": (subj[:80]),
                    "snippet": snippet,
                    "url": None,
                    "app": "Mail",
                    "ts": float(ts),
                    "extra": {"from": frm},
                })
                if len(out) >= 5000:
                    break
            mbox.close()
        except Exception:
            continue
        if len(out) >= 5000:
            break
    return out


def _extract_body(msg) -> str:
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = (part.get("Content-Disposition") or "").lower()
                if ctype == "text/plain" and "attachment" not in disp:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            return payload.decode(charset, errors="replace")
                        except Exception:
                            return payload.decode("utf-8", errors="replace")
            return ""
        payload = msg.get_payload(decode=True)
        if not payload:
            return ""
        charset = msg.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except Exception:
            return payload.decode("utf-8", errors="replace")
    except Exception:
        return ""


def poll_once() -> list[dict]:
    return []
