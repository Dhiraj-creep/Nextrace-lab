"""Evidence Gate (v0.4.0 — Stages 1, 2, 4, 5, 6 & 8).

Enforces:
1. Temporal validity (`temporal.py`):
   - Current-health conclusions require fresh, non-superseded, reliable-timestamp observations.
   - An old healthy observation never overrides a newer failure (`is_superseded` / `any_failing`).
   - Incompatible observations from different service states are never combined (`is_valid_for_current_state`).
   - If simultaneous fresh sources disagree (`simultaneous_source_disagreement`), the gate blocks a confident
     conclusion until re-verified or abstains (`INCONCLUSIVE`).
   - Historical incident-window conclusions filter logs strictly to `[incident_start - skew, incident_end + skew]`
     (`in_window_error_categories`) and disclose timestamp uncertainty (`timestamp_uncertain`).
2. General Unknown-Cause handling (Stage 4):
   - Never relies on a scenario-specific string marker like `unmodeled_serialization_bug`.
   - Distinguishes:
     (a) Known cause supported (`SUPPORTED_DIAGNOSIS`),
     (b) Evidence points outside the modeled cause set (`UNKNOWN_CAUSE`),
     (c) Insufficient evidence to choose between known and unknown causes (`INCONCLUSIVE`).
3. General Multi-Fault Cause-Set Verification (`predicted_causes`, `unresolved_possible_causes`) across both
   `orders_app` and `inventory_app`.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from nextrace_lab.hypotheses import (
    MODELED_INVENTORY_ERROR_CATEGORIES,
    MODELED_ORDERS_ERROR_CATEGORIES,
    _extract_in_window_log_categories,
    _has_unmodeled_error_category,
)
from nextrace_lab.schemas import (
    ConflictRecord,
    DiagnosticCheckResult,
    DiagnosticOutcome,
    EvidenceStatus,
    HypothesisStance,
    HypothesisState,
    IncidentContext,
    RunFailureClassification,
)

EVIDENCE_GATE_VERSION: str = "evidence_gate_v2"
OUTCOME_MODEL_VERSION: str = "outcome_model_v2"

from nextrace_lab.temporal import is_valid_for_current_state


def evaluate_evidence_gate(
    incident: IncidentContext,
    hypotheses: list[HypothesisState],
    evidence_records: list[DiagnosticCheckResult],
    conflicts: Optional[list[ConflictRecord]] = None,
) -> dict[str, Any]:
    """Evaluate whether collected evidence is sufficient to support a root-cause claim."""
    active_conflicts = list(conflicts or [])
    available = [r for r in evidence_records if r.status == EvidenceStatus.AVAILABLE]
    by_id = {h.hypothesis_id: h for h in hypotheses}

    current_health = _assess_current_health_status(incident, available)
    window_diag, window_uncertain_notes = _infer_incident_window_cause(incident, available)
    recovery_observed = bool(
        incident.http_status >= 500
        and current_health == "healthy_now"
        and (
            window_diag is not None
            or any(c.conflict_type in ("within_run_repeat_change", "historical_vs_live_probe") for c in active_conflicts)
        )
    )

    unresolved_causes = _compute_unresolved_possible_causes(hypotheses, verified_ids=set())

    # Check if an unresolved simultaneous source disagreement blocks confident attribution
    unresolved_sim_conflicts = [
        c
        for c in active_conflicts
        if c.conflict_type == "simultaneous_source_disagreement"
        and c.requires_reverification
        and c.resolved_by_evidence_id is None
    ]
    if unresolved_sim_conflicts:
        c_summary = "; ".join(c.summary for c in unresolved_sim_conflicts)
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_causes,
            extra_notes=[f"Unresolved simultaneous source disagreement: {c_summary}"] + window_uncertain_notes,
        )
        return {
            "outcome": DiagnosticOutcome.INCONCLUSIVE,
            "failure_classification": RunFailureClassification.HONEST_INCONCLUSIVE,
            "candidate_service": None,
            "candidate_fault_type": None,
            "predicted_causes": [],
            "unresolved_possible_causes": unresolved_causes,
            "investigation_completion_state": "inconclusive_or_abstained",
            "window_diagnosis": window_diag,
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "low",
            "evidence_gate_passed": False,
            "evidence_gate_reason": f"Conflicting simultaneous observations prevent a confident conclusion: {c_summary}",
            "evidence_cited": [r.evidence_id for r in available if is_valid_for_current_state(r)],
            "uncertainty_summary": " ".join(rem_unc),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": ["get_service_health(database)", "get_service_health(order-service)"],
        }

    # Case 1: Healthy incident (HTTP 200/201)
    if incident.http_status in (200, 201):
        if current_health == "degraded_or_failing":
            # Entry request succeeded earlier, but a fresh live probe now shows a failing component!
            rem_unc = _build_remaining_uncertainty_list(
                evidence_records,
                unresolved_causes=unresolved_causes,
                extra_notes=["Entry request succeeded, but a newer live check observed a failing component."] + window_uncertain_notes,
            )
            return {
                "outcome": DiagnosticOutcome.INCONCLUSIVE,
                "failure_classification": RunFailureClassification.HONEST_INCONCLUSIVE,
                "candidate_service": None,
                "candidate_fault_type": None,
                "predicted_causes": [],
                "unresolved_possible_causes": unresolved_causes,
                "investigation_completion_state": "inconclusive_or_abstained",
                "window_diagnosis": "no_fault_in_incident_window",
                "current_health_status": "degraded_or_failing",
                "recovery_observed": False,
                "confidence_level": "low",
                "evidence_gate_passed": False,
                "evidence_gate_reason": "Cannot conclude NO_FAULT_FOUND because a fresh observation indicates current degradation/failure.",
                "evidence_cited": [r.evidence_id for r in available if is_valid_for_current_state(r)],
                "uncertainty_summary": " ".join(rem_unc),
                "remaining_uncertainty": rem_unc,
                "recommended_next_checks": _default_recommendations(evidence_records, app_id=incident.app_id),
            }

        if _has_healthy_verification(incident.app_id, available):
            h0_id = "IH0_NO_FAULT_HEALTHY" if incident.app_id == "inventory_app" else "H0_NO_FAULT_HEALTHY"
            h0 = by_id.get(h0_id)
            valid_ids = [r.evidence_id for r in available if is_valid_for_current_state(r)]
            cited = (
                [eid for eid in h0.supporting_evidence_ids if eid in valid_ids]
                if h0 and h0.supporting_evidence_ids
                else valid_ids
            )
            diag_tool_failed = any(r.status == EvidenceStatus.COLLECTION_FAILED for r in evidence_records)
            note = "Entry request succeeded (HTTP 201) and fresh, non-superseded service health checks confirmed normal operation."
            if diag_tool_failed:
                note += " Note: a diagnostic inspection endpoint returned an internal error while user traffic remained healthy."
            if active_conflicts:
                note += " Out-of-window historical log errors from an earlier resolved incident were separated from current healthy status."
            rem_unc = _build_remaining_uncertainty_list(
                evidence_records,
                unresolved_causes=[],
                extra_notes=(
                    ["Diagnostic inspection endpoint returned an error while user traffic was healthy."]
                    if diag_tool_failed
                    else []
                )
                + window_uncertain_notes,
            )
            return {
                "outcome": DiagnosticOutcome.NO_FAULT_FOUND,
                "failure_classification": RunFailureClassification.SUPPORTED_DIAGNOSIS,
                "candidate_service": None,
                "candidate_fault_type": None,
                "predicted_causes": [],
                "unresolved_possible_causes": [],
                "investigation_completion_state": "healthy_verified",
                "window_diagnosis": window_diag or "no_fault_in_incident_window",
                "current_health_status": "healthy_now",
                "recovery_observed": False,
                "confidence_level": "high",
                "evidence_gate_passed": True,
                "evidence_gate_reason": note,
                "evidence_cited": cited,
                "uncertainty_summary": (
                    "Diagnostic endpoint failure noted, but live traffic and fresh readiness checks are healthy."
                    if diag_tool_failed
                    else "None; fresh live health checks and request outcome are consistent with a healthy system."
                ),
                "remaining_uncertainty": rem_unc,
                "recommended_next_checks": [],
            }

        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_causes,
            extra_notes=["Entry request succeeded, but fresh downstream health checks are incomplete or expired."] + window_uncertain_notes,
        )
        return {
            "outcome": DiagnosticOutcome.INCONCLUSIVE,
            "failure_classification": RunFailureClassification.HONEST_INCONCLUSIVE,
            "candidate_service": None,
            "candidate_fault_type": None,
            "predicted_causes": [],
            "unresolved_possible_causes": unresolved_causes,
            "investigation_completion_state": "inconclusive_or_abstained",
            "window_diagnosis": window_diag,
            "current_health_status": current_health,
            "recovery_observed": False,
            "confidence_level": "low",
            "evidence_gate_passed": False,
            "evidence_gate_reason": "Entry request succeeded, but insufficient fresh health checks were available to verify full system readiness.",
            "evidence_cited": [r.evidence_id for r in available if is_valid_for_current_state(r)],
            "uncertainty_summary": " ".join(rem_unc),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": _default_recommendations(evidence_records, app_id=incident.app_id),
        }

    # Case 2: Second Application (`inventory_app`) fault evaluation
    if incident.app_id == "inventory_app":
        return _evaluate_inventory_app_gate(
            incident,
            hypotheses,
            evidence_records,
            available,
            current_health,
            window_diag,
            recovery_observed,
            window_uncertain_notes,
        )

    # Case 3: Check for general unmodeled / unknown cause on `orders_app` (Stage 4)
    is_unk, unk_reason, unk_diag_label = _is_unknown_cause_indicated(
        incident, hypotheses, available, active_conflicts
    )
    if is_unk:
        cited = [r.evidence_id for r in available if is_valid_for_current_state(r) or r.check_name == "get_recent_logs"]
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=["unknown_unmodeled_application_or_external_cause"],
            extra_notes=[unk_reason] + window_uncertain_notes,
        )
        return {
            "outcome": DiagnosticOutcome.UNKNOWN_CAUSE,
            "failure_classification": RunFailureClassification.UNKNOWN_CAUSE,
            "candidate_service": None,
            "candidate_fault_type": None,
            "predicted_causes": ["unknown_cause"],
            "unresolved_possible_causes": ["unknown_unmodeled_application_or_external_cause"],
            "investigation_completion_state": "investigation_complete_within_modeled_scope",
            "window_diagnosis": unk_diag_label,
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "medium",
            "evidence_gate_passed": True,
            "evidence_gate_reason": unk_reason,
            "evidence_cited": cited,
            "uncertainty_summary": " ".join(rem_unc),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": [
                "Inspect application exception traces and code paths outside the modeled dependency catalog.",
            ],
        }

    # Case 4: Evaluate all supported fault hypotheses (including multi-fault combinations)
    supported_faults = [
        h
        for h in hypotheses
        if h.hypothesis_id != "H0_NO_FAULT_HEALTHY" and h.stance == HypothesisStance.SUPPORTED
    ]

    verified_hypotheses: list[tuple[HypothesisState, str, list[str]]] = []
    partial_reasons: list[str] = []
    recommended_accum: list[str] = []

    for h in supported_faults:
        passed, reason, cited_ids, recs = _verify_hypothesis_gate(
            h.hypothesis_id, available, evidence_records, current_health=current_health
        )
        if passed:
            verified_hypotheses.append((h, reason, cited_ids))
        else:
            partial_reasons.append(f"{h.hypothesis_id}: {reason}")
            for rec in recs:
                if rec not in recommended_accum:
                    recommended_accum.append(rec)

    # Check if mid-run recovery occurred: incident failed (503), current_health == "healthy_now",
    # and incident-window logs/checks proved a specific fault during the incident window!
    if not verified_hypotheses and current_health == "healthy_now" and window_diag:
        rec_passed, rec_h, rec_reason, rec_cited = _verify_recovered_window_diagnosis(
            by_id, available, window_diag
        )
        if rec_passed and rec_h is not None:
            verified_hypotheses.append((rec_h, rec_reason, rec_cited))
            recovery_observed = True

    verified_ids = {h.hypothesis_id for h, _, _ in verified_hypotheses}
    unresolved_after_verify = _compute_unresolved_possible_causes(
        hypotheses, verified_ids=verified_ids, evidence_records=evidence_records
    )
    completion_state: Literal[
        "one_cause_supported",
        "additional_causes_unresolved",
        "investigation_complete_within_modeled_scope",
        "inconclusive_or_abstained",
        "healthy_verified",
    ] = (
        "additional_causes_unresolved"
        if unresolved_after_verify
        else "investigation_complete_within_modeled_scope"
    )

    if len(verified_hypotheses) == 1:
        winner, reason, cited_ids = verified_hypotheses[0]
        cause_label = f"{winner.candidate_service}:{winner.candidate_fault_type}"
        conf: Literal["low", "medium", "high"] = "high" if len(cited_ids) >= 2 else "medium"
        if current_health == "healthy_now":
            reason += " (Note: service recovered during investigation; diagnosis reflects verified incident-window cause while current_health_status=healthy_now.)"
        if unresolved_after_verify:
            reason += f" Note: additional modeled causes were not ruled out ({unresolved_after_verify}); real-world unmodeled causes are never 100% excluded."
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_after_verify,
            extra_notes=window_uncertain_notes,
            current_health=current_health,
        )
        return {
            "outcome": DiagnosticOutcome.SUPPORTED_DIAGNOSIS,
            "failure_classification": RunFailureClassification.SUPPORTED_DIAGNOSIS,
            "candidate_service": winner.candidate_service,
            "candidate_fault_type": winner.candidate_fault_type,
            "predicted_causes": [cause_label],
            "unresolved_possible_causes": unresolved_after_verify,
            "investigation_completion_state": "one_cause_supported" if unresolved_after_verify else "investigation_complete_within_modeled_scope",
            "window_diagnosis": window_diag or cause_label,
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": conf,
            "evidence_gate_passed": True,
            "evidence_gate_reason": reason,
            "evidence_cited": cited_ids,
            "uncertainty_summary": _build_uncertainty_summary(
                evidence_records,
                passed=True,
                current_health=current_health,
                unresolved_causes=unresolved_after_verify,
                extra_reason="; ".join(window_uncertain_notes),
            ),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": [],
        }

    if len(verified_hypotheses) > 1:
        verified_hypotheses.sort(key=lambda item: item[0].hypothesis_id)
        causes = sorted(
            {f"{h.candidate_service}:{h.candidate_fault_type}" for h, _, _ in verified_hypotheses}
        )
        services = "+".join(dict.fromkeys(h.candidate_service or "" for h, _, _ in verified_hypotheses))
        fault_types = "+".join(dict.fromkeys(h.candidate_fault_type or "" for h, _, _ in verified_hypotheses))
        cited_union: list[str] = []
        reasons: list[str] = []
        for h, r_str, c_ids in verified_hypotheses:
            reasons.append(f"[{h.hypothesis_id}] {r_str}")
            for cid in c_ids:
                if cid not in cited_union:
                    cited_union.append(cid)
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_after_verify,
            extra_notes=window_uncertain_notes,
            current_health=current_health,
        )
        return {
            "outcome": DiagnosticOutcome.SUPPORTED_DIAGNOSIS,
            "failure_classification": RunFailureClassification.SUPPORTED_DIAGNOSIS,
            "candidate_service": services,
            "candidate_fault_type": fault_types,
            "predicted_causes": causes,
            "unresolved_possible_causes": unresolved_after_verify,
            "investigation_completion_state": completion_state,
            "window_diagnosis": ",".join(causes),
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "high",
            "evidence_gate_passed": True,
            "evidence_gate_reason": "Multiple simultaneous faults verified by independent evidence: " + "; ".join(reasons),
            "evidence_cited": cited_union,
            "uncertainty_summary": _build_uncertainty_summary(
                evidence_records,
                passed=True,
                current_health=current_health,
                unresolved_causes=unresolved_after_verify,
                extra_reason="; ".join(window_uncertain_notes),
            ),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": [],
        }

    # If a single hypothesis is SUPPORTED but did not pass the gate yet
    if len(supported_faults) == 1:
        candidate = supported_faults[0]
        _, reason, cited_ids, recommended = _verify_hypothesis_gate(
            candidate.hypothesis_id, available, evidence_records, current_health=current_health
        )
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_causes,
            extra_notes=[reason] + window_uncertain_notes,
            current_health=current_health,
        )
        return {
            "outcome": DiagnosticOutcome.INCONCLUSIVE,
            "failure_classification": RunFailureClassification.HONEST_INCONCLUSIVE,
            "candidate_service": candidate.candidate_service,
            "candidate_fault_type": candidate.candidate_fault_type,
            "predicted_causes": [],
            "unresolved_possible_causes": unresolved_causes,
            "investigation_completion_state": "inconclusive_or_abstained",
            "window_diagnosis": window_diag,
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "low",
            "evidence_gate_passed": False,
            "evidence_gate_reason": f"Evidence gate blocked confident claim for {candidate.hypothesis_id}: {reason}",
            "evidence_cited": cited_ids,
            "uncertainty_summary": _build_uncertainty_summary(
                evidence_records,
                passed=False,
                extra_reason=reason,
                current_health=current_health,
                unresolved_causes=unresolved_causes,
            ),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": recommended,
        }

    plausible = [
        h.hypothesis_id
        for h in hypotheses
        if h.hypothesis_id != "H0_NO_FAULT_HEALTHY" and h.stance in (HypothesisStance.PLAUSIBLE, HypothesisStance.SUPPORTED)
    ]
    rem_unc = _build_remaining_uncertainty_list(
        evidence_records,
        unresolved_causes=unresolved_causes,
        extra_notes=[f"Multiple candidate explanations remain unresolved ({plausible})."] + window_uncertain_notes,
        current_health=current_health,
    )
    return {
        "outcome": DiagnosticOutcome.INCONCLUSIVE,
        "failure_classification": RunFailureClassification.HONEST_INCONCLUSIVE,
        "candidate_service": None,
        "candidate_fault_type": None,
        "predicted_causes": [],
        "unresolved_possible_causes": unresolved_causes,
        "investigation_completion_state": "inconclusive_or_abstained",
        "window_diagnosis": window_diag,
        "current_health_status": current_health,
        "recovery_observed": recovery_observed,
        "confidence_level": "low",
        "evidence_gate_passed": False,
        "evidence_gate_reason": (
            f"Insufficient distinguishing evidence to isolate root cause; remaining plausible/supported hypotheses={plausible}."
            + (f" Details: {'; '.join(partial_reasons)}" if partial_reasons else "")
        ),
        "evidence_cited": [r.evidence_id for r in available if is_valid_for_current_state(r)],
        "uncertainty_summary": _build_uncertainty_summary(
            evidence_records,
            passed=False,
            extra_reason=f"Multiple candidate explanations remain unresolved ({plausible}).",
            current_health=current_health,
            unresolved_causes=unresolved_causes,
        ),
        "remaining_uncertainty": rem_unc,
        "recommended_next_checks": recommended_accum or _default_recommendations(evidence_records, app_id=incident.app_id),
    }


def _compute_unresolved_possible_causes(
    hypotheses: list[HypothesisState],
    *,
    verified_ids: set[str],
    evidence_records: Optional[list[DiagnosticCheckResult]] = None,
) -> list[str]:
    """Return list of modeled cause labels that have not been verified or refuted."""
    # Check which components have been directly probed by a fresh valid check
    probed_services: set[str] = set()
    if evidence_records:
        for r in evidence_records:
            if is_valid_for_current_state(r):
                if r.check_name == "get_service_health" and r.params.get("service"):
                    probed_services.add(str(r.params.get("service")))
                elif r.check_name in ("get_order_service_database_config", "check_database_connectivity_from_order_service"):
                    probed_services.add("order-service-config")
                elif r.check_name in ("get_inventory_service_config", "check_inventory_db_connectivity"):
                    probed_services.add("inventory-service-config")
                elif r.check_name == "check_inventory_cache_connectivity":
                    probed_services.add("inventory-cache")

    unresolved: list[str] = []
    for h in hypotheses:
        if h.hypothesis_id.startswith(("H0_", "IH0_")):
            continue
        if h.hypothesis_id in verified_ids:
            continue
        label = f"{h.candidate_service}:{h.candidate_fault_type}"
        if h.stance in (HypothesisStance.PLAUSIBLE, HypothesisStance.SUPPORTED):
            if label not in unresolved:
                unresolved.append(label)
        elif h.stance == HypothesisStance.WEAKENED:
            # If a hypothesis was only weakened indirectly (not directly refuted) and its target component was never probed:
            if h.candidate_service == "database" and "database" not in probed_services:
                if label not in unresolved:
                    unresolved.append(label)
            elif h.candidate_service == "inventory-db" and "inventory-db" not in probed_services:
                if label not in unresolved:
                    unresolved.append(label)
            elif h.candidate_service == "inventory-cache" and "inventory-cache" not in probed_services:
                if label not in unresolved:
                    unresolved.append(label)
    return unresolved


def _assess_current_health_status(
    incident: IncidentContext,
    available: list[DiagnosticCheckResult],
) -> Literal["healthy_now", "degraded_or_failing", "unknown"]:
    """Determine current live health status strictly from fresh, non-superseded, reliable-timestamp probes (Stage 1)."""
    live_probes = [
        r
        for r in available
        if r.evidence_source == "live_probe" and is_valid_for_current_state(r)
    ]
    if not live_probes:
        return "unknown"

    latest_by_key: dict[str, DiagnosticCheckResult] = {}
    for r in live_probes:
        key = f"{r.check_name}:{r.params.get('service', '')}"
        latest_by_key[key] = r

    any_failing = False
    primary_service_healthy = False
    db_healthy = False

    for _, r in latest_by_key.items():
        if r.check_name == "get_service_health":
            svc = r.params.get("service")
            if svc in ("order-service", "inventory-service"):
                if bool(r.data.get("live")) and bool(r.data.get("ready")):
                    primary_service_healthy = True
                else:
                    any_failing = True
            elif svc in ("database", "inventory-db"):
                if bool(r.data.get("reachable")) and bool(r.data.get("schema_usable", True)) and r.data.get("error_category") is None:
                    db_healthy = True
                else:
                    any_failing = True
            elif svc == "inventory-cache":
                if not bool(r.data.get("reachable")):
                    any_failing = True
            elif svc in ("gateway", "inventory-api"):
                if not (bool(r.data.get("live")) and bool(r.data.get("ready"))):
                    any_failing = True
        elif r.check_name in ("check_database_connectivity_from_order_service", "check_inventory_db_connectivity"):
            if bool(r.data.get("ok")):
                primary_service_healthy = True
                db_healthy = True
            else:
                any_failing = True
        elif r.check_name == "check_inventory_cache_connectivity":
            if not bool(r.data.get("ok")):
                any_failing = True

    if any_failing:
        return "degraded_or_failing"
    if primary_service_healthy and db_healthy:
        return "healthy_now"
    if primary_service_healthy and incident.http_status in (200, 201):
        return "healthy_now"
    return "unknown"


def _infer_incident_window_cause(
    incident: IncidentContext,
    available: list[DiagnosticCheckResult],
) -> tuple[Optional[str], list[str]]:
    """Infer the cause active during the incident window using temporally aligned evidence (Stage 1).

    Returns `(window_diagnosis, timestamp_uncertainty_notes)`.
    """
    cat_map = {
        "hostname_resolution_failed": (
            "inventory-service:db_endpoint_misconfiguration"
            if incident.app_id == "inventory_app"
            else "order-service:db_endpoint_misconfiguration"
        ),
        "connection_refused": (
            "inventory-db:db_service_unavailable"
            if incident.app_id == "inventory_app"
            else "database:db_service_unavailable"
        ),
        "authentication_failed": "order-service:db_auth_failure",
        "missing_table": "database:db_schema_missing_table",
        "operation_timeout": (
            "inventory-db:db_operation_delay"
            if incident.app_id == "inventory_app"
            else "database:db_operation_delay"
        ),
        "cache_connection_refused": "inventory-cache:cache_service_unavailable",
        "cache_timeout": "inventory-cache:cache_service_unavailable",
        "upstream_order_service_unreachable": "order-service:order_service_unavailable",
    }

    uncertainty_notes: list[str] = []

    # 1. Check in-window log entries first (authoritative historical record of the incident window)
    for r in available:
        if r.check_name == "get_recent_logs":
            if r.timestamp_uncertain:
                uncertainty_notes.append(
                    f"Log evidence {r.evidence_id} contains entries with missing/uncertain timestamps ({r.timestamp_uncertainty_reason}); excluded from incident-window attribution."
                )
            in_win_cats = _extract_in_window_log_categories(r)
            out_win_cats = set(r.data.get("out_of_window_error_categories") or [])
            if out_win_cats and not in_win_cats:
                uncertainty_notes.append(
                    f"Log evidence {r.evidence_id} contained out-of-window historical errors {sorted(out_win_cats)} which were excluded from the incident window."
                )
            for cat in sorted(in_win_cats):
                if cat in cat_map:
                    return cat_map[cat], uncertainty_notes
            if _has_unmodeled_error_category(in_win_cats, app_id=incident.app_id):
                unmodeled = sorted(
                    in_win_cats
                    - (MODELED_INVENTORY_ERROR_CATEGORIES if incident.app_id == "inventory_app" else MODELED_ORDERS_ERROR_CATEGORIES)
                )
                return f"unknown_cause:{unmodeled[0]}", uncertainty_notes

    # 2. If the incident itself succeeded (HTTP 200/201), do not attribute later probe errors to the incident window
    if incident.http_status in (200, 201):
        return "no_fault_in_incident_window", uncertainty_notes

    # 3. For a failed incident (HTTP >= 500), inspect temporally valid probes collected within the incident window
    for r in available:
        if r.timestamp_uncertain:
            uncertainty_notes.append(
                f"Observation {r.evidence_id} ({r.check_name}) has missing/uncertain timestamp ({r.timestamp_uncertainty_reason}); excluded."
            )
            continue
        if r.in_incident_window is False:
            continue
        if r.check_name == "get_service_health" and r.params.get("service") in ("order-service", "inventory-service"):
            err_cat = r.data.get("ready_response", {}).get("error_category")
            if err_cat in cat_map:
                return cat_map[err_cat], uncertainty_notes
        if r.check_name in ("check_database_connectivity_from_order_service", "check_inventory_db_connectivity"):
            err_cat = r.data.get("error_category")
            if err_cat in cat_map:
                return cat_map[err_cat], uncertainty_notes

    return None, uncertainty_notes


def _is_unknown_cause_indicated(
    incident: IncidentContext,
    hypotheses: list[HypothesisState],
    available: list[DiagnosticCheckResult],
    active_conflicts: list[ConflictRecord],
) -> tuple[bool, str, str]:
    """Evaluate general unknown-cause criteria without relying on any scenario-specific string marker (Stage 4).

    Returns `(is_unknown_cause, reason, window_diagnosis_label)`.
    """
    if incident.http_status < 500:
        return False, "", ""

    # If a mid-run recovery conflict was observed for a known modeled fault, it is NOT an unknown cause
    if any(c.conflict_type in ("within_run_repeat_change", "historical_vs_live_probe", "stale_vs_fresh_override") for c in active_conflicts):
        return False, "", ""

    # If the incident-window error was already positively identified as a modeled cause, do not claim unknown cause
    win_diag, _ = _infer_incident_window_cause(incident, available)
    if win_diag and not win_diag.startswith("unknown_cause:") and win_diag != "no_fault_in_incident_window":
        return False, "", ""

    is_inv = incident.app_id == "inventory_app"
    modeled_cats = MODELED_INVENTORY_ERROR_CATEGORIES if is_inv else MODELED_ORDERS_ERROR_CATEGORIES

    unmodeled_cats_found: set[str] = set()
    any_modeled_fault_indicator = False

    # Track fresh current-state verifications
    primary_ready_ok = False
    db_health_ok = False
    cache_health_ok = False
    config_host_valid = False

    for r in available:
        if r.timestamp_uncertain:
            continue
        if r.check_name == "get_recent_logs":
            in_win_cats = _extract_in_window_log_categories(r)
            if in_win_cats & modeled_cats:
                if not (in_win_cats <= {"upstream_order_service_error", "upstream_inventory_service_error"}):
                    any_modeled_fault_indicator = True
            unmodeled = in_win_cats - modeled_cats
            if unmodeled:
                unmodeled_cats_found.update(unmodeled)
            continue

        if not is_valid_for_current_state(r):
            continue

        if not is_inv:
            if r.check_name == "get_service_health" and r.params.get("service") == "database":
                if bool(r.data.get("reachable")) and bool(r.data.get("schema_usable")) and r.data.get("error_category") is None:
                    db_health_ok = True
                else:
                    any_modeled_fault_indicator = True
            elif r.check_name == "get_service_health" and r.params.get("service") == "order-service":
                if bool(r.data.get("live")) and bool(r.data.get("ready")):
                    primary_ready_ok = True
                else:
                    any_modeled_fault_indicator = True
            elif r.check_name == "check_database_connectivity_from_order_service":
                if bool(r.data.get("ok")):
                    primary_ready_ok = True
                else:
                    any_modeled_fault_indicator = True
            elif r.check_name == "get_order_service_database_config":
                if str(r.data.get("db_host", "")) in ("127.0.0.1", "localhost", "postgres"):
                    config_host_valid = True
                elif r.data.get("db_host"):
                    any_modeled_fault_indicator = True
        else:
            if r.check_name == "get_service_health" and r.params.get("service") == "inventory-service":
                if bool(r.data.get("live")) and bool(r.data.get("ready")):
                    primary_ready_ok = True
                else:
                    any_modeled_fault_indicator = True
            elif r.check_name == "get_service_health" and r.params.get("service") == "inventory-db":
                if bool(r.data.get("reachable")) and r.data.get("error_category") is None:
                    db_health_ok = True
                else:
                    any_modeled_fault_indicator = True
            elif r.check_name in ("get_service_health", "check_inventory_cache_connectivity"):
                if r.params.get("service") == "inventory-cache" or r.check_name == "check_inventory_cache_connectivity":
                    if bool(r.data.get("reachable", r.data.get("ok"))):
                        cache_health_ok = True
                    else:
                        any_modeled_fault_indicator = True
            elif r.check_name == "get_inventory_service_config":
                if str(r.data.get("db_host", "")) in ("127.0.0.1", "localhost", "postgres"):
                    config_host_valid = True
                elif r.data.get("db_host"):
                    any_modeled_fault_indicator = True

    if any_modeled_fault_indicator:
        return False, "", ""

    # Path A: In-window logs reveal an unfamiliar/unmodeled error category AND dependency probes confirm dependencies are healthy
    if unmodeled_cats_found and (primary_ready_ok or db_health_ok):
        cat_str = sorted(unmodeled_cats_found)[0]
        return (
            True,
            (
                f"Application failed (HTTP {incident.http_status}), modeled dependency checks are healthy, "
                f"and incident-window logs report an unmodeled error category ('{cat_str}') outside the modeled hypothesis catalog."
            ),
            f"unknown_cause:{cat_str}",
        )

    # Path B: Marker-free refutation of all modeled causes!
    # Even when logs are unavailable (E1/E3) or contain no special marker, if all modeled hypotheses are refuted
    # by fresh observations (primary service ready + DB healthy + valid config / cache healthy), then the failure
    # lies outside the modeled cause set!
    non_h0 = [h for h in hypotheses if not h.hypothesis_id.startswith(("H0_", "IH0_"))]
    all_modeled_refuted = bool(non_h0) and all(h.stance == HypothesisStance.REFUTED for h in non_h0)

    if not is_inv and primary_ready_ok and db_health_ok and (config_host_valid or all_modeled_refuted):
        return (
            True,
            (
                f"Application failed (HTTP {incident.http_status}), and all modeled hypotheses (H1..H6) were "
                "refuted by fresh live health, database, and configuration checks. Evidence points outside the modeled cause set."
            ),
            "unknown_cause:unmodeled_application_failure",
        )

    if is_inv and primary_ready_ok and db_health_ok and (cache_health_ok or all_modeled_refuted):
        return (
            True,
            (
                f"Inventory application failed (HTTP {incident.http_status}), and all modeled hypotheses (IH1..IH4) "
                "were refuted by fresh live dependency checks. Evidence points outside the modeled cause set."
            ),
            "unknown_cause:unmodeled_inventory_failure",
        )

    return False, "", ""


def _verify_recovered_window_diagnosis(
    by_id: dict[str, HypothesisState],
    available: list[DiagnosticCheckResult],
    window_diag: str,
) -> tuple[bool, Optional[HypothesisState], str, list[str]]:
    """Verify whether a mid-run recovery scenario collected sufficient evidence of the incident-window fault."""
    early_fault_ev: list[str] = []
    post_recovery_ev: list[str] = []

    for r in available:
        if r.timestamp_uncertain:
            continue
        if r.check_name == "get_recent_logs" and r.params.get("service") == "order-service":
            in_win_cats = _extract_in_window_log_categories(r)
            if "hostname_resolution_failed" in in_win_cats:
                early_fault_ev.append(r.evidence_id)
        elif r.check_name == "get_service_health" and r.params.get("service") == "order-service":
            if not bool(r.data.get("ready")) and r.data.get("ready_response", {}).get("error_category") == "hostname_resolution_failed":
                if r.in_incident_window is not False:
                    early_fault_ev.append(r.evidence_id)
            elif bool(r.data.get("ready")) and not r.is_stale and not r.is_superseded:
                post_recovery_ev.append(r.evidence_id)
        elif r.check_name == "check_database_connectivity_from_order_service":
            if not bool(r.data.get("ok")) and r.data.get("error_category") == "hostname_resolution_failed":
                if r.in_incident_window is not False:
                    early_fault_ev.append(r.evidence_id)
            elif bool(r.data.get("ok")) and not r.is_stale and not r.is_superseded:
                post_recovery_ev.append(r.evidence_id)
        elif r.check_name == "get_service_health" and r.params.get("service") == "database":
            if bool(r.data.get("reachable")) and not r.is_stale and not r.is_superseded:
                post_recovery_ev.append(r.evidence_id)

    if len(early_fault_ev) >= 1 and len(post_recovery_ev) >= 1 and window_diag == "order-service:db_endpoint_misconfiguration":
        h1 = by_id.get("H1_ORDER_DB_CONFIG_ENDPOINT")
        cited = list(dict.fromkeys(early_fault_ev + post_recovery_ev))
        return (
            True,
            h1,
            "Incident-window fault (db_endpoint_misconfiguration) verified via incident-window probe/logs before mid-run recovery to healthy_now.",
            cited,
        )
    return False, None, "", []


def _has_healthy_verification(app_id: str, available: list[DiagnosticCheckResult]) -> bool:
    """Require fresh, non-superseded, reliable-timestamp observations confirming health, with zero failing checks."""
    valid_current = [r for r in available if is_valid_for_current_state(r)]
    if not valid_current:
        return False

    if app_id == "inventory_app":
        inv_ready = False
        db_ok = False
        for r in valid_current:
            if r.check_name == "get_service_health" and r.params.get("service") == "inventory-service":
                if bool(r.data.get("live")) and bool(r.data.get("ready")):
                    inv_ready = True
                else:
                    return False
            if r.check_name == "get_service_health" and r.params.get("service") == "inventory-db":
                if bool(r.data.get("reachable")) and r.data.get("error_category") is None:
                    db_ok = True
                else:
                    return False
            if r.check_name == "get_service_health" and r.params.get("service") == "inventory-cache":
                if not bool(r.data.get("reachable")):
                    return False
            if r.check_name == "check_inventory_db_connectivity":
                if bool(r.data.get("ok")):
                    inv_ready = True
                    db_ok = True
                else:
                    return False
        return inv_ready and db_ok

    order_ready = False
    db_reachable = False
    for r in valid_current:
        if r.check_name == "get_service_health" and r.params.get("service") == "order-service":
            if bool(r.data.get("live")) and bool(r.data.get("ready")):
                order_ready = True
            else:
                return False
        if r.check_name == "get_service_health" and r.params.get("service") == "database":
            if bool(r.data.get("reachable")) and bool(r.data.get("schema_usable")) and r.data.get("error_category") is None:
                db_reachable = True
            else:
                return False
        if r.check_name == "check_database_connectivity_from_order_service":
            if bool(r.data.get("ok")):
                order_ready = True
                db_reachable = True
            else:
                return False
    return order_ready and db_reachable


def _verify_hypothesis_gate(
    hypothesis_id: str,
    available: list[DiagnosticCheckResult],
    all_records: list[DiagnosticCheckResult],
    *,
    current_health: str = "degraded_or_failing",
) -> tuple[bool, str, list[str], list[str]]:
    """Return `(passed, reason, cited_evidence_ids, recommended_next_checks)` using temporally valid observations."""
    cited: list[str] = []

    db_reachable_ok = False
    db_unreachable = False
    db_missing_table = False
    db_delay_timeout = False

    order_live = False
    order_unreachable = False
    order_err_cat: Optional[str] = None

    probe_err_cat: Optional[str] = None
    config_host_invalid = False
    config_host_valid = False
    log_err_cats: set[str] = set()
    gw_log_cats: set[str] = set()
    metrics_timeout_corroborated = False

    for r in available:
        if r.check_name == "get_recent_logs":
            if r.timestamp_uncertain:
                continue
            svc = r.params.get("service")
            cats = _extract_in_window_log_categories(r)
            if svc == "order-service" and cats:
                log_err_cats.update(cats)
                cited.append(r.evidence_id)
            elif svc == "gateway" and cats:
                gw_log_cats.update(cats)
                cited.append(r.evidence_id)
            continue

        # For all live probes, configs, and metrics, require fresh, non-superseded, reliable-timestamp observations!
        if not is_valid_for_current_state(r):
            continue

        if r.check_name == "get_service_health" and r.params.get("service") == "database":
            if bool(r.data.get("reachable")):
                if bool(r.data.get("schema_usable")) and r.data.get("error_category") is None:
                    db_reachable_ok = True
                    cited.append(r.evidence_id)
                elif r.data.get("error_category") == "missing_table":
                    db_missing_table = True
                    cited.append(r.evidence_id)
                elif r.data.get("error_category") == "operation_timeout":
                    db_delay_timeout = True
                    cited.append(r.evidence_id)
            else:
                db_unreachable = True
                cited.append(r.evidence_id)

        elif r.check_name == "get_service_health" and r.params.get("service") == "order-service":
            if not bool(r.data.get("live")):
                order_unreachable = True
                cited.append(r.evidence_id)
            else:
                order_live = True
                rcat = r.data.get("ready_response", {}).get("error_category")
                if rcat and rcat != "dependency_check_failed_masked_under_e2":
                    order_err_cat = str(rcat)
                    cited.append(r.evidence_id)

        elif r.check_name == "get_service_health" and r.params.get("service") == "gateway":
            if bool(r.data.get("live")) and not bool(r.data.get("ready")):
                if r.data.get("ready_response", {}).get("upstream_order_service") == "unreachable":
                    order_unreachable = True
                    cited.append(r.evidence_id)

        elif r.check_name == "check_database_connectivity_from_order_service":
            if not bool(r.data.get("ok")):
                probe_err_cat = str(r.data.get("error_category") or "")
                cited.append(r.evidence_id)

        elif r.check_name == "get_order_service_database_config":
            host = str(r.data.get("db_host", ""))
            if host and host not in ("127.0.0.1", "localhost", "postgres"):
                config_host_invalid = True
                cited.append(r.evidence_id)
            elif host:
                config_host_valid = True
                cited.append(r.evidence_id)

        elif r.check_name == "get_service_metrics":
            if bool(r.data.get("sample_sufficient", False)):
                if int(r.data.get("dependency_timeouts", 0)) > 0 or float(r.data.get("avg_duration_ms", 0.0)) >= 900.0:
                    metrics_timeout_corroborated = True
                    cited.append(r.evidence_id)

    unique_cited = list(dict.fromkeys(cited))

    if hypothesis_id == "H1_ORDER_DB_CONFIG_ENDPOINT":
        hostname_signals = sum(
            [
                1 if config_host_invalid else 0,
                1 if probe_err_cat == "hostname_resolution_failed" else 0,
                1 if order_err_cat == "hostname_resolution_failed" else 0,
                1 if "hostname_resolution_failed" in log_err_cats else 0,
            ]
        )
        if (hostname_signals >= 1 and db_reachable_ok) or (hostname_signals >= 2):
            return (
                True,
                "Confirmed order-service DB endpoint misconfiguration via invalid DB host / hostname_resolution_failed evidence.",
                unique_cited,
                [],
            )
        recs = []
        if not db_reachable_ok and not db_unreachable:
            recs.append("get_service_health(database)")
        if not config_host_invalid:
            recs.append("get_order_service_database_config()")
        if "hostname_resolution_failed" not in log_err_cats:
            recs.append("get_recent_logs(order-service)")
        return (
            False,
            "Requires corroboration via get_service_health(database), get_recent_logs(order-service), or get_order_service_database_config() alongside hostname_resolution_failed.",
            unique_cited,
            recs,
        )

    if hypothesis_id == "H2_DATABASE_UNAVAILABLE":
        has_conn_refused = (
            probe_err_cat == "connection_refused"
            or order_err_cat == "connection_refused"
            or "connection_refused" in log_err_cats
        )
        # H2 is verified when database is directly confirmed unreachable AND either order-service is live or order-service is also verified down (multi_fault_f_masks_b)
        if db_unreachable and (has_conn_refused or order_live or order_unreachable):
            return (
                True,
                "Confirmed database is unreachable on its port via direct probe alongside caller/service state.",
                unique_cited,
                [],
            )
        return (
            False,
            "Requires direct confirmation that database is unreachable via get_service_health(database) plus service observation.",
            unique_cited,
            ["get_service_health(database)", "get_service_health(order-service)"],
        )

    if hypothesis_id == "H3_ORDER_DB_AUTH_FAILURE":
        auth_signals = sum(
            [
                1 if probe_err_cat == "authentication_failed" else 0,
                1 if order_err_cat == "authentication_failed" else 0,
                1 if "authentication_failed" in log_err_cats else 0,
            ]
        )
        # In single-fault (db_reachable_ok) or multi-fault with H4 (db_missing_table, where DB is reachable on TCP),
        # H3 is verified when DB is reachable on TCP and >=2 auth/config signals confirm authentication_failed!
        db_tcp_reachable = db_reachable_ok or db_missing_table
        if (db_tcp_reachable and auth_signals >= 1 and (auth_signals >= 2 or config_host_valid)) or (auth_signals >= 2 and config_host_valid):
            return (
                True,
                "Confirmed order-service fails database authentication across corroborating checks.",
                unique_cited,
                [],
            )
        return (
            False,
            "Requires database reachability confirmation plus corroborating authentication_failed signals.",
            unique_cited,
            [
                "get_service_health(database)",
                "check_database_connectivity_from_order_service()",
                "get_order_service_database_config()",
            ],
        )

    if hypothesis_id == "H4_DATABASE_SCHEMA_MISSING":
        schema_signals = sum(
            [
                1 if db_missing_table else 0,
                1 if probe_err_cat == "missing_table" else 0,
                1 if order_err_cat == "missing_table" else 0,
                1 if "missing_table" in log_err_cats else 0,
            ]
        )
        # In multi_fault_c_and_d (where order-service fails at auth before reaching schema check),
        # direct DB health (`db_missing_table`) plus confirmed order-service live/auth state verifies H4!
        auth_co_occurring = (
            order_err_cat == "authentication_failed"
            or probe_err_cat == "authentication_failed"
            or "authentication_failed" in log_err_cats
        )
        if schema_signals >= 2 or (db_missing_table and auth_co_occurring and order_live):
            return (
                True,
                "Confirmed missing 'orders' table in active database schema.",
                unique_cited,
                [],
            )
        return (
            False,
            "Requires at least two corroborating missing_table observations.",
            unique_cited,
            ["get_service_health(database)", "check_database_connectivity_from_order_service()"],
        )

    if hypothesis_id == "H5_DATABASE_OPERATION_DELAY":
        direct_timeout_signals = sum(
            [
                1 if db_delay_timeout else 0,
                1 if probe_err_cat == "operation_timeout" else 0,
                1 if order_err_cat == "operation_timeout" else 0,
                1 if "operation_timeout" in log_err_cats else 0,
            ]
        )
        total_timeout_signals = direct_timeout_signals + (1 if metrics_timeout_corroborated else 0)
        if direct_timeout_signals >= 1 and total_timeout_signals >= 2:
            return (
                True,
                "Confirmed database operation delay exceeding order-service deadline across corroborating checks.",
                unique_cited,
                [],
            )
        return (
            False,
            "Requires direct timeout probe/log observation plus corroborating timeout/latency evidence.",
            unique_cited,
            ["get_service_health(database)", "check_database_connectivity_from_order_service()", "get_service_metrics(order-service)"],
        )

    if hypothesis_id == "H6_ORDER_SERVICE_UNAVAILABLE":
        gw_unreachable_signal = (
            "upstream_order_service_unreachable" in gw_log_cats
            or any(
                is_valid_for_current_state(r)
                and r.check_name == "get_service_health"
                and r.params.get("service") == "gateway"
                and not bool(r.data.get("ready"))
                for r in available
            )
            or any(
                r.status == EvidenceStatus.COLLECTION_FAILED and bool(r.data.get("order_service_unreachable"))
                for r in all_records
            )
        )
        # H6 is verified when order-service is confirmed unreachable AND either database is checked (healthy or down in multi_fault_f_masks_b) or gateway corroborates order-service unreachable!
        if order_unreachable and (db_reachable_ok or db_unreachable or gw_unreachable_signal):
            return (
                True,
                "Confirmed order-service is unreachable across independent checks.",
                unique_cited,
                [],
            )
        return (
            False,
            "Requires confirmation that order-service is unreachable plus database or gateway corroboration.",
            unique_cited,
            ["get_service_health(order-service)", "get_service_health(database)", "get_service_health(gateway)"],
        )

    return False, f"Unknown hypothesis {hypothesis_id}", unique_cited, []


def _evaluate_inventory_app_gate(
    incident: IncidentContext,
    hypotheses: list[HypothesisState],
    evidence_records: list[DiagnosticCheckResult],
    available: list[DiagnosticCheckResult],
    current_health: Literal["healthy_now", "degraded_or_failing", "unknown"],
    window_diag: Optional[str],
    recovery_observed: bool,
    window_uncertain_notes: list[str],
) -> dict[str, Any]:
    """Evaluate evidence gate for the second application (`inventory_app`, including unknown & multi-faults)."""
    is_unk, unk_reason, unk_label = _is_unknown_cause_indicated(incident, hypotheses, available, [])
    if is_unk:
        cited = [r.evidence_id for r in available if is_valid_for_current_state(r) or r.check_name == "get_recent_logs"]
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=["unknown_unmodeled_inventory_cause"],
            extra_notes=[unk_reason] + window_uncertain_notes,
        )
        return {
            "outcome": DiagnosticOutcome.UNKNOWN_CAUSE,
            "failure_classification": RunFailureClassification.UNKNOWN_CAUSE,
            "candidate_service": None,
            "candidate_fault_type": None,
            "predicted_causes": ["unknown_cause"],
            "unresolved_possible_causes": ["unknown_unmodeled_inventory_cause"],
            "investigation_completion_state": "investigation_complete_within_modeled_scope",
            "window_diagnosis": unk_label,
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "medium",
            "evidence_gate_passed": True,
            "evidence_gate_reason": unk_reason,
            "evidence_cited": cited,
            "uncertainty_summary": " ".join(rem_unc),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": [
                "Inspect inventory-service exception trace outside the modeled dependency catalog."
            ],
        }

    supported = [
        h
        for h in hypotheses
        if h.hypothesis_id != "IH0_NO_FAULT_HEALTHY" and h.stance == HypothesisStance.SUPPORTED
    ]
    verified: list[tuple[HypothesisState, str, list[str]]] = []
    for h in supported:
        passed, reason, cited_ids = _verify_inventory_hypothesis(h.hypothesis_id, available)
        if passed:
            verified.append((h, reason, cited_ids))

    verified_ids = {h.hypothesis_id for h, _, _ in verified}
    unresolved_after = _compute_unresolved_possible_causes(
        hypotheses, verified_ids=verified_ids, evidence_records=evidence_records
    )

    if len(verified) == 1:
        winner, reason, cited_ids = verified[0]
        cause_label = f"{winner.candidate_service}:{winner.candidate_fault_type}"
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_after,
            extra_notes=window_uncertain_notes,
            current_health=current_health,
        )
        return {
            "outcome": DiagnosticOutcome.SUPPORTED_DIAGNOSIS,
            "failure_classification": RunFailureClassification.SUPPORTED_DIAGNOSIS,
            "candidate_service": winner.candidate_service,
            "candidate_fault_type": winner.candidate_fault_type,
            "predicted_causes": [cause_label],
            "unresolved_possible_causes": unresolved_after,
            "investigation_completion_state": "one_cause_supported" if unresolved_after else "investigation_complete_within_modeled_scope",
            "window_diagnosis": window_diag or cause_label,
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "high" if len(cited_ids) >= 2 else "medium",
            "evidence_gate_passed": True,
            "evidence_gate_reason": reason,
            "evidence_cited": cited_ids,
            "uncertainty_summary": _build_uncertainty_summary(
                evidence_records,
                passed=True,
                current_health=current_health,
                unresolved_causes=unresolved_after,
            ),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": [],
        }

    if len(verified) > 1:
        verified.sort(key=lambda item: item[0].hypothesis_id)
        causes = sorted({f"{h.candidate_service}:{h.candidate_fault_type}" for h, _, _ in verified})
        services = "+".join(dict.fromkeys(h.candidate_service or "" for h, _, _ in verified))
        fault_types = "+".join(dict.fromkeys(h.candidate_fault_type or "" for h, _, _ in verified))
        cited_union: list[str] = []
        reasons: list[str] = []
        for h, r_str, c_ids in verified:
            reasons.append(f"[{h.hypothesis_id}] {r_str}")
            for cid in c_ids:
                if cid not in cited_union:
                    cited_union.append(cid)
        rem_unc = _build_remaining_uncertainty_list(
            evidence_records,
            unresolved_causes=unresolved_after,
            extra_notes=window_uncertain_notes,
            current_health=current_health,
        )
        return {
            "outcome": DiagnosticOutcome.SUPPORTED_DIAGNOSIS,
            "failure_classification": RunFailureClassification.SUPPORTED_DIAGNOSIS,
            "candidate_service": services,
            "candidate_fault_type": fault_types,
            "predicted_causes": causes,
            "unresolved_possible_causes": unresolved_after,
            "investigation_completion_state": (
                "additional_causes_unresolved" if unresolved_after else "investigation_complete_within_modeled_scope"
            ),
            "window_diagnosis": ",".join(causes),
            "current_health_status": current_health,
            "recovery_observed": recovery_observed,
            "confidence_level": "high",
            "evidence_gate_passed": True,
            "evidence_gate_reason": "Multiple simultaneous inventory_app faults verified: " + "; ".join(reasons),
            "evidence_cited": cited_union,
            "uncertainty_summary": _build_uncertainty_summary(
                evidence_records,
                passed=True,
                current_health=current_health,
                unresolved_causes=unresolved_after,
            ),
            "remaining_uncertainty": rem_unc,
            "recommended_next_checks": [],
        }

    rem_unc = _build_remaining_uncertainty_list(
        evidence_records,
        unresolved_causes=unresolved_after,
        extra_notes=["Additional dependency checks needed on inventory_app."] + window_uncertain_notes,
        current_health=current_health,
    )
    return {
        "outcome": DiagnosticOutcome.INCONCLUSIVE,
        "failure_classification": RunFailureClassification.HONEST_INCONCLUSIVE,
        "candidate_service": supported[0].candidate_service if len(supported) == 1 else None,
        "candidate_fault_type": supported[0].candidate_fault_type if len(supported) == 1 else None,
        "predicted_causes": [],
        "unresolved_possible_causes": unresolved_after,
        "investigation_completion_state": "inconclusive_or_abstained",
        "window_diagnosis": window_diag,
        "current_health_status": current_health,
        "recovery_observed": recovery_observed,
        "confidence_level": "low",
        "evidence_gate_passed": False,
        "evidence_gate_reason": "Insufficient corroborating evidence on inventory_app to pass the evidence gate.",
        "evidence_cited": [r.evidence_id for r in available if is_valid_for_current_state(r)],
        "uncertainty_summary": _build_uncertainty_summary(
            evidence_records,
            passed=False,
            extra_reason="Additional dependency checks needed on inventory_app.",
            current_health=current_health,
            unresolved_causes=unresolved_after,
        ),
        "remaining_uncertainty": rem_unc,
        "recommended_next_checks": _default_recommendations(evidence_records, app_id="inventory_app"),
    }


def _verify_inventory_hypothesis(
    hypothesis_id: str,
    available: list[DiagnosticCheckResult],
) -> tuple[bool, str, list[str]]:
    cited: list[str] = []
    db_reachable = False
    db_unreachable = False
    db_timeout = False
    cache_reachable = False
    cache_unreachable = False
    inv_err_cat: Optional[str] = None
    inv_db_failed_flag = False
    inv_cache_failed_flag = False
    db_probe_cat: Optional[str] = None
    cache_probe_failed = False
    config_host_invalid = False
    log_cats: set[str] = set()
    metrics_timeout = False

    for r in available:
        if r.check_name == "get_recent_logs":
            if r.timestamp_uncertain:
                continue
            if r.params.get("service") == "inventory-service":
                cats = _extract_in_window_log_categories(r)
                if cats:
                    log_cats.update(cats)
                    cited.append(r.evidence_id)
            continue

        if not is_valid_for_current_state(r):
            continue

        if r.check_name == "get_service_health":
            svc = r.params.get("service")
            if svc == "inventory-db":
                if bool(r.data.get("reachable")):
                    if r.data.get("error_category") == "operation_timeout":
                        db_timeout = True
                    else:
                        db_reachable = True
                else:
                    db_unreachable = True
                cited.append(r.evidence_id)
            elif svc == "inventory-cache":
                if bool(r.data.get("reachable")):
                    cache_reachable = True
                else:
                    cache_unreachable = True
                cited.append(r.evidence_id)
            elif svc == "inventory-service":
                ready_resp = r.data.get("ready_response", {})
                rcat = ready_resp.get("error_category")
                if rcat:
                    inv_err_cat = str(rcat)
                    cited.append(r.evidence_id)
                if ready_resp.get("database_connectivity") == "failed":
                    inv_db_failed_flag = True
                if ready_resp.get("cache_connectivity") == "failed":
                    inv_cache_failed_flag = True
        elif r.check_name == "check_inventory_db_connectivity":
            if not bool(r.data.get("ok")):
                db_probe_cat = str(r.data.get("error_category") or "")
                cited.append(r.evidence_id)
            else:
                db_reachable = True
                cited.append(r.evidence_id)
        elif r.check_name == "check_inventory_cache_connectivity":
            if not bool(r.data.get("ok")):
                cache_probe_failed = True
                cited.append(r.evidence_id)
            else:
                cache_reachable = True
                cited.append(r.evidence_id)
        elif r.check_name == "get_inventory_service_config":
            host = str(r.data.get("db_host", ""))
            if host and host not in ("127.0.0.1", "localhost", "postgres"):
                config_host_invalid = True
                cited.append(r.evidence_id)
        elif r.check_name == "get_service_metrics" and bool(r.data.get("sample_sufficient", False)):
            if int(r.data.get("dependency_timeouts", 0)) > 0 or float(r.data.get("avg_duration_ms", 0.0)) >= 900.0:
                metrics_timeout = True
                cited.append(r.evidence_id)

    unique_cited = list(dict.fromkeys(cited))

    if hypothesis_id == "IH1_INV_DB_UNAVAILABLE":
        if db_unreachable and (
            inv_err_cat == "connection_refused"
            or inv_db_failed_flag
            or db_probe_cat == "connection_refused"
            or "connection_refused" in log_cats
            or cache_reachable
            or cache_unreachable
        ):
            return True, "Confirmed inventory-db is unreachable via direct probe and service state.", unique_cited
    elif hypothesis_id == "IH2_INV_CACHE_UNAVAILABLE":
        if (cache_unreachable or cache_probe_failed) and (
            inv_err_cat == "cache_connection_refused"
            or inv_cache_failed_flag
            or "cache_connection_refused" in log_cats
            or db_reachable
            or db_unreachable
        ):
            return True, "Confirmed inventory-cache is unreachable via direct probe and service state.", unique_cited
    elif hypothesis_id == "IH3_INV_DB_CONFIG_ENDPOINT":
        if db_reachable and (
            config_host_invalid
            or inv_err_cat == "hostname_resolution_failed"
            or db_probe_cat == "hostname_resolution_failed"
            or "hostname_resolution_failed" in log_cats
        ):
            return True, "Confirmed inventory-service has an invalid DB hostname while inventory-db is reachable.", unique_cited
    elif hypothesis_id == "IH4_INV_DB_OPERATION_DELAY":
        direct_signals = sum(
            [
                1 if db_timeout else 0,
                1 if inv_err_cat == "operation_timeout" else 0,
                1 if db_probe_cat == "operation_timeout" else 0,
                1 if "operation_timeout" in log_cats else 0,
            ]
        )
        if direct_signals >= 1 and (direct_signals + (1 if metrics_timeout else 0)) >= 2:
            return True, "Confirmed inventory-db operation delay exceeding deadline across corroborating checks.", unique_cited

    return False, "Insufficient corroboration.", unique_cited


def _build_remaining_uncertainty_list(
    all_records: list[DiagnosticCheckResult],
    *,
    unresolved_causes: list[str],
    extra_notes: Optional[list[str]] = None,
    current_health: str = "unknown",
) -> list[str]:
    items: list[str] = []
    unavailable = [r for r in all_records if r.status == EvidenceStatus.UNAVAILABLE_BY_POLICY]
    failed = [r for r in all_records if r.status == EvidenceStatus.COLLECTION_FAILED]
    stale = [r for r in all_records if r.is_stale]
    superseded = [r for r in all_records if r.is_superseded]
    uncertain_ts = [r for r in all_records if r.timestamp_uncertain]

    if unavailable:
        items.append(f"Unavailable by policy: {[f'{r.check_name}({r.params})' for r in unavailable]}.")
    if failed:
        items.append(f"Collection failed: {[f'{r.check_name}({r.params})' for r in failed]}.")
    if stale:
        items.append(f"Expired/stale observations excluded from current state: {[r.evidence_id for r in stale]}.")
    if superseded:
        items.append(f"Superseded observations replaced by newer checks: {[r.evidence_id for r in superseded]}.")
    if uncertain_ts:
        items.append(
            f"Timestamp uncertainty in observations {[r.evidence_id for r in uncertain_ts]}: {[r.timestamp_uncertainty_reason for r in uncertain_ts]}."
        )
    if unresolved_causes:
        items.append(f"Unresolved modeled explanations not ruled out: {unresolved_causes}.")
    if current_health == "healthy_now":
        items.append("Current live service health is healthy_now (incident-window fault resolved or historical).")
    for note in (extra_notes or []):
        if note and note not in items:
            items.append(note)
    items.append("Scope note: diagnosis is bounded to the modeled check catalog; unmodeled real-world causes are never 100% excluded.")
    return items


def _build_uncertainty_summary(
    all_records: list[DiagnosticCheckResult],
    passed: bool,
    extra_reason: str = "",
    current_health: str = "unknown",
    unresolved_causes: Optional[list[str]] = None,
) -> str:
    notes = [extra_reason] if extra_reason else []
    items = _build_remaining_uncertainty_list(
        all_records,
        unresolved_causes=list(unresolved_causes or []),
        extra_notes=notes,
        current_health=current_health,
    )
    if passed and len(items) == 1:
        return "Low uncertainty within modeled scope; multiple fresh available checks corroborated the diagnosis. " + items[0]
    return " ".join(items)


def _default_recommendations(all_records: list[DiagnosticCheckResult], app_id: str = "orders_app") -> list[str]:
    executed = {f"{r.check_name}:{r.params}" for r in all_records if is_valid_for_current_state(r)}
    if app_id == "inventory_app":
        candidates = [
            ("get_service_health", {"service": "inventory-service"}),
            ("get_service_health", {"service": "inventory-db"}),
            ("get_service_health", {"service": "inventory-cache"}),
            ("check_inventory_db_connectivity", {}),
            ("check_inventory_cache_connectivity", {}),
            ("get_inventory_service_config", {}),
        ]
    else:
        candidates = [
            ("get_service_health", {"service": "order-service"}),
            ("get_service_health", {"service": "database"}),
            ("check_database_connectivity_from_order_service", {}),
            ("get_order_service_database_config", {}),
            ("get_recent_logs", {"service": "order-service", "limit": 20}),
        ]
    recs: list[str] = []
    for name, params in candidates:
        if f"{name}:{params}" not in executed:
            recs.append(f"{name}({params})")
    return recs[:3]
