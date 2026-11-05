"""Gateway service: receives user requests, forwards to order-service, logs structured events."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
import httpx
from pydantic import BaseModel, Field

from nextrace_lab.logging_utils import append_log_event, utc_now_iso

app = FastAPI(title="NexTrace Gateway Service", version="0.3.0")

SERVICE_NAME = "gateway"
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


def get_order_service_url() -> str:
    return os.environ.get("ORDER_SERVICE_URL", "http://127.0.0.1:18001").rstrip("/")


def get_forward_timeout_sec() -> float:
    return float(os.environ.get("ORDER_SERVICE_TIMEOUT_SEC", "2.5"))


class CreateOrderPayload(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=1000)


@app.get("/health/live")
def health_live() -> dict[str, Any]:
    return {"service": SERVICE_NAME, "status": "live", "timestamp": utc_now_iso()}


@app.get("/health/ready")
def health_ready(response: Response) -> dict[str, Any]:
    order_url = get_order_service_url()
    started = time.perf_counter()
    try:
        resp = httpx.get(f"{order_url}/health/live", timeout=1.0)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if resp.status_code == 200:
            return {
                "service": SERVICE_NAME,
                "status": "ready",
                "upstream_order_service": "reachable",
                "latency_ms": latency_ms,
                "timestamp": utc_now_iso(),
            }
        response.status_code = 503
        return {
            "service": SERVICE_NAME,
            "status": "not_ready",
            "upstream_order_service": f"http_{resp.status_code}",
            "latency_ms": latency_ms,
            "timestamp": utc_now_iso(),
        }
    except httpx.RequestError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        response.status_code = 503
        return {
            "service": SERVICE_NAME,
            "status": "not_ready",
            "upstream_order_service": "unreachable",
            "reason": type(exc).__name__,
            "latency_ms": latency_ms,
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
    started = time.perf_counter()
    order_url = get_order_service_url()
    timeout_sec = get_forward_timeout_sec()

    append_log_event(
        service=SERVICE_NAME,
        level="INFO",
        event="order_request_received",
        request_id=request_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        upstream_url=order_url,
    )

    try:
        upstream_resp = httpx.post(
            f"{order_url}/orders",
            json=payload.model_dump(),
            headers={"X-Request-ID": request_id},
            timeout=timeout_sec,
        )
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["total_duration_ms"] += duration_ms
        _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
        _METRICS["last_event_time_utc"] = utc_now_iso()

        if upstream_resp.status_code in (200, 201):
            body = upstream_resp.json()
            response.status_code = 201
            append_log_event(
                service=SERVICE_NAME,
                level="INFO",
                event="order_request_succeeded",
                request_id=request_id,
                order_id=body.get("order_id"),
                status_code=201,
                duration_ms=duration_ms,
            )
            return body

        _METRICS["failure_count"] += 1
        _METRICS["dependency_failures"] += 1
        response.status_code = 503
        append_log_event(
            service=SERVICE_NAME,
            level="ERROR",
            event="order_request_failed_upstream",
            request_id=request_id,
            upstream_status_code=upstream_resp.status_code,
            status_code=503,
            duration_ms=duration_ms,
            error_category="upstream_order_service_error",
        )
        return {
            "error": "order_processing_failed",
            "message": "Unable to process order at this time.",
            "request_id": request_id,
            "status_code": 503,
        }

    except httpx.TimeoutException as exc:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["failure_count"] += 1
        _METRICS["dependency_failures"] += 1
        _METRICS["dependency_timeouts"] += 1
        _METRICS["total_duration_ms"] += duration_ms
        _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
        _METRICS["last_event_time_utc"] = utc_now_iso()
        response.status_code = 503
        append_log_event(
            service=SERVICE_NAME,
            level="ERROR",
            event="order_request_upstream_timeout",
            request_id=request_id,
            status_code=503,
            duration_ms=duration_ms,
            error_category="upstream_order_service_timeout",
            exception_type=type(exc).__name__,
        )
        return {
            "error": "order_processing_failed",
            "message": "Unable to process order at this time.",
            "request_id": request_id,
            "status_code": 503,
        }
    except httpx.RequestError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        _METRICS["request_count"] += 1
        _METRICS["failure_count"] += 1
        _METRICS["dependency_failures"] += 1
        _METRICS["total_duration_ms"] += duration_ms
        _METRICS["max_duration_ms"] = max(float(_METRICS["max_duration_ms"]), duration_ms)
        _METRICS["last_event_time_utc"] = utc_now_iso()
        response.status_code = 503
        append_log_event(
            service=SERVICE_NAME,
            level="ERROR",
            event="order_request_upstream_unreachable",
            request_id=request_id,
            status_code=503,
            duration_ms=duration_ms,
            error_category="upstream_order_service_unreachable",
            exception_type=type(exc).__name__,
        )
        return {
            "error": "order_processing_failed",
            "message": "Unable to process order at this time.",
            "request_id": request_id,
            "status_code": 503,
        }


@app.get("/orders/{order_id}")
def get_order(order_id: str, request: Request, response: Response) -> dict[str, Any]:
    request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    order_url = get_order_service_url()
    timeout_sec = get_forward_timeout_sec()
    try:
        upstream_resp = httpx.get(
            f"{order_url}/orders/{order_id}",
            headers={"X-Request-ID": request_id},
            timeout=timeout_sec,
        )
        response.status_code = upstream_resp.status_code
        return upstream_resp.json()
    except httpx.RequestError:
        response.status_code = 503
        return {
            "error": "order_lookup_failed",
            "message": "Unable to retrieve order at this time.",
            "request_id": request_id,
            "status_code": 503,
        }
