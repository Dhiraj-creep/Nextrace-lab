"""Controlled Diagnostic Interface (v0.4.0 — Stages 1, 3, 5, 6 & 8).

All diagnostic strategies (fixed checklists, rule-based, heuristic scored selectors, and AI-guided selectors)
MUST interact with the environment exclusively through this interface.

Enforces:
- Allowlisted check catalog and parameter validation.
- Evidence availability conditions E0, E1, E2, E3, E4 (metrics unavailable), and E5 (metrics stale/low-sample),
  plus historical E2_phase2_minimal_v1.
- Explicit check cost accounting and budget enforcement (`attempt_charged_v2` charges declared cost for all
  admitted attempts including unavailable and failed checks; `legacy_free_unavailable_v1` preserved separately).
- Separate tracking of `attempts_admitted`, `successful_observations_count`, and `rejected_pre_dispatch_count`.
- Shared temporal evidence layer (`temporal.py`): event time, collection time, observation interval,
  evaluation time, freshness status, supersession, incident-window alignment, and timestamp uncertainty.
- Monotonic wall-clock deadline propagation (`DeadlineTracker`) to all HTTP and TCP/DB/Cache probes.
- Multi-application and multi-backend support (`orders_app` and `inventory_app`; local TCP substitutes and
  Docker PostgreSQL / Redis).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import socket
import time
from typing import Any, Callable, Optional

import httpx

from nextrace_lab.budget_ledger import DeadlineExceededError, DeadlineTracker
from nextrace_lab.check_catalog import CHECK_CATALOG, validate_check_call
from nextrace_lab.logging_utils import parse_utc_iso, read_recent_logs, utc_now_iso
from nextrace_lab.schemas import (
    CostModelVersion,
    DiagnosticCheckResult,
    EvidenceCondition,
    EvidenceStatus,
    IncidentContext,
)

COST_MODEL_VERSION: CostModelVersion = "attempt_charged_v2"

from nextrace_lab.temporal import (
    filter_log_entries_for_incident_window,
    is_timestamp_in_incident_window,
    parse_event_timestamp_safely,
    refresh_temporal_evidence_state,
)

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


class PreDispatchCallRejectedError(RuntimeError):
    """Raised when a diagnostic check call is rejected before network dispatch."""

    def __init__(self, message: str, reason: str = "budget_exhausted_on_call") -> None:
        super().__init__(message)
        self.reason = reason


class BudgetExhaustedError(PreDispatchCallRejectedError):
    """Raised when a check execution would exceed the remaining diagnostic budget."""

    def __init__(self, message: str) -> None:
        super().__init__(message, reason="budget_exhausted_on_call")


class DiagnosticInterface:
    """Single controlled diagnostic tool surface for all investigators."""

    def __init__(
        self,
        evidence_condition: EvidenceCondition = EvidenceCondition.E0,
        budget_limit: int = 8,
        app_id: str = "orders_app",
        deadline_tracker: Optional[DeadlineTracker] = None,
        clock_fn: Callable[[], float] = time.monotonic,
        utc_clock_fn: Callable[[], str] = utc_now_iso,
        on_after_check_hook: Optional[Callable[[int, DiagnosticCheckResult], None]] = None,
        incident: Optional[IncidentContext] = None,
        cost_model_version: CostModelVersion = "attempt_charged_v2",
        evidence_policy_version: Optional[str] = None,
    ) -> None:
        self.evidence_condition = EvidenceCondition(evidence_condition)
        self.budget_limit = budget_limit
        self.app_id = app_id
        self.deadline_tracker = deadline_tracker or DeadlineTracker(max_wall_clock_sec=25.0, clock_fn=clock_fn)
        self.clock_fn = clock_fn
        self.utc_clock_fn = utc_clock_fn
        self.on_after_check_hook = on_after_check_hook
        self.incident = incident
        self.cost_model_version: CostModelVersion = cost_model_version
        self.evidence_policy_version = evidence_policy_version or f"{self.evidence_condition.value}_v2"
        self._simulated_clock_offset_sec: float = 0.0

        self.budget_used = 0
        self.step_counter = 0
        self.attempts_admitted = 0
        self.successful_observations_count = 0
        self.rejected_pre_dispatch_count = 0
        self.history: list[DiagnosticCheckResult] = []
        self._record_acquired_monotonic: dict[str, float] = {}
        self._unavailable_calls_seen: set[str] = set()
        self.redundant_unavailable_checks = 0

    def set_incident_context(self, incident: IncidentContext) -> None:
        """Bind the active IncidentContext so temporal incident-window alignment is enforced."""
        self.incident = incident
        self.refresh_staleness_flags()

    def now_monotonic(self) -> float:
        return self.clock_fn() + self._simulated_clock_offset_sec

    def now_utc_iso(self) -> str:
        base_iso = self.utc_clock_fn()
        if self._simulated_clock_offset_sec > 0.0:
            try:
                dt = parse_utc_iso(base_iso) + timedelta(seconds=self._simulated_clock_offset_sec)
                return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            except Exception:
                return base_iso
        return base_iso

    def advance_simulated_clock(self, seconds: float) -> None:
        """Advance simulated monotonic and UTC clocks for freshness TTL expiration testing."""
        self._simulated_clock_offset_sec += max(0.0, float(seconds))
        self.refresh_staleness_flags()

    def refresh_staleness_flags(self) -> list[str]:
        """Update freshness, supersession, and incident-window alignment across all historical records."""
        stale_ids, _ = refresh_temporal_evidence_state(
            self.history,
            self._record_acquired_monotonic,
            self.now_monotonic(),
            evaluation_time_utc=self.now_utc_iso(),
            incident=self.incident,
        )
        return stale_ids

    def get_superseded_ids(self) -> list[str]:
        _, superseded_ids = refresh_temporal_evidence_state(
            self.history,
            self._record_acquired_monotonic,
            self.now_monotonic(),
            evaluation_time_utc=self.now_utc_iso(),
            incident=self.incident,
        )
        return superseded_ids

    @property
    def budget_remaining(self) -> int:
        return max(0, self.budget_limit - self.budget_used)

    def can_afford(self, check_name: str) -> bool:
        spec = CHECK_CATALOG.get(check_name)
        if spec is None:
            return False
        return spec.cost_units <= self.budget_remaining

    @staticmethod
    def canonical_call_key(check_name: str, params: dict[str, Any]) -> str:
        _, _, norm = validate_check_call(check_name, params)
        target = norm if norm else (params or {})
        return f"{check_name}:{json.dumps(target, sort_keys=True)}"

    def is_known_unavailable(self, check_name: str, params: dict[str, Any]) -> bool:
        return self.canonical_call_key(check_name, params) in self._unavailable_calls_seen

    def count_prior_executions(self, check_name: str, params: dict[str, Any]) -> int:
        key = self.canonical_call_key(check_name, params)
        count = 0
        for rec in self.history:
            if self.canonical_call_key(rec.check_name, rec.params) == key:
                count += 1
        return count

    def get_latest_fresh_result(self, check_name: str, params: dict[str, Any]) -> Optional[DiagnosticCheckResult]:
        """Return the most recent AVAILABLE non-stale, non-superseded result for `(check_name, params)`, or None."""
        self.refresh_staleness_flags()
        key = self.canonical_call_key(check_name, params)
        for rec in reversed(self.history):
            if self.canonical_call_key(rec.check_name, rec.params) == key and rec.status == EvidenceStatus.AVAILABLE:
                if not rec.is_stale and not rec.is_superseded and not rec.timestamp_uncertain:
                    return rec
                return None
        return None

    def _is_blocked_by_policy(self, check_name: str, params: dict[str, Any]) -> tuple[bool, str]:
        cond = self.evidence_condition
        service = params.get("service")

        if self.evidence_policy_version == "E2_phase2_minimal_v1":
            if check_name in (
                "get_recent_logs",
                "get_order_service_database_config",
                "get_inventory_service_config",
                "check_database_connectivity_from_order_service",
                "check_inventory_db_connectivity",
                "get_service_metrics",
            ):
                return True, f"Historical Policy E2_phase2_minimal_v1 blocks {check_name}."
            return False, ""

        if cond == EvidenceCondition.E0:
            return False, ""

        if cond == EvidenceCondition.E1:
            if check_name == "get_recent_logs" and service in ("order-service", "inventory-service"):
                return True, f"Policy E1 ({self.evidence_policy_version}) blocks {service} log retrieval."
            return False, ""

        if cond == EvidenceCondition.E2:
            if check_name in (
                "check_database_connectivity_from_order_service",
                "check_inventory_db_connectivity",
            ):
                return True, f"Policy E2 ({self.evidence_policy_version}) blocks active database connectivity probe."
            return False, ""

        if cond == EvidenceCondition.E3:
            if check_name == "get_recent_logs" and service in ("order-service", "inventory-service"):
                return True, f"Policy E3 ({self.evidence_policy_version}) blocks {service} log retrieval."
            if check_name in ("get_order_service_database_config", "get_inventory_service_config"):
                return True, f"Policy E3 ({self.evidence_policy_version}) blocks service database configuration inspection."
            return False, ""

        if cond == EvidenceCondition.E4:
            if check_name == "get_service_metrics":
                return True, f"Policy E4 ({self.evidence_policy_version}) blocks service metrics collection."
            return False, ""

        return False, ""

    def _http_timeout(self, default_sec: float, context: str) -> float:
        return self.deadline_tracker.effective_timeout(default_sec, context=context)

    def register_observation(
        self,
        res: DiagnosticCheckResult,
        *,
        acquired_monotonic: Optional[float] = None,
    ) -> DiagnosticCheckResult:
        """Append a pre-constructed DiagnosticCheckResult (e.g. in unit tests) with full temporal tracking."""
        acq = self.now_monotonic() if acquired_monotonic is None else float(acquired_monotonic)
        self._record_acquired_monotonic[res.evidence_id] = acq
        self.history.append(res)
        self.refresh_staleness_flags()
        return res

    def execute_check(self, check_name: str, params: Optional[dict[str, Any]] = None) -> DiagnosticCheckResult:
        """Validate and execute a single diagnostic check with cost, policy, freshness, and deadline enforcement."""
        raw_params = dict(params or {})
        started = time.perf_counter()
        collection_utc = self.now_utc_iso()

        # 1. Check monotonic deadline before dispatching any check
        try:
            self.deadline_tracker.check_not_expired(context=f"execute_check({check_name})")
        except DeadlineExceededError as exc:
            self.rejected_pre_dispatch_count += 1
            self.step_counter += 1
            ev_id = f"ev-{self.step_counter:02d}"
            res = DiagnosticCheckResult(
                evidence_id=ev_id,
                step_number=self.step_counter,
                check_name=check_name,
                params=raw_params,
                status=EvidenceStatus.COLLECTION_FAILED,
                cost_units=0,
                latency_ms=0.0,
                timestamp_utc=collection_utc,
                collection_time_utc=collection_utc,
                evaluation_time_utc=collection_utc,
                freshness_status="not_applicable",
                summary=f"Check rejected before dispatch: monotonic wall-clock deadline exceeded ({exc})",
                data={"reason": "monotonic_deadline_exceeded", "detail": str(exc), "rejected_pre_dispatch": True},
            )
            self._record_acquired_monotonic[ev_id] = self.now_monotonic()
            self.history.append(res)
            self.refresh_staleness_flags()
            return res

        # 2. Validate against allowlisted check catalog
        valid, reason, normalized_params = validate_check_call(check_name, raw_params)
        if not valid:
            self.rejected_pre_dispatch_count += 1
            self.step_counter += 1
            ev_id = f"ev-{self.step_counter:02d}"
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            res = DiagnosticCheckResult(
                evidence_id=ev_id,
                step_number=self.step_counter,
                check_name=check_name,
                params=raw_params,
                status=EvidenceStatus.INVALID_CALL,
                cost_units=0,
                latency_ms=latency_ms,
                timestamp_utc=collection_utc,
                collection_time_utc=collection_utc,
                evaluation_time_utc=collection_utc,
                freshness_status="not_applicable",
                summary=f"Invalid diagnostic check call: {reason}",
                data={"error": reason, "rejected_pre_dispatch": True},
            )
            self._record_acquired_monotonic[ev_id] = self.now_monotonic()
            self.history.append(res)
            self.refresh_staleness_flags()
            return res

        spec = CHECK_CATALOG[check_name]
        call_key = f"{check_name}:{json.dumps(normalized_params, sort_keys=True)}"
        repeat_idx = self.count_prior_executions(check_name, normalized_params) + 1
        blocked, policy_reason = self._is_blocked_by_policy(check_name, normalized_params)

        # 3. Determine attempt cost under active CostModelVersion (Stage 3)
        if blocked and self.cost_model_version == "legacy_free_unavailable_v1":
            attempt_cost = 0
        else:
            attempt_cost = spec.cost_units

        # 4. Enforce budget limit BEFORE admitting the attempt
        if self.budget_used + attempt_cost > self.budget_limit:
            self.rejected_pre_dispatch_count += 1
            raise BudgetExhaustedError(
                f"Cannot execute '{check_name}' (cost={attempt_cost}): "
                f"budget_used={self.budget_used}, budget_limit={self.budget_limit}"
            )

        # 5. Admit attempt and charge declared attempt cost
        self.step_counter += 1
        self.attempts_admitted += 1
        self.budget_used += attempt_cost
        ev_id = f"ev-{self.step_counter:02d}"

        if blocked:
            if call_key in self._unavailable_calls_seen:
                self.redundant_unavailable_checks += 1
            self._unavailable_calls_seen.add(call_key)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            res = DiagnosticCheckResult(
                evidence_id=ev_id,
                step_number=self.step_counter,
                check_name=check_name,
                params=normalized_params,
                status=EvidenceStatus.UNAVAILABLE_BY_POLICY,
                cost_units=attempt_cost,
                latency_ms=latency_ms,
                timestamp_utc=collection_utc,
                collection_time_utc=collection_utc,
                evaluation_time_utc=collection_utc,
                freshness_ttl_sec=spec.freshness_ttl_sec,
                freshness_status="not_applicable",
                evidence_source=spec.evidence_source,
                repeat_index=repeat_idx,
                summary=f"Unavailable under evidence condition {self.evidence_condition.value}: {policy_reason}",
                data={
                    "evidence_condition": self.evidence_condition.value,
                    "evidence_policy_version": self.evidence_policy_version,
                    "cost_model_version": self.cost_model_version,
                    "policy_reason": policy_reason,
                },
            )
            self._record_acquired_monotonic[ev_id] = self.now_monotonic()
            self.history.append(res)
            self.refresh_staleness_flags()
            return res

        try:
            status, summary, data = self._dispatch(check_name, normalized_params)
        except DeadlineExceededError as exc:
            status = EvidenceStatus.COLLECTION_FAILED
            summary = f"Check timed out against monotonic deadline: {exc}"
            data = {"reason": "monotonic_deadline_exceeded", "detail": str(exc)}
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)

        if status == EvidenceStatus.AVAILABLE:
            self.successful_observations_count += 1

        raw_event_ts = data.get("event_time_utc") if "event_time_utc" in data else collection_utc
        _, ts_uncertain, ts_unc_reason = parse_event_timestamp_safely(raw_event_ts)
        if bool(data.get("timestamp_uncertain", False)):
            ts_uncertain = True
            ts_unc_reason = data.get("timestamp_uncertainty_reason") or ts_unc_reason

        event_time_utc = str(raw_event_ts) if raw_event_ts is not None else None
        obs_interval = data.get("observation_interval_sec")
        obs_start_utc = data.get("observation_interval_start_utc")
        obs_end_utc = data.get("observation_interval_end_utc")
        is_stale_flag = bool(data.get("is_stale", False))

        in_win: Optional[bool] = None
        if self.incident is not None and event_time_utc is not None and not ts_uncertain:
            in_win, _, _ = is_timestamp_in_incident_window(event_time_utc, self.incident)

        res = DiagnosticCheckResult(
            evidence_id=ev_id,
            step_number=self.step_counter,
            check_name=check_name,
            params=normalized_params,
            status=status,
            cost_units=attempt_cost,
            latency_ms=latency_ms,
            timestamp_utc=collection_utc,
            event_time_utc=event_time_utc,
            collection_time_utc=collection_utc,
            evaluation_time_utc=collection_utc,
            observation_interval_sec=float(obs_interval) if obs_interval is not None else None,
            observation_interval_start_utc=str(obs_start_utc) if obs_start_utc else None,
            observation_interval_end_utc=str(obs_end_utc) if obs_end_utc else None,
            freshness_ttl_sec=spec.freshness_ttl_sec,
            freshness_status="stale" if is_stale_flag else ("fresh" if status == EvidenceStatus.AVAILABLE else "not_applicable"),
            is_stale=is_stale_flag,
            timestamp_uncertain=ts_uncertain,
            timestamp_uncertainty_reason=ts_unc_reason,
            in_incident_window=in_win,
            evidence_source=spec.evidence_source,
            repeat_index=repeat_idx,
            summary=summary,
            data=data,
        )
        self._record_acquired_monotonic[ev_id] = self.now_monotonic()
        self.history.append(res)
        self.refresh_staleness_flags()

        if self.on_after_check_hook is not None:
            self.on_after_check_hook(self.step_counter, res)
            self.refresh_staleness_flags()

        return res

    def _dispatch(
        self, check_name: str, params: dict[str, Any]
    ) -> tuple[EvidenceStatus, str, dict[str, Any]]:
        if check_name == "get_recent_logs":
            service = str(params["service"])
            limit = int(params.get("limit", 20))
            entries = read_recent_logs(service=service, limit=limit)
            window_filtered = filter_log_entries_for_incident_window(entries, self.incident)

            in_win_entries = window_filtered["in_window_entries"]
            in_win_errors = window_filtered["in_window_error_entries"]
            out_win_errors = window_filtered["out_of_window_error_entries"]
            unc_errors = window_filtered["uncertain_error_entries"]

            in_win_cats = window_filtered["in_window_error_categories"]
            out_win_cats = window_filtered["out_of_window_error_categories"]
            unc_cats = window_filtered["uncertain_error_categories"]

            all_error_entries = [e for e in entries if e.get("level") == "ERROR"]
            all_cats = sorted({str(e.get("error_category")) for e in all_error_entries if e.get("error_category")})
            events = sorted({str(e.get("event")) for e in entries if e.get("event")})

            valid_ts_list = [
                str(e.get("timestamp_utc") or e.get("timestamp"))
                for e in (in_win_entries or entries)
                if e.get("timestamp_utc") or e.get("timestamp")
            ]
            earliest_ts = valid_ts_list[0] if valid_ts_list else None
            latest_ts = valid_ts_list[-1] if valid_ts_list else self.now_utc_iso()

            summary = (
                f"Retrieved {len(entries)} recent log entries for {service} "
                f"(in_window_errors={len(in_win_errors)} {in_win_cats}; "
                f"out_of_window_historical_errors={len(out_win_errors)} {out_win_cats}; "
                f"uncertain_timestamp_errors={len(unc_errors)} {unc_cats})."
            )
            return (
                EvidenceStatus.AVAILABLE,
                summary,
                {
                    "service": service,
                    "entries_count": len(entries),
                    "error_count": len(in_win_errors),
                    "total_unfiltered_error_count": len(all_error_entries),
                    "out_of_window_error_count": len(out_win_errors),
                    "uncertain_timestamp_error_count": len(unc_errors),
                    "error_categories": in_win_cats,
                    "in_window_error_categories": in_win_cats,
                    "out_of_window_error_categories": out_win_cats,
                    "uncertain_error_categories": unc_cats,
                    "all_unfiltered_error_categories": all_cats,
                    "observed_events": events,
                    "event_time_utc": latest_ts,
                    "observation_interval_start_utc": earliest_ts,
                    "observation_interval_end_utc": latest_ts,
                    "timestamp_uncertain": window_filtered["timestamp_uncertain"],
                    "timestamp_uncertainty_reason": window_filtered["timestamp_uncertainty_reason"],
                    "in_window_entries": in_win_entries[-10:],
                    "out_of_window_entries": out_win_errors[-5:],
                    "entries": entries[-10:],
                },
            )

        if check_name == "get_service_health":
            service = str(params["service"])
            if service == "gateway":
                return self._check_http_service_health("gateway", GATEWAY_URL)
            if service == "order-service":
                return self._check_http_service_health("order-service", ORDER_URL)
            if service == "database":
                return self._check_database_health(port=DB_PORT, service_label="database", dbname="nextrace_orders")
            if service == "inventory-api":
                return self._check_http_service_health("inventory-api", INV_API_URL)
            if service == "inventory-service":
                return self._check_http_service_health("inventory-service", INV_SERVICE_URL)
            if service == "inventory-db":
                return self._check_database_health(port=INV_DB_PORT, service_label="inventory-db", dbname="nextrace_inventory")
            if service == "inventory-cache":
                return self._check_cache_health(port=INV_CACHE_PORT, service_label="inventory-cache")
            return EvidenceStatus.NOT_APPLICABLE, f"Unsupported service {service}", {}

        if check_name == "get_service_metrics":
            service = str(params["service"])
            url_map = {
                "gateway": GATEWAY_URL,
                "order-service": ORDER_URL,
                "inventory-api": INV_API_URL,
                "inventory-service": INV_SERVICE_URL,
            }
            base_url = url_map.get(service)
            if not base_url:
                return EvidenceStatus.NOT_APPLICABLE, f"Unsupported metrics service {service}", {}
            return self._check_service_metrics(service, base_url)

        if check_name == "check_database_connectivity_from_order_service":
            try:
                timeout_sec = self._http_timeout(2.2, context="check_database_connectivity_from_order_service")
                resp = httpx.get(f"{ORDER_URL}/internal/diagnostics/db-connectivity", timeout=timeout_sec)
                if resp.status_code != 200:
                    return (
                        EvidenceStatus.COLLECTION_FAILED,
                        f"order-service diagnostic probe returned HTTP {resp.status_code}",
                        {"http_status": resp.status_code, "diagnostic_endpoint_failed": True},
                    )
                body = resp.json()
                probe = body.get("probe", {})
                ok = bool(probe.get("ok"))
                err_cat = probe.get("error_category")
                host = probe.get("configured_host")
                port = probe.get("configured_port")
                summary = (
                    f"Order-service DB connectivity probe: ok={ok}, "
                    f"target={host}:{port}, error_category={err_cat}, latency_ms={probe.get('latency_ms')}"
                )
                return EvidenceStatus.AVAILABLE, summary, {**probe, "event_time_utc": body.get("timestamp") or self.now_utc_iso()}
            except httpx.RequestError as exc:
                return (
                    EvidenceStatus.COLLECTION_FAILED,
                    f"Failed to contact order-service for DB connectivity probe: {type(exc).__name__}",
                    {"reason": type(exc).__name__, "order_service_unreachable": True},
                )

        if check_name == "get_order_service_database_config":
            try:
                timeout_sec = self._http_timeout(1.5, context="get_order_service_database_config")
                resp = httpx.get(f"{ORDER_URL}/internal/diagnostics/db-config", timeout=timeout_sec)
                if resp.status_code != 200:
                    return (
                        EvidenceStatus.COLLECTION_FAILED,
                        f"order-service config endpoint returned HTTP {resp.status_code}",
                        {
                            "http_status": resp.status_code,
                            "diagnostic_endpoint_failed": True,
                            "reason": "diagnostic_endpoint_http_error",
                        },
                    )
                body = resp.json()
                cfg = body.get("sanitized_config", {})
                summary = (
                    f"Order-service DB config: db_host={cfg.get('db_host')}, "
                    f"db_port={cfg.get('db_port')}, db_name={cfg.get('db_name')}, db_user={cfg.get('db_user')}"
                )
                return EvidenceStatus.AVAILABLE, summary, {**cfg, "event_time_utc": body.get("timestamp") or self.now_utc_iso()}
            except httpx.RequestError as exc:
                return (
                    EvidenceStatus.COLLECTION_FAILED,
                    f"Failed to contact order-service for DB config inspection: {type(exc).__name__}",
                    {"reason": type(exc).__name__, "order_service_unreachable": True},
                )

        # Inventory App specialized checks
        if check_name == "check_inventory_db_connectivity":
            try:
                timeout_sec = self._http_timeout(2.2, context="check_inventory_db_connectivity")
                resp = httpx.get(f"{INV_SERVICE_URL}/internal/diagnostics/db-connectivity", timeout=timeout_sec)
                if resp.status_code != 200:
                    return (
                        EvidenceStatus.COLLECTION_FAILED,
                        f"inventory-service DB probe returned HTTP {resp.status_code}",
                        {"http_status": resp.status_code},
                    )
                body = resp.json()
                probe = body.get("probe", {})
                ok = bool(probe.get("ok"))
                err_cat = probe.get("error_category")
                summary = (
                    f"Inventory-service DB probe: ok={ok}, "
                    f"target={probe.get('configured_host')}:{probe.get('configured_port')}, error_category={err_cat}"
                )
                return EvidenceStatus.AVAILABLE, summary, {**probe, "event_time_utc": body.get("timestamp") or self.now_utc_iso()}
            except httpx.RequestError as exc:
                return (
                    EvidenceStatus.COLLECTION_FAILED,
                    f"Failed to contact inventory-service for DB probe: {type(exc).__name__}",
                    {"reason": type(exc).__name__, "inventory_service_unreachable": True},
                )

        if check_name == "check_inventory_cache_connectivity":
            try:
                timeout_sec = self._http_timeout(2.0, context="check_inventory_cache_connectivity")
                resp = httpx.get(f"{INV_SERVICE_URL}/internal/diagnostics/cache-connectivity", timeout=timeout_sec)
                if resp.status_code != 200:
                    return (
                        EvidenceStatus.COLLECTION_FAILED,
                        f"inventory-service cache probe returned HTTP {resp.status_code}",
                        {"http_status": resp.status_code},
                    )
                body = resp.json()
                probe = body.get("probe", {})
                ok = bool(probe.get("ok"))
                err_cat = probe.get("error_category")
                summary = (
                    f"Inventory-service Cache probe: ok={ok}, "
                    f"target={probe.get('configured_host')}:{probe.get('configured_port')}, "
                    f"cache_mode={probe.get('cache_mode')}, error_category={err_cat}"
                )
                return EvidenceStatus.AVAILABLE, summary, {**probe, "event_time_utc": body.get("timestamp") or self.now_utc_iso()}
            except httpx.RequestError as exc:
                return (
                    EvidenceStatus.COLLECTION_FAILED,
                    f"Failed to contact inventory-service for Cache probe: {type(exc).__name__}",
                    {"reason": type(exc).__name__, "inventory_service_unreachable": True},
                )

        if check_name == "get_inventory_service_config":
            try:
                timeout_sec = self._http_timeout(1.5, context="get_inventory_service_config")
                resp = httpx.get(f"{INV_SERVICE_URL}/internal/diagnostics/db-config", timeout=timeout_sec)
                if resp.status_code != 200:
                    return (
                        EvidenceStatus.COLLECTION_FAILED,
                        f"inventory-service config endpoint returned HTTP {resp.status_code}",
                        {"http_status": resp.status_code},
                    )
                body = resp.json()
                cfg = body.get("sanitized_config", {})
                summary = (
                    f"Inventory-service config: db_host={cfg.get('db_host')}:{cfg.get('db_port')}, "
                    f"cache_host={cfg.get('cache_host')}:{cfg.get('cache_port')}, cache_mode={cfg.get('cache_mode')}"
                )
                return EvidenceStatus.AVAILABLE, summary, {**cfg, "event_time_utc": body.get("timestamp") or self.now_utc_iso()}
            except httpx.RequestError as exc:
                return (
                    EvidenceStatus.COLLECTION_FAILED,
                    f"Failed to contact inventory-service for config inspection: {type(exc).__name__}",
                    {"reason": type(exc).__name__, "inventory_service_unreachable": True},
                )

        return EvidenceStatus.INVALID_CALL, f"Unhandled check {check_name}", {}

    def _check_service_metrics(
        self, service_name: str, base_url: str
    ) -> tuple[EvidenceStatus, str, dict[str, Any]]:
        try:
            timeout_sec = self._http_timeout(1.5, context=f"get_service_metrics({service_name})")
            resp = httpx.get(f"{base_url}/internal/metrics", timeout=timeout_sec)
            if resp.status_code != 200:
                return (
                    EvidenceStatus.COLLECTION_FAILED,
                    f"{service_name} metrics endpoint returned HTTP {resp.status_code}",
                    {"service": service_name, "http_status": resp.status_code},
                )
            body = dict(resp.json())
            if self.evidence_condition == EvidenceCondition.E5:
                stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                body["last_event_time_utc"] = stale_ts
                body["event_time_utc"] = stale_ts
                body["request_count"] = min(1, int(body.get("request_count", 0)))
                body["minimum_sample_threshold"] = 2
                body["sample_sufficient"] = False
                body["is_stale"] = True
                body["stale_reason"] = "E5_METRICS_STALE: metrics snapshot is stale (600s old) and below minimum_sample_threshold (2)."
            else:
                req_cnt = int(body.get("request_count", 0))
                min_thresh = int(body.get("minimum_sample_threshold", 2))
                body["sample_sufficient"] = req_cnt >= min_thresh
                body["event_time_utc"] = body.get("last_event_time_utc") or body.get("collection_time_utc") or self.now_utc_iso()
                body["observation_interval_sec"] = body.get("collection_window_sec", 10.0)
                body["observation_interval_start_utc"] = body.get("started_at_utc")
                body["observation_interval_end_utc"] = body.get("collection_time_utc")
                body["is_stale"] = False

            summary = (
                f"{service_name} metrics: requests={body.get('request_count')}, "
                f"failures={body.get('failure_count')}, error_rate={body.get('error_rate')}, "
                f"dep_failures={body.get('dependency_failures')}, dep_timeouts={body.get('dependency_timeouts')}, "
                f"avg_ms={body.get('avg_duration_ms')}, sample_sufficient={body.get('sample_sufficient')}, "
                f"is_stale={body.get('is_stale')}"
            )
            return EvidenceStatus.AVAILABLE, summary, body
        except httpx.RequestError as exc:
            return (
                EvidenceStatus.COLLECTION_FAILED,
                f"Failed to retrieve metrics from {service_name}: {type(exc).__name__}",
                {"service": service_name, "reachable": False, "reason": type(exc).__name__},
            )

    def _check_http_service_health(
        self, service_name: str, base_url: str
    ) -> tuple[EvidenceStatus, str, dict[str, Any]]:
        live_ok = False
        ready_ok = False
        live_body: dict[str, Any] = {}
        ready_body: dict[str, Any] = {}
        unreachable_reason: Optional[str] = None

        try:
            t_live = self._http_timeout(1.0, context=f"health_live({service_name})")
            r_live = httpx.get(f"{base_url}/health/live", timeout=t_live)
            live_ok = r_live.status_code == 200
            live_body = r_live.json()
        except httpx.RequestError as exc:
            unreachable_reason = type(exc).__name__

        if live_ok:
            try:
                t_ready = self._http_timeout(1.5, context=f"health_ready({service_name})")
                r_ready = httpx.get(f"{base_url}/health/ready", timeout=t_ready)
                ready_ok = r_ready.status_code == 200
                ready_body = r_ready.json()
            except httpx.RequestError as exc:
                unreachable_reason = type(exc).__name__

        if self.evidence_policy_version == "E2_phase2_minimal_v1" and not ready_ok and ready_body.get("error_category"):
            ready_body = dict(ready_body)
            ready_body["error_category"] = "dependency_check_failed_masked_under_e2"

        summary = (
            f"Service {service_name} health: live={live_ok}, ready={ready_ok}"
            + (f", error_category={ready_body.get('error_category')}" if ready_body.get("error_category") else "")
            + (f", unreachable_reason={unreachable_reason}" if unreachable_reason else "")
        )
        return (
            EvidenceStatus.AVAILABLE,
            summary,
            {
                "service": service_name,
                "live": live_ok,
                "ready": ready_ok,
                "live_response": live_body,
                "ready_response": ready_body,
                "unreachable_reason": unreachable_reason,
                "event_time_utc": ready_body.get("timestamp") or live_body.get("timestamp") or self.now_utc_iso(),
            },
        )

    def _check_database_health(
        self,
        port: int = DB_PORT,
        service_label: str = "database",
        dbname: str = "nextrace_orders",
    ) -> tuple[EvidenceStatus, str, dict[str, Any]]:
        started = time.perf_counter()
        timeout_sec = self._http_timeout(1.5, context=f"db_health({service_label})")
        db_driver = os.environ.get("NEXTRACE_DB_DRIVER", "local_tcp").lower()

        if db_driver in ("postgresql", "postgres") or os.environ.get("NEXTRACE_RUNTIME_ACTIVE", "").lower() == "docker":
            return self._check_postgresql_database_health(
                port=port, service_label=service_label, dbname=dbname, timeout_sec=timeout_sec, started=started
            )

        connected = False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=timeout_sec) as sock:
                connected = True
                sock.settimeout(timeout_sec)
                req = {
                    "action": "ping",
                    "user": os.environ.get("DB_USER", "nextrace_user"),
                    "password": os.environ.get("DB_PASSWORD", "nextrace_local_dev_pw"),
                    "dbname": dbname,
                }
                sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
                fh = sock.makefile("r", encoding="utf-8")
                line = fh.readline()
                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                if line:
                    resp = json.loads(line)
                    ok = bool(resp.get("ok"))
                    err_cat = resp.get("error_category")
                    summary = (
                        f"Database ({service_label}) direct health check on 127.0.0.1:{port}: "
                        f"reachable=True, schema_usable={ok}, error_category={err_cat}, latency_ms={latency_ms}"
                    )
                    return (
                        EvidenceStatus.AVAILABLE,
                        summary,
                        {
                            "service": service_label,
                            "reachable": True,
                            "schema_usable": ok,
                            "error_category": err_cat,
                            "latency_ms": latency_ms,
                            "backend": "local_sqlite_tcp",
                            "host": "127.0.0.1",
                            "port": port,
                            "event_time_utc": self.now_utc_iso(),
                        },
                    )
                return (
                    EvidenceStatus.AVAILABLE,
                    f"Database ({service_label}) TCP port 127.0.0.1:{port} open.",
                    {
                        "service": service_label,
                        "reachable": True,
                        "schema_usable": True,
                        "error_category": None,
                        "latency_ms": latency_ms,
                        "backend": "local_sqlite_tcp",
                        "host": "127.0.0.1",
                        "port": port,
                        "event_time_utc": self.now_utc_iso(),
                    },
                )
        except (TimeoutError, socket.timeout) as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if not connected:
                return (
                    EvidenceStatus.AVAILABLE,
                    f"Database ({service_label}) direct health check on 127.0.0.1:{port}: reachable=False (connection_refused).",
                    {
                        "service": service_label,
                        "reachable": False,
                        "schema_usable": False,
                        "error_category": "connection_refused",
                        "latency_ms": latency_ms,
                        "backend": "local_sqlite_tcp",
                        "detail": str(exc),
                        "host": "127.0.0.1",
                        "port": port,
                        "event_time_utc": self.now_utc_iso(),
                    },
                )
            return (
                EvidenceStatus.AVAILABLE,
                f"Database ({service_label}) direct health check on 127.0.0.1:{port} timed out after {latency_ms}ms.",
                {
                    "service": service_label,
                    "reachable": True,
                    "schema_usable": False,
                    "error_category": "operation_timeout",
                    "latency_ms": latency_ms,
                    "backend": "local_sqlite_tcp",
                    "detail": str(exc),
                    "host": "127.0.0.1",
                    "port": port,
                    "event_time_utc": self.now_utc_iso(),
                },
            )
        except OSError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return (
                EvidenceStatus.AVAILABLE,
                f"Database ({service_label}) direct health check on 127.0.0.1:{port}: reachable=False (connection_refused).",
                {
                    "service": service_label,
                    "reachable": False,
                    "schema_usable": False,
                    "error_category": "connection_refused",
                    "latency_ms": latency_ms,
                    "backend": "local_sqlite_tcp",
                    "detail": str(exc),
                    "host": "127.0.0.1",
                    "port": port,
                    "event_time_utc": self.now_utc_iso(),
                },
            )

    def _check_postgresql_database_health(
        self,
        *,
        port: int,
        service_label: str,
        dbname: str,
        timeout_sec: float,
        started: float,
    ) -> tuple[EvidenceStatus, str, dict[str, Any]]:
        """Execute direct PostgreSQL protocol health check in Docker mode."""
        connected = False
        try:
            import psycopg  # type: ignore[import-not-found]

            options_parts: list[str] = []
            raw_sp = os.environ.get("DB_SEARCH_PATH") or os.environ.get("NEXTRACE_DB_SEARCH_PATH")
            delay_ms = 0
            stmt_timeout_ms = None
            if service_label == "inventory-db":
                ov_file = os.environ.get("NEXTRACE_INV_CONFIG_OVERRIDE_FILE")
                if not ov_file:
                    default_ov = Path(__file__).resolve().parent.parent / "var" / "runtime" / "inv_service_override.json"
                    if default_ov.exists():
                        ov_file = str(default_ov)
                inv_fault_ov = Path(__file__).resolve().parent.parent / "var" / "runtime" / "inv_db_fault_override.json"
            else:
                ov_file = os.environ.get("NEXTRACE_ORDER_CONFIG_OVERRIDE_FILE")
                if not ov_file:
                    default_ov = Path(__file__).resolve().parent.parent / "var" / "runtime" / "order_service_override.json"
                    if default_ov.exists():
                        ov_file = str(default_ov)
                inv_fault_ov = None

            if ov_file and Path(ov_file).exists():
                try:
                    with open(ov_file, "r", encoding="utf-8") as fh:
                        ov_data = json.load(fh)
                        if not raw_sp:
                            raw_sp = ov_data.get("db_search_path") or ov_data.get("search_path")
                        from services.order_service.db import validate_operation_delay_ms, validate_positive_timeout_ms
                        delay_ms = validate_operation_delay_ms(ov_data.get("operation_delay_ms"))
                        if "statement_timeout_ms" in ov_data:
                            stmt_timeout_ms = validate_positive_timeout_ms(ov_data["statement_timeout_ms"], default_ms=1500)
                except Exception:
                    pass

            if inv_fault_ov and inv_fault_ov.exists():
                try:
                    with open(inv_fault_ov, "r", encoding="utf-8") as fh:
                        fav_data = json.load(fh)
                        from services.order_service.db import validate_operation_delay_ms
                        f_delay = validate_operation_delay_ms(fav_data.get("operation_delay_ms"))
                        if f_delay > 0:
                            delay_ms = f_delay
                except Exception:
                    pass

            if raw_sp:
                from services.order_service.db import sanitize_search_path
                clean_sp = sanitize_search_path(str(raw_sp))
                if clean_sp:
                    options_parts.append(f"-c search_path={clean_sp}")
            if stmt_timeout_ms:
                options_parts.append(f"-c statement_timeout={int(stmt_timeout_ms)}")
            options = " ".join(options_parts) if options_parts else None

            db_user = os.environ.get("INV_DB_USER" if service_label == "inventory-db" else "DB_USER", "nextrace_user")
            db_pw = os.environ.get("INV_DB_PASSWORD" if service_label == "inventory-db" else "DB_PASSWORD", "nextrace_local_dev_pw")

            with psycopg.connect(
                host="127.0.0.1",
                port=port,
                dbname=dbname,
                user=db_user,
                password=db_pw,
                connect_timeout=max(1, int(timeout_sec)),
                options=options,
            ) as conn:
                connected = True
                with conn.cursor() as cur:
                    if delay_ms > 0:
                        cur.execute("SELECT pg_sleep(%s);", (delay_ms / 1000.0,))
                    table_name = "inventory_reservations" if service_label == "inventory-db" else "orders"
                    cur.execute(f"SELECT 1 FROM {table_name} LIMIT 1;")
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return (
                EvidenceStatus.AVAILABLE,
                f"PostgreSQL ({service_label}) direct health check on 127.0.0.1:{port}: reachable=True, schema_usable=True.",
                {
                    "service": service_label,
                    "reachable": True,
                    "schema_usable": True,
                    "error_category": None,
                    "latency_ms": latency_ms,
                    "backend": "docker_postgresql",
                    "host": "127.0.0.1",
                    "port": port,
                    "event_time_utc": self.now_utc_iso(),
                },
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            msg = str(exc).lower()
            if "does not exist" in msg or "undefinedtable" in msg:
                return (
                    EvidenceStatus.AVAILABLE,
                    f"PostgreSQL ({service_label}) missing required schema table on 127.0.0.1:{port}.",
                    {
                        "service": service_label,
                        "reachable": True,
                        "schema_usable": False,
                        "error_category": "missing_table",
                        "latency_ms": latency_ms,
                        "backend": "docker_postgresql",
                        "detail": str(exc),
                        "host": "127.0.0.1",
                        "port": port,
                        "event_time_utc": self.now_utc_iso(),
                    },
                )
            if connected and ("timeout" in msg or "timed out" in msg or "57014" in msg or "canceled" in msg):
                return (
                    EvidenceStatus.AVAILABLE,
                    f"PostgreSQL ({service_label}) direct health check on 127.0.0.1:{port} timed out after {latency_ms}ms.",
                    {
                        "service": service_label,
                        "reachable": True,
                        "schema_usable": False,
                        "error_category": "operation_timeout",
                        "latency_ms": latency_ms,
                        "backend": "docker_postgresql",
                        "detail": str(exc),
                        "host": "127.0.0.1",
                        "port": port,
                        "event_time_utc": self.now_utc_iso(),
                    },
                )
            if "timeout" in msg or "timed out" in msg:
                return (
                    EvidenceStatus.AVAILABLE,
                    f"PostgreSQL ({service_label}) timed out on 127.0.0.1:{port}.",
                    {
                        "service": service_label,
                        "reachable": False,
                        "schema_usable": False,
                        "error_category": "connection_refused",
                        "latency_ms": latency_ms,
                        "backend": "docker_postgresql",
                        "detail": str(exc),
                        "host": "127.0.0.1",
                        "port": port,
                        "event_time_utc": self.now_utc_iso(),
                    },
                )
            return (
                EvidenceStatus.AVAILABLE,
                f"PostgreSQL ({service_label}) unreachable on 127.0.0.1:{port}: {type(exc).__name__}.",
                {
                    "service": service_label,
                    "reachable": False,
                    "schema_usable": False,
                    "error_category": "connection_refused",
                    "latency_ms": latency_ms,
                    "backend": "docker_postgresql",
                    "detail": str(exc),
                    "host": "127.0.0.1",
                    "port": port,
                    "event_time_utc": self.now_utc_iso(),
                },
            )

    def _check_cache_health(
        self,
        port: int = INV_CACHE_PORT,
        service_label: str = "inventory-cache",
    ) -> tuple[EvidenceStatus, str, dict[str, Any]]:
        started = time.perf_counter()
        timeout_sec = self._http_timeout(1.2, context=f"cache_health({service_label})")
        cache_driver = os.environ.get("NEXTRACE_CACHE_DRIVER", "local_tcp").lower()
        use_redis = cache_driver == "redis" or os.environ.get("NEXTRACE_RUNTIME_ACTIVE", "").lower() == "docker"

        try:
            with socket.create_connection(("127.0.0.1", port), timeout=timeout_sec) as sock:
                sock.settimeout(timeout_sec)
                if use_redis:
                    sock.sendall(b"*1\r\n$4\r\nPING\r\n")
                    raw = sock.recv(128).decode("utf-8", errors="replace").strip()
                    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                    ok = raw.startswith("+PONG")
                    backend_name = "docker_redis"
                else:
                    sock.sendall((json.dumps({"action": "ping"}) + "\n").encode("utf-8"))
                    fh = sock.makefile("r", encoding="utf-8")
                    line = fh.readline()
                    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                    resp = json.loads(line) if line else {"ok": True}
                    ok = bool(resp.get("ok"))
                    backend_name = str(resp.get("backend", "local_tcp_cache_substitute"))

                summary = (
                    f"Cache ({service_label}) direct health check on 127.0.0.1:{port}: "
                    f"reachable={ok}, backend={backend_name}, latency_ms={latency_ms}"
                )
                return (
                    EvidenceStatus.AVAILABLE,
                    summary,
                    {
                        "service": service_label,
                        "reachable": ok,
                        "backend": backend_name,
                        "latency_ms": latency_ms,
                        "host": "127.0.0.1",
                        "port": port,
                        "event_time_utc": self.now_utc_iso(),
                    },
                )
        except OSError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return (
                EvidenceStatus.AVAILABLE,
                f"Cache ({service_label}) direct health check on 127.0.0.1:{port}: reachable=False (cache_connection_refused).",
                {
                    "service": service_label,
                    "reachable": False,
                    "backend": "docker_redis" if use_redis else "local_tcp_cache_substitute",
                    "error_category": "cache_connection_refused",
                    "latency_ms": latency_ms,
                    "detail": str(exc),
                    "host": "127.0.0.1",
                    "port": port,
                    "event_time_utc": self.now_utc_iso(),
                },
            )
