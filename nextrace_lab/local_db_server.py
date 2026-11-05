"""Standalone TCP database service process for the local_sqlite_tcp backend.

Provides an independent TCP database server on 127.0.0.1:15432 (and 15433 for inventory_app)
backed by durable SQLite storage. Supports protocol-level readiness and query checks and
controlled database-side fault modes:
- authentication_failed (Fault C)
- missing_table via isolated disposable schema file (Fault D, never dropping persistent user tables)
- operation_timeout exceeding client deadline (Fault E)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socketserver
import sqlite3
import threading
import time
from typing import Any

from nextrace_lab.logging_utils import emit_structured_log, utc_now_iso

_DB_LOCK = threading.Lock()
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_FAULT_OVERRIDE_FILE = ROOT_DIR / "var" / "runtime" / "db_fault_override.json"


def get_sqlite_path() -> Path:
    """Return path to the persistent orders SQLite file."""
    override = os.environ.get("NEXTRACE_SQLITE_PATH")
    if override:
        path = Path(override)
    else:
        path = ROOT_DIR / "var" / "data" / "orders.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_disposable_missing_schema_path() -> Path:
    """Return path to an isolated disposable SQLite file with no 'orders' table (Fault D)."""
    path = ROOT_DIR / "var" / "data" / "disposable_missing_schema.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK:
        conn = sqlite3.connect(str(path), timeout=3.0)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_metadata (version TEXT);")
            conn.execute("DROP TABLE IF EXISTS orders;")
            conn.commit()
        finally:
            conn.close()
    return path


def load_db_fault_override() -> dict[str, Any]:
    """Read optional database fault override configuration."""
    override_path = Path(os.environ.get("NEXTRACE_DB_FAULT_OVERRIDE_FILE", str(DB_FAULT_OVERRIDE_FILE)))
    if not override_path.exists():
        return {}
    try:
        with open(override_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def init_sqlite_schema(db_path: Path) -> None:
    """Initialize the minimal persistent orders schema if not already present."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


class _DatabaseTCPHandler(socketserver.StreamRequestHandler):
    """Handle single JSON-line TCP requests from order-service, inventory-service, or protocol health probes."""

    def handle(self) -> None:
        start_t = time.perf_counter()
        raw = self.rfile.readline(65536)
        if not raw:
            return
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            resp = {"ok": False, "error_category": "protocol_error", "error": str(exc), "detail": str(exc)}
            self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
            return

        op = req.get("action") or req.get("op") or "ping"
        request_id = req.get("request_id")
        db_user = str(req.get("user") or req.get("db_user") or "nextrace_user")
        db_password = str(req.get("password") or req.get("db_password") or "nextrace_local_dev_pw")
        expected_user = os.environ.get("DB_USER", "nextrace_user")
        expected_password = os.environ.get("DB_PASSWORD", "nextrace_local_dev_pw")

        fault_cfg = load_db_fault_override()

        # 1. Protocol-level authentication check (Fault C)
        if db_user != expected_user or db_password != expected_password:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            emit_structured_log(
                service="database",
                request_id=request_id,
                event="authentication_failed",
                outcome="failure",
                duration_ms=dur_ms,
                error_category="authentication_failed",
                details={"db_user": db_user, "reason": "FATAL: password authentication failed"},
            )
            resp = {
                "ok": False,
                "error_category": "authentication_failed",
                "error": f"FATAL: password authentication failed for user '{db_user}'",
                "detail": f"FATAL: password authentication failed for user '{db_user}'",
            }
            self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
            return

        # 2. Controlled operation delay (Fault E / inv_fault_upstream_timeout)
        delay_ms = float(fault_cfg.get("operation_delay_ms", 0.0) or 0.0)
        if delay_ms > 0:
            emit_structured_log(
                service="database",
                request_id=request_id,
                event="database_operation_delayed",
                outcome="failure",
                duration_ms=delay_ms,
                error_category="operation_timeout",
                details={"op": op, "injected_delay_ms": delay_ms},
            )
            time.sleep(delay_ms / 1000.0)

        # 3. Select persistent vs isolated disposable missing-schema DB file (Fault D)
        if fault_cfg.get("active_schema_mode") == "missing_orders_table":
            db_path = get_disposable_missing_schema_path()
        else:
            db_path = self.server.db_path  # type: ignore[attr-defined]

        try:
            if op == "ping":
                verify_schema = bool(req.get("verify_schema", True))
                with _DB_LOCK:
                    conn = sqlite3.connect(str(db_path), timeout=2.0)
                    try:
                        conn.execute("SELECT 1;").fetchone()
                        if verify_schema:
                            conn.execute("SELECT order_id FROM orders LIMIT 1;").fetchall()
                    finally:
                        conn.close()
                resp = {
                    "ok": True,
                    "status": "healthy",
                    "probe_category": "database_usable",
                    "timestamp_utc": utc_now_iso(),
                }
            elif op == "insert_order":
                order_id = str(req["order_id"])
                product_id = str(req["product_id"])
                quantity = int(req["quantity"])
                created_at = str(req.get("created_at") or utc_now_iso())
                with _DB_LOCK:
                    conn = sqlite3.connect(str(db_path), timeout=3.0)
                    try:
                        conn.execute(
                            "INSERT INTO orders (order_id, product_id, quantity, request_id, created_at) VALUES (?, ?, ?, ?, ?);",
                            (order_id, product_id, quantity, str(request_id or ""), created_at),
                        )
                        conn.commit()
                    finally:
                        conn.close()
                dur_ms = (time.perf_counter() - start_t) * 1000.0
                emit_structured_log(
                    service="database",
                    request_id=request_id,
                    event="order_row_inserted",
                    outcome="success",
                    duration_ms=dur_ms,
                    details={"order_id": order_id, "product_id": product_id, "quantity": quantity},
                )
                record = {
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "request_id": request_id,
                    "created_at": created_at,
                }
                resp = {"ok": True, "order": record, "record": record}
            elif op in ("get_order", "fetch_order"):
                order_id = str(req["order_id"])
                with _DB_LOCK:
                    conn = sqlite3.connect(str(db_path), timeout=2.0)
                    try:
                        row = conn.execute(
                            "SELECT order_id, product_id, quantity, request_id, created_at FROM orders WHERE order_id = ?;",
                            (order_id,),
                        ).fetchone()
                    finally:
                        conn.close()
                if row is None:
                    resp = {"ok": True, "order": None, "record": None}
                else:
                    record = {
                        "order_id": row[0],
                        "product_id": row[1],
                        "quantity": row[2],
                        "request_id": row[3],
                        "created_at": row[4],
                    }
                    resp = {"ok": True, "order": record, "record": record}
            else:
                resp = {"ok": False, "error_category": "invalid_operation", "error": f"Unknown op: {op}", "detail": f"Unknown op: {op}"}
        except sqlite3.OperationalError as exc:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            msg = str(exc)
            err_cat = "missing_table" if "no such table" in msg.lower() else "storage_error"
            emit_structured_log(
                service="database",
                request_id=request_id,
                event="database_operation_failed",
                outcome="failure",
                duration_ms=dur_ms,
                error_category=err_cat,
                details={"op": op, "error": msg},
            )
            resp = {"ok": False, "error_category": err_cat, "error": msg, "detail": msg}
        except Exception as exc:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            emit_structured_log(
                service="database",
                request_id=request_id,
                event="database_operation_failed",
                outcome="failure",
                duration_ms=dur_ms,
                error_category="storage_error",
                details={"op": op, "error": str(exc)},
            )
            resp = {"ok": False, "error_category": "storage_error", "error": str(exc), "detail": str(exc)}

        try:
            self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
        except OSError:
            pass


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], db_path: Path):
        self.db_path = db_path
        super().__init__(server_address, _DatabaseTCPHandler)


def run_server(host: str = "127.0.0.1", port: int = 15432, db_path: Path | None = None) -> None:
    """Initialize schema and serve TCP database requests until interrupted."""
    resolved_path = db_path or get_sqlite_path()
    init_sqlite_schema(resolved_path)
    emit_structured_log(
        service="database",
        event="database_server_started",
        outcome="info",
        details={"host": host, "port": port, "storage_file": resolved_path.name, "backend": "local_sqlite_tcp"},
    )
    with ReusableThreadingTCPServer((host, port), resolved_path) as server:
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            emit_structured_log(
                service="database",
                event="database_server_stopped",
                outcome="info",
                details={"host": host, "port": port},
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="NexTrace local TCP database service")
    parser.add_argument("--host", default=os.environ.get("DB_BIND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DB_BIND_PORT", "15432")))
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
