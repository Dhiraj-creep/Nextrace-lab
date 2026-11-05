"""Independent Evaluator: scores DiagnosticReport against private GroundTruthLabel (Stages 1C, 4, 6 & 9).

Computes:
- Service attribution accuracy
- Fault-type accuracy
- Joint root-cause accuracy
- Multi-fault cause-set precision, recall, and exact-set match (Stage 6)
- Unknown-cause recognition and false-certainty avoidance (Stage 6)
- Window-diagnosis vs current-health separation accuracy (Stage 4)
- Supported diagnosis rate & honest inconclusive rate
- Unsupported confident claim rate & overclaim rate
- Explicit RunFailureClassification breakdown (Stage 1C)
- Average budget used, checks executed, redundant unavailable requests, and AI token/USD usage
"""

from __future__ import annotations

from typing import Any

from nextrace_lab.controller import FAULT_CATALOG
from nextrace_lab.schemas import (
    DiagnosticOutcome,
    DiagnosticReport,
    EvaluationScore,
    GroundTruthLabel,
    RunFailureClassification,
    ScenarioName,
)


def get_ground_truth(scenario: ScenarioName) -> GroundTruthLabel:
    """Retrieve private ground-truth label for a scenario."""
    entry = FAULT_CATALOG[scenario]
    return GroundTruthLabel(
        scenario=scenario,
        app_id=entry.get("app_id", "orders_app"),
        split=entry.get("split", "development"),
        expected_is_faulty=bool(entry["expected_is_faulty"]),
        expected_service=entry["expected_service"],
        expected_fault_type=entry["expected_fault_type"],
        expected_causes=list(entry.get("expected_causes", [])),
        identifiable_causes=list(entry.get("identifiable_causes") or entry.get("expected_causes", [])),
        masked_causes=list(entry.get("masked_causes", [])),
        is_multi_fault=bool(entry.get("is_multi_fault", False)),
        is_unknown_cause=bool(entry.get("is_unknown_cause", False)),
        expected_current_health=entry.get("expected_current_health"),
        expected_window_cause=entry.get("expected_window_cause"),
        description=entry["description"],
    )


def score_diagnostic_report(
    report: DiagnosticReport,
    ground_truth: GroundTruthLabel,
    wall_clock_ms: float,
) -> EvaluationScore:
    """Independently score a single DiagnosticReport against its GroundTruthLabel."""
    outcome = report.outcome
    exec_failure = outcome == DiagnosticOutcome.EXECUTION_FAILURE

    expected_set = set(ground_truth.expected_causes)
    pred_list = list(report.predicted_causes)
    if not pred_list and outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS and report.candidate_service and report.candidate_fault_type:
        pred_list = [f"{report.candidate_service}:{report.candidate_fault_type}"]
    pred_set = set(pred_list)

    # Check window vs current health separation (Stage 4)
    window_vs_current_ok: bool | None = None
    if ground_truth.expected_current_health is not None:
        health_ok = report.current_health_status == ground_truth.expected_current_health
        if ground_truth.scenario in ("challenging_recovery_mid_run", "challenging_historical_logs_healthy_now"):
            win_ok = report.window_diagnosis == ground_truth.expected_window_cause
            window_vs_current_ok = bool(health_ok and win_ok)
        else:
            window_vs_current_ok = bool(health_ok)

    unknown_avoided_false_certainty: bool | None = None

    if not ground_truth.expected_is_faulty:
        # Healthy scenario (including challenging_diag_endpoint_failure & challenging_historical_logs_healthy_now)
        service_correct = (outcome == DiagnosticOutcome.NO_FAULT_FOUND) and (report.candidate_service is None)
        fault_type_correct = (outcome == DiagnosticOutcome.NO_FAULT_FOUND) and (report.candidate_fault_type is None)
        joint_accurate = service_correct and fault_type_correct
        supported_diag = outcome == DiagnosticOutcome.NO_FAULT_FOUND and report.evidence_gate_passed
        inconclusive = outcome == DiagnosticOutcome.INCONCLUSIVE
        honest_inconclusive = inconclusive and not report.evidence_gate_passed
        unsupported_claim = outcome in (DiagnosticOutcome.SUPPORTED_DIAGNOSIS, DiagnosticOutcome.NO_FAULT_FOUND) and (
            not report.evidence_gate_passed or len(report.evidence_cited) == 0
        )
        false_attribution = outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
        overclaim = unsupported_claim or false_attribution
        precision = 1.0 if joint_accurate else 0.0
        recall = 1.0 if joint_accurate else 0.0
        exact_match = joint_accurate

    elif ground_truth.is_unknown_cause:
        # Stage 6.4: Unknown / unmodeled application error scenario
        if outcome == DiagnosticOutcome.UNKNOWN_CAUSE:
            service_correct = True
            fault_type_correct = True
            joint_accurate = True
            supported_diag = True
            inconclusive = False
            honest_inconclusive = False
            unsupported_claim = False
            false_attribution = False
            overclaim = False
            unknown_avoided_false_certainty = True
            precision = 1.0
            recall = 1.0
            exact_match = True
        elif outcome == DiagnosticOutcome.INCONCLUSIVE:
            service_correct = False
            fault_type_correct = False
            joint_accurate = False
            supported_diag = False
            inconclusive = True
            honest_inconclusive = True
            unsupported_claim = False
            false_attribution = False
            overclaim = False
            unknown_avoided_false_certainty = True
            precision = 0.0
            recall = 0.0
            exact_match = False
        else:
            # Forced a wrong modeled hypothesis on an unknown cause!
            service_correct = False
            fault_type_correct = False
            joint_accurate = False
            supported_diag = False
            inconclusive = False
            honest_inconclusive = False
            unsupported_claim = True
            false_attribution = True
            overclaim = True
            unknown_avoided_false_certainty = False
            precision = 0.0
            recall = 0.0
            exact_match = False

    elif ground_truth.is_multi_fault:
        # Multi-fault scenario scored by cause-set precision, recall, and exact match
        inter = pred_set & expected_set
        precision = round(len(inter) / len(pred_set), 4) if pred_set else 0.0
        recall = round(len(inter) / len(expected_set), 4) if expected_set else 0.0
        exact_match = (pred_set == expected_set) and (outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS)
        identifiable_set = set(ground_truth.identifiable_causes or ground_truth.expected_causes)
        identifiable_match = (pred_set == identifiable_set) and (outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS)
        service_correct = exact_match
        fault_type_correct = exact_match
        joint_accurate = exact_match
        supported_diag = (outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS) and report.evidence_gate_passed and len(inter) > 0
        inconclusive = outcome == DiagnosticOutcome.INCONCLUSIVE
        honest_inconclusive = inconclusive and not report.evidence_gate_passed
        unsupported_claim = (
            outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
            and (not report.evidence_gate_passed or len(report.evidence_cited) == 0)
        )
        false_attribution = (
            outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS and len(pred_set - expected_set) > 0
        ) or (outcome == DiagnosticOutcome.NO_FAULT_FOUND)
        overclaim = unsupported_claim or false_attribution

    else:
        # Standard single-fault scenario
        is_supported = outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
        service_correct = is_supported and (report.candidate_service == ground_truth.expected_service)
        fault_type_correct = is_supported and (report.candidate_fault_type == ground_truth.expected_fault_type)
        joint_accurate = service_correct and fault_type_correct
        supported_diag = is_supported and report.evidence_gate_passed
        inconclusive = outcome == DiagnosticOutcome.INCONCLUSIVE
        honest_inconclusive = inconclusive and not report.evidence_gate_passed
        unsupported_claim = is_supported and (not report.evidence_gate_passed or len(report.evidence_cited) < 2)
        false_attribution = (is_supported and not joint_accurate) or (outcome == DiagnosticOutcome.NO_FAULT_FOUND)
        overclaim = unsupported_claim or (is_supported and not joint_accurate)
        inter = pred_set & expected_set
        precision = round(len(inter) / len(pred_set), 4) if pred_set else (1.0 if joint_accurate else 0.0)
        recall = round(len(inter) / len(expected_set), 4) if expected_set else (1.0 if joint_accurate else 0.0)
        exact_match = joint_accurate

    notes: list[str] = []
    if exec_failure:
        notes.append(f"Execution failure ({report.failure_classification.value}): {report.execution_error or 'unknown error'}.")
    elif joint_accurate:
        notes.append("Accurate diagnosis supported by cited evidence.")
    elif ground_truth.is_multi_fault and (precision > 0 or recall > 0):
        notes.append(f"Multi-fault partial match: precision={precision:.2f}, recall={recall:.2f}, predicted={sorted(pred_set)}.")
    elif honest_inconclusive:
        notes.append("Honest inconclusive outcome under insufficient/blocked evidence.")
    elif false_attribution:
        notes.append(
            f"False attribution: predicted ({report.candidate_service}, {report.candidate_fault_type}, causes={pred_list}) "
            f"vs expected ({ground_truth.expected_service}, {ground_truth.expected_fault_type}, causes={ground_truth.expected_causes})."
        )
    else:
        notes.append("Did not reach a supported accurate diagnosis.")

    ai_tokens = 0
    ai_cost = 0.0
    ai_fallbacks = 0
    if report.ai_metadata:
        ai_tokens = int(report.ai_metadata.get("total_tokens", 0))
        ai_cost = float(report.ai_metadata.get("estimated_cost_usd", 0.0))
        ai_fallbacks = int(report.ai_metadata.get("fallback_activations", 0))

    return EvaluationScore(
        run_id=report.run_id,
        scenario=ground_truth.scenario,
        app_id=ground_truth.app_id,
        split=ground_truth.split,
        evidence_condition=report.evidence_condition,
        method_name=report.method_name,
        budget_limit=report.budget_limit,
        budget_used=report.budget_used,
        checks_executed=report.checks_executed,
        outcome=outcome,
        failure_classification=report.failure_classification,
        predicted_service=report.candidate_service,
        predicted_fault_type=report.candidate_fault_type,
        predicted_causes=pred_list,
        expected_service=ground_truth.expected_service,
        expected_fault_type=ground_truth.expected_fault_type,
        expected_causes=ground_truth.expected_causes,
        identifiable_causes=ground_truth.identifiable_causes,
        masked_causes=ground_truth.masked_causes,
        service_correct=service_correct,
        fault_type_correct=fault_type_correct,
        joint_root_cause_accurate=joint_accurate,
        cause_set_precision=precision,
        cause_set_recall=recall,
        exact_set_match=exact_match,
        identifiable_set_match=identifiable_match if ground_truth.is_multi_fault else joint_accurate,
        is_multi_fault_scenario=ground_truth.is_multi_fault,
        is_unknown_cause_scenario=ground_truth.is_unknown_cause,
        unknown_cause_avoided_false_certainty=unknown_avoided_false_certainty,
        window_vs_current_separated_correctly=window_vs_current_ok,
        supported_diagnosis=supported_diag,
        inconclusive_outcome=inconclusive,
        honest_inconclusive=honest_inconclusive,
        unsupported_confident_claim=unsupported_claim,
        overclaim_under_insufficient_evidence=overclaim,
        false_attribution_rate_flag=false_attribution,
        execution_failure_flag=exec_failure,
        redundant_unavailable_count=report.redundant_unavailable_checks,
        wall_clock_ms=round(wall_clock_ms, 2),
        ai_tokens_total=ai_tokens,
        ai_estimated_cost_usd=round(ai_cost, 6),
        ai_fallback_count=ai_fallbacks,
        scoring_notes=" ".join(notes),
    )


def _compute_group_metrics(scores: list[EvaluationScore]) -> dict[str, Any]:
    total = len(scores)
    if total == 0:
        return {"total_runs": 0}

    def rate(pred_count: int, denom: int = total) -> float:
        return round(pred_count / denom, 4) if denom > 0 else 0.0

    multi_scores = [s for s in scores if s.is_multi_fault_scenario]
    unknown_scores = [s for s in scores if s.is_unknown_cause_scenario]
    sep_scores = [s for s in scores if s.window_vs_current_separated_correctly is not None]

    failure_class_counts: dict[str, int] = {}
    for cls in RunFailureClassification:
        cnt = sum(1 for s in scores if s.failure_classification == cls)
        if cnt > 0:
            failure_class_counts[cls.value] = cnt

    return {
        "total_runs": total,
        "service_accuracy_rate": rate(sum(1 for s in scores if s.service_correct)),
        "fault_type_accuracy_rate": rate(sum(1 for s in scores if s.fault_type_correct)),
        "joint_root_cause_accuracy_rate": rate(sum(1 for s in scores if s.joint_root_cause_accurate)),
        "cause_set_precision_avg": round(sum(s.cause_set_precision for s in scores) / total, 4),
        "cause_set_recall_avg": round(sum(s.cause_set_recall for s in scores) / total, 4),
        "exact_set_match_rate": rate(sum(1 for s in scores if s.exact_set_match)),
        "multi_fault_runs": len(multi_scores),
        "multi_fault_precision_avg": (
            round(sum(s.cause_set_precision for s in multi_scores) / len(multi_scores), 4)
            if multi_scores
            else None
        ),
        "multi_fault_recall_avg": (
            round(sum(s.cause_set_recall for s in multi_scores) / len(multi_scores), 4)
            if multi_scores
            else None
        ),
        "multi_fault_exact_match_rate": (
            rate(sum(1 for s in multi_scores if s.exact_set_match), len(multi_scores))
            if multi_scores
            else None
        ),
        "unknown_cause_runs": len(unknown_scores),
        "unknown_cause_avoided_false_certainty_rate": (
            rate(sum(1 for s in unknown_scores if s.unknown_cause_avoided_false_certainty), len(unknown_scores))
            if unknown_scores
            else None
        ),
        "window_vs_current_separation_rate": (
            rate(sum(1 for s in sep_scores if s.window_vs_current_separated_correctly), len(sep_scores))
            if sep_scores
            else None
        ),
        "supported_diagnosis_rate": rate(sum(1 for s in scores if s.supported_diagnosis)),
        "inconclusive_rate": rate(sum(1 for s in scores if s.inconclusive_outcome)),
        "honest_inconclusive_rate": rate(sum(1 for s in scores if s.honest_inconclusive)),
        "unsupported_confident_claim_rate": rate(sum(1 for s in scores if s.unsupported_confident_claim)),
        "overclaim_rate": rate(sum(1 for s in scores if s.overclaim_under_insufficient_evidence)),
        "false_attribution_rate": rate(sum(1 for s in scores if s.false_attribution_rate_flag)),
        "execution_failure_rate": rate(sum(1 for s in scores if s.execution_failure_flag)),
        "failure_classification_counts": failure_class_counts,
        "avg_budget_used": round(sum(s.budget_used for s in scores) / total, 2),
        "avg_checks_executed": round(sum(s.checks_executed for s in scores) / total, 2),
        "total_redundant_unavailable_checks": sum(s.redundant_unavailable_count for s in scores),
        "avg_wall_clock_ms": round(sum(s.wall_clock_ms for s in scores) / total, 2),
        "total_ai_tokens": sum(s.ai_tokens_total for s in scores),
        "total_ai_cost_usd": round(sum(s.ai_estimated_cost_usd for s in scores), 6),
        "total_ai_fallbacks": sum(s.ai_fallback_count for s in scores),
    }


def summarize_scores(scores: list[EvaluationScore]) -> dict[str, Any]:
    """Aggregate EvaluationScore list overall and stratified by method, split, evidence, budget, and app."""
    overall = _compute_group_metrics(scores)
    if not scores:
        return overall

    methods = sorted({s.method_name for s in scores})
    splits = sorted({s.split for s in scores})
    conditions = sorted({s.evidence_condition.value for s in scores})
    budgets = sorted({s.budget_limit for s in scores})
    apps = sorted({s.app_id for s in scores})

    by_method = {m: _compute_group_metrics([s for s in scores if s.method_name == m]) for m in methods}
    by_split = {sp: _compute_group_metrics([s for s in scores if s.split == sp]) for sp in splits}
    by_condition = {c: _compute_group_metrics([s for s in scores if s.evidence_condition.value == c]) for c in conditions}
    by_budget = {str(b): _compute_group_metrics([s for s in scores if s.budget_limit == b]) for b in budgets}
    by_app = {a: _compute_group_metrics([s for s in scores if s.app_id == a]) for a in apps}

    by_method_and_split: dict[str, dict[str, Any]] = {}
    for m in methods:
        by_method_and_split[m] = {
            sp: _compute_group_metrics([s for s in scores if s.method_name == m and s.split == sp])
            for sp in splits
        }

    by_method_and_condition: dict[str, dict[str, Any]] = {}
    for m in methods:
        by_method_and_condition[m] = {
            c: _compute_group_metrics([s for s in scores if s.method_name == m and s.evidence_condition.value == c])
            for c in conditions
        }

    by_method_and_budget: dict[str, dict[str, Any]] = {}
    for m in methods:
        by_method_and_budget[m] = {
            str(b): _compute_group_metrics([s for s in scores if s.method_name == m and s.budget_limit == b])
            for b in budgets
        }

    overall["by_method"] = by_method
    overall["by_split"] = by_split
    overall["by_evidence_condition"] = by_condition
    overall["by_budget"] = by_budget
    overall["by_app"] = by_app
    overall["by_method_and_split"] = by_method_and_split
    overall["by_method_and_condition"] = by_method_and_condition
    overall["by_method_and_budget"] = by_method_and_budget
    return overall
