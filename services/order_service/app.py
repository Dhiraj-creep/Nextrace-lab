"""Order Service: validates order requests, persists to database, exposes controlled diagnostic probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from nextrace_lab.logging_utils import append_log_event, utc_now_iso
from services.order_service.db import (
    DatabaseOperationError,
    fetch_order_record,
    insert_order_record,
    load_db_config,
    probe_db_connectivity,
)

app = FastAPI(title="NexTrace Order Service", version="0.3.0")

SERVICE_NAME = "order-service"
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


def _load_runtime_override_flags() -> dict[str, Any]:
    override_file = os.environ.get("NEXTRACE_ORDER_CONFIG_OVERRIDE_FILE", "")
    if override_file and Path(override_file).exists():
        try:
            with open(override_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


class CreateOrderPayload(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=1000)


@app.get("/health/live")
def health_live() -> dict[str, Any]:
    return {"service": SERVICE_NAME, "status": "live", "timestamp": utc_now_iso()}


@app.get("/health/ready")
def health_ready(response: Response) -> dict[str, Any]:
    probe = probe_db_connectivity()
    if probe.get("ok"):
        return {
            "service": SERVICE_NAME,
            "status": "ready",
            "database_connectivity": "ok",
            "latency_ms": probe.get("latency_ms"),
            "timestamp": utc_now_iso(),
        }
    response.status_code = 503
    return {
        "service": SERVICE_NAME,
        "status": "not_ready",
        "database_connectivity": "failed",
        "error_category": probe.get("error_category"),
        "latency_ms": probe.get("latency_ms"),
        "timestamp": utc_now_iso(),
    }


@app.get("/internal/diagnostics/db-config")
def diagnostics_db_config(response: Response) -> dict[str, Any]:
    flags = _load_runtime_override_flags()
    if flags.get("fail_diagnostics_db_config"):
        response.status_code = 500
        return {
            "service": SERVICE_NAME,
            "status": "diagnostic_endpoint_error",
            "reason": "simulated_config_inspector_failure",
            "timestamp": utc_now_iso(),
        }
    cfg = load_db_config()
    return {
        "service": SERVICE_NAME,
        "sanitized_config": cfg.sanitized_dict(),
        "timestamp": utc_now_iso(),
    }


@app.get("/internal/diagnostics/db-connectivity")
def diagnostics_db_connectivity() -> dict[str, Any]:
    probe = probe_db_connectivity()
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


@app.post("/orders")
def create_order(payload: CreateOrderPayload, request: Request, response: Response) -> dict[str, Any]:
    request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    order_id = f"ord-{uuid.uuid4().hex[:10]}"
    started = time.perf_counter()
    cfg = load_db_config()
    flags = _load_runtime_override_flags()

    append_log_event(
        service=SERVICE_NAME,
        level="INFO",
        event="order_persistence_started",
        request_id=request_id,
        order_id=order_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        configured_db_host=cfg.host,
        configured_db_port=cfg.port,
    )

    unmodeled_fault = None
    if flags.get("inject_unmodeled_validation_contract_error"):
        unmodeled_fault = (
            "validation_schema_contract_error",
            "Unexpected JSON schema contract violation in payload validator",
        )
    elif flags.get("inject_unmodeled_currency_rounding_crash"):
        unmodeled_fault = (
            "currency_rounding_arithmetic_crash",
            "Floating point arithmetic crash in multi-currency conversion module",
        )
    elif flags.get("inject_unmodeled_app_error"):
        unmodeled_fault = (
            "unmodeled_serialization_bug",
            "Unhandled Decimal/Currency serialization exception in discount calculator before DB commit",
        )

    if unmodeled_fault is not None:
        err_cat, err_det = unmodeled_fault
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
            order_id=order_id,
            configured_db_host=cfg.host,
            configured_db_port=cfg.port,
            error_category=err_cat,
            error_detail=err_det,
            duration_ms=duration_ms,
        )
        return {
            "error": "internal_application_error",
            "error_category": err_cat,
            "error_detail": err_det,
            "request_id": request_id,
        }

    try:
        record = insert_order_record(
            order_id=order_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            request_id=request_id,
            config=cfg,
        )
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["total_duration_ms"] += duration_ms
        _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
        _METRICS["last_event_time_utc"] = utc_now_iso()
        response.status_code = 201
        append_log_event(
            service=SERVICE_NAME,
            level="INFO",
            event="order_persisted",
            request_id=request_id,
            order_id=order_id,
            duration_ms=duration_ms,
            status_code=201,
        )
        return record
    except DatabaseOperationError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["failure_count"] += 1
        _METRICS["dependency_failures"] += 1
        if exc.error_category == "operation_timeout":
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
            order_id=order_id,
            configured_db_host=exc.configured_host,
            configured_db_port=exc.configured_port,
            error_category=exc.error_category,
            error_detail=exc.detail,
            duration_ms=duration_ms,
        )
        return {
            "error": "database_unavailable",
            "error_category": exc.error_category,
            "request_id": request_id,
        }


@app.get("/orders/{order_id}")
def get_order(order_id: str, request: Request, response: Response) -> dict[str, Any]:
    request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    cfg = load_db_config()
    try:
        record = fetch_order_record(order_id=order_id, config=cfg)
        if record is None:
            response.status_code = 404
            return {"error": "order_not_found", "order_id": order_id, "request_id": request_id}
        return record
    except DatabaseOperationError as exc:
        response.status_code = 503
        append_log_event(
            service=SERVICE_NAME,
            level="ERROR",
            event="database_read_failed",
            request_id=request_id,
            order_id=order_id,
            configured_db_host=exc.configured_host,
            configured_db_port=exc.configured_port,
            error_category=exc.error_category,
            error_detail=exc.detail,
        )
        return {
            "error": "database_unavailable",
            "error_category": exc.error_category,
            "request_id": request_id,
        }
