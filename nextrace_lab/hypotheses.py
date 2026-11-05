"""Hypothesis Catalog, Temporally Valid Hypothesis Updater, and Conflict Detector (v0.4.0 — Stages 1, 2, 4 & 8).

Maintains explicit candidate explanations for both `orders_app` and `inventory_app`:
- Recomputes hypothesis support when evidence expires (`is_stale`) or is superseded (`is_superseded`).
- Filters log evidence strictly to `in_window_error_categories` aligned with the incident window.
- Rejects/flags observations with missing or uncertain timestamps (`timestamp_uncertain=True`).
- Detects within-run changes, stale-vs-fresh overrides, historical-vs-live conflicts, and simultaneous source disagreements.
- Supports general unknown-cause inference (without relying on scenario-specific string markers) and general
  multi-fault combinations across both applications (`multi_fault_a_and_b`, `multi_fault_c_and_d`,
  `multi_fault_f_masks_b`, `inv_multi_fault_db_and_cache`).
"""

from __future__ import annotations

from typing import Any, Optional

from nextrace_lab.schemas import (
    ConflictRecord,
    DiagnosticCheckResult,
    EvidenceStatus,
    HypothesisStance,
    HypothesisState,
    IncidentContext,
)
from nextrace_lab.temporal import is_valid_for_current_state

MODELED_ORDERS_ERROR_CATEGORIES: frozenset[str] = frozenset(
    {
        "hostname_resolution_failed",
        "connection_refused",
        "authentication_failed",
        "missing_table",
        "operation_timeout",
        "upstream_order_service_unreachable",
        "upstream_order_service_error",
        "upstream_order_service_timeout",
        "dependency_check_failed_masked_under_e2",
    }
)

MODELED_INVENTORY_ERROR_CATEGORIES: frozenset[str] = frozenset(
    {
        "connection_refused",
        "cache_connection_refused",
        "cache_timeout",
        "hostname_resolution_failed",
        "operation_timeout",
        "upstream_inventory_service_unreachable",
        "upstream_inventory_service_error",
        "upstream_inventory_service_timeout",
    }
)


def build_initial_hypotheses(incident: IncidentContext) -> list[HypothesisState]:
    """Initialize candidate hypothesis set from the observed incident symptom and application ID."""
    if incident.app_id == "inventory_app":
        return [
            HypothesisState(
                hypothesis_id="IH0_NO_FAULT_HEALTHY",
                candidate_service=None,
                candidate_fault_type=None,
                description="All inventory_app services, database, and cache are healthy.",
                stance=HypothesisStance.PLAUSIBLE if incident.http_status < 400 else HypothesisStance.WEAKENED,
                confidence_level="medium" if incident.http_status < 400 else "low",
            ),
            HypothesisState(
                hypothesis_id="IH1_INV_DB_UNAVAILABLE",
                candidate_service="inventory-db",
                candidate_fault_type="db_service_unavailable",
                description="inventory-db service is stopped or unreachable.",
                stance=HypothesisStance.PLAUSIBLE,
                confidence_level="low",
            ),
            HypothesisState(
                hypothesis_id="IH2_INV_CACHE_UNAVAILABLE",
                candidate_service="inventory-cache",
                candidate_fault_type="cache_service_unavailable",
                description="inventory-cache service is stopped or unreachable.",
                stance=HypothesisStance.PLAUSIBLE,
                confidence_level="low",
            ),
            HypothesisState(
                hypothesis_id="IH3_INV_DB_CONFIG_ENDPOINT",
                candidate_service="inventory-service",
                candidate_fault_type="db_endpoint_misconfiguration",
                description="inventory-service is configured with an invalid/unresolvable database hostname.",
                stance=HypothesisStance.PLAUSIBLE,
                confidence_level="low",
            ),
            HypothesisState(
                hypothesis_id="IH4_INV_DB_OPERATION_DELAY",
                candidate_service="inventory-db",
                candidate_fault_type="db_operation_delay",
                description="inventory-db operations experience high latency exceeding inventory-service timeout.",
                stance=HypothesisStance.PLAUSIBLE,
                confidence_level="low",
            ),
        ]

    is_healthy_incident = incident.http_status in (200, 201)
    return [
        HypothesisState(
            hypothesis_id="H0_NO_FAULT_HEALTHY",
            candidate_service=None,
            candidate_fault_type=None,
            description="No active service fault; gateway, order-service, and database are healthy.",
            stance=HypothesisStance.PLAUSIBLE if is_healthy_incident else HypothesisStance.WEAKENED,
            confidence_level="medium" if is_healthy_incident else "low",
        ),
        HypothesisState(
            hypothesis_id="H1_ORDER_DB_CONFIG_ENDPOINT",
            candidate_service="order-service",
            candidate_fault_type="db_endpoint_misconfiguration",
            description="order-service is configured with an invalid or unresolvable database hostname.",
            stance=HypothesisStance.PLAUSIBLE,
            confidence_level="low",
        ),
        HypothesisState(
            hypothesis_id="H2_DATABASE_UNAVAILABLE",
            candidate_service="database",
            candidate_fault_type="db_service_unavailable",
            description="The database process/container is stopped or unreachable on its listening port.",
            stance=HypothesisStance.PLAUSIBLE,
            confidence_level="low",
        ),
        HypothesisState(
            hypothesis_id="H3_ORDER_DB_AUTH_FAILURE",
            candidate_service="order-service",
            candidate_fault_type="db_auth_failure",
            description="order-service is configured with invalid database credentials rejected by authentication.",
            stance=HypothesisStance.PLAUSIBLE,
            confidence_level="low",
        ),
        HypothesisState(
            hypothesis_id="H4_DATABASE_SCHEMA_MISSING",
            candidate_service="database",
            candidate_fault_type="db_schema_missing_table",
            description="The database is reachable, but the active schema is missing the required 'orders' table.",
            stance=HypothesisStance.PLAUSIBLE,
            confidence_level="low",
        ),
        HypothesisState(
            hypothesis_id="H5_DATABASE_OPERATION_DELAY",
            candidate_service="database",
            candidate_fault_type="db_operation_delay",
            description="Database queries experience high latency exceeding order-service's operation deadline.",
            stance=HypothesisStance.PLAUSIBLE,
            confidence_level="low",
        ),
        HypothesisState(
            hypothesis_id="H6_ORDER_SERVICE_UNAVAILABLE",
            candidate_service="order-service",
            candidate_fault_type="order_service_unavailable",
            description="The order-service process/container is stopped or unreachable from the gateway.",
            stance=HypothesisStance.PLAUSIBLE,
            confidence_level="low",
        ),
    ]


def _support(h: HypothesisState, ev_id: str, confidence: str = "medium") -> None:
    if ev_id not in h.supporting_evidence_ids:
        h.supporting_evidence_ids.append(ev_id)
    if h.stance != HypothesisStance.REFUTED:
        h.stance = HypothesisStance.SUPPORTED
        if confidence == "high" or h.confidence_level == "low":
            h.confidence_level = confidence  # type: ignore[assignment]


def _force_support_live_override(h: HypothesisState, ev_id: str, confidence: str = "high") -> None:
    if ev_id not in h.supporting_evidence_ids:
        h.supporting_evidence_ids.append(ev_id)
    h.stance = HypothesisStance.SUPPORTED
    h.confidence_level = confidence  # type: ignore[assignment]


def _weaken(h: HypothesisState, ev_id: str) -> None:
    if h.stance == HypothesisStance.PLAUSIBLE:
        h.stance = HypothesisStance.WEAKENED
        h.confidence_level = "low"


def _refute(h: HypothesisState, ev_id: str) -> None:
    if ev_id not in h.refuting_evidence_ids:
        h.refuting_evidence_ids.append(ev_id)
    h.stance = HypothesisStance.REFUTED
    h.confidence_level = "low"


def _extract_in_window_log_categories(rec: DiagnosticCheckResult) -> set[str]:
    """Return only temporally valid in-window error categories from a log check."""
    if rec.timestamp_uncertain:
        return set()
    if "in_window_error_categories" in rec.data:
        return set(rec.data.get("in_window_error_categories") or [])
    if rec.in_incident_window is False:
        return set()
    return set(rec.data.get("error_categories") or [])


def _has_unmodeled_error_category(cats: set[str], app_id: str = "orders_app") -> bool:
    if not cats:
        return False
    modeled = MODELED_INVENTORY_ERROR_CATEGORIES if app_id == "inventory_app" else MODELED_ORDERS_ERROR_CATEGORIES
    return bool(cats - modeled)


def detect_conflicts(
    history: list[DiagnosticCheckResult],
    existing_conflicts: list[ConflictRecord],
) -> list[ConflictRecord]:
    """Inspect evidence history and return updated list of ConflictRecords (Stage 1 & 4)."""
    conflicts = list(existing_conflicts)
    seen_keys: set[str] = {
        f"{c.conflict_type}:{c.earlier_evidence_id}:{c.later_evidence_id}" for c in conflicts
    }

    if len(history) < 2:
        return conflicts

    latest = history[-1]
    if latest.status != EvidenceStatus.AVAILABLE:
        return conflicts

    # 1. Within-run repeat observation change (or stale-vs-fresh override)
    same_check_earlier = [
        earlier for earlier in history[:-1]
        if earlier.check_name == latest.check_name
        and earlier.params == latest.params
        and earlier.status == EvidenceStatus.AVAILABLE
    ]
    if same_check_earlier:
        for earlier in same_check_earlier:
            earlier_ok = (
                earlier.data.get("ready")
                if "ready" in earlier.data
                else (earlier.data.get("reachable") if "reachable" in earlier.data else earlier.data.get("ok"))
            )
            latest_ok = (
                latest.data.get("ready")
                if "ready" in latest.data
                else (latest.data.get("reachable") if "reachable" in latest.data else latest.data.get("ok"))
            )
            if earlier_ok is not None and latest_ok is not None and bool(earlier_ok) != bool(latest_ok):
                ctype = "stale_vs_fresh_override" if earlier.is_stale else "within_run_repeat_change"
                ckey = f"{ctype}:{earlier.evidence_id}:{latest.evidence_id}"
                if ckey not in seen_keys:
                    seen_keys.add(ckey)
                    conflicts.append(
                        ConflictRecord(
                            conflict_id=f"conf-{len(conflicts) + 1:02d}",
                            conflict_type=ctype,  # type: ignore[arg-type]
                            summary=(
                                f"Check {latest.check_name}({latest.params}) changed state during investigation: "
                                f"{earlier.evidence_id} (stale={earlier.is_stale}) had ok/ready={earlier_ok}, "
                                f"whereas fresh {latest.evidence_id} has ok/ready={latest_ok}."
                            ),
                            earlier_evidence_id=earlier.evidence_id,
                            later_evidence_id=latest.evidence_id,
                            detected_at_step=latest.step_number,
                            requires_reverification=False,
                            resolved_by_evidence_id=latest.evidence_id,
                        )
                    )

    # 2. Historical log failure vs currently healthy live probes
    log_failures: list[DiagnosticCheckResult] = []
    live_healthy_probes: list[DiagnosticCheckResult] = []
    for rec in history:
        if rec.status != EvidenceStatus.AVAILABLE:
            continue
        if rec.check_name == "get_recent_logs":
            total_errs = int(rec.data.get("total_unfiltered_error_count", rec.data.get("error_count", 0)))
            if total_errs > 0:
                log_failures.append(rec)
        elif not rec.is_stale and not rec.is_superseded:
            if rec.check_name in ("check_database_connectivity_from_order_service", "check_inventory_db_connectivity") and bool(rec.data.get("ok")):
                live_healthy_probes.append(rec)
            elif rec.check_name == "get_service_health" and rec.params.get("service") in ("order-service", "inventory-service"):
                if bool(rec.data.get("live")) and bool(rec.data.get("ready")):
                    live_healthy_probes.append(rec)

    if log_failures and live_healthy_probes:
        first_log = log_failures[0]
        latest_probe = live_healthy_probes[-1]
        in_win_cats = _extract_in_window_log_categories(first_log)
        out_win_cats = set(first_log.data.get("out_of_window_error_categories") or [])
        all_cats = in_win_cats | out_win_cats | set(first_log.data.get("error_categories") or [])
        # Only flag historical_vs_live_probe when the log error is a modeled dependency error
        if not _has_unmodeled_error_category(in_win_cats) and (all_cats & (MODELED_ORDERS_ERROR_CATEGORIES | MODELED_INVENTORY_ERROR_CATEGORIES)):
            ckey = f"historical_vs_live_probe:{first_log.evidence_id}:{latest_probe.evidence_id}"
            if ckey not in seen_keys:
                seen_keys.add(ckey)
                conflicts.append(
                    ConflictRecord(
                        conflict_id=f"conf-{len(conflicts) + 1:02d}",
                        conflict_type="historical_vs_live_probe",
                        summary=(
                            f"Log check ({first_log.evidence_id}, in_window={sorted(in_win_cats)}, "
                            f"out_of_window={sorted(out_win_cats)}) indicates past errors, but live probe "
                            f"({latest_probe.evidence_id}) shows dependencies are currently healthy."
                        ),
                        earlier_evidence_id=first_log.evidence_id,
                        later_evidence_id=latest_probe.evidence_id,
                        detected_at_step=latest.step_number,
                        requires_reverification=len(live_healthy_probes) < 2,
                        resolved_by_evidence_id=latest_probe.evidence_id if len(live_healthy_probes) >= 2 else None,
                    )
                )

    # 3. Simultaneous source disagreement within the same fresh interval
    # Example: direct DB health says reachable=True, schema_usable=True, while fresh order-service probe/health
    # against 127.0.0.1 says connection_refused (not hostname_resolution_failed or authentication_failed)!
    fresh_valid = [r for r in history if is_valid_for_current_state(r)]
    db_health_rec: Optional[DiagnosticCheckResult] = None
    caller_conn_refused_rec: Optional[DiagnosticCheckResult] = None
    config_invalid_host = False

    for r in fresh_valid:
        if r.check_name == "get_order_service_database_config":
            host = str(r.data.get("db_host", ""))
            if host and host not in ("127.0.0.1", "localhost", "postgres"):
                config_invalid_host = True
        elif r.check_name == "get_service_health" and r.params.get("service") == "database":
            db_health_rec = r
        elif r.check_name == "check_database_connectivity_from_order_service":
            if not bool(r.data.get("ok")) and r.data.get("error_category") == "connection_refused":
                cfg_h = str(r.data.get("configured_host") or "127.0.0.1")
                if cfg_h in ("127.0.0.1", "localhost", "postgres"):
                    caller_conn_refused_rec = r
        elif r.check_name == "get_service_health" and r.params.get("service") == "order-service":
            if not bool(r.data.get("ready")) and r.data.get("ready_response", {}).get("error_category") == "connection_refused":
                caller_conn_refused_rec = r

    if db_health_rec is not None and caller_conn_refused_rec is not None and not config_invalid_host:
        db_ok = bool(db_health_rec.data.get("reachable")) and bool(db_health_rec.data.get("schema_usable", True))
        if db_ok:
            # Check if a repeat execution of whichever was earlier has already resolved it
            earlier_r = db_health_rec if db_health_rec.step_number < caller_conn_refused_rec.step_number else caller_conn_refused_rec
            later_r = caller_conn_refused_rec if earlier_r is db_health_rec else db_health_rec
            ckey = f"simultaneous_source_disagreement:{earlier_r.evidence_id}:{later_r.evidence_id}"
            if ckey not in seen_keys:
                seen_keys.add(ckey)
                conflicts.append(
                    ConflictRecord(
                        conflict_id=f"conf-{len(conflicts) + 1:02d}",
                        conflict_type="simultaneous_source_disagreement",
                        summary=(
                            f"Simultaneous fresh sources disagree on database reachability: "
                            f"{db_health_rec.evidence_id} reports database reachable=True, whereas "
                            f"{caller_conn_refused_rec.evidence_id} reports connection_refused."
                        ),
                        earlier_evidence_id=earlier_r.evidence_id,
                        later_evidence_id=later_r.evidence_id,
                        detected_at_step=latest.step_number,
                        requires_reverification=True,
                        resolved_by_evidence_id=None,
                    )
                )

    return conflicts


def recompute_hypotheses_from_history(
    incident: IncidentContext,
    hypotheses: list[HypothesisState],
    history: list[DiagnosticCheckResult],
) -> dict[str, str]:
    """Recompute hypothesis stances from scratch over `history` so expired or superseded evidence loses support.

    Preserves audit trails (`expired_or_superseded_evidence_ids` and `missing_evidence_notes`) while ensuring
    no hypothesis retains active support from stale, superseded, or timestamp-uncertain observations.
    """
    before_stances = {h.hypothesis_id: h.stance.value for h in hypotheses}
    fresh_hyps = build_initial_hypotheses(incident)
    fresh_by_id = {h.hypothesis_id: h for h in fresh_hyps}

    # Carry over prior audit notes of expired/superseded IDs
    prior_expired: dict[str, list[str]] = {
        h.hypothesis_id: list(h.expired_or_superseded_evidence_ids) for h in hypotheses
    }

    for rec in history:
        # If an observation is stale, superseded, or timestamp-uncertain, do NOT let it grant active support/refutation
        if rec.status == EvidenceStatus.AVAILABLE and (rec.is_stale or rec.is_superseded or rec.timestamp_uncertain):
            for h in fresh_hyps:
                tag = (
                    f"{rec.evidence_id}(stale)"
                    if rec.is_stale
                    else (
                        f"{rec.evidence_id}(superseded_by={rec.superseded_by_evidence_id})"
                        if rec.is_superseded
                        else f"{rec.evidence_id}(timestamp_uncertain={rec.timestamp_uncertainty_reason})"
                    )
                )
                if rec.evidence_id in ( next(( ph.supporting_evidence_ids + ph.refuting_evidence_ids for ph in hypotheses if ph.hypothesis_id == h.hypothesis_id), []) ):
                    if tag not in h.expired_or_superseded_evidence_ids:
                        h.expired_or_superseded_evidence_ids.append(tag)
                if rec.timestamp_uncertain:
                    note = f"{rec.evidence_id}: timestamp uncertain ({rec.timestamp_uncertainty_reason}); excluded from active attribution"
                    if note not in h.missing_evidence_notes:
                        h.missing_evidence_notes.append(note)
            continue

        _apply_single_valid_observation(fresh_by_id, fresh_hyps, rec, incident=incident)

    # Copy recomputed state back into the caller's `hypotheses` list in-place
    for h_orig in hypotheses:
        h_new = fresh_by_id[h_orig.hypothesis_id]
        for exp_id in prior_expired.get(h_orig.hypothesis_id, []):
            if exp_id not in h_new.expired_or_superseded_evidence_ids:
                h_new.expired_or_superseded_evidence_ids.append(exp_id)
        h_orig.stance = h_new.stance
        h_orig.confidence_level = h_new.confidence_level
        h_orig.supporting_evidence_ids = h_new.supporting_evidence_ids
        h_orig.refuting_evidence_ids = h_new.refuting_evidence_ids
        h_orig.expired_or_superseded_evidence_ids = h_new.expired_or_superseded_evidence_ids
        h_orig.missing_evidence_notes = h_new.missing_evidence_notes

    return _diff_stances(before_stances, hypotheses)


def update_hypotheses_with_evidence(
    hypotheses: list[HypothesisState],
    result: DiagnosticCheckResult,
    *,
    history: Optional[list[DiagnosticCheckResult]] = None,
    incident: Optional[IncidentContext] = None,
) -> dict[str, str]:
    """Update hypothesis stances based on a newly executed diagnostic check result (or full history if provided)."""
    if history is not None and incident is not None:
        return recompute_hypotheses_from_history(incident, hypotheses, history)

    before_stances = {h.hypothesis_id: h.stance.value for h in hypotheses}
    by_id = {h.hypothesis_id: h for h in hypotheses}

    if result.status == EvidenceStatus.AVAILABLE and (result.is_stale or result.is_superseded or result.timestamp_uncertain):
        for h in hypotheses:
            if result.timestamp_uncertain:
                note = f"{result.evidence_id}: timestamp uncertain ({result.timestamp_uncertainty_reason})"
                if note not in h.missing_evidence_notes:
                    h.missing_evidence_notes.append(note)
        return _diff_stances(before_stances, hypotheses)

    _apply_single_valid_observation(by_id, hypotheses, result, incident=incident)
    return _diff_stances(before_stances, hypotheses)


def _apply_single_valid_observation(
    by_id: dict[str, HypothesisState],
    hypotheses: list[HypothesisState],
    result: DiagnosticCheckResult,
    *,
    incident: Optional[IncidentContext] = None,
) -> None:
    ev_id = result.evidence_id
    cname = result.check_name
    params = result.params
    data = result.data

    if result.status in (EvidenceStatus.UNAVAILABLE_BY_POLICY, EvidenceStatus.COLLECTION_FAILED, EvidenceStatus.INVALID_CALL):
        for h in hypotheses:
            if cname in (
                "get_recent_logs",
                "check_database_connectivity_from_order_service",
                "get_order_service_database_config",
                "get_service_metrics",
                "check_inventory_db_connectivity",
                "check_inventory_cache_connectivity",
                "get_inventory_service_config",
            ):
                note = f"{ev_id}: {cname}({params}) was {result.status.value}"
                if note not in h.missing_evidence_notes:
                    h.missing_evidence_notes.append(note)

        if result.status == EvidenceStatus.COLLECTION_FAILED and data.get("order_service_unreachable") and "H6_ORDER_SERVICE_UNAVAILABLE" in by_id:
            _support(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id, confidence="medium")
            if "H0_NO_FAULT_HEALTHY" in by_id:
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
        return

    if "IH0_NO_FAULT_HEALTHY" in by_id:
        _update_inventory_hypotheses_single(by_id, hypotheses, result)
        return

    # ---------------- orders_app updates ----------------
    if cname == "get_service_health":
        svc = params.get("service")
        if svc == "gateway":
            live = bool(data.get("live"))
            ready = bool(data.get("ready"))
            ready_resp = data.get("ready_response", {})
            if live and not ready and ready_resp.get("upstream_order_service") == "unreachable":
                _support(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id, confidence="high")
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
                for hid in (
                    "H1_ORDER_DB_CONFIG_ENDPOINT",
                    "H2_DATABASE_UNAVAILABLE",
                    "H3_ORDER_DB_AUTH_FAILURE",
                    "H4_DATABASE_SCHEMA_MISSING",
                    "H5_DATABASE_OPERATION_DELAY",
                ):
                    _weaken(by_id[hid], ev_id)
            elif live and ready:
                _refute(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id)

        elif svc == "order-service":
            live = bool(data.get("live"))
            ready = bool(data.get("ready"))
            ready_resp = data.get("ready_response", {})
            err_cat = ready_resp.get("error_category")
            if not live:
                _support(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id, confidence="high")
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
                # Note: when order-service is stopped (H6), caller-side DB checks cannot run through order-service,
                # so weaken H1..H5 rather than hard-refuting H2/H4/H5 (which may co-exist as masked/parallel DB faults!).
                for hid in (
                    "H1_ORDER_DB_CONFIG_ENDPOINT",
                    "H2_DATABASE_UNAVAILABLE",
                    "H3_ORDER_DB_AUTH_FAILURE",
                    "H4_DATABASE_SCHEMA_MISSING",
                    "H5_DATABASE_OPERATION_DELAY",
                ):
                    _weaken(by_id[hid], ev_id)
            else:
                _refute(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id)
                if ready:
                    _force_support_live_override(by_id["H0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")
                    for hid in (
                        "H1_ORDER_DB_CONFIG_ENDPOINT",
                        "H2_DATABASE_UNAVAILABLE",
                        "H3_ORDER_DB_AUTH_FAILURE",
                        "H4_DATABASE_SCHEMA_MISSING",
                        "H5_DATABASE_OPERATION_DELAY",
                    ):
                        if by_id[hid].supporting_evidence_ids:
                            by_id[hid].stance = HypothesisStance.WEAKENED
                        else:
                            _refute(by_id[hid], ev_id)
                else:
                    _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
                    if err_cat == "dependency_check_failed_masked_under_e2":
                        for hid in (
                            "H1_ORDER_DB_CONFIG_ENDPOINT",
                            "H2_DATABASE_UNAVAILABLE",
                            "H3_ORDER_DB_AUTH_FAILURE",
                            "H4_DATABASE_SCHEMA_MISSING",
                            "H5_DATABASE_OPERATION_DELAY",
                        ):
                            if by_id[hid].stance == HypothesisStance.WEAKENED:
                                by_id[hid].stance = HypothesisStance.PLAUSIBLE
                    else:
                        _apply_db_error_category(by_id, err_cat, ev_id, confidence="medium")

        elif svc == "database":
            reachable = bool(data.get("reachable"))
            schema_usable = bool(data.get("schema_usable"))
            err_cat = data.get("error_category")
            if not reachable:
                _force_support_live_override(by_id["H2_DATABASE_UNAVAILABLE"], ev_id, confidence="high")
                for hid in ("H0_NO_FAULT_HEALTHY", "H4_DATABASE_SCHEMA_MISSING", "H5_DATABASE_OPERATION_DELAY"):
                    _refute(by_id[hid], ev_id)
                # Caller-side faults (H1, H3) or order-service liveness (H6) can co-occur in multi-fault scenarios;
                # only weaken them if they are not already supported.
                for hid in ("H1_ORDER_DB_CONFIG_ENDPOINT", "H3_ORDER_DB_AUTH_FAILURE"):
                    _weaken(by_id[hid], ev_id)
            else:
                _refute(by_id["H2_DATABASE_UNAVAILABLE"], ev_id)
                if not schema_usable and err_cat == "missing_table":
                    _force_support_live_override(by_id["H4_DATABASE_SCHEMA_MISSING"], ev_id, confidence="high")
                    for hid in ("H0_NO_FAULT_HEALTHY", "H5_DATABASE_OPERATION_DELAY"):
                        _refute(by_id[hid], ev_id)
                    # Do NOT hard-refute H1 or H3 if caller-side config/auth fault co-occurs (e.g. multi_fault_c_and_d)!
                    for hid in ("H1_ORDER_DB_CONFIG_ENDPOINT", "H3_ORDER_DB_AUTH_FAILURE"):
                        _weaken(by_id[hid], ev_id)
                elif err_cat == "operation_timeout":
                    _force_support_live_override(by_id["H5_DATABASE_OPERATION_DELAY"], ev_id, confidence="high")
                    for hid in ("H0_NO_FAULT_HEALTHY", "H4_DATABASE_SCHEMA_MISSING"):
                        _refute(by_id[hid], ev_id)
                    for hid in ("H1_ORDER_DB_CONFIG_ENDPOINT", "H3_ORDER_DB_AUTH_FAILURE"):
                        _weaken(by_id[hid], ev_id)
                elif schema_usable and err_cat is None:
                    _refute(by_id["H4_DATABASE_SCHEMA_MISSING"], ev_id)
                    _refute(by_id["H5_DATABASE_OPERATION_DELAY"], ev_id)
                    _support(by_id["H0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")

    elif cname == "get_service_metrics":
        if result.is_stale or not bool(data.get("sample_sufficient", False)):
            note = f"{ev_id}: metrics for {params.get('service')} stale or below sample threshold (requests={data.get('request_count')})"
            for h in hypotheses:
                if note not in h.missing_evidence_notes:
                    h.missing_evidence_notes.append(note)
        else:
            dep_timeouts = int(data.get("dependency_timeouts", 0))
            dep_failures = int(data.get("dependency_failures", 0))
            avg_ms = float(data.get("avg_duration_ms", 0.0))
            if dep_timeouts > 0 or avg_ms >= 900.0:
                _support(by_id["H5_DATABASE_OPERATION_DELAY"], ev_id, confidence="medium")
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
            elif dep_failures > 0:
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
                _weaken(by_id["H5_DATABASE_OPERATION_DELAY"], ev_id)

    elif cname == "check_database_connectivity_from_order_service":
        ok = bool(data.get("ok"))
        err_cat = data.get("error_category")
        _refute(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id)
        if ok:
            _force_support_live_override(by_id["H0_NO_FAULT_HEALTHY"], ev_id, confidence="high")
            for hid in (
                "H1_ORDER_DB_CONFIG_ENDPOINT",
                "H2_DATABASE_UNAVAILABLE",
                "H3_ORDER_DB_AUTH_FAILURE",
                "H4_DATABASE_SCHEMA_MISSING",
                "H5_DATABASE_OPERATION_DELAY",
            ):
                if by_id[hid].supporting_evidence_ids:
                    by_id[hid].stance = HypothesisStance.WEAKENED
                else:
                    _refute(by_id[hid], ev_id)
        else:
            _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
            _apply_db_error_category(by_id, err_cat, ev_id, confidence="high")

    elif cname == "get_order_service_database_config":
        _refute(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id)
        db_host = str(data.get("db_host", ""))
        if db_host and db_host not in ("127.0.0.1", "localhost", "postgres"):
            _force_support_live_override(by_id["H1_ORDER_DB_CONFIG_ENDPOINT"], ev_id, confidence="high")
            _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
            _refute(by_id["H3_ORDER_DB_AUTH_FAILURE"], ev_id)
            for hid in ("H4_DATABASE_SCHEMA_MISSING", "H5_DATABASE_OPERATION_DELAY"):
                _weaken(by_id[hid], ev_id)
        else:
            _refute(by_id["H1_ORDER_DB_CONFIG_ENDPOINT"], ev_id)

    elif cname == "get_recent_logs":
        svc = params.get("service")
        in_win_cats = _extract_in_window_log_categories(result)
        out_win_cats = set(data.get("out_of_window_error_categories") or [])
        if out_win_cats and not in_win_cats:
            note = f"{ev_id}: ignored out-of-window historical log categories {sorted(out_win_cats)}"
            for h in hypotheses:
                if note not in h.missing_evidence_notes:
                    h.missing_evidence_notes.append(note)
            return

        if svc == "gateway":
            if "upstream_order_service_unreachable" in in_win_cats:
                _support(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id, confidence="medium")
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
            elif "upstream_order_service_error" in in_win_cats or "upstream_order_service_timeout" in in_win_cats:
                _refute(by_id["H6_ORDER_SERVICE_UNAVAILABLE"], ev_id)
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
        elif svc == "order-service":
            if _has_unmodeled_error_category(in_win_cats, app_id="orders_app"):
                _refute(by_id["H0_NO_FAULT_HEALTHY"], ev_id)
                for hid in (
                    "H1_ORDER_DB_CONFIG_ENDPOINT",
                    "H2_DATABASE_UNAVAILABLE",
                    "H3_ORDER_DB_AUTH_FAILURE",
                    "H4_DATABASE_SCHEMA_MISSING",
                    "H5_DATABASE_OPERATION_DELAY",
                    "H6_ORDER_SERVICE_UNAVAILABLE",
                ):
                    _weaken(by_id[hid], ev_id)
            else:
                for cat in in_win_cats:
                    _apply_db_error_category(by_id, cat, ev_id, confidence="medium", is_log_evidence=True)


def _apply_db_error_category(
    by_id: dict[str, HypothesisState],
    err_cat: Any,
    ev_id: str,
    confidence: str = "medium",
    is_log_evidence: bool = False,
) -> None:
    if not err_cat:
        return
    mapping = {
        "hostname_resolution_failed": "H1_ORDER_DB_CONFIG_ENDPOINT",
        "connection_refused": "H2_DATABASE_UNAVAILABLE",
        "authentication_failed": "H3_ORDER_DB_AUTH_FAILURE",
        "missing_table": "H4_DATABASE_SCHEMA_MISSING",
        "operation_timeout": "H5_DATABASE_OPERATION_DELAY",
    }
    target_hid = mapping.get(str(err_cat))
    if not target_hid:
        return

    if is_log_evidence:
        _support(by_id[target_hid], ev_id, confidence=confidence)
    else:
        _force_support_live_override(by_id[target_hid], ev_id, confidence=confidence)

    # Caller-side faults (H1, H3) can co-occur with database-side faults (H2, H4, H5) in multi-fault scenarios.
    # For example, H1 + H2 (`multi_fault_a_and_b`) or H3 + H4 (`multi_fault_c_and_d`).
    caller_faults = {"H1_ORDER_DB_CONFIG_ENDPOINT", "H3_ORDER_DB_AUTH_FAILURE"}
    db_faults = {"H2_DATABASE_UNAVAILABLE", "H4_DATABASE_SCHEMA_MISSING", "H5_DATABASE_OPERATION_DELAY"}

    for other_hid in mapping.values():
        if other_hid == target_hid:
            continue
        if target_hid in caller_faults and other_hid in db_faults:
            # Caller failed before reaching DB query/port -> DB state itself has not been directly tested yet!
            _weaken(by_id[other_hid], ev_id)
        elif is_log_evidence:
            _weaken(by_id[other_hid], ev_id)
        else:
            _refute(by_id[other_hid], ev_id)


def _update_inventory_hypotheses_single(
    by_id: dict[str, HypothesisState],
    hypotheses: list[HypothesisState],
    result: DiagnosticCheckResult,
) -> None:
    ev_id = result.evidence_id
    cname = result.check_name
    params = result.params
    data = result.data

    if cname == "get_service_health":
        svc = params.get("service")
        if svc == "inventory-service":
            ready = bool(data.get("ready"))
            ready_resp = data.get("ready_response", {})
            err_cat = ready_resp.get("error_category")
            if ready:
                _force_support_live_override(by_id["IH0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")
                for hid in ("IH1_INV_DB_UNAVAILABLE", "IH2_INV_CACHE_UNAVAILABLE", "IH3_INV_DB_CONFIG_ENDPOINT", "IH4_INV_DB_OPERATION_DELAY"):
                    _refute(by_id[hid], ev_id)
            else:
                _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)
                _apply_inv_error_category(by_id, err_cat, ev_id, confidence="medium")
                # Check if readiness response explicitly reports both database_connectivity and cache_connectivity failed
                if ready_resp.get("database_connectivity") == "failed" and ready_resp.get("cache_connectivity") == "failed":
                    _force_support_live_override(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id, confidence="medium")
        elif svc == "inventory-db":
            reachable = bool(data.get("reachable"))
            err_cat = data.get("error_category")
            if not reachable:
                _force_support_live_override(by_id["IH1_INV_DB_UNAVAILABLE"], ev_id, confidence="high")
                for hid in ("IH0_NO_FAULT_HEALTHY", "IH3_INV_DB_CONFIG_ENDPOINT", "IH4_INV_DB_OPERATION_DELAY"):
                    _refute(by_id[hid], ev_id)
                # Note: Do NOT hard-refute IH2_INV_CACHE_UNAVAILABLE because cache can also be down in inv_multi_fault_db_and_cache!
                _weaken(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id)
            else:
                _refute(by_id["IH1_INV_DB_UNAVAILABLE"], ev_id)
                if err_cat == "operation_timeout":
                    _force_support_live_override(by_id["IH4_INV_DB_OPERATION_DELAY"], ev_id, confidence="high")
                    for hid in ("IH0_NO_FAULT_HEALTHY", "IH3_INV_DB_CONFIG_ENDPOINT"):
                        _refute(by_id[hid], ev_id)
                    _weaken(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id)
                else:
                    _refute(by_id["IH4_INV_DB_OPERATION_DELAY"], ev_id)
                    _support(by_id["IH0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")
        elif svc == "inventory-cache":
            reachable = bool(data.get("reachable"))
            if not reachable:
                _force_support_live_override(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id, confidence="high")
                _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)
                # Do NOT hard-refute IH1_INV_DB_UNAVAILABLE if DB hasn't been checked or is already supported!
                for hid in ("IH1_INV_DB_UNAVAILABLE", "IH3_INV_DB_CONFIG_ENDPOINT", "IH4_INV_DB_OPERATION_DELAY"):
                    _weaken(by_id[hid], ev_id)
            else:
                _refute(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id)
                _support(by_id["IH0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")

    elif cname == "check_inventory_db_connectivity":
        ok = bool(data.get("ok"))
        err_cat = data.get("error_category")
        if ok:
            _refute(by_id["IH1_INV_DB_UNAVAILABLE"], ev_id)
            _refute(by_id["IH3_INV_DB_CONFIG_ENDPOINT"], ev_id)
            _refute(by_id["IH4_INV_DB_OPERATION_DELAY"], ev_id)
            _support(by_id["IH0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")
        else:
            _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)
            _apply_inv_error_category(by_id, err_cat, ev_id, confidence="high")

    elif cname == "check_inventory_cache_connectivity":
        ok = bool(data.get("ok"))
        if ok:
            _refute(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id)
            _support(by_id["IH0_NO_FAULT_HEALTHY"], ev_id, confidence="medium")
        else:
            _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)
            _force_support_live_override(by_id["IH2_INV_CACHE_UNAVAILABLE"], ev_id, confidence="high")
            for hid in ("IH1_INV_DB_UNAVAILABLE", "IH3_INV_DB_CONFIG_ENDPOINT", "IH4_INV_DB_OPERATION_DELAY"):
                _weaken(by_id[hid], ev_id)

    elif cname == "get_inventory_service_config":
        db_host = str(data.get("db_host", ""))
        if db_host and db_host not in ("127.0.0.1", "localhost", "postgres"):
            _force_support_live_override(by_id["IH3_INV_DB_CONFIG_ENDPOINT"], ev_id, confidence="high")
            _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)
            for hid in ("IH1_INV_DB_UNAVAILABLE", "IH2_INV_CACHE_UNAVAILABLE", "IH4_INV_DB_OPERATION_DELAY"):
                _weaken(by_id[hid], ev_id)
        else:
            _refute(by_id["IH3_INV_DB_CONFIG_ENDPOINT"], ev_id)

    elif cname == "get_recent_logs":
        svc = params.get("service")
        in_win_cats = _extract_in_window_log_categories(result)
        if svc == "inventory-service":
            if _has_unmodeled_error_category(in_win_cats, app_id="inventory_app"):
                _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)
                for hid in ("IH1_INV_DB_UNAVAILABLE", "IH2_INV_CACHE_UNAVAILABLE", "IH3_INV_DB_CONFIG_ENDPOINT", "IH4_INV_DB_OPERATION_DELAY"):
                    _weaken(by_id[hid], ev_id)
            else:
                for cat in in_win_cats:
                    _apply_inv_error_category(by_id, cat, ev_id, confidence="medium")

    elif cname == "get_service_metrics":
        if not result.is_stale and bool(data.get("sample_sufficient", False)):
            if int(data.get("dependency_timeouts", 0)) > 0 or float(data.get("avg_duration_ms", 0.0)) >= 900.0:
                _support(by_id["IH4_INV_DB_OPERATION_DELAY"], ev_id, confidence="medium")
                _refute(by_id["IH0_NO_FAULT_HEALTHY"], ev_id)


def _apply_inv_error_category(
    by_id: dict[str, HypothesisState],
    err_cat: Any,
    ev_id: str,
    confidence: str = "medium",
) -> None:
    mapping = {
        "connection_refused": "IH1_INV_DB_UNAVAILABLE",
        "cache_connection_refused": "IH2_INV_CACHE_UNAVAILABLE",
        "cache_timeout": "IH2_INV_CACHE_UNAVAILABLE",
        "hostname_resolution_failed": "IH3_INV_DB_CONFIG_ENDPOINT",
        "operation_timeout": "IH4_INV_DB_OPERATION_DELAY",
    }
    target = mapping.get(str(err_cat))
    if not target:
        return
    _force_support_live_override(by_id[target], ev_id, confidence=confidence)
    for other in set(mapping.values()):
        if other != target:
            _weaken(by_id[other], ev_id)


def _diff_stances(before: dict[str, str], hypotheses: list[HypothesisState]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for h in hypotheses:
        old = before.get(h.hypothesis_id)
        if old != h.stance.value:
            updates[h.hypothesis_id] = f"{old} -> {h.stance.value}"
    return updates
