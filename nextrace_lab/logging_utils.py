"""Structured JSON logging, sanitization, and bounded runtime-isolated log retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import threading
from typing import Any, Literal, Optional

from nextrace_lab.schemas import StructuredLogRecord

_LOG_LOCK = threading.Lock()

_SECRET_PATTERNS = [
    re.compile(r"(postgres(?:ql)?://[^:\s]+:)([^@\s]+)(@)", re.IGNORECASE),
    re.compile(r"((?:password|passwd|secret|token|api_key)\s*[=:]\s*)([^\s,;\"']+)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([^\s,;\"']+)", re.IGNORECASE),
]


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_utc_iso(ts: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp string into a timezone-aware datetime."""
    cleaned = ts.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def sanitize_text(value: Optional[str]) -> Optional[str]:
    """Redact credentials, passwords, or connection-string secrets from text."""
    if value is None:
        return None
    result = str(value)
    result = _SECRET_PATTERNS[0].sub(r"\1***REDACTED***\3", result)
    result = _SECRET_PATTERNS[1].sub(r"\1***REDACTED***", result)
    result = _SECRET_PATTERNS[2].sub(r"\1***REDACTED***", result)
    return result


def redact_sensitive_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize a dictionary, redacting secret keys and values."""
    sanitized: dict[str, Any] = {}
    secret_keys = {"password", "db_password", "secret", "token", "dsn", "connection_string", "api_key"}
    for key, val in data.items():
        if any(sk in key.lower() for sk in secret_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(val, str):
            sanitized[key] = sanitize_text(val)
        elif isinstance(val, dict):
            sanitized[key] = redact_sensitive_fields(val)
        elif isinstance(val, list):
            sanitized[key] = [
                redact_sensitive_fields(item)
                if isinstance(item, dict)
                else (sanitize_text(item) if isinstance(item, str) else item)
                for item in val
            ]
        else:
            sanitized[key] = val
    return sanitized


sanitize_dict = redact_sensitive_fields


def get_log_dir(runtime_mode: Optional[str] = None) -> Path:
    """Return the runtime-isolated directory where structured service JSONL logs are stored."""
    base = os.environ.get("NEXTRACE_LOG_DIR")
    if base:
        path = Path(base)
    else:
        root = Path(__file__).resolve().parent.parent / "var" / "logs"
        mode = (runtime_mode or os.environ.get("NEXTRACE_RUNTIME_ACTIVE") or "local").lower()
        path = root / "docker_postgresql" if mode == "docker" else root
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_log_event(
    *,
    service: str,
    level: str = "INFO",
    event: str,
    request_id: Optional[str] = None,
    runtime_mode: Optional[str] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Append a sanitized JSONL log entry for `service` and return the record dict."""
    ts = utc_now_iso()
    record: dict[str, Any] = {
        "timestamp": ts,
        "timestamp_utc": ts,
        "service": service,
        "level": level.upper(),
        "event": event,
        "request_id": request_id,
    }
    record.update(redact_sensitive_fields(kwargs))
    log_file = get_log_dir(runtime_mode=runtime_mode) / f"{service}.jsonl"
    with _LOG_LOCK:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return record


def read_recent_logs(
    *,
    service: str,
    limit: int = 20,
    runtime_mode: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Read the most recent `limit` structured log entries for `service`."""
    if limit <= 0:
        return []
    capped = min(limit, 200)
    log_file = get_log_dir(runtime_mode=runtime_mode) / f"{service}.jsonl"
    if not log_file.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with open(log_file, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entries.append(redact_sensitive_fields(json.loads(line)))
                except Exception:
                    continue
    except OSError:
        return []
    return entries[-capped:]


def emit_structured_log(
    *,
    service: str,
    event: str,
    outcome: Literal["success", "failure", "info"],
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    error_category: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    runtime_mode: Optional[str] = None,
) -> StructuredLogRecord:
    """Emit a sanitized structured JSON log record to disk and return it."""
    record = StructuredLogRecord(
        timestamp_utc=utc_now_iso(),
        service=service,
        request_id=request_id,
        event=event,
        outcome=outcome,
        duration_ms=round(duration_ms, 3) if duration_ms is not None else None,
        error_category=sanitize_text(error_category),
        details=redact_sensitive_fields(details or {}),
    )
    append_log_event(
        service=service,
        level="ERROR" if outcome == "failure" else "INFO",
        event=event,
        request_id=request_id,
        outcome=outcome,
        duration_ms=record.duration_ms,
        error_category=record.error_category,
        details=record.details,
        runtime_mode=runtime_mode,
    )
    return record
