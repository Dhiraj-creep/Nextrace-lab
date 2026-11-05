"""Centralized Stopping Policy for Diagnostic Investigations (Stage 2).

Moves stop/continue decisions out of individual selectors into a shared engine policy so
all compared methods (`deterministic_checklist_early_stop_v1`, `improved_checklist_early_stop_v1`,
`rule_adaptive_v1`, `scored_adaptive_v2`, ablations, and AI selectors) obey identical stopping
rules when given identical evidence.

Modes:
1. `first_supported_cause`
   Stop as soon as the Evidence Gate passes for a supported diagnosis, or when no affordable
   valid check can improve the decision.
2. `investigate_additional_causes`
   After one cause is supported, continue only while remaining budget and available checks
   can test unresolved plausible/weakened/unverified hypotheses on unprobed components under a
   general rule that does not hardcode specific hypothesis IDs or service names.
3. `fixed_no_early_stop`
   Historical reference mode for non-early-stop fixed checklists (`deterministic_checklist_v1`,
   `improved_checklist_v1`), which run until their static sequence ends or budget is exhausted.
4. `legacy_phase3_v1`
   Preserves historical Phase 3 stopping behavior for backward compatibility when explicitly requested.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from nextrace_lab.check_catalog import (
    CHECK_CATALOG,
    get_candidate_check_instances,
    get_expected_outcomes_for_check_instance,
)
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.evidence_gate import evaluate_evidence_gate
from nextrace_lab.schemas import (
    STOPPING_POLICY_VERSION,
    ConflictRecord,
    EvidenceStatus,
    HypothesisStance,
    HypothesisState,
    IncidentContext,
    StoppingPolicyMode,
)
from nextrace_lab.temporal import is_valid_for_current_state


class StoppingDecision(BaseModel):
    """Structured result of evaluating the centralized stopping policy."""

    should_stop: bool
    reason: str
    explanation: str
    mode: StoppingPolicyMode
    policy_version: str = STOPPING_POLICY_VERSION
    evidence_gate_passed: bool = False
    unresolved_hypothesis_ids: list[str] = Field(default_factory=list)
    unresolved_possible_causes: list[str] = Field(default_factory=list)
    investigation_completion_state: str = "in_progress"


def _directly_probed_services(interface: DiagnosticInterface) -> set[str]:
    """Return the set of services that have a temporally valid AVAILABLE direct observation."""
    probed: set[str] = set()
    for r in interface.history:
        if not is_valid_for_current_state(r):
            continue
        svc = str(r.params.get("service", "")).strip()
        if svc and r.check_name == "get_service_health":
            probed.add(svc)
    return probed


def get_unresolved_additional_hypotheses(
    incident: IncidentContext,
    hypotheses: list[HypothesisState],
    interface: DiagnosticInterface,
    gate: Optional[dict[str, Any]] = None,
) -> list[HypothesisState]:
    """Return non-refuted fault hypotheses that remain unresolved after initial gate satisfaction.

    General rule (no hardcoded hypothesis IDs or service names):
    A fault hypothesis `h` (`candidate_service != 'none'` and `stance != REFUTED`) is unresolved if:
    1. `h.stance == SUPPORTED` and its cause string `service:fault_type` is not yet in `gate['predicted_causes']`
       (i.e. observed as supported by a single signal, but not yet corroborated to pass the Evidence Gate), OR
    2. `h.stance in (PLAUSIBLE, WEAKENED)` and its `candidate_service` has not yet been directly probed
       by a temporally valid `get_service_health` check (so an independent co-occurring fault on that
       component has not yet been ruled out).
    """
    if gate is None:
        gate = evaluate_evidence_gate(incident, hypotheses, interface.history)

    verified_causes = set(gate.get("predicted_causes", []))
    probed_services = _directly_probed_services(interface)
    unresolved: list[HypothesisState] = []

    for h in hypotheses:
        if h.candidate_service == "none" or h.hypothesis_id.startswith(("H0_", "IH0_")):
            continue
        if h.stance == HypothesisStance.REFUTED:
            continue
        cause_str = f"{h.candidate_service}:{h.candidate_fault_type}"
        if cause_str in verified_causes:
            continue

        if h.stance == HypothesisStance.SUPPORTED:
            unresolved.append(h)
        elif h.stance in (HypothesisStance.PLAUSIBLE, HypothesisStance.WEAKENED):
            if h.candidate_service not in probed_services:
                unresolved.append(h)

    return unresolved


def get_affordable_checks_for_hypotheses(
    incident: IncidentContext,
    target_hypotheses: list[HypothesisState],
    interface: DiagnosticInterface,
    conflicts: Optional[list[ConflictRecord]] = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Return affordable, non-exhausted candidate checks that can test at least one target hypothesis."""
    if interface.budget_remaining <= 0 or not target_hypotheses:
        return []

    target_ids = {h.hypothesis_id for h in target_hypotheses}
    target_services = {h.candidate_service for h in target_hypotheses if h.candidate_service != "none"}
    supported_unverified = any(h.stance == HypothesisStance.SUPPORTED for h in target_hypotheses)
    active_conflicts = list(conflicts or [])
    needs_conflict_reverify = any(
        c.requires_reverification and c.resolved_by_evidence_id is None
        for c in active_conflicts
    )

    matching_checks: list[tuple[str, dict[str, Any]]] = []
    for check_name, params in get_candidate_check_instances(app_id=incident.app_id):
        spec = CHECK_CATALOG[check_name]
        if spec.cost_units > interface.budget_remaining:
            continue

        prior_same = [
            r
            for r in interface.history
            if interface.canonical_call_key(r.check_name, r.params)
            == interface.canonical_call_key(check_name, params)
        ]
        if any(
            r.status in (EvidenceStatus.UNAVAILABLE_BY_POLICY, EvidenceStatus.COLLECTION_FAILED, EvidenceStatus.INVALID_CALL)
            for r in prior_same
        ):
            continue

        has_fresh_valid = any(is_valid_for_current_state(r) for r in prior_same)
        if has_fresh_valid and not (needs_conflict_reverify and spec.evidence_source == "live_probe" and len(prior_same) < 2):
            continue

        svc = str(params.get("service", "")).strip()
        outcome_map = get_expected_outcomes_for_check_instance(check_name, params, app_id=incident.app_id)
        tests_target_id = bool(target_ids & set(outcome_map.keys()))
        probes_target_service = bool(svc and svc in target_services)

        # When testing unprobed components after one cause is already supported, require either:
        # - corroboration of an already-SUPPORTED unverified hypothesis, or
        # - a direct probe of an unprobed target component.
        if supported_unverified and (tests_target_id or probes_target_service):
            matching_checks.append((check_name, params))
        elif probes_target_service and check_name == "get_service_health":
            matching_checks.append((check_name, params))

    return matching_checks


def has_any_affordable_informative_check(
    incident: IncidentContext,
    interface: DiagnosticInterface,
    conflicts: Optional[list[ConflictRecord]] = None,
) -> bool:
    """Return True if at least one allowlisted check for this app is affordable and not already fresh/unavailable."""
    if interface.budget_remaining <= 0:
        return False
    active_conflicts = list(conflicts or [])
    needs_conflict_reverify = any(
        c.requires_reverification and c.resolved_by_evidence_id is None
        for c in active_conflicts
    )
    for check_name, params in get_candidate_check_instances(app_id=incident.app_id):
        spec = CHECK_CATALOG[check_name]
        if spec.cost_units > interface.budget_remaining:
            continue
        prior_same = [
            r
            for r in interface.history
            if interface.canonical_call_key(r.check_name, r.params)
            == interface.canonical_call_key(check_name, params)
        ]
        if any(
            r.status in (EvidenceStatus.UNAVAILABLE_BY_POLICY, EvidenceStatus.COLLECTION_FAILED, EvidenceStatus.INVALID_CALL)
            for r in prior_same
        ):
            continue
        has_fresh_valid = any(is_valid_for_current_state(r) for r in prior_same)
        if has_fresh_valid and not (needs_conflict_reverify and spec.evidence_source == "live_probe" and len(prior_same) < 2):
            continue
        return True
    return False


def evaluate_stopping_policy(
    incident: IncidentContext,
    hypotheses: list[HypothesisState],
    interface: DiagnosticInterface,
    conflicts: Optional[list[ConflictRecord]] = None,
    mode: StoppingPolicyMode = "first_supported_cause",
) -> StoppingDecision:
    """Evaluate the shared stopping policy for the current investigation state."""
    interface.refresh_staleness_flags()
    active_conflicts = list(conflicts or [])
    gate = evaluate_evidence_gate(incident, hypotheses, interface.history, conflicts=active_conflicts)
    gate_passed = bool(gate.get("evidence_gate_passed", False))

    unresolved_hyps = get_unresolved_additional_hypotheses(incident, hypotheses, interface, gate)
    unresolved_ids = [h.hypothesis_id for h in unresolved_hyps]
    unresolved_causes = [f"{h.candidate_service}:{h.candidate_fault_type}" for h in unresolved_hyps]

    # 1. Fixed non-early-stop mode (historical baseline reference only)
    if mode == "fixed_no_early_stop":
        if interface.budget_remaining <= 0:
            return StoppingDecision(
                should_stop=True,
                reason="budget_exhausted",
                explanation="Remaining diagnostic budget is 0.",
                mode=mode,
                evidence_gate_passed=gate_passed,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state="completed_budget_exhausted",
            )
        return StoppingDecision(
            should_stop=False,
            reason="continue_fixed_sequence",
            explanation="Fixed checklist continues until static sequence ends or budget is exhausted.",
            mode=mode,
            evidence_gate_passed=gate_passed,
            unresolved_hypothesis_ids=unresolved_ids,
            unresolved_possible_causes=unresolved_causes,
            investigation_completion_state="in_progress",
        )

    # 2. First supported cause mode
    if mode == "first_supported_cause":
        if gate_passed:
            return StoppingDecision(
                should_stop=True,
                reason="evidence_gate_satisfied",
                explanation=(
                    "Centralized stopping policy (`first_supported_cause`): Evidence Gate passed "
                    f"for diagnosis ({gate.get('outcome')})."
                ),
                mode=mode,
                evidence_gate_passed=True,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state="completed_first_supported_cause",
            )
        if interface.budget_remaining <= 0:
            return StoppingDecision(
                should_stop=True,
                reason="budget_exhausted",
                explanation="Centralized stopping policy (`first_supported_cause`): diagnostic budget exhausted.",
                mode=mode,
                evidence_gate_passed=False,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state="stopped_budget_exhausted",
            )
        if not has_any_affordable_informative_check(incident, interface, conflicts=active_conflicts):
            return StoppingDecision(
                should_stop=True,
                reason="no_affordable_informative_checks_remaining",
                explanation=(
                    "Centralized stopping policy (`first_supported_cause`): no affordable valid checks "
                    "remain that can improve the decision."
                ),
                mode=mode,
                evidence_gate_passed=False,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state="stopped_no_informative_checks",
            )
        return StoppingDecision(
            should_stop=False,
            reason="continue_until_supported_cause",
            explanation="Evidence Gate not yet satisfied and affordable informative checks remain.",
            mode=mode,
            evidence_gate_passed=False,
            unresolved_hypothesis_ids=unresolved_ids,
            unresolved_possible_causes=unresolved_causes,
            investigation_completion_state="in_progress",
        )

    # 3. Investigate additional causes mode
    if mode in ("investigate_additional_causes", "legacy_phase3_v1"):
        if interface.budget_remaining <= 0:
            return StoppingDecision(
                should_stop=True,
                reason="budget_exhausted",
                explanation=f"Centralized stopping policy (`{mode}`): diagnostic budget exhausted.",
                mode=mode,
                evidence_gate_passed=gate_passed,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state=(
                    "completed_partial_multi_cause_budget_exhausted" if gate_passed else "stopped_budget_exhausted"
                ),
            )

        if not gate_passed:
            if not has_any_affordable_informative_check(incident, interface, conflicts=active_conflicts):
                return StoppingDecision(
                    should_stop=True,
                    reason="no_affordable_informative_checks_remaining",
                    explanation=f"Centralized stopping policy (`{mode}`): no affordable valid checks remain.",
                    mode=mode,
                    evidence_gate_passed=False,
                    unresolved_hypothesis_ids=unresolved_ids,
                    unresolved_possible_causes=unresolved_causes,
                    investigation_completion_state="stopped_no_informative_checks",
                )
            return StoppingDecision(
                should_stop=False,
                reason="continue_initial_diagnosis",
                explanation="Evidence Gate not yet satisfied; continuing investigation.",
                mode=mode,
                evidence_gate_passed=False,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state="in_progress",
            )

        # Gate passed: check whether unresolved additional hypotheses can still be tested within budget
        affordable_additional = get_affordable_checks_for_hypotheses(
            incident, unresolved_hyps, interface, conflicts=active_conflicts
        )
        if unresolved_hyps and affordable_additional:
            return StoppingDecision(
                should_stop=False,
                reason="continue_for_unresolved_additional_causes",
                explanation=(
                    f"Centralized stopping policy (`{mode}`): primary diagnosis is supported, "
                    f"but {len(unresolved_hyps)} unresolved hypothesis(es) ({', '.join(unresolved_ids)}) "
                    f"have {len(affordable_additional)} affordable check(s) remaining."
                ),
                mode=mode,
                evidence_gate_passed=True,
                unresolved_hypothesis_ids=unresolved_ids,
                unresolved_possible_causes=unresolved_causes,
                investigation_completion_state="investigating_additional_causes",
            )

        completion_state = (
            "completed_all_plausible_causes_tested"
            if not unresolved_hyps
            else "completed_primary_supported_additional_untestable"
        )
        return StoppingDecision(
            should_stop=True,
            reason="evidence_gate_satisfied",
            explanation=(
                f"Centralized stopping policy (`{mode}`): Evidence Gate satisfied and no further "
                "affordable checks can test unresolved hypotheses."
            ),
            mode=mode,
            evidence_gate_passed=True,
            unresolved_hypothesis_ids=unresolved_ids,
            unresolved_possible_causes=unresolved_causes,
            investigation_completion_state=completion_state,
        )

    raise ValueError(f"Unsupported stopping policy mode: {mode}")
