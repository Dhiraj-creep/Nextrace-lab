"""Shared Hypothesis-Driven Diagnostic Investigation Engine (Stages 1B, 1C, 2, 3, 4, 7 & 8).

Runs a step-by-step investigation loop with centralized stopping policy enforcement:
- Fixed checklists (`deterministic_checklist_v1`, `improved_checklist_v1`)
- Fair early-stopping fixed checklists (`deterministic_checklist_early_stop_v1`, `improved_checklist_early_stop_v1`)
- Rule-based adaptive selector (`rule_adaptive_v1`)
- Scored distinguishing-value vs cost selector & cleanly isolated single-factor ablations
  (`scored_adaptive_v2`, `scored_no_cost_v2`, `scored_no_avail_v2`, `scored_no_reliability_v2`)
- AI selectors (`mock_ai_offline_v1`, `ai_live_v1`, `ai_hybrid_fallback_v1`, `ai_adaptive_v1`)

All methods share the same:
- Allowlisted DiagnosticInterface
- Centralized stopping policy (`stopping_policy.py`)
- Monotonic DeadlineTracker (`budget_ledger.py`)
- Hypothesis state representation, temporal validity, and conflict detector (`hypotheses.py`, `temporal.py`)
- Evidence sufficiency gate (`evidence_gate.py`)
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Protocol

from nextrace_lab.check_catalog import CHECK_CATALOG_VERSION
from nextrace_lab.diagnostic_interface import (
    COST_MODEL_VERSION,
    DiagnosticInterface,
    PreDispatchCallRejectedError,
)
from nextrace_lab.evidence_gate import (
    EVIDENCE_GATE_VERSION,
    OUTCOME_MODEL_VERSION,
    evaluate_evidence_gate,
)
from nextrace_lab.hypotheses import (
    build_initial_hypotheses,
    detect_conflicts,
    recompute_hypotheses_from_history,
    update_hypotheses_with_evidence,
)
from nextrace_lab.logging_utils import utc_now_iso
from nextrace_lab.schemas import (
    APP_ADAPTER_VERSION,
    EVIDENCE_POLICY_VERSION,
    STOPPING_POLICY_VERSION,
    CandidateCheckScore,
    ConflictRecord,
    DecisionLogEntry,
    DiagnosticCheckCall,
    DiagnosticOutcome,
    DiagnosticReport,
    EvidenceStatus,
    HypothesisStance,
    HypothesisState,
    IncidentContext,
    RunFailureClassification,
    StoppingPolicyMode,
)
from nextrace_lab.stopping_policy import (
    evaluate_stopping_policy,
    get_unresolved_additional_hypotheses,
)


class CheckSelectorProtocol(Protocol):
    method_name: str

    def select_next_check(
        self,
        incident: IncidentContext,
        hypotheses: list[HypothesisState],
        interface: DiagnosticInterface,
    ) -> Optional[DiagnosticCheckCall]: ...


def run_investigation_with_selector(
    *,
    run_id: str,
    method_name: str,
    incident: IncidentContext,
    interface: DiagnosticInterface,
    selector: Any,
    stopping_policy_mode: StoppingPolicyMode = "first_supported_cause",
    runtime_mode: Literal["local", "docker"] = "local",
    backend_name: str = "local_sqlite_tcp",
    ai_metadata_provider: Optional[Any] = None,
) -> DiagnosticReport:
    """Execute a complete bounded diagnostic investigation using the provided selector and centralized stopping policy."""
    started_at_utc = utc_now_iso()
    hypotheses = build_initial_hypotheses(incident)
    decision_log: list[DecisionLogEntry] = []
    conflicts: list[ConflictRecord] = []
    step = 0
    max_steps = max(14, interface.budget_limit * 2)
    selector_failed_flag = False
    selector_error_msg: Optional[str] = None
    last_stop_decision = None

    while step < max_steps:
        step += 1
        interface.refresh_staleness_flags()
        recompute_hypotheses_from_history(incident, hypotheses, interface.history)
        conflicts = detect_conflicts(interface.history, conflicts)

        plausible_before = [
            h.hypothesis_id
            for h in hypotheses
            if h.stance in (HypothesisStance.PLAUSIBLE, HypothesisStance.SUPPORTED)
        ]

        # Centralized stopping policy evaluation before selector invocation
        stop_decision = evaluate_stopping_policy(
            incident,
            hypotheses,
            interface,
            conflicts=conflicts,
            mode=stopping_policy_mode,
        )
        last_stop_decision = stop_decision

        if stop_decision.should_stop:
            decision_log.append(
                DecisionLogEntry(
                    step_number=step,
                    timestamp_utc=utc_now_iso(),
                    plausible_hypotheses_before=plausible_before,
                    chosen_check=None,
                    chosen_params={},
                    selection_rationale=stop_decision.explanation,
                    candidate_scores=[],
                    conflicts_active=[c.conflict_id for c in conflicts],
                    budget_used=interface.budget_used,
                    budget_remaining=interface.budget_remaining,
                    stop_decision=True,
                    stop_reason=stop_decision.reason,
                    ai_usage=None,
                )
            )
            break

        ai_step_usage: Optional[dict[str, Any]] = None
        candidate_scores: list[CandidateCheckScore] = []
        try:
            if hasattr(selector, "ledger"):
                call, ai_step_usage = selector.select_next_check(
                    incident, hypotheses, interface, conflicts=conflicts
                )
            elif hasattr(selector, "last_candidate_scores"):
                call = selector.select_next_check(
                    incident, hypotheses, interface, conflicts=conflicts
                )
                candidate_scores = list(getattr(selector, "last_candidate_scores", []))
            else:
                call = selector.select_next_check(incident, hypotheses, interface)
        except Exception as exc:
            selector_failed_flag = True
            selector_error_msg = f"{type(exc).__name__}: {exc}"
            decision_log.append(
                DecisionLogEntry(
                    step_number=step,
                    timestamp_utc=utc_now_iso(),
                    plausible_hypotheses_before=plausible_before,
                    chosen_check=None,
                    chosen_params={},
                    selection_rationale=f"Selector raised exception: {selector_error_msg}",
                    budget_used=interface.budget_used,
                    budget_remaining=interface.budget_remaining,
                    stop_decision=True,
                    stop_reason="selector_exception",
                    ai_usage=ai_step_usage,
                )
            )
            break

        if call is None:
            # Selector had no check to propose; re-evaluate stopping policy
            stop_reason = (
                stop_decision.reason
                if stop_decision.should_stop
                else (
                    "budget_exhausted"
                    if interface.budget_remaining == 0
                    else "no_affordable_informative_checks_remaining"
                )
            )
            decision_log.append(
                DecisionLogEntry(
                    step_number=step,
                    timestamp_utc=utc_now_iso(),
                    plausible_hypotheses_before=plausible_before,
                    chosen_check=None,
                    chosen_params={},
                    selection_rationale=f"Selector returned None ({stop_reason}).",
                    candidate_scores=candidate_scores,
                    conflicts_active=[c.conflict_id for c in conflicts],
                    budget_used=interface.budget_used,
                    budget_remaining=interface.budget_remaining,
                    stop_decision=True,
                    stop_reason=stop_reason,
                    ai_usage=ai_step_usage,
                )
            )
            break

        try:
            res = interface.execute_check(call.check_name, call.params)
        except PreDispatchCallRejectedError as exc:
            decision_log.append(
                DecisionLogEntry(
                    step_number=step,
                    timestamp_utc=utc_now_iso(),
                    plausible_hypotheses_before=plausible_before,
                    chosen_check=call.check_name,
                    chosen_params=call.params,
                    selection_rationale=call.rationale,
                    observation_summary=str(exc),
                    candidate_scores=candidate_scores,
                    conflicts_active=[c.conflict_id for c in conflicts],
                    budget_used=interface.budget_used,
                    budget_remaining=interface.budget_remaining,
                    stop_decision=True,
                    stop_reason=exc.reason,
                    ai_usage=ai_step_usage,
                )
            )
            break

        updates = update_hypotheses_with_evidence(hypotheses, res)
        recompute_hypotheses_from_history(incident, hypotheses, interface.history)
        conflicts = detect_conflicts(interface.history, conflicts)

        decision_log.append(
            DecisionLogEntry(
                step_number=step,
                timestamp_utc=utc_now_iso(),
                plausible_hypotheses_before=plausible_before,
                chosen_check=call.check_name,
                chosen_params=res.params,
                selection_rationale=call.rationale,
                evidence_id=res.evidence_id,
                evidence_status=res.status,
                observation_summary=res.summary,
                hypothesis_updates=updates,
                candidate_scores=candidate_scores,
                conflicts_active=[c.conflict_id for c in conflicts],
                budget_used=interface.budget_used,
                budget_remaining=interface.budget_remaining,
                stop_decision=False,
                stop_reason=None,
                ai_usage=ai_step_usage,
            )
        )

    stale_ids = interface.refresh_staleness_flags()
    recompute_hypotheses_from_history(incident, hypotheses, interface.history)
    conflicts = detect_conflicts(interface.history, conflicts)
    evaluation_utc = utc_now_iso()
    gate = evaluate_evidence_gate(incident, hypotheses, interface.history, conflicts=conflicts)

    unavailable_count = sum(1 for r in interface.history if r.status == EvidenceStatus.UNAVAILABLE_BY_POLICY)
    failed_count = sum(1 for r in interface.history if r.status == EvidenceStatus.COLLECTION_FAILED)
    invalid_count = sum(1 for r in interface.history if r.status == EvidenceStatus.INVALID_CALL)
    superseded_ids = [r.evidence_id for r in interface.history if r.is_superseded]

    ai_meta: Optional[dict[str, Any]] = None
    ai_budget_snap: Optional[dict[str, Any]] = None
    if ai_metadata_provider is not None and hasattr(ai_metadata_provider, "ledger"):
        ai_meta = ai_metadata_provider.ledger.model_dump()
        if hasattr(ai_metadata_provider, "suite_budget_ledger"):
            ai_budget_snap = ai_metadata_provider.suite_budget_ledger.get_run_snapshot(run_id)

    # Determine Stage 1C / Stage 2 failure classification
    failure_class = RunFailureClassification(
        gate.get("failure_classification", RunFailureClassification.HONEST_INCONCLUSIVE)
    )
    if selector_failed_flag:
        failure_class = RunFailureClassification.SELECTOR_FAILURE
    elif gate["outcome"] == DiagnosticOutcome.INCONCLUSIVE:
        if failed_count > 0 and failed_count == len(interface.history):
            failure_class = RunFailureClassification.DIAGNOSTIC_TOOL_FAILURE
        elif interface.budget_remaining == 0 and unavailable_count == 0 and failed_count == 0:
            failure_class = RunFailureClassification.BUDGET_EXHAUSTION
        else:
            failure_class = RunFailureClassification.HONEST_INCONCLUSIVE

    # Unresolved possible causes and investigation completion state
    unresolved_hyps = get_unresolved_additional_hypotheses(incident, hypotheses, interface, gate)
    unresolved_causes = [f"{h.candidate_service}:{h.candidate_fault_type}" for h in unresolved_hyps]
    completion_state = gate.get("investigation_completion_state", "inconclusive_or_abstained")
    rem_uncertainty = list(gate.get("remaining_uncertainty", []))

    # Determine method_version string
    m_ver = "v2" if method_name.endswith("_v2") else "v1"

    return DiagnosticReport(
        run_id=run_id,
        method_name=method_name,
        method_version=m_ver,
        stopping_policy_mode=stopping_policy_mode,
        stopping_policy_version=STOPPING_POLICY_VERSION,
        evidence_gate_version=EVIDENCE_GATE_VERSION,
        evidence_policy_version=EVIDENCE_POLICY_VERSION,
        check_catalog_version=CHECK_CATALOG_VERSION,
        cost_model_version=interface.cost_model_version or COST_MODEL_VERSION,
        outcome_model_version=OUTCOME_MODEL_VERSION,
        app_adapter_version=APP_ADAPTER_VERSION,
        app_id=incident.app_id,
        started_at_utc=started_at_utc,
        completed_at_utc=evaluation_utc,
        evaluation_time_utc=evaluation_utc,
        runtime_mode=runtime_mode,
        backend_name=backend_name,
        evidence_condition=interface.evidence_condition,
        budget_limit=interface.budget_limit,
        budget_used=interface.budget_used,
        attempts_admitted=interface.attempts_admitted,
        successful_observations_count=interface.successful_observations_count,
        rejected_pre_dispatch_count=interface.rejected_pre_dispatch_count,
        checks_executed=len(interface.history),
        unavailable_checks_count=unavailable_count,
        failed_checks_count=failed_count,
        invalid_checks_count=invalid_count,
        redundant_unavailable_checks=interface.redundant_unavailable_checks,
        incident=incident,
        outcome=gate["outcome"],
        failure_classification=failure_class,
        candidate_service=gate["candidate_service"],
        candidate_fault_type=gate["candidate_fault_type"],
        predicted_causes=gate.get("predicted_causes", []),
        unresolved_possible_causes=unresolved_causes,
        investigation_completion_state=completion_state,
        recovery_observed=bool(gate.get("recovery_observed", False)),
        remaining_uncertainty=rem_uncertainty,
        window_diagnosis=gate.get("window_diagnosis"),
        current_health_status=gate.get("current_health_status", "unknown"),
        confidence_level=gate["confidence_level"],
        uncertainty_summary=gate["uncertainty_summary"],
        evidence_cited=gate["evidence_cited"],
        evidence_records=interface.history,
        conflicts_detected=conflicts,
        stale_evidence_ids=stale_ids,
        superseded_evidence_ids=superseded_ids,
        final_hypotheses=hypotheses,
        decision_log=decision_log,
        evidence_gate_passed=gate["evidence_gate_passed"],
        evidence_gate_reason=gate["evidence_gate_reason"],
        recommended_next_checks=gate["recommended_next_checks"],
        ai_metadata=ai_meta,
        ai_budget_snapshot=ai_budget_snap,
        monotonic_elapsed_sec=round(interface.deadline_tracker.elapsed_sec(), 4),
        monotonic_deadline_sec=round(interface.deadline_tracker.max_wall_clock_sec, 4),
        execution_error=selector_error_msg,
    )
