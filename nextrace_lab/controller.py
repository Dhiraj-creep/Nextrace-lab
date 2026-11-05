"""Experiment Controller: manages service lifecycle, fault scenarios, multi-faults, and second application (Stages 1, 5, 6 & 8).

This module is part of the private control plane. Diagnostic selectors and
investigators must NEVER import or invoke this module.
All state-mutating functions are protected by the cross-process `LabExecutionLock` (Stage 1E).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from typing import Any, Literal, Optional

import httpx

from nextrace_lab.lab_lock import acquire_lab_lock
from nextrace_lab.local_cache_server import CACHE_FAULT_OVERRIDE_FILE
from nextrace_lab.local_db_server import (
    DB_FAULT_OVERRIDE_FILE,
    get_disposable_missing_schema_path,
    get_sqlite_path,
    init_sqlite_schema,
)
from nextrace_lab.logging_utils import append_log_event, get_log_dir, utc_now_iso
from nextrace_lab.schemas import EvidenceCondition, ScenarioName

ROOT_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = ROOT_DIR / "var"
RUNTIME_DIR = VAR_DIR / "runtime"
PIDS_FILE = RUNTIME_DIR / "local_pids.json"
OVERRIDE_FILE = RUNTIME_DIR / "order_service_override.json"
EVIDENCE_POLICY_FILE = RUNTIME_DIR / "evidence_policy.json"

INV_OVERRIDE_FILE = RUNTIME_DIR / "inv_service_override.json"
INV_DB_FAULT_OVERRIDE_FILE = RUNTIME_DIR / "inv_db_fault_override.json"
INV_SQLITE_PATH = VAR_DIR / "data" / "inventory.sqlite3"
ACTIVE_APP_FILE = RUNTIME_DIR / "active_app.txt"

GATEWAY_PORT = int(os.environ.get("HOST_GATEWAY_PORT", "18000"))
ORDER_PORT = int(os.environ.get("HOST_ORDER_PORT", "18001"))
DB_PORT = int(os.environ.get("HOST_DB_PORT", "15432"))

INV_API_PORT = int(os.environ.get("HOST_INV_API_PORT", "18010"))
INV_SERVICE_PORT = int(os.environ.get("HOST_INV_SERVICE_PORT", "18011"))
INV_DB_PORT = int(os.environ.get("HOST_INV_DB_PORT", "15433"))
INV_CACHE_PORT = int(os.environ.get("HOST_INV_CACHE_PORT", "16379"))

GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"
ORDER_URL = f"http://127.0.0.1:{ORDER_PORT}"
INV_API_URL = f"http://127.0.0.1:{INV_API_PORT}"
INV_SERVICE_URL = f"http://127.0.0.1:{INV_SERVICE_PORT}"

SUPPORTED_FAULT_NAMES = (
    "fault_a",
    "fault_b",
    "fault_c",
    "fault_d",
    "fault_e",
    "fault_f",
    "challenging_recovery_mid_run",
    "challenging_diag_endpoint_failure",
    "challenging_historical_logs_healthy_now",
    "challenging_unknown_app_error",
    "unknown_order_validation_contract_error",
    "unknown_order_currency_rounding_crash",
    "multi_fault_a_and_b",
    "multi_fault_c_and_d",
    "multi_fault_f_masks_b",
    "inv_fault_db_unavailable",
    "inv_fault_cache_unavailable",
    "inv_fault_bad_db_config",
    "inv_fault_upstream_timeout",
    "inv_unknown_sku_parser_exception",
    "inv_multi_fault_db_and_cache",
)

FAULT_CATALOG: dict[str, dict[str, Any]] = {
    # ---------------- Primary orders_app scenarios ----------------
    "healthy": {
        "scenario": "healthy",
        "app_id": "orders_app",
        "split": "development",
        "expected_is_faulty": False,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": [],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "no_fault_in_incident_window",
        "description": "All orders_app services running with valid configuration and usable database schema.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    "fault_a": {
        "scenario": "fault_a",
        "app_id": "orders_app",
        "split": "development",
        "expected_is_faulty": True,
        "expected_service": "order-service",
        "expected_fault_type": "db_endpoint_misconfiguration",
        "expected_causes": ["order-service:db_endpoint_misconfiguration"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "order-service:db_endpoint_misconfiguration",
        "description": "Order service configured with an unresolvable database hostname while database remains healthy.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    "fault_b": {
        "scenario": "fault_b",
        "app_id": "orders_app",
        "split": "development",
        "expected_is_faulty": True,
        "expected_service": "database",
        "expected_fault_type": "db_service_unavailable",
        "expected_causes": ["database:db_service_unavailable"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "database:db_service_unavailable",
        "description": "Database service process/container is stopped while gateway and order-service remain running.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    "fault_c": {
        "scenario": "fault_c",
        "app_id": "orders_app",
        "split": "held_out",
        "expected_is_faulty": True,
        "expected_service": "order-service",
        "expected_fault_type": "db_auth_failure",
        "expected_causes": ["order-service:db_auth_failure"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "order-service:db_auth_failure",
        "description": "Order service configured with invalid database credentials rejected by database authentication.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    "fault_d": {
        "scenario": "fault_d",
        "app_id": "orders_app",
        "split": "held_out",
        "expected_is_faulty": True,
        "expected_service": "database",
        "expected_fault_type": "db_schema_missing_table",
        "expected_causes": ["database:db_schema_missing_table"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "database:db_schema_missing_table",
        "description": "Database active schema switched to an isolated disposable schema lacking the 'orders' table.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    "fault_e": {
        "scenario": "fault_e",
        "app_id": "orders_app",
        "split": "held_out",
        "expected_is_faulty": True,
        "expected_service": "database",
        "expected_fault_type": "db_operation_delay",
        "expected_causes": ["database:db_operation_delay"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "database:db_operation_delay",
        "description": "Database operations experience a controlled delay (1800ms) exceeding order-service's 1000ms deadline.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    "fault_f": {
        "scenario": "fault_f",
        "app_id": "orders_app",
        "split": "held_out",
        "expected_is_faulty": True,
        "expected_service": "order-service",
        "expected_fault_type": "order_service_unavailable",
        "expected_causes": ["order-service:order_service_unavailable"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "order-service:order_service_unavailable",
        "description": "Order service process/container is stopped while gateway and database remain running.",
        "supported_backends": ["local_sqlite_tcp", "docker_postgresql"],
    },
    # ---------------- Challenging & Multi-Fault scenarios (Stage 6) ----------------
    "challenging_recovery_mid_run": {
        "scenario": "challenging_recovery_mid_run",
        "app_id": "orders_app",
        "split": "stress_challenging",
        "expected_is_faulty": True,
        "expected_service": "order-service",
        "expected_fault_type": "db_endpoint_misconfiguration",
        "expected_causes": ["order-service:db_endpoint_misconfiguration"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "order-service:db_endpoint_misconfiguration",
        "description": "Order-service DB host misconfiguration fails at incident time, then recovers after check #1 executes.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "challenging_diag_endpoint_failure": {
        "scenario": "challenging_diag_endpoint_failure",
        "app_id": "orders_app",
        "split": "stress_challenging",
        "expected_is_faulty": False,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": [],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "no_fault_in_incident_window",
        "description": "Diagnostic DB-config inspection endpoint fails (HTTP 500) while user traffic and services are healthy.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "challenging_historical_logs_healthy_now": {
        "scenario": "challenging_historical_logs_healthy_now",
        "app_id": "orders_app",
        "split": "stress_challenging",
        "expected_is_faulty": False,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": [],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "order-service:db_endpoint_misconfiguration",
        "description": "Historical failure logs from an earlier resolved incident remain in log files while current service health and traffic are normal.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "challenging_unknown_app_error": {
        "scenario": "challenging_unknown_app_error",
        "app_id": "orders_app",
        "split": "stress_challenging",
        "expected_is_faulty": True,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": ["unknown_cause"],
        "is_multi_fault": False,
        "is_unknown_cause": True,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "unknown_cause:unmodeled_application_failure",
        "description": "Order-service throws an unmodeled internal serialization exception while all modeled dependencies and configs are healthy.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "unknown_order_validation_contract_error": {
        "scenario": "unknown_order_validation_contract_error",
        "app_id": "orders_app",
        "split": "stress_challenging",
        "expected_is_faulty": True,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": ["unknown_cause"],
        "is_multi_fault": False,
        "is_unknown_cause": True,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "unknown_cause:unmodeled_application_failure",
        "description": "Order-service validation contract error in payload validator while database is healthy.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "unknown_order_currency_rounding_crash": {
        "scenario": "unknown_order_currency_rounding_crash",
        "app_id": "orders_app",
        "split": "reserved_eval",
        "expected_is_faulty": True,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": ["unknown_cause"],
        "is_multi_fault": False,
        "is_unknown_cause": True,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "unknown_cause:unmodeled_application_failure",
        "description": "Order-service currency conversion arithmetic crash (reserved evaluation fixture) while database is healthy.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "multi_fault_a_and_b": {
        "scenario": "multi_fault_a_and_b",
        "app_id": "orders_app",
        "split": "multi_fault",
        "expected_is_faulty": True,
        "expected_service": "order-service+database",
        "expected_fault_type": "db_endpoint_misconfiguration+db_service_unavailable",
        "expected_causes": [
            "database:db_service_unavailable",
            "order-service:db_endpoint_misconfiguration",
        ],
        "is_multi_fault": True,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "database:db_service_unavailable,order-service:db_endpoint_misconfiguration",
        "description": "Two simultaneous faults: order-service has an invalid DB hostname AND database process is stopped.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "multi_fault_c_and_d": {
        "scenario": "multi_fault_c_and_d",
        "app_id": "orders_app",
        "split": "multi_fault",
        "expected_is_faulty": True,
        "expected_service": "order-service+database",
        "expected_fault_type": "db_auth_failure+db_schema_missing_table",
        "expected_causes": [
            "database:db_schema_missing_table",
            "order-service:db_auth_failure",
        ],
        "is_multi_fault": True,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "database:db_schema_missing_table,order-service:db_auth_failure",
        "description": "Two simultaneous faults: order-service has invalid DB password AND database has missing orders table.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    "multi_fault_f_masks_b": {
        "scenario": "multi_fault_f_masks_b",
        "app_id": "orders_app",
        "split": "multi_fault",
        "expected_is_faulty": True,
        "expected_service": "order-service+database",
        "expected_fault_type": "order_service_unavailable+db_service_unavailable",
        "expected_causes": [
            "database:db_service_unavailable",
            "order-service:order_service_unavailable",
        ],
        "identifiable_causes": [
            "order-service:order_service_unavailable",
            "database:db_service_unavailable",
        ],
        "masked_causes": [
            "database:db_service_unavailable",
        ],
        "is_multi_fault": True,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "database:db_service_unavailable,order-service:order_service_unavailable",
        "description": "Masking multi-fault: order-service process is stopped AND database process is also stopped.",
        "supported_backends": ["local_sqlite_tcp"],
    },
    # ---------------- Second application (`inventory_app`, Stage 8) ----------------
    "inv_healthy": {
        "scenario": "inv_healthy",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": False,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": [],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "no_fault_in_incident_window",
        "description": "All inventory_app services (inventory-api, inventory-service, inventory-db, inventory-cache) are healthy.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute", "docker_postgres_redis"],
    },
    "inv_fault_db_unavailable": {
        "scenario": "inv_fault_db_unavailable",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": True,
        "expected_service": "inventory-db",
        "expected_fault_type": "db_service_unavailable",
        "expected_causes": ["inventory-db:db_service_unavailable"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "inventory-db:db_service_unavailable",
        "description": "inventory-db process is stopped while inventory-cache and inventory-service remain running.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute", "docker_postgres_redis"],
    },
    "inv_fault_cache_unavailable": {
        "scenario": "inv_fault_cache_unavailable",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": True,
        "expected_service": "inventory-cache",
        "expected_fault_type": "cache_service_unavailable",
        "expected_causes": ["inventory-cache:cache_service_unavailable"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "inventory-cache:cache_service_unavailable",
        "description": "inventory-cache (local_tcp_cache_substitute) is stopped while inventory-db remains healthy.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute", "docker_postgres_redis"],
    },
    "inv_fault_bad_db_config": {
        "scenario": "inv_fault_bad_db_config",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": True,
        "expected_service": "inventory-service",
        "expected_fault_type": "db_endpoint_misconfiguration",
        "expected_causes": ["inventory-service:db_endpoint_misconfiguration"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "inventory-service:db_endpoint_misconfiguration",
        "description": "inventory-service configured with unresolvable db_host while inventory-db and inventory-cache are healthy.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute", "docker_postgres_redis"],
    },
    "inv_fault_upstream_timeout": {
        "scenario": "inv_fault_upstream_timeout",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": True,
        "expected_service": "inventory-db",
        "expected_fault_type": "db_operation_delay",
        "expected_causes": ["inventory-db:db_operation_delay"],
        "is_multi_fault": False,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "inventory-db:db_operation_delay",
        "description": "inventory-db operations experience a controlled delay (1800ms) exceeding inventory-service's 1000ms deadline.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute", "docker_postgres_redis"],
    },
    "inv_unknown_sku_parser_exception": {
        "scenario": "inv_unknown_sku_parser_exception",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": True,
        "expected_service": None,
        "expected_fault_type": None,
        "expected_causes": ["unknown_cause"],
        "is_multi_fault": False,
        "is_unknown_cause": True,
        "expected_current_health": "healthy_now",
        "expected_window_cause": "unknown_cause:unmodeled_application_failure",
        "description": "Inventory-service SKU parser exception while inventory-db and inventory-cache are healthy.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute"],
    },
    "inv_multi_fault_db_and_cache": {
        "scenario": "inv_multi_fault_db_and_cache",
        "app_id": "inventory_app",
        "split": "second_app",
        "expected_is_faulty": True,
        "expected_service": "inventory-db+inventory-cache",
        "expected_fault_type": "db_service_unavailable+cache_service_unavailable",
        "expected_causes": [
            "inventory-cache:cache_service_unavailable",
            "inventory-db:db_service_unavailable",
        ],
        "is_multi_fault": True,
        "is_unknown_cause": False,
        "expected_current_health": "degraded_or_failing",
        "expected_window_cause": "inventory-cache:cache_service_unavailable,inventory-db:db_service_unavailable",
        "description": "Two simultaneous faults: inventory-db process stopped AND inventory-cache process stopped.",
        "supported_backends": ["local_sqlite_tcp_and_local_tcp_cache_substitute", "docker_postgres_redis"],
    },
}


class ControllerError(RuntimeError):
    """Raised when environment setup, fault injection, or verification fails."""


def _ensure_docker_in_path() -> None:
    """Ensure standard Docker Desktop bin directories are in PATH if not already found."""
    if shutil.which("docker") is not None:
        return
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DockerDesktop" / "resources" / "bin",
        Path("C:/Program Files/Docker/Docker/resources/bin"),
    ]
    for c in candidates:
        if c.exists() and (c / "docker.exe").exists():
            os.environ["PATH"] = str(c) + os.pathsep + os.environ.get("PATH", "")
            break


def is_docker_available() -> bool:
    """Check whether docker CLI and daemon are accessible on the host."""
    _ensure_docker_in_path()
    if shutil.which("docker") is None:
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def resolve_runtime_mode(requested: Optional[str] = None) -> Literal["local", "docker"]:
    """Determine runtime mode ('local' or 'docker')."""
    mode = (requested or os.environ.get("NEXTRACE_RUNTIME") or "auto").lower()
    if mode == "docker":
        if not is_docker_available():
            raise ControllerError(
                "Docker runtime was requested, but Docker CLI / daemon is not installed or accessible on this host."
            )
        resolved = "docker"
    elif mode == "local":
        resolved = "local"
    else:
        resolved = "docker" if is_docker_available() else "local"
    os.environ["NEXTRACE_RUNTIME_ACTIVE"] = resolved
    return resolved


def get_backend_name(runtime_mode: Literal["local", "docker"], app_id: str = "orders_app") -> str:
    """Return explicit backend identifier."""
    if app_id == "inventory_app":
        return "docker_postgres_redis" if runtime_mode == "docker" else "local_sqlite_tcp_and_local_tcp_cache_substitute"
    return "docker_postgresql" if runtime_mode == "docker" else "local_sqlite_tcp"


def _clear_service_logs(services: tuple[str, ...] = ("gateway", "order-service", "inventory-api", "inventory-service")) -> None:
    """Truncate JSONL service logs before a fresh scenario setup so past scenario logs do not leak across runs."""
    log_dir = get_log_dir()
    for svc in services:
        fpath = log_dir / f"{svc}.jsonl"
        if fpath.exists():
            try:
                fpath.write_text("", encoding="utf-8")
            except OSError:
                pass


def _reset_service_metrics(urls: tuple[str, ...] = (GATEWAY_URL, ORDER_URL)) -> None:
    for url in urls:
        try:
            httpx.post(f"{url}/internal/metrics/reset", timeout=0.5)
        except Exception:
            pass


def _load_pids() -> dict[str, Any]:
    if not PIDS_FILE.exists():
        return {"root_dir": str(ROOT_DIR)}
    try:
        with open(PIDS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("root_dir") != str(ROOT_DIR):
            for name in ("gateway", "order-service", "database", "inventory-api", "inventory-service", "inventory-db", "inventory-cache"):
                _kill_pid(data.get(name))
            return {"root_dir": str(ROOT_DIR)}
        return data
    except Exception:
        return {"root_dir": str(ROOT_DIR)}


def _save_pids(pids: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    pids["root_dir"] = str(ROOT_DIR)
    with open(PIDS_FILE, "w", encoding="utf-8") as fh:
        json.dump(pids, fh, indent=2)


def _is_pid_running(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        res = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in res.stdout
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _kill_pid(pid: Optional[int]) -> None:
    if not pid or not _is_pid_running(pid):
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline and _is_pid_running(pid):
        time.sleep(0.05)


def _is_tcp_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _base_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT_DIR)
    env["PYTHONUNBUFFERED"] = "1"
    env["NEXTRACE_RUNTIME_ACTIVE"] = "local"
    env["NEXTRACE_LOG_DIR"] = str(VAR_DIR / "logs")
    env["NEXTRACE_SQLITE_PATH"] = str(get_sqlite_path())
    env["NEXTRACE_ORDER_CONFIG_OVERRIDE_FILE"] = str(OVERRIDE_FILE)
    env["NEXTRACE_DB_FAULT_OVERRIDE_FILE"] = str(DB_FAULT_OVERRIDE_FILE)
    env["NEXTRACE_INV_CONFIG_OVERRIDE_FILE"] = str(INV_OVERRIDE_FILE)
    env["NEXTRACE_CACHE_FAULT_OVERRIDE_FILE"] = str(CACHE_FAULT_OVERRIDE_FILE)
    env["NEXTRACE_DB_DRIVER"] = "local_tcp"
    env["DB_HOST"] = "127.0.0.1"
    env["DB_PORT"] = str(DB_PORT)
    env["DB_NAME"] = "nextrace_orders"
    env["DB_USER"] = "nextrace_user"
    env["DB_PASSWORD"] = "nextrace_local_dev_pw"
    env["DB_CONNECT_TIMEOUT_SEC"] = "1.0"
    env["ORDER_SERVICE_URL"] = ORDER_URL
    env["ORDER_SERVICE_TIMEOUT_SEC"] = "2.5"
    env["INVENTORY_SERVICE_URL"] = INV_SERVICE_URL
    env["INVENTORY_SERVICE_TIMEOUT_SEC"] = "2.5"
    return env


def _spawn_background_process(cmd: list[str], env: dict[str, str], log_name: str) -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = RUNTIME_DIR / f"{log_name}.stdout.log"
    stderr_path = RUNTIME_DIR / f"{log_name}.stderr.log"
    stdout_fh = open(stdout_path, "a", encoding="utf-8")
    stderr_fh = open(stderr_path, "a", encoding="utf-8")

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        stdout=stdout_fh,
        stderr=stderr_fh,
        creationflags=creationflags,
    )
    return proc.pid


def _start_local_database(pids: dict[str, Any], env: dict[str, str]) -> None:
    if _is_pid_running(pids.get("database")) and _is_tcp_port_open("127.0.0.1", DB_PORT):
        return
    _kill_pid(pids.get("database"))
    init_sqlite_schema(get_sqlite_path())
    pid = _spawn_background_process(
        [sys.executable, "-m", "nextrace_lab.local_db_server", "--host", "127.0.0.1", "--port", str(DB_PORT)],
        env=env,
        log_name="database",
    )
    pids["database"] = pid
    _save_pids(pids)


def _start_local_order_service(pids: dict[str, Any], env: dict[str, str], force_restart: bool = False) -> None:
    if not force_restart and _is_pid_running(pids.get("order-service")) and _is_tcp_port_open("127.0.0.1", ORDER_PORT):
        return
    _kill_pid(pids.get("order-service"))
    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline and _is_tcp_port_open("127.0.0.1", ORDER_PORT, timeout=0.2):
        time.sleep(0.05)

    pid = _spawn_background_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.order_service.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(ORDER_PORT),
            "--log-level",
            "warning",
        ],
        env=env,
        log_name="order-service",
    )
    pids["order-service"] = pid
    _save_pids(pids)


def _start_local_gateway(pids: dict[str, Any], env: dict[str, str], force_restart: bool = False) -> None:
    if not force_restart and _is_pid_running(pids.get("gateway")) and _is_tcp_port_open("127.0.0.1", GATEWAY_PORT):
        return
    _kill_pid(pids.get("gateway"))
    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline and _is_tcp_port_open("127.0.0.1", GATEWAY_PORT, timeout=0.2):
        time.sleep(0.05)

    pid = _spawn_background_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.gateway.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(GATEWAY_PORT),
            "--log-level",
            "warning",
        ],
        env=env,
        log_name="gateway",
    )
    pids["gateway"] = pid
    _save_pids(pids)


# ---------------- Second Application (`inventory_app`) Process Helpers (Stage 8) ----------------


def _start_local_inv_db(pids: dict[str, Any], env: dict[str, str]) -> None:
    if _is_pid_running(pids.get("inventory-db")) and _is_tcp_port_open("127.0.0.1", INV_DB_PORT):
        return
    _kill_pid(pids.get("inventory-db"))
    init_sqlite_schema(INV_SQLITE_PATH)
    inv_env = dict(env)
    inv_env["NEXTRACE_SQLITE_PATH"] = str(INV_SQLITE_PATH)
    inv_env["NEXTRACE_DB_FAULT_OVERRIDE_FILE"] = str(INV_DB_FAULT_OVERRIDE_FILE)
    pid = _spawn_background_process(
        [sys.executable, "-m", "nextrace_lab.local_db_server", "--host", "127.0.0.1", "--port", str(INV_DB_PORT)],
        env=inv_env,
        log_name="inventory-db",
    )
    pids["inventory-db"] = pid
    _save_pids(pids)


def _start_local_inv_cache(pids: dict[str, Any], env: dict[str, str]) -> None:
    if _is_pid_running(pids.get("inventory-cache")) and _is_tcp_port_open("127.0.0.1", INV_CACHE_PORT):
        return
    _kill_pid(pids.get("inventory-cache"))
    pid = _spawn_background_process(
        [sys.executable, "-m", "nextrace_lab.local_cache_server", "--host", "127.0.0.1", "--port", str(INV_CACHE_PORT)],
        env=env,
        log_name="inventory-cache",
    )
    pids["inventory-cache"] = pid
    _save_pids(pids)


def _start_local_inv_service(pids: dict[str, Any], env: dict[str, str], force_restart: bool = False) -> None:
    if not force_restart and _is_pid_running(pids.get("inventory-service")) and _is_tcp_port_open("127.0.0.1", INV_SERVICE_PORT):
        return
    _kill_pid(pids.get("inventory-service"))
    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline and _is_tcp_port_open("127.0.0.1", INV_SERVICE_PORT, timeout=0.2):
        time.sleep(0.05)

    pid = _spawn_background_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.inventory_app.inventory_service_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(INV_SERVICE_PORT),
            "--log-level",
            "warning",
        ],
        env=env,
        log_name="inventory-service",
    )
    pids["inventory-service"] = pid
    _save_pids(pids)


def _start_local_inv_api(pids: dict[str, Any], env: dict[str, str], force_restart: bool = False) -> None:
    if not force_restart and _is_pid_running(pids.get("inventory-api")) and _is_tcp_port_open("127.0.0.1", INV_API_PORT):
        return
    _kill_pid(pids.get("inventory-api"))
    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline and _is_tcp_port_open("127.0.0.1", INV_API_PORT, timeout=0.2):
        time.sleep(0.05)

    pid = _spawn_background_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.inventory_app.api_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(INV_API_PORT),
            "--log-level",
            "warning",
        ],
        env=env,
        log_name="inventory-api",
    )
    pids["inventory-api"] = pid
    _save_pids(pids)


def set_evidence_condition(condition: EvidenceCondition | str) -> EvidenceCondition:
    """Configure the active evidence condition enforced by the Diagnostic Interface."""
    cond = EvidenceCondition(condition)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_POLICY_FILE, "w", encoding="utf-8") as fh:
        json.dump({"evidence_condition": cond.value, "updated_at_utc": utc_now_iso()}, fh, indent=2)
    return cond


def get_evidence_condition() -> EvidenceCondition:
    """Read the currently configured evidence condition (defaults to E0)."""
    if not EVIDENCE_POLICY_FILE.exists():
        return EvidenceCondition.E0
    try:
        with open(EVIDENCE_POLICY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return EvidenceCondition(data.get("evidence_condition", "E0"))
    except Exception:
        return EvidenceCondition.E0


def wait_for_service_state(
    *,
    expect_gateway_ready: bool = True,
    expect_order_live: bool = True,
    expect_order_ready: bool = True,
    expect_db_reachable: bool = True,
    timeout_sec: float = 12.0,
) -> dict[str, Any]:
    """Bounded polling for expected service liveness, readiness, and DB states."""
    deadline = time.perf_counter() + timeout_sec
    last_snapshot: dict[str, Any] = {}

    while time.perf_counter() < deadline:
        gw_live = False
        gw_ready = False
        ord_live = False
        ord_ready = False
        db_up = _is_tcp_port_open("127.0.0.1", DB_PORT, timeout=0.4)

        try:
            r = httpx.get(f"{GATEWAY_URL}/health/live", timeout=0.6)
            gw_live = r.status_code == 200
        except Exception:
            pass

        try:
            r = httpx.get(f"{GATEWAY_URL}/health/ready", timeout=0.8)
            gw_ready = r.status_code == 200
        except Exception:
            pass

        try:
            r = httpx.get(f"{ORDER_URL}/health/live", timeout=0.6)
            ord_live = r.status_code == 200
        except Exception:
            pass

        try:
            r = httpx.get(f"{ORDER_URL}/health/ready", timeout=1.3)
            ord_ready = r.status_code == 200
        except Exception:
            pass

        last_snapshot = {
            "gateway_live": gw_live,
            "gateway_ready": gw_ready,
            "order_service_live": ord_live,
            "order_service_ready": ord_ready,
            "database_reachable": db_up,
        }

        if (
            gw_live
            and (gw_ready == expect_gateway_ready)
            and (ord_live == expect_order_live)
            and (ord_ready == expect_order_ready)
            and (db_up == expect_db_reachable)
        ):
            return last_snapshot

        time.sleep(0.15)

    raise ControllerError(
        f"Timed out waiting for expected service state after {timeout_sec}s. Last observed state: {last_snapshot}"
    )


def wait_for_inventory_state(
    *,
    expect_api_ready: bool = True,
    expect_inv_live: bool = True,
    expect_inv_ready: bool = True,
    expect_db_reachable: bool = True,
    expect_cache_reachable: bool = True,
    timeout_sec: float = 12.0,
) -> dict[str, Any]:
    """Bounded polling for expected inventory_app service states (Stage 8)."""
    deadline = time.perf_counter() + timeout_sec
    last_snapshot: dict[str, Any] = {}

    while time.perf_counter() < deadline:
        api_live = False
        api_ready = False
        inv_live = False
        inv_ready = False
        db_up = _is_tcp_port_open("127.0.0.1", INV_DB_PORT, timeout=0.4)
        cache_up = _is_tcp_port_open("127.0.0.1", INV_CACHE_PORT, timeout=0.4)

        try:
            r = httpx.get(f"{INV_API_URL}/health/live", timeout=0.6)
            api_live = r.status_code == 200
        except Exception:
            pass

        try:
            r = httpx.get(f"{INV_API_URL}/health/ready", timeout=0.8)
            api_ready = r.status_code == 200
        except Exception:
            pass

        try:
            r = httpx.get(f"{INV_SERVICE_URL}/health/live", timeout=0.6)
            inv_live = r.status_code == 200
        except Exception:
            pass

        try:
            r = httpx.get(f"{INV_SERVICE_URL}/health/ready", timeout=1.3)
            inv_ready = r.status_code == 200
        except Exception:
            pass

        last_snapshot = {
            "inventory_api_live": api_live,
            "inventory_api_ready": api_ready,
            "inventory_service_live": inv_live,
            "inventory_service_ready": inv_ready,
            "inventory_db_reachable": db_up,
            "inventory_cache_reachable": cache_up,
        }

        if (
            api_live
            and (api_ready == expect_api_ready)
            and (inv_live == expect_inv_live)
            and (inv_ready == expect_inv_ready)
            and (db_up == expect_db_reachable)
            and (cache_up == expect_cache_reachable)
        ):
            return last_snapshot

        time.sleep(0.15)

    raise ControllerError(
        f"Timed out waiting for expected inventory_app state after {timeout_sec}s. Last observed state: {last_snapshot}"
    )


def _clear_all_fault_overrides(app_id: Optional[str] = None) -> bool:
    """Remove fault override files scoped by app_id (or all apps if app_id is None); return True if any existed."""
    changed = False
    if app_id == "orders_app":
        targets = (OVERRIDE_FILE, DB_FAULT_OVERRIDE_FILE)
    elif app_id == "inventory_app":
        targets = (INV_OVERRIDE_FILE, INV_DB_FAULT_OVERRIDE_FILE, CACHE_FAULT_OVERRIDE_FILE)
    else:
        targets = (OVERRIDE_FILE, DB_FAULT_OVERRIDE_FILE, INV_OVERRIDE_FILE, INV_DB_FAULT_OVERRIDE_FILE, CACHE_FAULT_OVERRIDE_FILE)

    for fpath in targets:
        if fpath.exists():
            fpath.unlink()
            changed = True
    return changed


def start_healthy_environment(runtime: Optional[str] = None, timeout_sec: float = 15.0) -> dict[str, Any]:
    """Start or restore all orders_app services to a clean, healthy configuration and wait for readiness."""
    with acquire_lab_lock("start_healthy_environment"):
        mode = resolve_runtime_mode(runtime)
        backend = get_backend_name(mode, app_id="orders_app")
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        (VAR_DIR / "logs").mkdir(parents=True, exist_ok=True)

        override_existed = _clear_all_fault_overrides(app_id="orders_app")
        _clear_service_logs(("gateway", "order-service"))

        if mode == "docker":
            _ensure_docker_in_path()
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.yml", "up", "-d", "postgres", "order-service", "gateway"],
                cwd=str(ROOT_DIR),
                check=True,
            )
        else:
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=override_existed)
            _start_local_gateway(pids, env, force_restart=False)

        state = wait_for_service_state(
            expect_gateway_ready=True,
            expect_order_live=True,
            expect_order_ready=True,
            expect_db_reachable=True,
            timeout_sec=timeout_sec,
        )
        _reset_service_metrics((GATEWAY_URL, ORDER_URL))
        return {"runtime": mode, "backend": backend, "state": state}


def start_healthy_inventory_environment(runtime: Optional[str] = None, timeout_sec: float = 15.0) -> dict[str, Any]:
    """Start or restore all inventory_app services to a clean, healthy configuration (Stage 8)."""
    with acquire_lab_lock("start_healthy_inventory_environment"):
        mode = resolve_runtime_mode(runtime)
        backend = get_backend_name(mode, app_id="inventory_app")
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        (VAR_DIR / "logs").mkdir(parents=True, exist_ok=True)

        _clear_all_fault_overrides(app_id="inventory_app")
        _clear_service_logs(("inventory-api", "inventory-service"))

        if mode == "docker":
            _ensure_docker_in_path()
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.yml", "up", "-d", "inventory-db", "inventory-cache", "inventory-service", "inventory-api"],
                cwd=str(ROOT_DIR),
                check=True,
            )
        else:
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_inv_db(pids, env)
            _start_local_inv_cache(pids, env)
            _start_local_inv_service(pids, env, force_restart=False)
            _start_local_inv_api(pids, env, force_restart=False)

        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=True,
            expect_db_reachable=True,
            expect_cache_reachable=True,
            timeout_sec=timeout_sec,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"runtime": mode, "backend": backend, "state": state}


def stop_environment(runtime: Optional[str] = None, app_id: str = "all") -> dict[str, Any]:
    """Stop running application services without deleting persistent database data."""
    with acquire_lab_lock("stop_environment"):
        mode = resolve_runtime_mode(runtime)
        backend = get_backend_name(mode, app_id=app_id if app_id in ("orders_app", "inventory_app") else "orders_app")
        if mode == "docker":
            _ensure_docker_in_path()
            if app_id == "orders_app":
                services = ["postgres", "order-service", "gateway"]
            elif app_id == "inventory_app":
                services = ["inventory-db", "inventory-cache", "inventory-service", "inventory-api"]
            else:
                services = []
            cmd = ["docker", "compose", "-f", "docker-compose.yml", "stop"]
            if services:
                cmd.extend(services)
            subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)
        else:
            pids = _load_pids()
            for name in (
                "gateway",
                "order-service",
                "database",
                "inventory-api",
                "inventory-service",
                "inventory-db",
                "inventory-cache",
            ):
                _kill_pid(pids.get(name))
            _save_pids({})
        return {"runtime": mode, "backend": backend, "stopped": True}


def trigger_mid_run_recovery() -> None:
    """Restore order-service DB config during an active investigation (for `challenging_recovery_mid_run`, Stage 6.1)."""
    if OVERRIDE_FILE.exists():
        try:
            OVERRIDE_FILE.unlink()
        except OSError:
            pass
    wait_for_service_state(
        expect_gateway_ready=True,
        expect_order_live=True,
        expect_order_ready=True,
        expect_db_reachable=True,
        timeout_sec=6.0,
    )


def apply_fault(
    fault_name: str,
    runtime: Optional[str] = None,
) -> dict[str, Any]:
    """Idempotently inject one of the controlled faults across orders_app or inventory_app."""
    if fault_name not in SUPPORTED_FAULT_NAMES:
        raise ControllerError(f"Unsupported fault name: {fault_name}")

    with acquire_lab_lock(f"apply_fault:{fault_name}"):
        mode = resolve_runtime_mode(runtime)
        is_inv = fault_name.startswith("inv_")
        target_app = "inventory_app" if is_inv else "orders_app"
        backend = get_backend_name(mode, app_id=target_app)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

        had_overrides = _clear_all_fault_overrides(app_id=target_app)
        if is_inv:
            try:
                ACTIVE_APP_FILE.write_text("inventory_app", encoding="utf-8")
            except OSError:
                pass
            _clear_service_logs(("inventory-api", "inventory-service"))
            return _apply_inventory_fault(fault_name, mode, backend)

        try:
            ACTIVE_APP_FILE.write_text("orders_app", encoding="utf-8")
        except OSError:
            pass
        _clear_service_logs(("gateway", "order-service"))

        if fault_name in ("fault_a", "challenging_recovery_mid_run"):
            # Note: order-service reads OVERRIDE_FILE dynamically on every request via load_db_config(),
            # so writing OVERRIDE_FILE without hardcoding env["DB_HOST"] allows mid-run recovery simply by removing OVERRIDE_FILE!
            if mode == "docker":
                with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "db_host": "invalid-db-host.internal",
                            "db_port": 5432,
                            "db_name": "nextrace_orders",
                        },
                        fh,
                        indent=2,
                    )
                state = wait_for_service_state(
                    expect_gateway_ready=True,
                    expect_order_live=True,
                    expect_order_ready=False,
                    expect_db_reachable=True,
                    timeout_sec=12.0,
                )
                _reset_service_metrics((GATEWAY_URL, ORDER_URL))
                return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "db_host": "invalid-db-host.internal",
                        "db_port": DB_PORT,
                        "db_name": "nextrace_orders",
                    },
                    fh,
                    indent=2,
                )
            _start_local_order_service(pids, env, force_restart=had_overrides)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "fault_b":
            if mode == "docker":
                _ensure_docker_in_path()
                subprocess.run(
                    ["docker", "compose", "-f", "docker-compose.yml", "stop", "postgres"],
                    cwd=str(ROOT_DIR),
                    check=True,
                )
                state = wait_for_service_state(
                    expect_gateway_ready=True,
                    expect_order_live=True,
                    expect_order_ready=False,
                    expect_db_reachable=False,
                    timeout_sec=12.0,
                )
                _reset_service_metrics((GATEWAY_URL, ORDER_URL))
                return {"fault": "fault_b", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            _kill_pid(pids.get("database"))
            pids.pop("database", None)
            _save_pids(pids)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=False,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": "fault_b", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "fault_c":
            if mode == "docker":
                with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "db_password": "wrong_invalid_password_fault_c",
                        },
                        fh,
                        indent=2,
                    )
                state = wait_for_service_state(
                    expect_gateway_ready=True,
                    expect_order_live=True,
                    expect_order_ready=False,
                    expect_db_reachable=True,
                    timeout_sec=12.0,
                )
                _reset_service_metrics((GATEWAY_URL, ORDER_URL))
                return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "db_host": "127.0.0.1",
                        "db_port": DB_PORT,
                        "db_name": "nextrace_orders",
                        "db_user": "nextrace_user",
                        "db_password": "wrong_invalid_password_fault_c",
                    },
                    fh,
                    indent=2,
                )
            _start_local_order_service(pids, env, force_restart=had_overrides)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": "fault_c", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "fault_d":
            if mode == "docker":
                with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "db_search_path": "missing_orders_schema",
                        },
                        fh,
                        indent=2,
                    )
                state = wait_for_service_state(
                    expect_gateway_ready=True,
                    expect_order_live=True,
                    expect_order_ready=False,
                    expect_db_reachable=True,
                    timeout_sec=12.0,
                )
                _reset_service_metrics((GATEWAY_URL, ORDER_URL))
                return {"fault": "fault_d", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

            pids = _load_pids()
            env = _base_subprocess_env()
            get_disposable_missing_schema_path()
            with open(DB_FAULT_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"active_schema_mode": "missing_orders_table"}, fh, indent=2)
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": "fault_d", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "fault_e":
            if mode == "docker":
                with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                    json.dump(
                        {
                            "operation_delay_ms": 1800,
                            "statement_timeout_ms": 300,
                        },
                        fh,
                        indent=2,
                    )
                state = wait_for_service_state(
                    expect_gateway_ready=True,
                    expect_order_live=True,
                    expect_order_ready=False,
                    expect_db_reachable=True,
                    timeout_sec=12.0,
                )
                _reset_service_metrics((GATEWAY_URL, ORDER_URL))
                return {"fault": "fault_e", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

            pids = _load_pids()
            env = _base_subprocess_env()
            with open(DB_FAULT_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"operation_delay_ms": 1800}, fh, indent=2)
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": "fault_e", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "fault_f":
            if mode == "docker":
                _ensure_docker_in_path()
                subprocess.run(
                    ["docker", "compose", "-f", "docker-compose.yml", "stop", "order-service"],
                    cwd=str(ROOT_DIR),
                    check=True,
                )
                state = wait_for_service_state(
                    expect_gateway_ready=False,
                    expect_order_live=False,
                    expect_order_ready=False,
                    expect_db_reachable=True,
                    timeout_sec=12.0,
                )
                _reset_service_metrics((GATEWAY_URL,))
                return {"fault": "fault_f", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_gateway(pids, env)
            _kill_pid(pids.get("order-service"))
            pids.pop("order-service", None)
            _save_pids(pids)
            state = wait_for_service_state(
                expect_gateway_ready=False,
                expect_order_live=False,
                expect_order_ready=False,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL,))
            return {"fault": "fault_f", "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "challenging_diag_endpoint_failure":
            # Stage 6.2: User traffic and all services are 100% healthy, but /internal/diagnostics/db-config returns HTTP 500
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"fail_diagnostics_db_config": True}, fh, indent=2)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=True,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "challenging_historical_logs_healthy_now":
            # Stage 6.3: All services are healthy now, but order-service.jsonl contains historical failure logs from 15 minutes ago
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=True,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            past_ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_file = get_log_dir() / "order-service.jsonl"
            historical_entry = {
                "timestamp": past_ts,
                "service": "order-service",
                "level": "ERROR",
                "event": "database_write_failed",
                "request_id": "req-historical-old-01",
                "order_id": "ord-historical-old",
                "configured_db_host": "invalid-db-host.internal",
                "configured_db_port": DB_PORT,
                "error_category": "hostname_resolution_failed",
                "error_detail": "Historical incident already resolved 15m ago",
            }
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(historical_entry) + "\n")
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "challenging_unknown_app_error":
            # Stage 6.4: Dependencies and config are 100% healthy, but POST /orders throws an unmodeled internal serialization exception
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"inject_unmodeled_app_error": True}, fh, indent=2)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=True,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "unknown_order_validation_contract_error":
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"inject_unmodeled_validation_contract_error": True}, fh, indent=2)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=True,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "unknown_order_currency_rounding_crash":
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"inject_unmodeled_currency_rounding_crash": True}, fh, indent=2)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=True,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "multi_fault_a_and_b":
            # Both Fault A (invalid DB hostname on order-service) AND Fault B (database process stopped) simultaneously!
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_gateway(pids, env)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "db_host": "invalid-db-host.internal",
                        "db_port": DB_PORT,
                        "db_name": "nextrace_orders",
                    },
                    fh,
                    indent=2,
                )
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _kill_pid(pids.get("database"))
            pids.pop("database", None)
            _save_pids(pids)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=False,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "multi_fault_c_and_d":
            # Both Fault C (invalid DB credentials on order-service) AND Fault D (database on missing orders table schema)
            pids = _load_pids()
            env = _base_subprocess_env()
            get_disposable_missing_schema_path()
            with open(DB_FAULT_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"active_schema_mode": "missing_orders_table"}, fh, indent=2)
            with open(OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "db_host": "127.0.0.1",
                        "db_port": DB_PORT,
                        "db_name": "nextrace_orders",
                        "db_user": "nextrace_user",
                        "db_password": "wrong_invalid_password_fault_c",
                    },
                    fh,
                    indent=2,
                )
            _start_local_database(pids, env)
            _start_local_order_service(pids, env, force_restart=had_overrides)
            _start_local_gateway(pids, env)
            state = wait_for_service_state(
                expect_gateway_ready=True,
                expect_order_live=True,
                expect_order_ready=False,
                expect_db_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL, ORDER_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        if fault_name == "multi_fault_f_masks_b":
            # Masking multi-fault: order-service stopped (Fault F) AND database stopped (Fault B)
            pids = _load_pids()
            env = _base_subprocess_env()
            _start_local_gateway(pids, env)
            _kill_pid(pids.get("order-service"))
            pids.pop("order-service", None)
            _kill_pid(pids.get("database"))
            pids.pop("database", None)
            _save_pids(pids)
            state = wait_for_service_state(
                expect_gateway_ready=False,
                expect_order_live=False,
                expect_order_ready=False,
                expect_db_reachable=False,
                timeout_sec=12.0,
            )
            _reset_service_metrics((GATEWAY_URL,))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

        raise ControllerError(f"Unhandled fault name: {fault_name}")


def _apply_inventory_fault(fault_name: str, mode: str, backend: str) -> dict[str, Any]:
    if fault_name == "inv_fault_db_unavailable":
        if mode == "docker":
            _ensure_docker_in_path()
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.yml", "stop", "inventory-db"],
                cwd=str(ROOT_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            state = wait_for_inventory_state(
                expect_api_ready=True,
                expect_inv_live=True,
                expect_inv_ready=False,
                expect_db_reachable=False,
                expect_cache_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_fault_cache_unavailable":
        if mode == "docker":
            _ensure_docker_in_path()
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.yml", "stop", "inventory-cache"],
                cwd=str(ROOT_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            state = wait_for_inventory_state(
                expect_api_ready=True,
                expect_inv_live=True,
                expect_inv_ready=False,
                expect_db_reachable=True,
                expect_cache_reachable=False,
                timeout_sec=12.0,
            )
            _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_fault_bad_db_config":
        if mode == "docker":
            with open(INV_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "db_host": "invalid-inv-db.internal",
                        "db_port": 5432,
                        "db_name": "nextrace_inventory",
                    },
                    fh,
                    indent=2,
                )
            state = wait_for_inventory_state(
                expect_api_ready=True,
                expect_inv_live=True,
                expect_inv_ready=False,
                expect_db_reachable=True,
                expect_cache_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_fault_upstream_timeout":
        if mode == "docker":
            with open(INV_DB_FAULT_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"operation_delay_ms": 1800}, fh, indent=2)
            with open(INV_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"operation_delay_ms": 1800, "db_statement_timeout_ms": 1500}, fh, indent=2)
            state = wait_for_inventory_state(
                expect_api_ready=True,
                expect_inv_live=True,
                expect_inv_ready=False,
                expect_db_reachable=True,
                expect_cache_reachable=True,
                timeout_sec=12.0,
            )
            _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_multi_fault_db_and_cache":
        if mode == "docker":
            _ensure_docker_in_path()
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.yml", "stop", "inventory-db", "inventory-cache"],
                cwd=str(ROOT_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            state = wait_for_inventory_state(
                expect_api_ready=True,
                expect_inv_live=True,
                expect_inv_ready=False,
                expect_db_reachable=False,
                expect_cache_reachable=False,
                timeout_sec=12.0,
            )
            _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
            return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    pids = _load_pids()
    env = _base_subprocess_env()
    _start_local_inv_db(pids, env)
    _start_local_inv_cache(pids, env)
    _start_local_inv_service(pids, env, force_restart=False)
    _start_local_inv_api(pids, env, force_restart=False)

    if fault_name == "inv_fault_db_unavailable":
        _kill_pid(pids.get("inventory-db"))
        pids.pop("inventory-db", None)
        _save_pids(pids)
        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=False,
            expect_db_reachable=False,
            expect_cache_reachable=True,
            timeout_sec=12.0,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_fault_cache_unavailable":
        _kill_pid(pids.get("inventory-cache"))
        pids.pop("inventory-cache", None)
        _save_pids(pids)
        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=False,
            expect_db_reachable=True,
            expect_cache_reachable=False,
            timeout_sec=12.0,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_fault_bad_db_config":
        with open(INV_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "db_host": "invalid-inv-db.internal",
                    "db_port": INV_DB_PORT,
                    "db_name": "nextrace_inventory",
                },
                fh,
                indent=2,
            )
        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=False,
            expect_db_reachable=True,
            expect_cache_reachable=True,
            timeout_sec=12.0,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_fault_upstream_timeout":
        with open(INV_DB_FAULT_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"operation_delay_ms": 1800}, fh, indent=2)
        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=False,
            expect_db_reachable=True,
            expect_cache_reachable=True,
            timeout_sec=12.0,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_unknown_sku_parser_exception":
        with open(INV_OVERRIDE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"inject_unmodeled_sku_parser_exception": True}, fh, indent=2)
        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=True,
            expect_db_reachable=True,
            expect_cache_reachable=True,
            timeout_sec=12.0,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    if fault_name == "inv_multi_fault_db_and_cache":
        _kill_pid(pids.get("inventory-db"))
        pids.pop("inventory-db", None)
        _kill_pid(pids.get("inventory-cache"))
        pids.pop("inventory-cache", None)
        _save_pids(pids)
        state = wait_for_inventory_state(
            expect_api_ready=True,
            expect_inv_live=True,
            expect_inv_ready=False,
            expect_db_reachable=False,
            expect_cache_reachable=False,
            timeout_sec=12.0,
        )
        _reset_service_metrics((INV_API_URL, INV_SERVICE_URL))
        return {"fault": fault_name, "runtime": mode, "backend": backend, "applied_at_utc": utc_now_iso(), "state": state}

    raise ControllerError(f"Unhandled inventory fault name: {fault_name}")


def reset_faults(runtime: Optional[str] = None, app_id: Optional[str] = None) -> dict[str, Any]:
    """Idempotently restore healthy configuration and services after any fault."""
    target_app = app_id
    if target_app is None:
        if ACTIVE_APP_FILE.exists():
            try:
                target_app = ACTIVE_APP_FILE.read_text(encoding="utf-8").strip()
            except OSError:
                target_app = None
        if not target_app:
            target_app = "orders_app"

    with acquire_lab_lock(f"reset_faults:{target_app}"):
        if target_app == "inventory_app":
            res = start_healthy_inventory_environment(runtime=runtime, timeout_sec=15.0)
        else:
            res = start_healthy_environment(runtime=runtime, timeout_sec=15.0)
        if ACTIVE_APP_FILE.exists():
            try:
                active_text = ACTIVE_APP_FILE.read_text(encoding="utf-8").strip()
                if not active_text or active_text == target_app or app_id is None:
                    ACTIVE_APP_FILE.unlink()
            except OSError:
                pass
        return {"reset": True, "restored_at_utc": utc_now_iso(), **res}


def submit_order(product_id: str, quantity: int, request_id: Optional[str] = None) -> tuple[int, dict[str, Any]]:
    """Submit a POST /orders request through the Gateway."""
    headers: dict[str, str] = {}
    if request_id:
        headers["X-Request-ID"] = request_id
    resp = httpx.post(
        f"{GATEWAY_URL}/orders",
        json={"product_id": product_id, "quantity": quantity},
        headers=headers,
        timeout=4.0,
    )
    return resp.status_code, resp.json()


def submit_inventory_reservation(sku: str, quantity: int, request_id: Optional[str] = None) -> tuple[int, dict[str, Any]]:
    """Submit a POST /inventory/reserve request through the Inventory API (Stage 8)."""
    headers: dict[str, str] = {}
    if request_id:
        headers["X-Request-ID"] = request_id
    resp = httpx.post(
        f"{INV_API_URL}/inventory/reserve",
        json={"sku": sku, "quantity": quantity},
        headers=headers,
        timeout=4.0,
    )
    return resp.status_code, resp.json()


def verify_order_persisted_independently(order_id: str, runtime: Optional[str] = None) -> dict[str, Any]:
    """Verify order persistence directly via a runtime-specific database query AND via API (Stage 1D)."""
    mode = resolve_runtime_mode(runtime)
    row: tuple[Any, ...] | None = None

    if mode == "docker":
        try:
            import psycopg  # type: ignore[import-not-found]

            with psycopg.connect(
                host="127.0.0.1",
                port=DB_PORT,
                dbname=os.environ.get("DB_NAME", "nextrace_orders"),
                user=os.environ.get("DB_USER", "nextrace_user"),
                password=os.environ.get("DB_PASSWORD", "nextrace_local_dev_pw"),
                connect_timeout=2,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT order_id, product_id, quantity, request_id, created_at::text FROM orders WHERE order_id = %s;",
                        (order_id,),
                    )
                    row = cur.fetchone()
        except Exception as exc:
            raise ControllerError(f"Direct PostgreSQL persistence verification failed for {order_id}: {exc}") from exc
    else:
        db_path = get_sqlite_path()
        if not db_path.exists():
            raise ControllerError(f"SQLite database file does not exist at {db_path}")
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        try:
            row = conn.execute(
                "SELECT order_id, product_id, quantity, request_id, created_at FROM orders WHERE order_id = ?;",
                (order_id,),
            ).fetchone()
        finally:
            conn.close()

    if row is None:
        raise ControllerError(f"Order {order_id} was not found in direct database storage ({get_backend_name(mode)})")

    api_resp = httpx.get(f"{GATEWAY_URL}/orders/{order_id}", timeout=2.5)
    if api_resp.status_code != 200:
        raise ControllerError(f"Gateway order lookup failed for {order_id}: HTTP {api_resp.status_code}")

    api_data = api_resp.json()
    if row[0] != order_id or row[1] != api_data["product_id"] or int(row[2]) != int(api_data["quantity"]):
        raise ControllerError(f"Database row mismatch for order {order_id}")

    return {
        "verified": True,
        "order_id": order_id,
        "product_id": api_data["product_id"],
        "quantity": api_data["quantity"],
        "request_id": api_data["request_id"],
        "created_at": api_data["created_at"],
        "direct_storage_verified": True,
        "backend": get_backend_name(mode),
    }


def verify_inventory_persisted_independently(reservation_id: str, runtime: Optional[str] = None) -> dict[str, Any]:
    """Verify inventory reservation persistence directly in DB AND Redis cache AND via API."""
    mode = resolve_runtime_mode(runtime)
    row: tuple[Any, ...] | None = None
    cache_verified = False
    cache_val: Optional[str] = None

    if mode == "docker":
        try:
            import psycopg  # type: ignore[import-not-found]

            with psycopg.connect(
                host="127.0.0.1",
                port=INV_DB_PORT,
                dbname=os.environ.get("INV_DB_NAME", "nextrace_inventory"),
                user=os.environ.get("INV_DB_USER", "nextrace_user"),
                password=os.environ.get("INV_DB_PASSWORD", "nextrace_local_dev_pw"),
                connect_timeout=2,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT reservation_id, sku, quantity, request_id, status, created_at::text FROM inventory_reservations WHERE reservation_id = %s;",
                        (reservation_id,),
                    )
                    row = cur.fetchone()
        except Exception as exc:
            raise ControllerError(f"Direct PostgreSQL persistence verification failed for {reservation_id}: {exc}") from exc

        # Check Redis cache
        try:
            with socket.create_connection(("127.0.0.1", INV_CACHE_PORT), timeout=2.0) as sock:
                sock.settimeout(2.0)
                cmd = f"*2\r\n$3\r\nGET\r\n${len(f'reservation:{reservation_id}')}\r\nreservation:{reservation_id}\r\n".encode("utf-8")
                sock.sendall(cmd)
                raw = sock.recv(1024).decode("utf-8", errors="replace")
                if "$" in raw and not "$-1" in raw:
                    cache_verified = True
                    cache_val = raw.strip()
        except Exception:
            pass
    else:
        db_path = INV_SQLITE_PATH
        if not db_path.exists():
            raise ControllerError(f"SQLite inventory database file does not exist at {db_path}")
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        try:
            row = conn.execute(
                "SELECT order_id, product_id, quantity, request_id, created_at FROM orders WHERE order_id = ?;",
                (reservation_id,),
            ).fetchone()
        finally:
            conn.close()

    if row is None:
        raise ControllerError(f"Reservation {reservation_id} was not found in direct database storage ({get_backend_name(mode, app_id='inventory_app')})")

    api_resp = httpx.get(f"{INV_API_URL}/inventory/reservations/{reservation_id}", timeout=2.5)
    if api_resp.status_code != 200:
        raise ControllerError(f"Inventory API lookup failed for {reservation_id}: HTTP {api_resp.status_code}")

    api_data = api_resp.json()
    if row[0] != reservation_id or row[1] != api_data["sku"] or int(row[2]) != int(api_data["quantity"]):
        raise ControllerError(f"Database row mismatch for reservation {reservation_id}")

    return {
        "verified": True,
        "reservation_id": reservation_id,
        "sku": api_data["sku"],
        "quantity": api_data["quantity"],
        "request_id": api_data["request_id"],
        "created_at": api_data["created_at"],
        "direct_storage_verified": True,
        "cache_verified": cache_verified,
        "cache_raw": cache_val,
        "backend": get_backend_name(mode, app_id="inventory_app"),
    }

