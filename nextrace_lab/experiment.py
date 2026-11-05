"""Experiment Runner: executes comparative experiments with shared AI budget ledger, counterbalanced ordering, and failure-safe artifact persistence (Stages 1, 6, 8 & 9).

Guarantees:
1. Cross-process `LabExecutionLock` protection for all experiment runs (Stage 1E).
2. Shared `SuiteAIBudgetLedger` across all runs in a suite (Stage 1A).
3. Monotonic `DeadlineTracker` enforced on every run (Stage 1B).
4. Explicit `RunFailureClassification` preserved in JSON/CSV/Markdown artifacts even when setup,
   diagnosis, or reset fails (Stage 1C).
5. Seed-recorded counterbalanced method execution order with clean per-run environment reset (Stage 9).
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
from typing import Any, Literal, Optional
import uuid

from nextrace_lab.baseline import SUPPORTED_METHODS, run_diagnostic_investigation
from nextrace_lab.budget_ledger import DeadlineTracker, SuiteAIBudgetLedger
from nextrace_lab.controller import (
    FAULT_CATALOG,
    ROOT_DIR,
    apply_fault,
    get_backend_name,
    reset_faults,
    resolve_runtime_mode,
     set_evidence_condition,
    start_healthy_environment,
    start_healthy_inventory_environment,
    submit_inventory_reservation,
    submit_order,
    trigger_mid_run_recovery,
)
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.evaluator import get_ground_truth, score_diagnostic_report, summarize_scores
from nextrace_lab.lab_lock import acquire_lab_lock
from nextrace_lab.logging_utils import utc_now_iso
from nextrace_lab.manifest_utils import compute_content_manifest
from nextrace_lab.schemas import (
    DiagnosticOutcome,
    DiagnosticReport,
    EvidenceCondition,
    EvaluationScore,
    IncidentContext,
    RunFailureClassification,
    ScenarioName,
)

ARTIFACTS_DIR = ROOT_DIR / "artifacts" / "experiments"

SCENARIOS_DEFAULT: list[ScenarioName] = [
    "healthy",
    "fault_a",
    "fault_b",
    "fault_c",
    "fault_d",
    "fault_e",
    "fault_f",
]
EVIDENCE_CONDITIONS_DEFAULT: list[EvidenceCondition] = [
    EvidenceCondition.E0,
    EvidenceCondition.E1,
    EvidenceCondition.E2,
    EvidenceCondition.E3,
]


def _get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "uncommitted-worktree"


def _compute_config_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def run_single_experiment(
    scenario: ScenarioName,
    evidence_condition: EvidenceCondition,
    budget_limit: int = 8,
    method_name: str = "deterministic_checklist_v1",
    runtime: Optional[str] = None,
    repetition: int = 1,
    ai_provider: Literal["gemini", "openai", "mock-deterministic"] = "mock-deterministic",
    ai_model_name: Optional[str] = None,
    suite_budget_ledger: Optional[SuiteAIBudgetLedger] = None,
    max_wall_clock_sec: float = 20.0,
    stopping_policy_mode: Optional[Any] = None,
) -> tuple[DiagnosticReport, EvaluationScore]:
    """Execute one controlled scenario run end-to-end and ALWAYS return a valid (DiagnosticReport, EvaluationScore)."""
    with acquire_lab_lock(f"run_single_experiment:{scenario}:{method_name}"):
        mode = resolve_runtime_mode(runtime)
        gt = get_ground_truth(scenario)
        app_id = gt.app_id
        backend = get_backend_name(mode, app_id=app_id)

        if stopping_policy_mode is not None:
            effective_stopping_mode = stopping_policy_mode
        elif gt.is_multi_fault:
            effective_stopping_mode = "investigate_additional_causes"
        elif method_name in ("deterministic_checklist_v1", "improved_checklist_v1"):
            effective_stopping_mode = "fixed_no_early_stop"
        else:
            effective_stopping_mode = "first_supported_cause"
        started_wall = time.perf_counter()
        started_utc = utc_now_iso()
        method_short = method_name.replace("_v1", "").replace("deterministic_", "det_")
        run_id = f"run-{scenario}-{evidence_condition.value.lower()}-b{budget_limit}-{method_short}-r{repetition}-{uuid.uuid4().hex[:6]}"
        req_id = f"exp-{scenario}-{evidence_condition.value.lower()}-{uuid.uuid4().hex[:6]}"

        deadline_tracker = DeadlineTracker(max_wall_clock_sec=max_wall_clock_sec)

        setup_error: Optional[str] = None
        diagnosis_error: Optional[str] = None
        reset_error: Optional[str] = None
        http_status: int = 0
        body: dict[str, Any] = {}

        def _after_check_hook(step_num: int, _res: Any) -> None:
            if scenario == "challenging_recovery_mid_run" and step_num == 1:
                try:
                    trigger_mid_run_recovery()
                    interface.advance_simulated_clock(35.0)
                except Exception:
                    pass

        interface = DiagnosticInterface(
            evidence_condition=evidence_condition,
            budget_limit=budget_limit,
            app_id=app_id,
            deadline_tracker=deadline_tracker,
            on_after_check_hook=_after_check_hook if scenario == "challenging_recovery_mid_run" else None,
        )

        # Phase 1: Setup & Incident Trigger
        try:
            set_evidence_condition(evidence_condition)
            if scenario == "healthy":
                start_healthy_environment(runtime=mode)
            elif scenario == "inv_healthy":
                start_healthy_inventory_environment(runtime=mode)
            else:
                apply_fault(scenario, runtime=mode)

            # Submit two requests so service metrics have sample_count >= 2 (minimum_sample_threshold=2)
            if app_id == "inventory_app":
                submit_inventory_reservation(sku="sku-laptop-101", quantity=1, request_id=f"{req_id}-warmup")
                http_status, body = submit_inventory_reservation(sku="sku-laptop-101", quantity=2, request_id=req_id)
            else:
                submit_order(product_id="sku-router-01", quantity=1, request_id=f"{req_id}-warmup")
                http_status, body = submit_order(product_id="sku-router-01", quantity=1, request_id=req_id)
        except Exception as exc:
            setup_error = f"Setup/Incident trigger failed: {type(exc).__name__}: {exc}"

        entry_ep = "POST /inventory/reserve" if app_id == "inventory_app" else "POST /orders"
        incident = IncidentContext(
            incident_id=f"inc-{uuid.uuid4().hex[:10]}",
            observed_at_utc=utc_now_iso(),
            app_id=app_id,
            entry_endpoint=entry_ep,
            request_id=req_id,
            http_status=http_status,
            symptom_summary=(
                f"{entry_ep} returned HTTP {http_status}"
                + (" (order/reservation failed)" if http_status >= 400 else " (succeeded)")
                + (f" [SETUP ERROR: {setup_error}]" if setup_error else "")
            ),
            response_excerpt=body,
        )

        # Phase 2: Diagnostic Investigation
        report: Optional[DiagnosticReport] = None
        if setup_error is None:
            try:
                report = run_diagnostic_investigation(
                    incident=incident,
                    interface=interface,
                    method_name=method_name,
                    stopping_policy_mode=effective_stopping_mode,
                    runtime_mode=mode,
                    backend_name=backend,
                    run_id=run_id,
                    ai_provider=ai_provider,
                    ai_model_name=ai_model_name,
                    suite_budget_ledger=suite_budget_ledger,
                    deadline_tracker=deadline_tracker,
                )
            except Exception as exc:
                diagnosis_error = f"Diagnostic execution failed: {type(exc).__name__}: {exc}"

        # Phase 3: Always attempt environment reset
        try:
            reset_faults(runtime=mode, app_id=app_id)
        except Exception as exc:
            reset_error = f"Reset failed: {type(exc).__name__}: {exc}"

        wall_clock_ms = (time.perf_counter() - started_wall) * 1000.0
        combined_errors = [e for e in (setup_error, diagnosis_error, reset_error) if e]

        if report is None:
            error_msg = " | ".join(combined_errors) if combined_errors else "Unknown execution failure"
            f_class = (
                RunFailureClassification.SETUP_FAILURE
                if setup_error
                else (
                    RunFailureClassification.RECOVERY_FAILURE
                    if reset_error and not diagnosis_error
                    else RunFailureClassification.SELECTOR_FAILURE
                )
            )
            report = DiagnosticReport(
                run_id=run_id,
                method_name=method_name,
                method_version="v1",
                app_id=app_id,
                started_at_utc=started_utc,
                completed_at_utc=utc_now_iso(),
                evaluation_time_utc=utc_now_iso(),
                runtime_mode=mode,
                backend_name=backend,
                evidence_condition=evidence_condition,
                budget_limit=budget_limit,
                budget_used=interface.budget_used,
                checks_executed=len(interface.history),
                unavailable_checks_count=0,
                failed_checks_count=0,
                invalid_checks_count=0,
                redundant_unavailable_checks=interface.redundant_unavailable_checks,
                incident=incident,
                outcome=DiagnosticOutcome.EXECUTION_FAILURE,
                failure_classification=f_class,
                candidate_service=None,
                candidate_fault_type=None,
                predicted_causes=[],
                confidence_level="low",
                uncertainty_summary=f"Run aborted due to execution error: {error_msg}",
                evidence_cited=[],
                evidence_records=interface.history,
                final_hypotheses=[],
                decision_log=[],
                evidence_gate_passed=False,
                evidence_gate_reason=f"Execution failure: {error_msg}",
                recommended_next_checks=[],
                monotonic_elapsed_sec=round(deadline_tracker.elapsed_sec(), 4),
                monotonic_deadline_sec=round(deadline_tracker.max_wall_clock_sec, 4),
                execution_error=error_msg,
            )
        elif reset_error is not None:
            report.execution_error = (f"{report.execution_error} | {reset_error}" if report.execution_error else reset_error)
            report.failure_classification = RunFailureClassification.RECOVERY_FAILURE

        score = score_diagnostic_report(report=report, ground_truth=gt, wall_clock_ms=wall_clock_ms)
        return report, score


def run_experiment_suite(
    scenarios: Optional[list[ScenarioName]] = None,
    evidence_conditions: Optional[list[EvidenceCondition]] = None,
    budgets: Optional[list[int]] = None,
    methods: Optional[list[str]] = None,
    repetitions: int = 1,
    runtime: Optional[str] = None,
    tag: str = "comparative",
    ai_provider: Literal["gemini", "openai", "mock-deterministic"] = "mock-deterministic",
    ai_model_name: Optional[str] = None,
    random_seed: int = 42,
    counterbalance_methods: bool = True,
    max_suite_ai_calls: int = 300,
    max_suite_ai_tokens: int = 600_000,
    max_suite_ai_usd: float = 2.00,
    max_wall_clock_sec: float = 20.0,
    stopping_policy_mode: Optional[str] = None,
) -> dict[str, Any]:
    """Execute a full comparative matrix of scenarios x evidence_conditions x budgets x methods x repetitions."""
    with acquire_lab_lock(f"run_experiment_suite:{tag}"):
        mode = resolve_runtime_mode(runtime)
        scen_list = scenarios or list(SCENARIOS_DEFAULT)
        cond_list = evidence_conditions or list(EVIDENCE_CONDITIONS_DEFAULT)
        budget_list = budgets or [8]
        method_list = methods or ["deterministic_checklist_v1", "improved_checklist_v1", "rule_adaptive_v1"]

        for m in method_list:
            if m not in SUPPORTED_METHODS:
                raise ValueError(f"Unsupported method '{m}'. Allowed: {SUPPORTED_METHODS}")

        apps_involved = sorted({get_ground_truth(s).app_id for s in scen_list})
        backend = ", ".join(get_backend_name(mode, app_id=a) for a in apps_involved)

        # Source Content Manifest Digest (Stage 8)
        content_manifest = compute_content_manifest(ROOT_DIR)
        manifest_digest = content_manifest["manifest_digest_sha256"]

        # Shared Suite-Wide AI Budget Ledger (Stage 1A)
        suite_ledger = SuiteAIBudgetLedger(
            max_calls_per_run=6,
            max_calls_per_suite=max_suite_ai_calls,
            max_tokens_per_run=24_000,
            max_tokens_per_suite=max_suite_ai_tokens,
            max_usd_per_run=0.15,
            max_usd_per_suite=max_suite_ai_usd,
        )

        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        git_commit = _get_git_commit()
        config_payload = {
            "scenarios": scen_list,
            "evidence_conditions": [c.value for c in cond_list],
            "budgets": budget_list,
            "methods": method_list,
            "repetitions": repetitions,
            "runtime": mode,
            "backend": backend,
            "ai_provider": ai_provider,
            "ai_model_name": ai_model_name,
            "random_seed": random_seed,
            "counterbalance_methods": counterbalance_methods,
            "stopping_policy_mode": stopping_policy_mode,
            "content_manifest_digest_sha256": manifest_digest,
        }
        cfg_hash = _compute_config_hash(config_payload)
        experiment_id = f"exp-{tag}-{timestamp_slug}-{cfg_hash[:6]}"
        exp_dir = ARTIFACTS_DIR / experiment_id
        runs_dir = exp_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        reports: list[DiagnosticReport] = []
        scores: list[EvaluationScore] = []
        execution_order_log: list[dict[str, Any]] = []

        rng = random.Random(random_seed)
        block_index = 0

        try:
            for rep in range(1, repetitions + 1):
                for scen in scen_list:
                    for cond in cond_list:
                        for b_limit in budget_list:
                            block_index += 1
                            # Counterbalance method execution order per block (Stage 9)
                            ordered_methods = list(method_list)
                            if counterbalance_methods and len(ordered_methods) > 1:
                                shift = (block_index - 1) % len(ordered_methods)
                                ordered_methods = ordered_methods[shift:] + ordered_methods[:shift]
                                if rep > 1:
                                    rng.shuffle(ordered_methods)

                            execution_order_log.append(
                                {
                                    "block_index": block_index,
                                    "repetition": rep,
                                    "scenario": scen,
                                    "evidence_condition": cond.value,
                                    "budget_limit": b_limit,
                                    "method_order": ordered_methods,
                                }
                            )

                            for m_name in ordered_methods:
                                report, score = run_single_experiment(
                                    scenario=scen,
                                    evidence_condition=cond,
                                    budget_limit=b_limit,
                                    method_name=m_name,
                                    runtime=mode,
                                    repetition=rep,
                                    ai_provider=ai_provider,
                                    ai_model_name=ai_model_name,
                                    suite_budget_ledger=suite_ledger,
                                    max_wall_clock_sec=max_wall_clock_sec,
                                    stopping_policy_mode=stopping_policy_mode,
                                )
                                reports.append(report)
                                scores.append(score)

                                run_path = runs_dir / f"{report.run_id}.json"
                                with open(run_path, "w", encoding="utf-8") as fh:
                                    json.dump(
                                        {
                                            "report": report.model_dump(),
                                            "evaluation": score.model_dump(),
                                        },
                                        fh,
                                        indent=2,
                                    )
        finally:
            try:
                set_evidence_condition(EvidenceCondition.E0)
                if "inventory_app" in apps_involved:
                    reset_faults(runtime=mode, app_id="inventory_app")
                if "orders_app" in apps_involved:
                    reset_faults(runtime=mode, app_id="orders_app")
            except Exception:
                pass

        summary = summarize_scores(scores)
        suite_budget_snap = suite_ledger.get_suite_snapshot()
        summary["suite_ai_budget_ledger"] = suite_budget_snap

        manifest = {
            "experiment_id": experiment_id,
            "created_at_utc": utc_now_iso(),
            "git_commit": git_commit,
            "content_manifest_digest_sha256": manifest_digest,
            "config_hash": cfg_hash,
            "random_seed": random_seed,
            "counterbalance_methods": counterbalance_methods,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "runtime_mode": mode,
            "backend_name": backend,
            "apps_evaluated": apps_involved,
            "scenarios": scen_list,
            "evidence_conditions": [c.value for c in cond_list],
            "budgets": budget_list,
            "methods": method_list,
            "repetitions": repetitions,
            "stopping_policy_mode": stopping_policy_mode,
            "ai_provider": ai_provider if any("ai_" in m for m in method_list) else None,
            "ai_is_mock": (ai_provider == "mock-deterministic") if any("ai_" in m for m in method_list) else None,
            "suite_ai_budget_ledger": suite_budget_snap,
            "counterbalanced_execution_blocks": execution_order_log,
            "summary": summary,
        }

        manifest_path = exp_dir / "manifest.json"
        summary_json_path = exp_dir / "summary.json"
        summary_csv_path = exp_dir / "scores.csv"
        summary_md_path = exp_dir / "summary.md"

        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)

        with open(summary_json_path, "w", encoding="utf-8") as fh:
            json.dump({"manifest": manifest, "scores": [s.model_dump() for s in scores]}, fh, indent=2)

        if scores:
            fieldnames = list(scores[0].model_dump().keys())
            with open(summary_csv_path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                for s in scores:
                    writer.writerow(s.model_dump())

        md_content = _render_markdown_summary(manifest, scores)
        with open(summary_md_path, "w", encoding="utf-8") as fh:
            fh.write(md_content)

        return {
            "experiment_id": experiment_id,
            "artifact_dir": str(exp_dir),
            "manifest_path": str(manifest_path),
            "summary_json_path": str(summary_json_path),
            "summary_csv_path": str(summary_csv_path),
            "summary_md_path": str(summary_md_path),
            "summary": summary,
        }


def _render_markdown_summary(manifest: dict[str, Any], scores: list[EvaluationScore]) -> str:
    summary = manifest["summary"]
    lines = [
        f"# NexTrace Comparative Experiment Report — `{manifest['experiment_id']}`",
        "",
        "## 1. Provenance & Environment Metadata",
        f"- **Created (UTC)**: `{manifest['created_at_utc']}`",
        f"- **Git Commit**: `{manifest['git_commit']}`",
        f"- **Source Content Manifest Digest (SHA-256)**: `{manifest.get('content_manifest_digest_sha256', 'unknown')}`",
        f"- **Config Hash**: `{manifest['config_hash']}`",
        f"- **Stopping Policy Mode**: `{manifest.get('stopping_policy_mode', 'default_per_scenario')}`",
        f"- **Random Seed**: `{manifest.get('random_seed', 42)}` (`counterbalance_methods={manifest.get('counterbalance_methods', True)}`)",
        f"- **Runtime Mode**: `{manifest['runtime_mode']}`",
        f"- **Active Backend(s)**: `{manifest['backend_name']}`",
        f"- **Applications Evaluated**: `{manifest.get('apps_evaluated', ['orders_app'])}`",
        f"- **Python / Platform**: `{manifest['python_version']}` on `{manifest['platform']}`",
        f"- **Methods Compared**: `{manifest['methods']}`",
        f"- **Budgets Evaluated**: `{manifest['budgets']}`",
        f"- **Evidence Conditions**: `{manifest['evidence_conditions']}`",
        f"- **Repetitions per Cell**: `{manifest['repetitions']}`",
    ]
    if manifest.get("ai_provider"):
        lines.append(
            f"- **AI Provider**: `{manifest['ai_provider']}` (`is_mock_ai={manifest['ai_is_mock']}`)"
        )
    lines.extend(["", "## 2. Aggregate Comparison by Method", ""])

    by_method = summary.get("by_method", {})
    if by_method:
        lines.extend(
            [
                "| Method | Runs | Joint Root-Cause Acc | Cause-Set Precision | Cause-Set Recall | Supported Diag Rate | Honest Inconclusive | Overclaim Rate | Avg Budget Used | Avg Checks | Redundant Unavail |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for m_name, m_stats in by_method.items():
            lines.append(
                f"| `{m_name}` | {m_stats['total_runs']} | {m_stats['joint_root_cause_accuracy_rate']:.2%} | "
                f"{m_stats.get('cause_set_precision_avg', 0.0):.2%} | {m_stats.get('cause_set_recall_avg', 0.0):.2%} | "
                f"{m_stats['supported_diagnosis_rate']:.2%} | {m_stats['honest_inconclusive_rate']:.2%} | "
                f"{m_stats['overclaim_rate']:.2%} | {m_stats['avg_budget_used']:.2f} | "
                f"{m_stats['avg_checks_executed']:.2f} | {m_stats['total_redundant_unavailable_checks']} |"
            )

    lines.extend(["", "## 3. Method Performance by Scenario Split", ""])
    by_ms = summary.get("by_method_and_split", {})
    if by_ms:
        lines.extend(
            [
                "| Method | Split | Runs | Joint Root-Cause Acc | Exact Set Match | Supported Rate | Honest Inconclusive | Overclaim Rate | Avg Budget |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for m_name, split_map in by_ms.items():
            for sp, st in split_map.items():
                if st.get("total_runs", 0) == 0:
                    continue
                lines.append(
                    f"| `{m_name}` | `{sp}` | {st['total_runs']} | {st['joint_root_cause_accuracy_rate']:.2%} | "
                    f"{st.get('exact_set_match_rate', 0.0):.2%} | {st['supported_diagnosis_rate']:.2%} | "
                    f"{st['honest_inconclusive_rate']:.2%} | {st['overclaim_rate']:.2%} | {st['avg_budget_used']:.2f} |"
                )

    lines.extend(["", "## 4. Method Performance by Evidence Condition (E0–E5)", ""])
    by_mc = summary.get("by_method_and_condition", {})
    if by_mc:
        lines.extend(
            [
                "| Method | Condition | Runs | Joint Root-Cause Acc | Supported Rate | Honest Inconclusive | Overclaim Rate | Avg Budget |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for m_name, cond_map in by_mc.items():
            for cond, st in cond_map.items():
                if st.get("total_runs", 0) == 0:
                    continue
                lines.append(
                    f"| `{m_name}` | `{cond}` | {st['total_runs']} | {st['joint_root_cause_accuracy_rate']:.2%} | "
                    f"{st['supported_diagnosis_rate']:.2%} | {st['honest_inconclusive_rate']:.2%} | "
                    f"{st['overclaim_rate']:.2%} | {st['avg_budget_used']:.2f} |"
                )

    lines.extend(["", "## 5. Method Performance by Budget Limit", ""])
    by_mb = summary.get("by_method_and_budget", {})
    if by_mb:
        lines.extend(
            [
                "| Method | Budget | Runs | Joint Root-Cause Acc | Supported Rate | Honest Inconclusive | Avg Budget Used |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for m_name, b_map in by_mb.items():
            for b_str, st in b_map.items():
                if st.get("total_runs", 0) == 0:
                    continue
                lines.append(
                    f"| `{m_name}` | `{b_str}` | {st['total_runs']} | {st['joint_root_cause_accuracy_rate']:.2%} | "
                    f"{st['supported_diagnosis_rate']:.2%} | {st['honest_inconclusive_rate']:.2%} | {st['avg_budget_used']:.2f} |"
                )

    lines.extend(
        [
            "",
            "## 6. Per-Run Score Table",
            "",
            "| Run ID | App | Scenario | Split | Cond | Method | Budget (Used/Lim) | Checks | Outcome | Class | Predicted Causes | Expected Causes | Joint Acc | Set Prec/Rec |",
            "|---|---|---|---|---|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for s in scores:
        pred_c = ", ".join(s.predicted_causes) if s.predicted_causes else f"{s.predicted_service}:{s.predicted_fault_type}"
        exp_c = ", ".join(s.expected_causes) if s.expected_causes else f"{s.expected_service}:{s.expected_fault_type}"
        lines.append(
            f"| `{s.run_id}` | `{s.app_id}` | `{s.scenario}` | `{s.split}` | `{s.evidence_condition.value}` | `{s.method_name}` | "
            f"{s.budget_used}/{s.budget_limit} | {s.checks_executed} | `{s.outcome.value}` | `{s.failure_classification.value}` | "
            f"`{pred_c}` | `{exp_c}` | `{s.joint_root_cause_accurate}` | {s.cause_set_precision:.2f}/{s.cause_set_recall:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    from nextrace_lab.cli import main
    raise SystemExit(main())
