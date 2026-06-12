"""Local web UI: a tiny stdlib HTTP server that serves the static UI and a JSON
search API. No external dependencies.
"""

from __future__ import annotations

import json
import mimetypes
import os
import socket
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from recall import config, db, search

WEB_DIR = config.WEB_DIR


def _find_free_port(preferred: int) -> int:
    """If `preferred` is taken, find the next free port."""
    p = preferred
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((config.HOST, p))
                return p
            except OSError:
                p += 1
    return preferred  # fall through and let the OS complain


class _Handler(BaseHTTPRequestHandler):
    server_version = "recall/0.1"

    # silence default access logs
    def log_message(self, fmt: str, *args) -> None:
        pass

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "not found")
            return
        ctype, _enc = mimetypes.guess_type(str(path))
        ctype = ctype or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path == "/" or path == "":
            self._send_file(WEB_DIR / "index.html")
            return
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            self._send_file(WEB_DIR / rel)
            return

        if path == "/api/search":
            qs = urllib.parse.parse_qs(url.query)
            q = (qs.get("q") or [""])[0]
            limit = int((qs.get("limit") or ["25"])[0])
            t0 = time.time()
            results = search.search(q, limit=limit) if q.strip() else []
            elapsed_ms = (time.time() - t0) * 1000
            self._send_json({
                "q": q,
                "count": len(results),
                "elapsed_ms": round(elapsed_ms, 1),
                "results": [
                    {
                        "id": r["id"],
                        "source": r["source"],
                        "title": r.get("title") or "",
                        "snippet": r.get("snippet") or "",
                        "url": r.get("url") or "",
                        "app": r.get("app") or "",
                        "ts": r.get("ts", 0),
                        "age": search.humanize_age(r.get("ts", 0)),
                    }
                    for r in results
                ],
            })
            return

        if path == "/api/status":
            self._send_json(db.stats())
            return

        if path == "/api/reindex":
            from recall import indexer
            counts = indexer.index_once(silent=True)
            self._send_json({"ok": True, "added": counts})
            return

        if path == "/api/open":
            # ?id=<item_id>  → returns the URL / app to open
            qs = urllib.parse.parse_qs(url.query)
            item_id = (qs.get("id") or [""])[0]
            row = db.conn().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                self._send_json({"ok": False, "error": "not found"}, status=404)
                return
            d = dict(row)
            try:
                d["extra"] = json.loads(d.get("extra") or "null")
            except Exception:
                d["extra"] = None
            self._send_json({"ok": True, "item": d})
            return

        # 404
        self.send_error(404, "not found")


def serve(host: str | None = None, port: int | None = None) -> None:
    host = host or config.HOST
    port = port or _find_free_port(config.PORT)
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"  recall UI ready at http://{host}:{port}/")
    print(f"  open that URL in your browser. Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopping.")
    finally:
        server.server_close()
