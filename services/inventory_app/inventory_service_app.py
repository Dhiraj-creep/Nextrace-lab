"""Inventory Service (`inventory-service` on port 18011, Stage 8 Second Application).

Connects to `inventory-db` (port 15433) and `inventory-cache` (port 16379).
Supports both real backends (PostgreSQL & Redis) and local lightweight substitutes (JSON-over-TCP).

Documented cache modes:
- `required` (default): cache is a required reservation lock/stock dependency; cache failure returns 503.
- `fallback_db`: cache failure logs a warning and falls back to database-only verification.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import socket
import time
from typing import Any
import uuid

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from nextrace_lab.logging_utils import append_log_event, utc_now_iso
from services.order_service.db import validate_operation_delay_ms

app = FastAPI(title="NexTrace Inventory Service", version="0.3.0")

SERVICE_NAME = "inventory-service"
STARTED_AT_UTC = utc_now_iso()
STARTED_MONOTONIC = time.monotonic()

_METRICS: dict[str, Any] = {
    "request_count": 0,
    "failure_count": 0,
    "dependency_failures": 0,
    "dependency_timeouts": 0,
    "total_duration_ms": 0.0,
    "max_duration_ms": 0.0,
    "last_event_time_utc": None,
}


@dataclass(frozen=True)
class InventoryDependencyConfig:
    db_driver: str  # "local_tcp" | "postgresql"
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_timeout_sec: float
    cache_driver: str  # "local_tcp" | "redis"
    cache_host: str
    cache_port: int
    cache_mode: str  # "required" | "fallback_db"
    cache_timeout_sec: float
    db_statement_timeout_ms: int = 1500
    db_lock_timeout_ms: int = 1000
    operation_delay_ms: int = 0

    def sanitized_dict(self) -> dict[str, Any]:
        return {
            "db_driver": self.db_driver,
            "db_host": self.db_host,
            "db_port": self.db_port,
            "db_name": self.db_name,
            "db_user": self.db_user,
            "db_password_redacted": "***REDACTED***",
            "connect_timeout_sec": self.db_timeout_sec,
            "statement_timeout_ms": self.db_statement_timeout_ms,
            "lock_timeout_ms": self.db_lock_timeout_ms,
            "operation_delay_ms": self.operation_delay_ms,
            "cache_driver": self.cache_driver,
            "cache_host": self.cache_host,
            "cache_port": self.cache_port,
            "cache_mode": self.cache_mode,
            "cache_timeout_sec": self.cache_timeout_sec,
        }


class DatabaseDependencyError(RuntimeError):
    """Structured database failure with explicit error_category."""

    def __init__(self, error_category: str, detail: str, configured_host: str, configured_port: int) -> None:
        super().__init__(f"[{error_category}] {detail}")
        self.error_category = error_category
        self.detail = detail
        self.configured_host = configured_host
        self.configured_port = configured_port


def _load_inv_override_flags() -> dict[str, Any]:
    override_file = os.environ.get("NEXTRACE_INV_CONFIG_OVERRIDE_FILE", "")
    if not override_file:
        for candidate in (
            Path("/app/var/runtime/inv_service_override.json"),
            Path(__file__).resolve().parent.parent.parent / "var" / "runtime" / "inv_service_override.json",
        ):
            if candidate.exists():
                override_file = str(candidate)
                break
    if override_file and Path(override_file).exists():
        try:
            with open(override_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _load_inv_db_fault_override_flags() -> dict[str, Any]:
    override_file = os.environ.get("NEXTRACE_DB_FAULT_OVERRIDE_FILE", "")
    if not override_file:
        for candidate in (
            Path("/app/var/runtime/inv_db_fault_override.json"),
            Path(__file__).resolve().parent.parent.parent / "var" / "runtime" / "inv_db_fault_override.json",
        ):
            if candidate.exists():
                override_file = str(candidate)
                break
    if override_file and Path(override_file).exists():
        try:
            with open(override_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def load_inv_config() -> InventoryDependencyConfig:
    overrides = _load_inv_override_flags()
    db_fault_overrides = _load_inv_db_fault_override_flags()

    raw_db_driver = str(
        overrides.get("db_driver")
        or os.environ.get("INV_DB_DRIVER")
        or os.environ.get("NEXTRACE_DB_DRIVER")
        or "local_tcp"
    )
    raw_cache_driver = str(
        overrides.get("cache_driver")
        or os.environ.get("INV_CACHE_DRIVER")
        or os.environ.get("NEXTRACE_CACHE_DRIVER")
        or ("redis" if os.environ.get("NEXTRACE_RUNTIME_MODE") == "docker" else "local_tcp")
    )
    stmt_timeout_ms = int(overrides.get("db_statement_timeout_ms") or db_fault_overrides.get("statement_timeout_ms") or os.environ.get("INV_DB_STATEMENT_TIMEOUT_MS", "1500"))
    lock_timeout_ms = int(overrides.get("db_lock_timeout_ms") or db_fault_overrides.get("lock_timeout_ms") or os.environ.get("INV_DB_LOCK_TIMEOUT_MS", "1000"))

    raw_delay = (
        overrides.get("operation_delay_ms")
        or db_fault_overrides.get("operation_delay_ms")
        or os.environ.get("INV_DB_OPERATION_DELAY_MS")
        or os.environ.get("NEXTRACE_DB_OPERATION_DELAY_MS")
    )
    operation_delay_ms = validate_operation_delay_ms(raw_delay)

    return InventoryDependencyConfig(
        db_driver=raw_db_driver,
        db_host=str(overrides.get("db_host") or os.environ.get("INV_DB_HOST", "127.0.0.1")),
        db_port=int(overrides.get("db_port") or os.environ.get("INV_DB_PORT", "15433")),
        db_name=str(overrides.get("db_name") or os.environ.get("INV_DB_NAME", "nextrace_inventory")),
        db_user=str(overrides.get("db_user") or os.environ.get("INV_DB_USER", "nextrace_user")),
        db_password=str(overrides.get("db_password") or os.environ.get("INV_DB_PASSWORD", "nextrace_local_dev_pw")),
        db_timeout_sec=float(overrides.get("db_timeout_sec") or os.environ.get("INV_DB_TIMEOUT_SEC", "1.0")),
        db_statement_timeout_ms=stmt_timeout_ms,
        db_lock_timeout_ms=lock_timeout_ms,
        operation_delay_ms=operation_delay_ms,
        cache_driver=raw_cache_driver,
        cache_host=str(overrides.get("cache_host") or os.environ.get("INV_CACHE_HOST", "127.0.0.1")),
        cache_port=int(overrides.get("cache_port") or os.environ.get("INV_CACHE_PORT", "16379")),
        cache_mode=str(overrides.get("cache_mode") or os.environ.get("INV_CACHE_MODE", "required")),
        cache_timeout_sec=float(overrides.get("cache_timeout_sec") or os.environ.get("INV_CACHE_TIMEOUT_SEC", "0.8")),
    )


class _TCPConnectError(OSError):
    """Raised when TCP socket connection itself fails or times out (before connect completes)."""


def _tcp_json_rpc(host: str, port: int, timeout_sec: float, payload: dict[str, Any]) -> dict[str, Any]:
    connected = False
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            connected = True
            sock.settimeout(timeout_sec)
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            fh = sock.makefile("r", encoding="utf-8")
            line = fh.readline()
            if not line:
                raise ConnectionError("Server closed connection without response")
            return json.loads(line)
    except (TimeoutError, socket.timeout) as exc:
        if not connected:
            raise _TCPConnectError(f"TCP connect timed out against {host}:{port}: {exc}") from exc
        raise


def _validate_inv_hostname(cfg: InventoryDependencyConfig) -> None:
    if cfg.db_host.endswith(".invalid") or cfg.db_host.endswith(".internal"):
        raise DatabaseDependencyError(
            "hostname_resolution_failed",
            f"Cannot resolve database host '{cfg.db_host}'",
            cfg.db_host,
            cfg.db_port,
        )
    try:
        socket.getaddrinfo(cfg.db_host, cfg.db_port)
    except socket.gaierror as exc:
        raise DatabaseDependencyError(
            "hostname_resolution_failed",
            f"Cannot resolve database host '{cfg.db_host}': {exc}",
            cfg.db_host,
            cfg.db_port,
        ) from exc


def _connect_postgresql_inv_db(cfg: InventoryDependencyConfig):
    """Establish PostgreSQL connection with bounded connect_timeout, statement_timeout, and lock_timeout."""
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row

    connect_timeout = max(1, int(round(cfg.db_timeout_sec)))
    options = f"-c statement_timeout={int(cfg.db_statement_timeout_ms)} -c lock_timeout={int(cfg.db_lock_timeout_ms)}"
    return psycopg.connect(
        host=cfg.db_host,
        port=cfg.db_port,
        dbname=cfg.db_name,
        user=cfg.db_user,
        password=cfg.db_password,
        connect_timeout=connect_timeout,
        options=options,
        row_factory=dict_row,
    )


def _map_inv_psycopg_exception(
    exc: Exception,
    cfg: InventoryDependencyConfig,
    target_relation: str = "inventory_reservations",
) -> DatabaseDependencyError:
    """Map psycopg / network exceptions to standard NexTrace error categories without exposing credentials."""
    msg = str(exc)
    raw = repr(exc)
    sqlstate = getattr(exc, "sqlstate", None)
    cls_name = type(exc).__name__
    msg_lower = msg.lower()

    if cfg.db_password and cfg.db_password in msg:
        msg = msg.replace(cfg.db_password, "***REDACTED***")
    if cfg.db_password and cfg.db_password in raw:
        raw = raw.replace(cfg.db_password, "***REDACTED***")

    # 1. Hostname resolution failed
    if (
        isinstance(exc, socket.gaierror)
        or "could not translate host name" in msg_lower
        or "name or service not known" in msg_lower
        or "getaddrinfo failed" in msg_lower
        or "nodename nor servname provided" in msg_lower
    ):
        return DatabaseDependencyError(
            "hostname_resolution_failed",
            f"Cannot resolve PostgreSQL host '{cfg.db_host}': {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    # 2. Authentication failure (SQLSTATE 28P01 / 28000)
    if (
        sqlstate in ("28P01", "28000")
        or "invalidpassword" in cls_name.lower()
        or "invalidauthorizationspecification" in cls_name.lower()
        or "password authentication failed" in msg_lower
        or "authentication failed" in msg_lower
    ):
        return DatabaseDependencyError(
            "authentication_failed",
            f"PostgreSQL authentication failed for user '{cfg.db_user}': {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    # 3. Query / statement / lock timeout (SQLSTATE 57014 / 55P03)
    if (
        sqlstate in ("57014", "55P03")
        or "querycanceled" in cls_name.lower()
        or "locknotavailable" in cls_name.lower()
        or "statement timeout" in msg_lower
        or "lock timeout" in msg_lower
        or "statement_timeout" in msg_lower
        or "lock_timeout" in msg_lower
        or "canceling statement due to statement timeout" in msg_lower
        or "canceling statement due to lock timeout" in msg_lower
        or isinstance(exc, (TimeoutError, socket.timeout))
    ):
        return DatabaseDependencyError(
            "operation_timeout",
            f"PostgreSQL operation timed out against {cfg.db_host}:{cfg.db_port}: {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    # 4. Undefined table: ONLY if actual target relation (e.g. 'inventory_reservations') does not exist
    if sqlstate == "42P01" or "undefinedtable" in cls_name.lower():
        if (
            f'relation "{target_relation}" does not exist' in msg_lower
            or f'table "{target_relation}" does not exist' in msg_lower
            or f'"{target_relation}"' in msg_lower
            or f" {target_relation} " in f" {msg_lower} "
        ):
            return DatabaseDependencyError(
                "missing_table",
                f"Required table '{target_relation}' does not exist in active database schema",
                cfg.db_host,
                cfg.db_port,
            )
        return DatabaseDependencyError(
            "database_error",
            f"PostgreSQL undefined relation error: {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    # Explicitly distinguish missing database (3D000) or missing schema (3F000)
    if sqlstate == "3D000" or "invalidcatalogname" in cls_name.lower():
        return DatabaseDependencyError(
            "database_error",
            f"PostgreSQL database '{cfg.db_name}' does not exist: {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    if sqlstate == "3F000" or "invalidschemaname" in cls_name.lower():
        return DatabaseDependencyError(
            "database_error",
            f"PostgreSQL schema does not exist: {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    # 5. Connection refused / service down
    if (
        sqlstate in ("08001", "08006")
        or isinstance(exc, (ConnectionRefusedError, ConnectionResetError))
        or "connectionrefused" in cls_name.lower()
        or "connection refused" in msg_lower
        or "could not connect to server" in msg_lower
        or "is the server running" in msg_lower
        or "10061" in msg
        or "111" in msg
    ):
        return DatabaseDependencyError(
            "connection_refused",
            f"PostgreSQL connection refused at {cfg.db_host}:{cfg.db_port}: {msg}",
            cfg.db_host,
            cfg.db_port,
        )

    return DatabaseDependencyError("database_error", msg, cfg.db_host, cfg.db_port)


def _probe_postgresql_inv_db(cfg: InventoryDependencyConfig, started: float) -> dict[str, Any]:
    try:
        _validate_inv_hostname(cfg)
        with _connect_postgresql_inv_db(cfg) as conn:
            with conn.cursor() as cur:
                if cfg.operation_delay_ms > 0:
                    cur.execute("SELECT pg_sleep(%s);", (cfg.operation_delay_ms / 1000.0,))
                cur.execute("SELECT 1 FROM inventory_reservations LIMIT 1;")
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {
            "ok": True,
            "configured_host": cfg.db_host,
            "configured_port": cfg.db_port,
            "dbname": cfg.db_name,
            "backend": "postgresql",
            "latency_ms": latency_ms,
            "error_category": None,
        }
    except DatabaseDependencyError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {
            "ok": False,
            "configured_host": exc.configured_host,
            "configured_port": exc.configured_port,
            "dbname": cfg.db_name,
            "backend": "postgresql",
            "latency_ms": latency_ms,
            "error_category": exc.error_category,
            "detail": exc.detail,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        err = _map_inv_psycopg_exception(exc, cfg, target_relation="inventory_reservations")
        return {
            "ok": False,
            "configured_host": err.configured_host,
            "configured_port": err.configured_port,
            "dbname": cfg.db_name,
            "backend": "postgresql",
            "latency_ms": latency_ms,
            "error_category": err.error_category,
            "detail": err.detail,
        }


def probe_inv_db(cfg: InventoryDependencyConfig | None = None) -> dict[str, Any]:
    active = cfg or load_inv_config()
    started = time.perf_counter()
    driver = active.db_driver.lower()

    if driver in ("postgresql", "postgres"):
        return _probe_postgresql_inv_db(active, started)

    if driver in ("local_tcp", "sqlite_tcp"):
        if active.db_host.endswith(".invalid") or active.db_host.endswith(".internal"):
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.db_host,
                "configured_port": active.db_port,
                "latency_ms": latency_ms,
                "error_category": "hostname_resolution_failed",
                "detail": f"Cannot resolve database host '{active.db_host}'",
            }
        try:
            try:
                socket.getaddrinfo(active.db_host, active.db_port)
            except socket.gaierror as exc:
                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                return {
                    "ok": False,
                    "configured_host": active.db_host,
                    "configured_port": active.db_port,
                    "latency_ms": latency_ms,
                    "error_category": "hostname_resolution_failed",
                    "detail": str(exc),
                }
            resp = _tcp_json_rpc(
                active.db_host,
                active.db_port,
                active.db_timeout_sec,
                {
                    "action": "ping",
                    "user": active.db_user,
                    "password": active.db_password,
                    "dbname": active.db_name,
                },
            )
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if not resp.get("ok"):
                return {
                    "ok": False,
                    "configured_host": active.db_host,
                    "configured_port": active.db_port,
                    "latency_ms": latency_ms,
                    "error_category": resp.get("error_category", "db_error"),
                    "detail": resp.get("detail", "Database ping failed"),
                }
            return {
                "ok": True,
                "configured_host": active.db_host,
                "configured_port": active.db_port,
                "latency_ms": latency_ms,
                "backend": "local_tcp",
                "error_category": None,
            }
        except _TCPConnectError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.db_host,
                "configured_port": active.db_port,
                "latency_ms": latency_ms,
                "error_category": "connection_refused",
                "detail": str(exc),
            }
        except (TimeoutError, socket.timeout) as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.db_host,
                "configured_port": active.db_port,
                "latency_ms": latency_ms,
                "error_category": "operation_timeout",
                "detail": str(exc),
            }
        except OSError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.db_host,
                "configured_port": active.db_port,
                "latency_ms": latency_ms,
                "error_category": "connection_refused",
                "detail": str(exc),
            }

    raise ValueError(f"Unsupported database driver: '{active.db_driver}'. Supported: 'local_tcp', 'postgresql'.")


def _redis_resp_command(host: str, port: int, timeout_sec: float, *args: str) -> str:
    """Send Redis command using RESP protocol and return raw response string."""
    parts = [f"*{len(args)}\r\n"]
    for a in args:
        encoded = a.encode("utf-8")
        parts.append(f"${len(encoded)}\r\n{a}\r\n")
    payload = "".join(parts).encode("utf-8")

    with socket.create_connection((host, port), timeout=timeout_sec) as s:
        s.settimeout(timeout_sec)
        s.sendall(payload)
        resp = s.recv(4096).decode("utf-8", errors="replace")
        return resp


def _redis_resp_ping(host: str, port: int, timeout_sec: float) -> bool:
    """Send Redis RESP PING and check for +PONG response."""
    with socket.create_connection((host, port), timeout=timeout_sec) as s:
        s.settimeout(timeout_sec)
        s.sendall(b"*1\r\n$4\r\nPING\r\n")
        raw = s.recv(128)
        return b"PONG" in raw


def probe_inv_cache(cfg: InventoryDependencyConfig | None = None) -> dict[str, Any]:
    active = cfg or load_inv_config()
    started = time.perf_counter()
    driver = active.cache_driver.lower()

    if driver in ("redis", "redis_real") or active.cache_port == 6379 or os.environ.get("NEXTRACE_RUNTIME_MODE") == "docker":
        try:
            ok = _redis_resp_ping(active.cache_host, active.cache_port, active.cache_timeout_sec)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if ok:
                return {
                    "ok": True,
                    "configured_host": active.cache_host,
                    "configured_port": active.cache_port,
                    "cache_mode": active.cache_mode,
                    "backend": "redis_real",
                    "latency_ms": latency_ms,
                    "error_category": None,
                }
            return {
                "ok": False,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "latency_ms": latency_ms,
                "error_category": "cache_error",
                "detail": "Redis PING did not return PONG",
            }
        except (TimeoutError, socket.timeout) as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "latency_ms": latency_ms,
                "error_category": "cache_timeout",
                "detail": str(exc),
            }
        except OSError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "latency_ms": latency_ms,
                "error_category": "cache_connection_refused",
                "detail": str(exc),
            }

    if driver in ("local_tcp", "local_tcp_cache_substitute"):
        try:
            resp = _tcp_json_rpc(
                active.cache_host,
                active.cache_port,
                active.cache_timeout_sec,
                {"action": "ping"},
            )
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if not resp.get("ok"):
                return {
                    "ok": False,
                    "configured_host": active.cache_host,
                    "configured_port": active.cache_port,
                    "cache_mode": active.cache_mode,
                    "latency_ms": latency_ms,
                    "error_category": resp.get("error_category", "cache_error"),
                    "detail": resp.get("detail", "Cache ping failed"),
                }
            return {
                "ok": True,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "backend": resp.get("backend", "local_tcp_cache_substitute"),
                "latency_ms": latency_ms,
                "error_category": None,
            }
        except _TCPConnectError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "latency_ms": latency_ms,
                "error_category": "cache_connection_refused",
                "detail": str(exc),
            }
        except (TimeoutError, socket.timeout) as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "latency_ms": latency_ms,
                "error_category": "cache_timeout",
                "detail": str(exc),
            }
        except OSError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": active.cache_host,
                "configured_port": active.cache_port,
                "cache_mode": active.cache_mode,
                "latency_ms": latency_ms,
                "error_category": "cache_connection_refused",
                "detail": str(exc),
            }

    raise ValueError(f"Unsupported cache driver: '{active.cache_driver}'. Supported: 'local_tcp', 'redis'.")


def _write_cache_reservation(cfg: InventoryDependencyConfig, reservation_id: str, sku: str, quantity: int) -> None:
    """Store reservation in Redis or local TCP cache substitute. Raises on failure."""
    key = f"reservation:{reservation_id}"
    val = f"{sku}:{quantity}"
    driver = cfg.cache_driver.lower()
    if driver in ("redis", "redis_real") or cfg.cache_port == 6379 or os.environ.get("NEXTRACE_RUNTIME_MODE") == "docker":
        raw = _redis_resp_command(cfg.cache_host, cfg.cache_port, cfg.cache_timeout_sec, "SET", key, val)
        clean = (raw or "").strip()
        if clean != "+OK":
            raise RuntimeError(f"Redis SET failed with unexpected response: {clean if clean else '<empty>'}")
    else:
        resp = _tcp_json_rpc(cfg.cache_host, cfg.cache_port, cfg.cache_timeout_sec, {"action": "set", "key": key, "value": val})
        if not resp.get("ok"):
            err_cat = resp.get("error_category", "cache_error")
            detail = resp.get("detail", "Local cache SET failed")
            raise RuntimeError(f"[{err_cat}] {detail}")


def _delete_cache_reservation(cfg: InventoryDependencyConfig, reservation_id: str) -> bool:
    """Attempt best-effort compensation cleanup of reservation key from Redis or local TCP cache.
    Returns True if deletion succeeded, False otherwise."""
    key = f"reservation:{reservation_id}"
    driver = cfg.cache_driver.lower()
    try:
        if driver in ("redis", "redis_real") or cfg.cache_port == 6379 or os.environ.get("NEXTRACE_RUNTIME_MODE") == "docker":
            raw = _redis_resp_command(cfg.cache_host, cfg.cache_port, cfg.cache_timeout_sec, "DEL", key)
            if not raw:
                return False
            clean = raw.strip()
            if clean.startswith(":") and clean[1:].lstrip("-").isdigit():
                # Valid integer response (e.g. :1 for deleted, :0 if key already absent)
                return True
            return False
        else:
            resp = _tcp_json_rpc(cfg.cache_host, cfg.cache_port, cfg.cache_timeout_sec, {"action": "delete", "key": key})
            return bool(resp.get("ok"))
    except Exception:
        return False


def _map_cache_exception(exc: Exception) -> tuple[str, str]:
    """Map cache exception to (error_category, safe_detail)."""
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "cache_timeout", f"Cache operation timed out: {type(exc).__name__}"
    if isinstance(exc, (ConnectionRefusedError, ConnectionResetError, _TCPConnectError)):
        return "cache_connection_refused", f"Cache connection refused: {type(exc).__name__}"
    if isinstance(exc, OSError):
        msg = str(exc)
        if "10061" in msg or "111" in msg or "refused" in msg.lower():
            return "cache_connection_refused", f"Cache connection refused: {type(exc).__name__}"
        return "cache_error", f"Cache socket error: {type(exc).__name__}"
    msg = str(exc)
    if "cache_timeout" in msg:
        return "cache_timeout", msg
    if "cache_connection_refused" in msg:
        return "cache_connection_refused", msg
    return "cache_error", f"Cache operation failed: {msg}"


class ReserveStockPayload(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=500)


@app.get("/health/live")
def health_live() -> dict[str, Any]:
    return {"service": SERVICE_NAME, "status": "live", "timestamp": utc_now_iso()}


@app.get("/health/ready")
def health_ready(response: Response) -> dict[str, Any]:
    cfg = load_inv_config()
    db_probe = probe_inv_db(cfg)
    cache_probe = probe_inv_cache(cfg)
    cache_ok = bool(cache_probe.get("ok")) or (cfg.cache_mode == "fallback_db")
    if db_probe.get("ok") and cache_ok:
        return {
            "service": SERVICE_NAME,
            "status": "ready",
            "database_connectivity": "ok",
            "cache_connectivity": "ok" if cache_probe.get("ok") else "degraded_fallback_db",
            "latency_ms": round(float(db_probe.get("latency_ms", 0.0)) + float(cache_probe.get("latency_ms", 0.0)), 2),
            "timestamp": utc_now_iso(),
        }
    response.status_code = 503
    err_cat = db_probe.get("error_category") if not db_probe.get("ok") else cache_probe.get("error_category")
    return {
        "service": SERVICE_NAME,
        "status": "not_ready",
        "database_connectivity": "ok" if db_probe.get("ok") else "failed",
        "cache_connectivity": "ok" if cache_probe.get("ok") else "failed",
        "error_category": err_cat,
        "timestamp": utc_now_iso(),
    }


@app.get("/internal/diagnostics/db-config")
def diagnostics_db_config() -> dict[str, Any]:
    cfg = load_inv_config()
    return {
        "service": SERVICE_NAME,
        "sanitized_config": cfg.sanitized_dict(),
        "timestamp": utc_now_iso(),
    }


@app.get("/internal/diagnostics/db-connectivity")
def diagnostics_db_connectivity() -> dict[str, Any]:
    probe = probe_inv_db()
    return {
        "service": SERVICE_NAME,
        "probe": probe,
        "timestamp": utc_now_iso(),
    }


@app.get("/internal/diagnostics/cache-connectivity")
def diagnostics_cache_connectivity() -> dict[str, Any]:
    probe = probe_inv_cache()
    return {
        "service": SERVICE_NAME,
        "probe": probe,
        "timestamp": utc_now_iso(),
    }


@app.get("/internal/metrics")
def internal_metrics() -> dict[str, Any]:
    count = int(_METRICS["request_count"])
    avg_ms = round(float(_METRICS["total_duration_ms"]) / count, 2) if count > 0 else 0.0
    error_rate = round(int(_METRICS["failure_count"]) / count, 4) if count > 0 else 0.0
    min_samples = 2
    return {
        "service": SERVICE_NAME,
        "started_at_utc": STARTED_AT_UTC,
        "collection_time_utc": utc_now_iso(),
        "last_event_time_utc": _METRICS["last_event_time_utc"] or STARTED_AT_UTC,
        "collection_window_sec": round(max(0.1, time.monotonic() - STARTED_MONOTONIC), 2),
        "request_count": count,
        "failure_count": int(_METRICS["failure_count"]),
        "error_rate": error_rate,
        "dependency_failures": int(_METRICS["dependency_failures"]),
        "dependency_timeouts": int(_METRICS["dependency_timeouts"]),
        "avg_duration_ms": avg_ms,
        "max_duration_ms": round(float(_METRICS["max_duration_ms"]), 2),
        "minimum_sample_threshold": min_samples,
        "sample_sufficient": count >= min_samples,
        "resets_on_restart": True,
    }


@app.post("/internal/metrics/reset")
def reset_internal_metrics() -> dict[str, Any]:
    _METRICS["request_count"] = 0
    _METRICS["failure_count"] = 0
    _METRICS["dependency_failures"] = 0
    _METRICS["dependency_timeouts"] = 0
    _METRICS["total_duration_ms"] = 0.0
    _METRICS["max_duration_ms"] = 0.0
    _METRICS["last_event_time_utc"] = utc_now_iso()
    return {"service": SERVICE_NAME, "metrics_reset": True, "timestamp": utc_now_iso()}


@app.post("/reserve")
def reserve_stock(payload: ReserveStockPayload, request: Request, response: Response) -> dict[str, Any]:
    request_id = request.headers.get("X-Request-ID") or f"invreq-{uuid.uuid4().hex[:12]}"
    reservation_id = f"rsv-{uuid.uuid4().hex[:10]}"
    started = time.perf_counter()
    cfg = load_inv_config()

    append_log_event(
        service=SERVICE_NAME,
        level="INFO",
        event="inventory_reservation_started",
        request_id=request_id,
        reservation_id=reservation_id,
        sku=payload.sku,
        quantity=payload.quantity,
        configured_db_host=cfg.db_host,
        configured_db_port=cfg.db_port,
        configured_cache_host=cfg.cache_host,
        configured_cache_port=cfg.cache_port,
        cache_mode=cfg.cache_mode,
    )

    flags = _load_inv_override_flags()
    if flags.get("inject_unmodeled_sku_parser_exception"):
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["failure_count"] += 1
        _METRICS["total_duration_ms"] += duration_ms
        _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
        _METRICS["last_event_time_utc"] = utc_now_iso()
        response.status_code = 500
        append_log_event(
            service=SERVICE_NAME,
            level="ERROR",
            event="internal_processing_exception",
            request_id=request_id,
            reservation_id=reservation_id,
            error_category="sku_format_parser_exception",
            error_detail="Invalid barcode format parser crash in SKU tokenizer",
            duration_ms=duration_ms,
        )
        return {
            "error": "internal_application_error",
            "error_category": "sku_format_parser_exception",
            "error_detail": "Invalid barcode format parser crash in SKU tokenizer",
            "request_id": request_id,
        }

    # Step 1: Check/update cache reservation lock
    cache_written = False
    cache_probe = probe_inv_cache(cfg)
    if not cache_probe.get("ok"):
        if cfg.cache_mode == "required":
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            _METRICS["request_count"] += 1
            _METRICS["failure_count"] += 1
            _METRICS["dependency_failures"] += 1
            if cache_probe.get("error_category") == "cache_timeout":
                _METRICS["dependency_timeouts"] += 1
            _METRICS["total_duration_ms"] += duration_ms
            _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
            _METRICS["last_event_time_utc"] = utc_now_iso()
            response.status_code = 503
            append_log_event(
                service=SERVICE_NAME,
                level="ERROR",
                event="cache_reservation_failed",
                request_id=request_id,
                reservation_id=reservation_id,
                configured_cache_host=cfg.cache_host,
                configured_cache_port=cfg.cache_port,
                error_category=cache_probe.get("error_category", "cache_connection_refused"),
                error_detail=cache_probe.get("detail", "Cache unreachable"),
                duration_ms=duration_ms,
            )
            return {
                "error": "cache_unavailable",
                "error_category": cache_probe.get("error_category", "cache_connection_refused"),
                "request_id": request_id,
            }
        else:
            append_log_event(
                service=SERVICE_NAME,
                level="WARNING",
                event="cache_degraded_fallback_db",
                request_id=request_id,
                reservation_id=reservation_id,
                error_category=cache_probe.get("error_category"),
            )
    else:
        # Cache is available: store reservation lock key
        try:
            _write_cache_reservation(cfg, reservation_id, payload.sku, payload.quantity)
            cache_written = True
            append_log_event(
                service=SERVICE_NAME,
                level="INFO",
                event="cache_reservation_written",
                request_id=request_id,
                reservation_id=reservation_id,
                sku=payload.sku,
                quantity=payload.quantity,
            )
        except Exception as exc:
            err_cat, err_detail = _map_cache_exception(exc)
            if cfg.cache_mode == "required":
                duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
                _METRICS["request_count"] += 1
                _METRICS["failure_count"] += 1
                _METRICS["dependency_failures"] += 1
                if err_cat == "cache_timeout":
                    _METRICS["dependency_timeouts"] += 1
                _METRICS["total_duration_ms"] += duration_ms
                _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
                _METRICS["last_event_time_utc"] = utc_now_iso()
                response.status_code = 503
                append_log_event(
                    service=SERVICE_NAME,
                    level="ERROR",
                    event="cache_reservation_write_failed",
                    request_id=request_id,
                    reservation_id=reservation_id,
                    configured_cache_host=cfg.cache_host,
                    configured_cache_port=cfg.cache_port,
                    error_category=err_cat,
                    error_detail=err_detail,
                    duration_ms=duration_ms,
                )
                return {
                    "error": "cache_unavailable",
                    "error_category": err_cat,
                    "request_id": request_id,
                }
            else:
                append_log_event(
                    service=SERVICE_NAME,
                    level="WARNING",
                    event="cache_write_failed_fallback_db",
                    request_id=request_id,
                    reservation_id=reservation_id,
                    error_category=err_cat,
                    error_detail=err_detail,
                )

    # Step 2: Persist reservation to inventory-db
    db_probe = probe_inv_db(cfg)
    if not db_probe.get("ok"):
        if cache_written:
            cleanup_ok = _delete_cache_reservation(cfg, reservation_id)
            append_log_event(
                service=SERVICE_NAME,
                level="INFO" if cleanup_ok else "WARNING",
                event="cache_compensation_cleanup",
                request_id=request_id,
                reservation_id=reservation_id,
                cleanup_success=cleanup_ok,
                reason="db_probe_failed",
            )
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["failure_count"] += 1
        _METRICS["dependency_failures"] += 1
        if db_probe.get("error_category") == "operation_timeout":
            _METRICS["dependency_timeouts"] += 1
        _METRICS["total_duration_ms"] += duration_ms
        _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
        _METRICS["last_event_time_utc"] = utc_now_iso()
        response.status_code = 503
        append_log_event(
            service=SERVICE_NAME,
            level="ERROR",
            event="database_write_failed",
            request_id=request_id,
            reservation_id=reservation_id,
            configured_db_host=cfg.db_host,
            configured_db_port=cfg.db_port,
            error_category=db_probe.get("error_category", "connection_refused"),
            error_detail=db_probe.get("detail", "Database unreachable"),
            duration_ms=duration_ms,
        )
        return {
            "error": "database_unavailable",
            "error_category": db_probe.get("error_category", "connection_refused"),
            "request_id": request_id,
        }

    # Execute direct database insertion
    if cfg.db_driver.lower() in ("postgresql", "postgres"):
        try:
            with _connect_postgresql_inv_db(cfg) as conn:
                try:
                    with conn.transaction():
                        with conn.cursor() as cur:
                            if cfg.operation_delay_ms > 0:
                                cur.execute("SELECT pg_sleep(%s);", (cfg.operation_delay_ms / 1000.0,))
                            cur.execute(
                                """
                                INSERT INTO inventory_reservations (reservation_id, sku, quantity, request_id, status, created_at)
                                VALUES (%s, %s, %s, %s, %s, NOW());
                                """,
                                (reservation_id, payload.sku, payload.quantity, request_id, "RESERVED"),
                            )
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise
        except Exception as exc:
            if cache_written:
                cleanup_ok = _delete_cache_reservation(cfg, reservation_id)
                append_log_event(
                    service=SERVICE_NAME,
                    level="INFO" if cleanup_ok else "WARNING",
                    event="cache_compensation_cleanup",
                    request_id=request_id,
                    reservation_id=reservation_id,
                    cleanup_success=cleanup_ok,
                    reason="postgres_write_failed",
                )
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            _METRICS["request_count"] += 1
            _METRICS["failure_count"] += 1
            _METRICS["dependency_failures"] += 1
            _METRICS["total_duration_ms"] += duration_ms
            _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
            _METRICS["last_event_time_utc"] = utc_now_iso()
            response.status_code = 503
            err = _map_inv_psycopg_exception(exc, cfg, target_relation="inventory_reservations")
            if err.error_category == "operation_timeout":
                _METRICS["dependency_timeouts"] += 1
            append_log_event(
                service=SERVICE_NAME,
                level="ERROR",
                event="database_write_failed",
                request_id=request_id,
                reservation_id=reservation_id,
                configured_db_host=cfg.db_host,
                configured_db_port=cfg.db_port,
                error_category=err.error_category,
                error_detail=err.detail,
                duration_ms=duration_ms,
            )
            return {
                "error": "database_unavailable",
                "error_category": err.error_category,
                "request_id": request_id,
            }
    else:
        try:
            resp = _tcp_json_rpc(
                cfg.db_host,
                cfg.db_port,
                cfg.db_timeout_sec,
                {
                    "action": "insert_order",
                    "user": cfg.db_user,
                    "password": cfg.db_password,
                    "dbname": cfg.db_name,
                    "order_id": reservation_id,
                    "product_id": payload.sku,
                    "quantity": payload.quantity,
                    "request_id": request_id,
                    "created_at": utc_now_iso(),
                },
            )
            if not resp.get("ok"):
                raise RuntimeError(resp.get("detail", "Local database insert failed"))
        except Exception as exc:
            if cache_written:
                cleanup_ok = _delete_cache_reservation(cfg, reservation_id)
                append_log_event(
                    service=SERVICE_NAME,
                    level="INFO" if cleanup_ok else "WARNING",
                    event="cache_compensation_cleanup",
                    request_id=request_id,
                    reservation_id=reservation_id,
                    cleanup_success=cleanup_ok,
                    reason="local_db_write_failed",
                )
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
            _METRICS["request_count"] += 1
            _METRICS["failure_count"] += 1
            _METRICS["dependency_failures"] += 1
            err_cat = "operation_timeout" if isinstance(exc, (TimeoutError, socket.timeout)) else "database_error"
            if err_cat == "operation_timeout":
                _METRICS["dependency_timeouts"] += 1
            _METRICS["total_duration_ms"] += duration_ms
            _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
            _METRICS["last_event_time_utc"] = utc_now_iso()
            response.status_code = 503
            append_log_event(
                service=SERVICE_NAME,
                level="ERROR",
                event="database_write_failed",
                request_id=request_id,
                reservation_id=reservation_id,
                configured_db_host=cfg.db_host,
                configured_db_port=cfg.db_port,
                error_category=err_cat,
                error_detail=str(exc),
                duration_ms=duration_ms,
            )
            return {
                "error": "database_unavailable",
                "error_category": err_cat,
                "request_id": request_id,
            }

    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    _METRICS["request_count"] += 1
    _METRICS["total_duration_ms"] += duration_ms
    _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
    _METRICS["last_event_time_utc"] = utc_now_iso()
    response.status_code = 201
    append_log_event(
        service=SERVICE_NAME,
        level="INFO",
        event="inventory_reserved",
        request_id=request_id,
        reservation_id=reservation_id,
        sku=payload.sku,
        quantity=payload.quantity,
        duration_ms=duration_ms,
        status_code=201,
    )
    return {
        "reservation_id": reservation_id,
        "sku": payload.sku,
        "quantity": payload.quantity,
        "request_id": request_id,
        "created_at": utc_now_iso(),
    }


@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: str, response: Response) -> dict[str, Any]:
    cfg = load_inv_config()
    if cfg.db_driver.lower() in ("postgresql", "postgres"):
        try:
            with _connect_postgresql_inv_db(cfg) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT reservation_id, sku, quantity, request_id, status, created_at::text
                        FROM inventory_reservations
                        WHERE reservation_id = %s;
                        """,
                        (reservation_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        response.status_code = 404
                        return {"error": "not_found", "reservation_id": reservation_id}
                    return {
                        "reservation_id": row["reservation_id"] if isinstance(row, dict) else row[0],
                        "sku": row["sku"] if isinstance(row, dict) else row[1],
                        "quantity": row["quantity"] if isinstance(row, dict) else row[2],
                        "request_id": row["request_id"] if isinstance(row, dict) else row[3],
                        "status": row["status"] if isinstance(row, dict) else row[4],
                        "created_at": row["created_at"] if isinstance(row, dict) else row[5],
                    }
        except Exception as exc:
            response.status_code = 503
            err = _map_inv_psycopg_exception(exc, cfg, target_relation="inventory_reservations")
            return {"error": "database_unavailable", "error_category": err.error_category}
    else:
        try:
            resp = _tcp_json_rpc(
                cfg.db_host,
                cfg.db_port,
                cfg.db_timeout_sec,
                {
                    "action": "get_order",
                    "user": cfg.db_user,
                    "password": cfg.db_password,
                    "dbname": cfg.db_name,
                    "order_id": reservation_id,
                },
            )
            order = resp.get("order") or resp.get("record")
            if not order:
                response.status_code = 404
                return {"error": "not_found", "reservation_id": reservation_id}
            return {
                "reservation_id": order["order_id"],
                "sku": order["product_id"],
                "quantity": order["quantity"],
                "request_id": order["request_id"],
                "status": "RESERVED",
                "created_at": order["created_at"],
            }
        except Exception as exc:
            response.status_code = 503
            return {"error": "database_unavailable", "detail": str(exc)}
