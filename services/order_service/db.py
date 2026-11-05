"""Database client abstraction for Order Service with lazy connections and protocol-level semantics."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import socket
import time
from typing import Any, Optional

from nextrace_lab.logging_utils import utc_now_iso

_SCHEMA_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def sanitize_schema_identifier(identifier: str) -> str:
    """Strictly validate a single PostgreSQL schema identifier (alphanumeric and underscore)."""
    clean = str(identifier).strip()
    if not clean or not _SCHEMA_IDENTIFIER_RE.match(clean):
        raise ValueError(
            f"Invalid PostgreSQL schema identifier: '{clean}'. "
            "Identifiers must start with a letter/underscore, contain only alphanumeric/underscore characters, "
            "and be at most 63 characters long."
        )
    return clean


def sanitize_search_path(raw: str | None) -> str | None:
    """Validate and sanitize a comma-separated PostgreSQL search_path string."""
    if not raw or not isinstance(raw, str):
        return None
    raw_clean = raw.strip()
    if not raw_clean:
        return None
    parts = [sanitize_schema_identifier(p) for p in raw_clean.split(",") if p.strip()]
    if not parts:
        return None
    return ", ".join(parts)


def validate_operation_delay_ms(raw: Any) -> int:
    """Strictly validate operation_delay_ms (integer >= 0, upper bounded at 60000 ms)."""
    if raw is None or isinstance(raw, bool):
        return 0
    val: int
    if isinstance(raw, int):
        val = raw
    elif isinstance(raw, str):
        clean = raw.strip()
        if not clean or not clean.isdigit():
            return 0
        try:
            val = int(clean)
        except ValueError:
            return 0
    else:
        return 0

    if val < 0:
        return 0
    if val > 60000:
        return 60000
    return val


def validate_positive_timeout_ms(raw: Any, default_ms: int) -> int:
    """Strictly validate positive integer timeout in milliseconds (> 0), falling back to default_ms."""
    if raw is None or isinstance(raw, bool):
        return default_ms
    val: int
    if isinstance(raw, int):
        val = raw
    elif isinstance(raw, str):
        clean = raw.strip()
        if not clean or not clean.isdigit():
            return default_ms
        try:
            val = int(clean)
        except ValueError:
            return default_ms
    else:
        return default_ms

    if val <= 0:
        return default_ms
    return val


@dataclass(frozen=True)
class DatabaseConfig:
    driver: str  # "local_tcp" or "postgresql"
    host: str
    port: int
    dbname: str
    user: str
    password: str
    connect_timeout_sec: float = 1.0
    statement_timeout_ms: int = 1500
    lock_timeout_ms: int = 1000
    search_path: Optional[str] = None
    operation_delay_ms: int = 0

    @property
    def db_search_path(self) -> Optional[str]:
        return self.search_path

    def sanitized_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "db_driver": self.driver,
            "db_host": self.host,
            "db_port": self.port,
            "db_name": self.dbname,
            "db_user": self.user,
            "db_password_redacted": "***REDACTED***",
            "connect_timeout_sec": self.connect_timeout_sec,
            "statement_timeout_ms": self.statement_timeout_ms,
            "lock_timeout_ms": self.lock_timeout_ms,
            "operation_delay_ms": self.operation_delay_ms,
        }
        if self.search_path is not None:
            d["db_search_path"] = self.search_path
        return d


class DatabaseOperationError(RuntimeError):
    """Structured database failure with explicit error_category."""

    def __init__(self, error_category: str, detail: str, configured_host: str, configured_port: int) -> None:
        super().__init__(f"[{error_category}] {detail}")
        self.error_category = error_category
        self.detail = detail
        self.configured_host = configured_host
        self.configured_port = configured_port


DatabaseDependencyError = DatabaseOperationError


def load_db_config() -> DatabaseConfig:
    """Load DB config from environment variables, allowing runtime override file for controlled faults."""
    override_file = os.environ.get("NEXTRACE_ORDER_CONFIG_OVERRIDE_FILE", "")
    overrides: dict[str, Any] = {}
    if override_file and Path(override_file).exists():
        try:
            with open(override_file, "r", encoding="utf-8") as fh:
                overrides = json.load(fh)
        except Exception:
            overrides = {}

    driver = str(overrides.get("db_driver") or os.environ.get("NEXTRACE_DB_DRIVER", "local_tcp"))
    host = str(overrides.get("db_host") or os.environ.get("DB_HOST", "127.0.0.1"))
    port = int(overrides.get("db_port") or os.environ.get("DB_PORT", "15432"))
    dbname = str(overrides.get("db_name") or os.environ.get("DB_NAME", "nextrace_orders"))
    user = str(overrides.get("db_user") or os.environ.get("DB_USER", "nextrace_user"))
    password = str(overrides.get("db_password") or os.environ.get("DB_PASSWORD", "nextrace_local_dev_pw"))
    timeout_sec = float(overrides.get("connect_timeout_sec") or os.environ.get("DB_CONNECT_TIMEOUT_SEC", "1.0"))

    raw_stmt = (
        overrides["statement_timeout_ms"]
        if "statement_timeout_ms" in overrides
        else os.environ.get("DB_STATEMENT_TIMEOUT_MS")
    )
    stmt_timeout_ms = validate_positive_timeout_ms(raw_stmt, default_ms=1500)

    raw_lock = (
        overrides["lock_timeout_ms"]
        if "lock_timeout_ms" in overrides
        else os.environ.get("DB_LOCK_TIMEOUT_MS")
    )
    lock_timeout_ms = validate_positive_timeout_ms(raw_lock, default_ms=1000)

    raw_search_path = (
        overrides.get("db_search_path")
        or overrides.get("search_path")
        or os.environ.get("DB_SEARCH_PATH")
        or os.environ.get("NEXTRACE_DB_SEARCH_PATH")
    )
    search_path = sanitize_search_path(str(raw_search_path)) if raw_search_path else None

    raw_delay = (
        overrides["operation_delay_ms"]
        if "operation_delay_ms" in overrides
        else (os.environ.get("DB_OPERATION_DELAY_MS") or os.environ.get("NEXTRACE_DB_OPERATION_DELAY_MS"))
    )
    operation_delay_ms = validate_operation_delay_ms(raw_delay)

    return DatabaseConfig(
        driver=driver,
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout_sec=timeout_sec,
        statement_timeout_ms=stmt_timeout_ms,
        lock_timeout_ms=lock_timeout_ms,
        search_path=search_path,
        operation_delay_ms=operation_delay_ms,
    )


def _tcp_rpc(cfg: DatabaseConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if cfg.host.endswith(".invalid") or cfg.host.endswith(".internal"):
        raise DatabaseOperationError(
            "hostname_resolution_failed",
            f"Cannot resolve database host '{cfg.host}'",
            cfg.host,
            cfg.port,
        )

    connected = False
    try:
        try:
            socket.getaddrinfo(cfg.host, cfg.port)
        except socket.gaierror as exc:
            raise DatabaseOperationError(
                "hostname_resolution_failed",
                f"Cannot resolve database host '{cfg.host}': {exc}",
                cfg.host,
                cfg.port,
            ) from exc

        with socket.create_connection((cfg.host, cfg.port), timeout=cfg.connect_timeout_sec) as sock:
            connected = True
            sock.settimeout(cfg.connect_timeout_sec)
            body = (json.dumps(payload) + "\n").encode("utf-8")
            sock.sendall(body)

            fh = sock.makefile("r", encoding="utf-8")
            line = fh.readline()
            if not line:
                raise DatabaseOperationError(
                    "connection_refused",
                    "Database process closed connection without returning data",
                    cfg.host,
                    cfg.port,
                )

            resp = json.loads(line)
            if not resp.get("ok", False):
                err_cat = resp.get("error_category", "database_error")
                detail = resp.get("detail") or resp.get("error") or "Unknown database error"
                raise DatabaseOperationError(err_cat, detail, cfg.host, cfg.port)
            return resp

    except DatabaseOperationError:
        raise
    except (TimeoutError, socket.timeout) as exc:
        if not connected:
            raise DatabaseOperationError(
                "operation_timeout",
                f"Database connect timed out against {cfg.host}:{cfg.port}: {exc}",
                cfg.host,
                cfg.port,
            ) from exc
        raise DatabaseOperationError(
            "operation_timeout",
            f"Database operation exceeded timeout ({cfg.connect_timeout_sec}s): {exc}",
            cfg.host,
            cfg.port,
        ) from exc
    except OSError as exc:
        raise DatabaseOperationError(
            "connection_refused",
            f"Cannot connect to database at {cfg.host}:{cfg.port}: {exc}",
            cfg.host,
            cfg.port,
        ) from exc


def _connect_postgresql(cfg: DatabaseConfig):
    """Establish PostgreSQL connection with bounded connect_timeout, statement_timeout, and lock_timeout."""
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row

    connect_timeout = max(1, int(round(cfg.connect_timeout_sec)))
    options_parts = [
        f"-c statement_timeout={int(cfg.statement_timeout_ms)}",
        f"-c lock_timeout={int(cfg.lock_timeout_ms)}",
    ]
    if cfg.search_path:
        options_parts.append(f"-c search_path={cfg.search_path}")
    options = " ".join(options_parts)
    return psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=connect_timeout,
        options=options,
        row_factory=dict_row,
    )


def probe_db_connectivity(config: DatabaseConfig | None = None) -> dict[str, Any]:
    """Execute a protocol-level connectivity and schema probe."""
    cfg = config or load_db_config()
    started = time.perf_counter()
    driver = cfg.driver.lower()

    if driver in ("local_tcp", "sqlite_tcp"):
        try:
            _tcp_rpc(
                cfg,
                {
                    "action": "ping",
                    "op": "ping",
                    "user": cfg.user,
                    "password": cfg.password,
                    "dbname": cfg.dbname,
                },
            )
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": True,
                "configured_host": cfg.host,
                "configured_port": cfg.port,
                "dbname": cfg.dbname,
                "latency_ms": latency_ms,
                "error_category": None,
            }
        except DatabaseOperationError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "ok": False,
                "configured_host": exc.configured_host,
                "configured_port": exc.configured_port,
                "dbname": cfg.dbname,
                "latency_ms": latency_ms,
                "error_category": exc.error_category,
                "detail": exc.detail,
            }

    if driver in ("postgresql", "postgres"):
        return _probe_postgresql(cfg, started)

    raise ValueError(f"Unsupported database driver: '{cfg.driver}'. Supported: 'local_tcp', 'postgresql'.")


def _apply_pg_delay(cur: Any, cfg: DatabaseConfig) -> None:
    """If operation_delay_ms > 0, sleep inside PostgreSQL using parameterized SELECT pg_sleep(%s)."""
    if cfg.operation_delay_ms > 0:
        cur.execute("SELECT pg_sleep(%s);", (cfg.operation_delay_ms / 1000.0,))


def _probe_postgresql(cfg: DatabaseConfig, started: float) -> dict[str, Any]:
    """Execute real PostgreSQL probe using psycopg with bounded execution timeouts."""
    try:
        _validate_db_hostname(cfg)
        with _connect_postgresql(cfg) as conn:
            with conn.cursor() as cur:
                _apply_pg_delay(cur, cfg)
                cur.execute("SELECT 1 FROM orders LIMIT 1;")
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {
            "ok": True,
            "configured_host": cfg.host,
            "configured_port": cfg.port,
            "dbname": cfg.dbname,
            "latency_ms": latency_ms,
            "error_category": None,
        }
    except DatabaseOperationError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {
            "ok": False,
            "configured_host": exc.configured_host,
            "configured_port": exc.configured_port,
            "dbname": cfg.dbname,
            "latency_ms": latency_ms,
            "error_category": exc.error_category,
            "detail": exc.detail,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        err = _map_psycopg_exception(exc, cfg, target_relation="orders")
        return {
            "ok": False,
            "configured_host": err.configured_host,
            "configured_port": err.configured_port,
            "dbname": cfg.dbname,
            "latency_ms": latency_ms,
            "error_category": err.error_category,
            "detail": err.detail,
        }


def _validate_db_hostname(cfg: DatabaseConfig) -> None:
    if cfg.host.endswith(".invalid") or cfg.host.endswith(".internal"):
        raise DatabaseOperationError(
            "hostname_resolution_failed",
            f"Cannot resolve database host '{cfg.host}'",
            cfg.host,
            cfg.port,
        )
    try:
        socket.getaddrinfo(cfg.host, cfg.port)
    except socket.gaierror as exc:
        raise DatabaseOperationError(
            "hostname_resolution_failed",
            f"Cannot resolve database host '{cfg.host}': {exc}",
            cfg.host,
            cfg.port,
        ) from exc


def _map_psycopg_exception(
    exc: Exception,
    cfg: DatabaseConfig,
    target_relation: str = "orders",
) -> DatabaseOperationError:
    """Map psycopg / network exceptions to standard NexTrace error categories without exposing credentials."""
    msg = str(exc)
    raw = repr(exc)
    sqlstate = getattr(exc, "sqlstate", None)
    cls_name = type(exc).__name__
    msg_lower = msg.lower()

    # Redact sensitive credentials if found in exception message or repr
    sanitized_msg = msg
    if cfg.password and cfg.password in sanitized_msg:
        sanitized_msg = sanitized_msg.replace(cfg.password, "***REDACTED***")
    if cfg.password and cfg.password in raw:
        raw = raw.replace(cfg.password, "***REDACTED***")

    # 1. Hostname / DNS resolution failure
    if (
        isinstance(exc, socket.gaierror)
        or "could not translate host name" in msg_lower
        or "name or service not known" in msg_lower
        or "getaddrinfo failed" in msg_lower
        or "nodename nor servname provided" in msg_lower
    ):
        return DatabaseOperationError(
            "hostname_resolution_failed",
            f"Cannot resolve PostgreSQL host '{cfg.host}': {sanitized_msg}",
            cfg.host,
            cfg.port,
        )

    # 2. Authentication failure (SQLSTATE 28P01 / 28000 or InvalidPassword / authentication failed)
    if (
        sqlstate in ("28P01", "28000")
        or "invalidpassword" in cls_name.lower()
        or "invalidauthorizationspecification" in cls_name.lower()
        or "password authentication failed" in msg_lower
        or "authentication failed" in msg_lower
    ):
        return DatabaseOperationError(
            "authentication_failed",
            f"PostgreSQL authentication failed for user '{cfg.user}' on database '{cfg.dbname}'",
            cfg.host,
            cfg.port,
        )

    # 3. Query / statement / lock timeout / cancellation
    # SQLSTATE 57014 (query_canceled) or 55P03 (lock_not_available) or TimeoutError
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
        return DatabaseOperationError(
            "operation_timeout",
            f"PostgreSQL operation exceeded timeout (statement_timeout={cfg.statement_timeout_ms}ms, lock_timeout={cfg.lock_timeout_ms}ms): {sanitized_msg}",
            cfg.host,
            cfg.port,
        )

    # 4. Undefined table: ONLY if actual target relation (e.g. 'orders') does not exist (SQLSTATE 42P01)
    # MUST NOT map missing database (3D000), missing role (28000), missing schema (3F000), or generic "does not exist"!
    if sqlstate == "42P01" or "undefinedtable" in cls_name.lower():
        if (
            f'relation "{target_relation}" does not exist' in msg_lower
            or f'table "{target_relation}" does not exist' in msg_lower
            or f'"{target_relation}"' in msg_lower
            or f" {target_relation} " in f" {msg_lower} "
        ):
            return DatabaseOperationError(
                "missing_table",
                f"Required table '{target_relation}' does not exist in active database schema",
                cfg.host,
                cfg.port,
            )
        return DatabaseOperationError(
            "database_error",
            f"PostgreSQL undefined relation error: {sanitized_msg}",
            cfg.host,
            cfg.port,
        )

    # Explicitly distinguish missing database (3D000 / InvalidCatalogName)
    if sqlstate == "3D000" or "invalidcatalogname" in cls_name.lower():
        return DatabaseOperationError(
            "database_error",
            f"PostgreSQL database '{cfg.dbname}' does not exist: {sanitized_msg}",
            cfg.host,
            cfg.port,
        )

    # Explicitly distinguish missing schema (3F000 / InvalidSchemaName)
    if sqlstate == "3F000" or "invalidschemaname" in cls_name.lower():
        return DatabaseOperationError(
            "database_error",
            f"PostgreSQL schema does not exist: {sanitized_msg}",
            cfg.host,
            cfg.port,
        )

    # 5. Connection refused / database unavailable (SQLSTATE 08001 / 08006 or ConnectionRefusedError / socket errors)
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
        return DatabaseOperationError(
            "connection_refused",
            f"Cannot connect to PostgreSQL at {cfg.host}:{cfg.port}: connection refused or port unreachable",
            cfg.host,
            cfg.port,
        )

    # 6. Fallback generic database error
    return DatabaseOperationError(
        "database_error",
        f"PostgreSQL operation failed: {sanitized_msg}",
        cfg.host,
        cfg.port,
    )


def insert_order_record(
    order_id: str,
    product_id: str,
    quantity: int,
    request_id: str,
    config: DatabaseConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_db_config()
    driver = cfg.driver.lower()

    if driver in ("local_tcp", "sqlite_tcp"):
        created_at = utc_now_iso()
        resp = _tcp_rpc(
            cfg,
            {
                "action": "insert_order",
                "op": "insert_order",
                "user": cfg.user,
                "password": cfg.password,
                "dbname": cfg.dbname,
                "order_id": order_id,
                "product_id": product_id,
                "quantity": quantity,
                "request_id": request_id,
                "created_at": created_at,
            },
        )
        return resp.get("record") or resp.get("order") or {}

    if driver in ("postgresql", "postgres"):
        return _insert_postgresql(order_id, product_id, quantity, request_id, cfg)

    raise ValueError(f"Unsupported database driver: '{cfg.driver}'. Supported: 'local_tcp', 'postgresql'.")


def _insert_postgresql(
    order_id: str,
    product_id: str,
    quantity: int,
    request_id: str,
    cfg: DatabaseConfig,
) -> dict[str, Any]:
    try:
        _validate_db_hostname(cfg)
        with _connect_postgresql(cfg) as conn:
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        _apply_pg_delay(cur, cfg)
                        cur.execute(
                            """
                            INSERT INTO orders (order_id, product_id, quantity, request_id, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                            RETURNING order_id, product_id, quantity, request_id, created_at::text;
                            """,
                            (order_id, product_id, quantity, request_id),
                        )
                        row = cur.fetchone()
                        if not row:
                            raise DatabaseOperationError(
                                "database_error",
                                "PostgreSQL INSERT did not return row",
                                cfg.host,
                                cfg.port,
                            )
                        return {
                            "order_id": row["order_id"],
                            "product_id": row["product_id"],
                            "quantity": int(row["quantity"]),
                            "request_id": row["request_id"],
                            "created_at": str(row["created_at"]),
                        }
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
    except DatabaseOperationError:
        raise
    except Exception as exc:
        raise _map_psycopg_exception(exc, cfg, target_relation="orders") from exc


def fetch_order_record(order_id: str, config: DatabaseConfig | None = None) -> dict[str, Any] | None:
    cfg = config or load_db_config()
    driver = cfg.driver.lower()

    if driver in ("local_tcp", "sqlite_tcp"):
        resp = _tcp_rpc(
            cfg,
            {
                "action": "fetch_order",
                "op": "get_order",
                "user": cfg.user,
                "password": cfg.password,
                "dbname": cfg.dbname,
                "order_id": order_id,
            },
        )
        return resp.get("record") or resp.get("order")

    if driver in ("postgresql", "postgres"):
        return _fetch_postgresql(order_id, cfg)

    raise ValueError(f"Unsupported database driver: '{cfg.driver}'. Supported: 'local_tcp', 'postgresql'.")


def _fetch_postgresql(order_id: str, cfg: DatabaseConfig) -> dict[str, Any] | None:
    try:
        _validate_db_hostname(cfg)
        with _connect_postgresql(cfg) as conn:
            with conn.cursor() as cur:
                _apply_pg_delay(cur, cfg)
                cur.execute(
                    """
                    SELECT order_id, product_id, quantity, request_id, created_at::text
                    FROM orders
                    WHERE order_id = %s;
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "order_id": row["order_id"],
                    "product_id": row["product_id"],
                    "quantity": int(row["quantity"]),
                    "request_id": row["request_id"],
                    "created_at": str(row["created_at"]),
                }
    except DatabaseOperationError:
        raise
    except Exception as exc:
        raise _map_psycopg_exception(exc, cfg, target_relation="orders") from exc
