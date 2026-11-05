"""Diagnostic Method Catalog & Unified Method Dispatcher (Stages 1D, 2, 3, 7 & 8).

Includes:
1. `deterministic_checklist_v1` — Original Phase 1 fixed checklist (historical non-early-stop reference).
2. `deterministic_checklist_early_stop_v1` — Fair early-stopping version of `deterministic_checklist_v1`.
3. `improved_checklist_v1` — Domain-ordered fixed checklist (historical non-early-stop reference).
4. `improved_checklist_early_stop_v1` — Fair early-stopping version of `improved_checklist_v1`.
5. `rule_adaptive_v1` — Deterministic hypothesis-driven adaptive selector with centralized stopping.
6. `scored_adaptive_v2` — Distinguishing-value vs cost heuristic scored selector (v2 standard).
7. `scored_no_cost_v2` — Single-factor ablation ignoring cost differences (v2 standard).
8. `scored_no_avail_v2` — Single-factor ablation ignoring availability discounting (v2 standard).
9. `scored_no_reliability_v2` — Single-factor ablation ignoring reliability discounting (v2 standard).
10. `scored_adaptive_v1`, `scored_no_cost_v1`, `scored_no_avail_v1`, `scored_no_reliability_v1` — Historical v1 aliases.
11. `mock_ai_offline_v1` — Offline deterministic mock AI adapter for test pipelines.
12. `ai_live_v1` — Real provider calls without fallback (`allow_fallback=False`).
13. `ai_hybrid_fallback_v1` — Real provider calls with fallback to `scored_adaptive_v2` (`allow_fallback=True`).
14. `ai_adaptive_v1` — Historical alias for `ai_hybrid_fallback_v1`.

All methods execute through `run_investigation_with_selector` in `nextrace_lab/engine.py` using the centralized stopping policy.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
import uuid

from nextrace_lab.ai_selector import AISelectorAdapter
from nextrace_lab.budget_ledger import DeadlineTracker, SuiteAIBudgetLedger
from nextrace_lab.check_catalog import (
    CHECK_CATALOG,
    get_candidate_check_instances,
    get_expected_outcomes_for_check_instance,
)
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.engine import run_investigation_with_selector
from nextrace_lab.evidence_gate import evaluate_evidence_gate
from nextrace_lab.hypotheses import recompute_hypotheses_from_history
from nextrace_lab.schemas import (
    ConflictRecord,
    DiagnosticCheckCall,
    DiagnosticReport,
    EvidenceStatus,
    HypothesisStance,
    HypothesisState,
    IncidentContext,
    StoppingPolicyMode,
)
from nextrace_lab.scored_selector import ScoredAdaptiveSelector
from nextrace_lab.stopping_policy import (
    evaluate_stopping_policy,
    get_affordable_checks_for_hypotheses,
    get_unresolved_additional_hypotheses,
)
from nextrace_lab.temporal import is_valid_for_current_state


SUPPORTED_METHODS = (
    "deterministic_checklist_v1",
    "deterministic_checklist_early_stop_v1",
    "improved_checklist_v1",
    "improved_checklist_early_stop_v1",
    "rule_adaptive_v1",
    "scored_adaptive_v1",
    "scored_no_cost_v1",
    "scored_no_avail_v1",
    "scored_no_reliability_v1",
    "scored_adaptive_v2",
    "scored_no_cost_v2",
    "scored_no_avail_v2",
    "scored_no_reliability_v2",
    "mock_ai_offline_v1",
    "ai_live_v1",
    "ai_hybrid_fallback_v1",
    "ai_adaptive_v1",
)

# Original Phase 1 fixed checklist order
CHECKLIST_V1_SEQUENCE: list[tuple[str, dict[str, Any], str]] = [
    ("get_service_health", {"service": "gateway"}, "Fixed step 1: Verify entry gateway liveness and readiness."),
    ("get_recent_logs", {"service": "gateway", "limit": 20}, "Fixed step 2: Inspect gateway logs for upstream forwarding errors."),
    ("get_service_health", {"service": "order-service"}, "Fixed step 3: Check order-service liveness and readiness."),
    ("check_database_connectivity_from_order_service", {}, "Fixed step 4: Execute active database connectivity probe from order-service."),
    ("get_order_service_database_config", {}, "Fixed step 5: Inspect sanitized database configuration on order-service."),
    ("get_recent_logs", {"service": "order-service", "limit": 20}, "Fixed step 6: Inspect order-service logs for database failure categories."),
    ("get_service_health", {"service": "database"}, "Fixed step 7: Directly check database service reachability and schema state."),
]

CHECKLIST_V1_INVENTORY_SEQUENCE: list[tuple[str, dict[str, Any], str]] = [
    ("get_service_health", {"service": "inventory-api"}, "Fixed step 1: Verify inventory-api liveness and readiness."),
    ("get_recent_logs", {"service": "inventory-api", "limit": 20}, "Fixed step 2: Inspect inventory-api logs for upstream forwarding errors."),
    ("get_service_health", {"service": "inventory-service"}, "Fixed step 3: Check inventory-service liveness and readiness."),
    ("check_inventory_db_connectivity", {}, "Fixed step 4: Execute active DB probe from inventory-service."),
    ("get_inventory_service_config", {}, "Fixed step 5: Inspect sanitized DB and cache configuration on inventory-service."),
    ("get_recent_logs", {"service": "inventory-service", "limit": 20}, "Fixed step 6: Inspect inventory-service logs."),
    ("get_service_health", {"service": "inventory-db"}, "Fixed step 7: Directly check inventory-db reachability."),
    ("get_service_health", {"service": "inventory-cache"}, "Fixed step 8: Directly check inventory-cache reachability."),
]

# Improved fixed checklist: prioritizes high-yield 1-cost dependency health checks first
IMPROVED_CHECKLIST_V1_SEQUENCE: list[tuple[str, dict[str, Any], str]] = [
    ("get_service_health", {"service": "order-service"}, "Improved fixed step 1: Check order-service liveness, readiness, and error_category (cost 1)."),
    ("get_service_health", {"service": "database"}, "Improved fixed step 2: Directly check database reachability, schema usability, and latency (cost 1)."),
    ("get_recent_logs", {"service": "order-service", "limit": 20}, "Improved fixed step 3: Inspect order-service logs for specific failure events (cost 1)."),
    ("check_database_connectivity_from_order_service", {}, "Improved fixed step 4: Run active DB connectivity probe from order-service (cost 2)."),
    ("get_order_service_database_config", {}, "Improved fixed step 5: Inspect order-service database configuration (cost 2)."),
    ("get_service_health", {"service": "gateway"}, "Improved fixed step 6: Check gateway health if budget remains (cost 1)."),
]

IMPROVED_CHECKLIST_V1_INVENTORY_SEQUENCE: list[tuple[str, dict[str, Any], str]] = [
    ("get_service_health", {"service": "inventory-service"}, "Improved fixed step 1: Check inventory-service liveness, readiness, and error_category (cost 1)."),
    ("get_service_health", {"service": "inventory-db"}, "Improved fixed step 2: Directly check inventory-db reachability and latency (cost 1)."),
    ("get_service_health", {"service": "inventory-cache"}, "Improved fixed step 3: Directly check inventory-cache reachability (cost 1)."),
    ("get_recent_logs", {"service": "inventory-service", "limit": 20}, "Improved fixed step 4: Inspect inventory-service logs (cost 1)."),
    ("check_inventory_db_connectivity", {}, "Improved fixed step 5: Run active DB probe from inventory-service (cost 2)."),
    ("get_inventory_service_config", {}, "Improved fixed step 6: Inspect inventory-service configuration (cost 2)."),
]


class FixedChecklistSelector:
    """Executes a static sequence of checks in order, stopping early when configured via centralized policy."""

    def __init__(
        self,
        method_name: str,
        sequence: list[tuple[str, dict[str, Any], str]],
        stop_when_gate_passes: bool = False,
        stopping_policy_mode: StoppingPolicyMode = "first_supported_cause",
    ) -> None:
        self.method_name = method_name
        self.sequence = sequence
        self.stop_when_gate_passes = stop_when_gate_passes
        self.stopping_policy_mode: StoppingPolicyMode = stopping_policy_mode
        self._cursor = 0

    def select_next_check(
        self,
        incident: IncidentContext,
        hypotheses: list[HypothesisState],
        interface: DiagnosticInterface,
    ) -> Optional[DiagnosticCheckCall]:
        if self.stop_when_gate_passes:
            stop_decision = evaluate_stopping_policy(
                incident, hypotheses, interface, mode=self.stopping_policy_mode
            )
            if stop_decision.should_stop:
                return None

        while self._cursor < len(self.sequence):
            check_name, params, rationale = self.sequence[self._cursor]
            self._cursor += 1
            if interface.can_afford(check_name):
                return DiagnosticCheckCall(
                    check_name=check_name,
                    params=params,
                    rationale=rationale,
                )
        return None


class RuleAdaptiveSelector:
    """Rule-based adaptive selector (`rule_adaptive_v1`): chooses checks distinguishing remaining hypotheses."""

    def __init__(
        self,
        stopping_policy_mode: StoppingPolicyMode = "first_supported_cause",
    ) -> None:
        self.method_name = "rule_adaptive_v1"
        self.stopping_policy_mode: StoppingPolicyMode = stopping_policy_mode

    def select_next_check(
        self,
        incident: IncidentContext,
        hypotheses: list[HypothesisState],
        interface: DiagnosticInterface,
        conflicts: Optional[list[ConflictRecord]] = None,
    ) -> Optional[DiagnosticCheckCall]:
        interface.refresh_staleness_flags()
        recompute_hypotheses_from_history(incident, hypotheses, interface.history)
        active_conflicts = list(conflicts or [])

        # Centralized stopping policy check
        stop_decision = evaluate_stopping_policy(
            incident,
            hypotheses,
            interface,
            conflicts=active_conflicts,
            mode=self.stopping_policy_mode,
        )
        if stop_decision.should_stop:
            return None

        gate = evaluate_evidence_gate(incident, hypotheses, interface.history, conflicts=active_conflicts)
        if gate.get("evidence_gate_passed", False):
            # In investigate_additional_causes mode, pick the first affordable check for unresolved hypotheses
            unresolved = get_unresolved_additional_hypotheses(incident, hypotheses, interface, gate)
            affordable_additional = get_affordable_checks_for_hypotheses(
                incident, unresolved, interface, conflicts=active_conflicts
            )
            if affordable_additional:
                cname, cparams = affordable_additional[0]
                return DiagnosticCheckCall(
                    check_name=cname,
                    params=cparams,
                    rationale=f"Rule adaptive multi-cause check: test unresolved hypothesis component ({cparams.get('service', cname)}).",
                )
            return None

        if interface.budget_remaining <= 0:
            return None

        if incident.app_id == "inventory_app":
            return self._select_inventory_adaptive(incident, hypotheses, interface)

        by_id = {h.hypothesis_id: h for h in hypotheses}

        def can_try(check_name: str, params: dict[str, Any]) -> bool:
            if not interface.can_afford(check_name):
                return False
            if interface.is_known_unavailable(check_name, params):
                return False
            prior_same = [
                r
                for r in interface.history
                if interface.canonical_call_key(r.check_name, r.params)
                == interface.canonical_call_key(check_name, params)
            ]
            if any(is_valid_for_current_state(r) for r in prior_same):
                return False
            return True

        if can_try("get_service_health", {"service": "order-service"}):
            return DiagnosticCheckCall(
                check_name="get_service_health",
                params={"service": "order-service"},
                rationale="Adaptive step: check order-service liveness & readiness (cost=1) to separate H6 from DB faults H1..H5.",
            )

        if can_try("get_service_health", {"service": "database"}):
            return DiagnosticCheckCall(
                check_name="get_service_health",
                params={"service": "database"},
                rationale="Adaptive step: check database direct health (cost=1) to test reachability (H2), schema (H4), and delay (H5).",
            )

        if by_id.get("H6_ORDER_SERVICE_UNAVAILABLE") and by_id["H6_ORDER_SERVICE_UNAVAILABLE"].stance == HypothesisStance.SUPPORTED:
            if can_try("get_service_health", {"service": "gateway"}):
                return DiagnosticCheckCall(
                    check_name="get_service_health",
                    params={"service": "gateway"},
                    rationale="Adaptive corroboration for H6: confirm gateway sees order-service as unreachable (cost=1).",
                )

        if by_id.get("H1_ORDER_DB_CONFIG_ENDPOINT") and by_id["H1_ORDER_DB_CONFIG_ENDPOINT"].stance == HypothesisStance.SUPPORTED:
            if can_try("get_recent_logs", {"service": "order-service", "limit": 20}):
                return DiagnosticCheckCall(
                    check_name="get_recent_logs",
                    params={"service": "order-service", "limit": 20},
                    rationale="Adaptive corroboration for H1: inspect order-service logs for hostname_resolution_failed (cost=1).",
                )
            if can_try("get_order_service_database_config", {}):
                return DiagnosticCheckCall(
                    check_name="get_order_service_database_config",
                    params={},
                    rationale="Adaptive fallback for H1: inspect order-service DB config to verify invalid db_host (cost=2).",
                )
            if can_try("check_database_connectivity_from_order_service", {}):
                return DiagnosticCheckCall(
                    check_name="check_database_connectivity_from_order_service",
                    params={},
                    rationale="Adaptive fallback for H1: run active DB connectivity probe from order-service (cost=2).",
                )

        if by_id.get("H3_ORDER_DB_AUTH_FAILURE") and by_id["H3_ORDER_DB_AUTH_FAILURE"].stance == HypothesisStance.SUPPORTED:
            if can_try("get_recent_logs", {"service": "order-service", "limit": 20}):
                return DiagnosticCheckCall(
                    check_name="get_recent_logs",
                    params={"service": "order-service", "limit": 20},
                    rationale="Adaptive corroboration for H3: check order-service logs for authentication_failed (cost=1).",
                )
            if can_try("check_database_connectivity_from_order_service", {}):
                return DiagnosticCheckCall(
                    check_name="check_database_connectivity_from_order_service",
                    params={},
                    rationale="Adaptive fallback for H3: run active DB probe to corroborate authentication_failed (cost=2).",
                )
            if can_try("get_order_service_database_config", {}):
                return DiagnosticCheckCall(
                    check_name="get_order_service_database_config",
                    params={},
                    rationale="Adaptive fallback for H3: verify valid DB host configuration to corroborate auth failure (cost=2).",
                )

        if by_id.get("H5_DATABASE_OPERATION_DELAY") and by_id["H5_DATABASE_OPERATION_DELAY"].stance == HypothesisStance.SUPPORTED:
            if can_try("get_service_metrics", {"service": "order-service"}):
                return DiagnosticCheckCall(
                    check_name="get_service_metrics",
                    params={"service": "order-service"},
                    rationale="Adaptive corroboration for H5: check order-service latency/timeout metrics (cost=1).",
                )

        for cname, cparams, reason in [
            ("get_recent_logs", {"service": "order-service", "limit": 20}, "Inspect order-service logs for root-cause error_category (cost=1)."),
            ("get_service_metrics", {"service": "order-service"}, "Check order-service metrics for timeout/failure counters (cost=1)."),
            ("check_database_connectivity_from_order_service", {}, "Run active DB connectivity probe from order-service (cost=2)."),
            ("get_order_service_database_config", {}, "Inspect order-service DB config (cost=2)."),
            ("get_service_health", {"service": "gateway"}, "Check gateway health status (cost=1)."),
        ]:
            if can_try(cname, cparams):
                return DiagnosticCheckCall(check_name=cname, params=cparams, rationale=reason)

        return None

    def _select_inventory_adaptive(
        self,
        incident: IncidentContext,
        hypotheses: list[HypothesisState],
        interface: DiagnosticInterface,
    ) -> Optional[DiagnosticCheckCall]:
        def can_try(check_name: str, params: dict[str, Any]) -> bool:
            if not interface.can_afford(check_name):
                return False
            if interface.is_known_unavailable(check_name, params):
                return False
            prior_same = [
                r
                for r in interface.history
                if interface.canonical_call_key(r.check_name, r.params)
                == interface.canonical_call_key(check_name, params)
            ]
            if any(is_valid_for_current_state(r) for r in prior_same):
                return False
            return True

        for cname, cparams, reason in [
            ("get_service_health", {"service": "inventory-service"}, "Check inventory-service readiness and error_category (cost=1)."),
            ("get_service_health", {"service": "inventory-db"}, "Check inventory-db reachability and latency (cost=1)."),
            ("get_service_health", {"service": "inventory-cache"}, "Check inventory-cache reachability (cost=1)."),
            ("get_recent_logs", {"service": "inventory-service", "limit": 20}, "Check inventory-service logs (cost=1)."),
            ("check_inventory_db_connectivity", {}, "Run active inventory-db connectivity probe (cost=2)."),
            ("check_inventory_cache_connectivity", {}, "Run active inventory-cache connectivity probe (cost=2)."),
            ("get_inventory_service_config", {}, "Inspect inventory-service DB and cache config (cost=2)."),
        ]:
            if can_try(cname, cparams):
                return DiagnosticCheckCall(check_name=cname, params=cparams, rationale=reason)
        return None


def run_diagnostic_investigation(
    incident: IncidentContext,
    interface: DiagnosticInterface,
    *,
    method_name: str = "deterministic_checklist_v1",
    stopping_policy_mode: Optional[StoppingPolicyMode] = None,
    runtime_mode: Literal["local", "docker"] = "local",
    backend_name: str = "local_sqlite_tcp",
    run_id: Optional[str] = None,
    ai_provider: Literal["gemini", "openai", "mock-deterministic"] = "mock-deterministic",
    ai_model_name: Optional[str] = None,
    suite_budget_ledger: Optional[SuiteAIBudgetLedger] = None,
    deadline_tracker: Optional[DeadlineTracker] = None,
) -> DiagnosticReport:
    """Execute any supported diagnostic method through the unified engine with centralized stopping policy."""
    active_run_id = run_id or f"run-{uuid.uuid4().hex[:10]}"
    ai_meta_provider: Optional[Any] = None
    is_inv = incident.app_id == "inventory_app"

    # Default stopping policy mode: fixed non-early-stop for historical reference checklists, first_supported_cause for all others
    if stopping_policy_mode is not None:
        effective_stopping_mode = stopping_policy_mode
    elif method_name in ("deterministic_checklist_v1", "improved_checklist_v1"):
        effective_stopping_mode = "fixed_no_early_stop"
    else:
        effective_stopping_mode = "first_supported_cause"

    if method_name == "deterministic_checklist_v1":
        seq = CHECKLIST_V1_INVENTORY_SEQUENCE if is_inv else CHECKLIST_V1_SEQUENCE
        selector: Any = FixedChecklistSelector(
            "deterministic_checklist_v1",
            seq,
            stop_when_gate_passes=False,
            stopping_policy_mode=effective_stopping_mode,
        )
    elif method_name == "deterministic_checklist_early_stop_v1":
        seq = CHECKLIST_V1_INVENTORY_SEQUENCE if is_inv else CHECKLIST_V1_SEQUENCE
        selector = FixedChecklistSelector(
            "deterministic_checklist_early_stop_v1",
            seq,
            stop_when_gate_passes=True,
            stopping_policy_mode=effective_stopping_mode,
        )
    elif method_name == "improved_checklist_v1":
        seq = IMPROVED_CHECKLIST_V1_INVENTORY_SEQUENCE if is_inv else IMPROVED_CHECKLIST_V1_SEQUENCE
        selector = FixedChecklistSelector(
            "improved_checklist_v1",
            seq,
            stop_when_gate_passes=False,
            stopping_policy_mode=effective_stopping_mode,
        )
    elif method_name == "improved_checklist_early_stop_v1":
        seq = IMPROVED_CHECKLIST_V1_INVENTORY_SEQUENCE if is_inv else IMPROVED_CHECKLIST_V1_SEQUENCE
        selector = FixedChecklistSelector(
            "improved_checklist_early_stop_v1",
            seq,
            stop_when_gate_passes=True,
            stopping_policy_mode=effective_stopping_mode,
        )
    elif method_name == "rule_adaptive_v1":
        selector = RuleAdaptiveSelector(stopping_policy_mode=effective_stopping_mode)
    elif method_name in (
        "scored_adaptive_v1",
        "scored_no_cost_v1",
        "scored_no_avail_v1",
        "scored_no_reliability_v1",
        "scored_adaptive_v2",
        "scored_no_cost_v2",
        "scored_no_avail_v2",
        "scored_no_reliability_v2",
    ):
        selector = ScoredAdaptiveSelector(
            variant=method_name,  # type: ignore[arg-type]
            stopping_policy_mode=effective_stopping_mode,
        )
    elif method_name == "mock_ai_offline_v1":
        selector = AISelectorAdapter(
            provider="mock-deterministic",
            method_name="mock_ai_offline_v1",
            allow_fallback=True,
            stopping_policy_mode=effective_stopping_mode,
            suite_budget_ledger=suite_budget_ledger,
            deadline_tracker=deadline_tracker or interface.deadline_tracker,
            run_id=active_run_id,
        )
        ai_meta_provider = selector
    elif method_name == "ai_live_v1":
        selector = AISelectorAdapter(
            provider=ai_provider,
            model_name=ai_model_name,
            method_name="ai_live_v1",
            allow_fallback=False,
            stopping_policy_mode=effective_stopping_mode,
            suite_budget_ledger=suite_budget_ledger,
            deadline_tracker=deadline_tracker or interface.deadline_tracker,
            run_id=active_run_id,
        )
        ai_meta_provider = selector
    elif method_name in ("ai_hybrid_fallback_v1", "ai_adaptive_v1"):
        selector = AISelectorAdapter(
            provider=ai_provider,
            model_name=ai_model_name,
            method_name=method_name,
            allow_fallback=True,
            stopping_policy_mode=effective_stopping_mode,
            suite_budget_ledger=suite_budget_ledger,
            deadline_tracker=deadline_tracker or interface.deadline_tracker,
            run_id=active_run_id,
        )
        ai_meta_provider = selector
    else:
        raise ValueError(f"Unsupported diagnostic method '{method_name}'. Supported: {SUPPORTED_METHODS}")

    return run_investigation_with_selector(
        run_id=active_run_id,
        method_name=method_name,
        incident=incident,
        interface=interface,
        selector=selector,
        stopping_policy_mode=effective_stopping_mode,
        runtime_mode=runtime_mode,
        backend_name=backend_name,
        ai_metadata_provider=ai_meta_provider,
    )
