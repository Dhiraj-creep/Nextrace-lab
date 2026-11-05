"""Local TCP Cache Server (`local_tcp_cache_substitute`) for the Second Application (`inventory_app`, Stage 8).

Provides a real, stateful TCP key-value reservation cache over localhost (default 127.0.0.1:16379)
when Docker / Redis is not installed on the host. Explicitly labeled `local_tcp_cache_substitute`
in runtime metadata and reports so it is never conflated with a full Redis instance.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socketserver
import threading
import time
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = ROOT_DIR / "var"
RUNTIME_DIR = VAR_DIR / "runtime"
CACHE_FAULT_OVERRIDE_FILE = RUNTIME_DIR / "inv_cache_fault_override.json"

_CACHE_LOCK = threading.Lock()
_CACHE_STORE: dict[str, Any] = {
    "stock:sku-laptop-101": 500,
    "stock:sku-sensor-202": 500,
    "stock:sku-router-303": 500,
}
_CACHE_STATS: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "writes": 0,
    "pings": 0,
}


def _load_cache_fault_override() -> dict[str, Any]:
    path_str = os.environ.get("NEXTRACE_CACHE_FAULT_OVERRIDE_FILE", str(CACHE_FAULT_OVERRIDE_FILE))
    fpath = Path(path_str)
    if not fpath.exists():
        return {}
    try:
        with open(fpath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class _CacheTCPHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._send({"ok": False, "error_category": "protocol_error", "detail": str(exc)})
            return

        overrides = _load_cache_fault_override()
        delay_ms = int(overrides.get("operation_delay_ms", 0) or 0)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        if overrides.get("reject_connections"):
            self._send(
                {
                    "ok": False,
                    "error_category": "cache_rejected",
                    "detail": "Cache server configured to reject operations",
                }
            )
            return

        action = req.get("action", "ping")
        with _CACHE_LOCK:
            if action == "ping":
                _CACHE_STATS["pings"] += 1
                self._send(
                    {
                        "ok": True,
                        "backend": "local_tcp_cache_substitute",
                        "keys_count": len(_CACHE_STORE),
                        "stats": dict(_CACHE_STATS),
                    }
                )
                return

            if action == "get":
                key = str(req.get("key", ""))
                if key in _CACHE_STORE:
                    _CACHE_STATS["hits"] += 1
                    self._send({"ok": True, "hit": True, "key": key, "value": _CACHE_STORE[key]})
                else:
                    _CACHE_STATS["misses"] += 1
                    self._send({"ok": True, "hit": False, "key": key, "value": None})
                return

            if action == "set":
                key = str(req.get("key", ""))
                val = req.get("value")
                _CACHE_STORE[key] = val
                _CACHE_STATS["writes"] += 1
                self._send({"ok": True, "key": key, "value": val})
                return

            if action in ("delete", "del"):
                key = str(req.get("key", ""))
                existed = key in _CACHE_STORE
                _CACHE_STORE.pop(key, None)
                self._send({"ok": True, "deleted": existed, "key": key})
                return

            self._send({"ok": False, "error_category": "unknown_action", "detail": f"Unsupported action: {action}"})

    def _send(self, payload: dict[str, Any]) -> None:
        self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
        self.wfile.flush()


class ThreadedCacheServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="NexTrace Local TCP Cache Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=16379)
    args = parser.parse_args()

    with ThreadedCacheServer((args.host, args.port), _CacheTCPHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
