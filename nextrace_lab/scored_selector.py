"""Distinguishing-Value vs Cost Scored Diagnostic Selector and Ablations (Stages 2 & 3).

Implements a transparent, inspectable heuristic check selector (`scored_adaptive_v2`, plus historical
`scored_adaptive_v1`) and three cleanly separated single-factor ablations:
- `scored_no_cost_v2` (`scored_no_cost_v1`): changes ONLY `normalized_cost = 1.0`.
- `scored_no_avail_v2` (`scored_no_avail_v1`): changes ONLY `availability_factor = 1.0`.
- `scored_no_reliability_v2` (`scored_no_reliability_v1`): changes ONLY `reliability_factor = 1.0`.

All stop/continue decisions are delegated to the centralized stopping policy (`stopping_policy.py`).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from nextrace_lab.check_catalog import (
    CHECK_CATALOG,
    get_candidate_check_instances,
    get_expected_outcomes_for_check_instance,
)
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.evidence_gate import evaluate_evidence_gate
from nextrace_lab.hypotheses import recompute_hypotheses_from_history
from nextrace_lab.schemas import (
    CandidateCheckScore,
    ConflictRecord,
    DiagnosticCheckCall,
    EvidenceStatus,
    HypothesisStance,
    HypothesisState,
    IncidentContext,
    StoppingPolicyMode,
)
from nextrace_lab.stopping_policy import (
    evaluate_stopping_policy,
    get_affordable_checks_for_hypotheses,
    get_unresolved_additional_hypotheses,
)
from nextrace_lab.temporal import is_valid_for_current_state


ScoredSelectorVariant = Literal[
    "scored_adaptive_v1",
    "scored_no_cost_v1",
    "scored_no_avail_v1",
    "scored_no_reliability_v1",
    "scored_adaptive_v2",
    "scored_no_cost_v2",
    "scored_no_avail_v2",
    "scored_no_reliability_v2",
]

EVIDENCE_SOURCE_AVAILABILITY_PRIORS: dict[str, float] = {
    "live_probe": 1.00,
    "logs": 0.92,
    "config": 0.90,
    "active_probe": 0.90,
    "metrics": 0.85,
}


class ScoredAdaptiveSelector:
    """Transparent heuristic check selector scoring distinguishing value vs cost (Stages 2 & 3)."""

    def __init__(
        self,
        variant: ScoredSelectorVariant = "scored_adaptive_v2",
        stopping_policy_mode: StoppingPolicyMode = "first_supported_cause",
    ) -> None:
        self.variant = variant
        self.method_name = variant
        self.stopping_policy_mode: StoppingPolicyMode = stopping_policy_mode
        self.last_candidate_scores: list[CandidateCheckScore] = []

    def _compute_factors(
        self,
        *,
        spec_cost: int,
        spec_reliability: float,
        spec_evidence_source: str,
        same_source_unavailable: bool,
    ) -> tuple[float, float, float]:
        """Compute (availability_factor, reliability_factor, normalized_cost) with strict single-factor ablation isolation."""
        base_avail = (
            0.20
            if same_source_unavailable
            else float(EVIDENCE_SOURCE_AVAILABILITY_PRIORS.get(spec_evidence_source, 0.90))
        )
        base_rel = float(spec_reliability)
        base_cost = float(max(1, spec_cost))

        is_no_cost = self.variant in ("scored_no_cost_v1", "scored_no_cost_v2")
        is_no_avail = self.variant in ("scored_no_avail_v1", "scored_no_avail_v2")
        is_no_rel = self.variant in ("scored_no_reliability_v1", "scored_no_reliability_v2")

        availability_factor = 1.0 if is_no_avail else base_avail
        reliability_factor = 1.0 if is_no_rel else base_rel
        normalized_cost = 1.0 if is_no_cost else base_cost

        return availability_factor, reliability_factor, normalized_cost

    def select_next_check(
        self,
        incident: IncidentContext,
        hypotheses: list[HypothesisState],
        interface: DiagnosticInterface,
        conflicts: Optional[list[ConflictRecord]] = None,
    ) -> Optional[DiagnosticCheckCall]:
        """Score all allowlisted candidate check instances and choose the highest-utility affordable check."""
        self.last_candidate_scores = []
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
        app_id = incident.app_id
        candidates = get_candidate_check_instances(app_id=app_id)

        investigating_additional = bool(gate.get("evidence_gate_passed", False))
        unresolved_additional: list[HypothesisState] = []
        allowed_additional_keys: set[str] = set()
        if investigating_additional:
            unresolved_additional = get_unresolved_additional_hypotheses(incident, hypotheses, interface, gate)
            allowed_additional_pairs = get_affordable_checks_for_hypotheses(
                incident, unresolved_additional, interface, conflicts=active_conflicts
            )
            allowed_additional_keys = {
                interface.canonical_call_key(cn, cp) for cn, cp in allowed_additional_pairs
            }
            active_hyps = list(unresolved_additional)
        else:
            active_hyps = [
                h
                for h in hypotheses
                if h.stance in (HypothesisStance.PLAUSIBLE, HypothesisStance.SUPPORTED)
            ]
            if incident.http_status >= 500:
                fault_hyps = [h for h in active_hyps if not h.hypothesis_id.startswith(("H0_", "IH0_"))]
                if fault_hyps:
                    active_hyps = fault_hyps

        scored_list: list[CandidateCheckScore] = []
        recommended_strs = set(gate.get("recommended_next_checks", []))

        unavailable_sources = {
            CHECK_CATALOG[r.check_name].evidence_source
            for r in interface.history
            if r.check_name in CHECK_CATALOG and r.status == EvidenceStatus.UNAVAILABLE_BY_POLICY
        }

        for check_name, params in candidates:
            spec = CHECK_CATALOG[check_name]
            cost = spec.cost_units
            if cost > interface.budget_remaining:
                continue

            call_key = interface.canonical_call_key(check_name, params)
            if investigating_additional and call_key not in allowed_additional_keys:
                continue

            prior_same = [
                r
                for r in interface.history
                if interface.canonical_call_key(r.check_name, r.params) == call_key
            ]

            has_failed_or_unavail = any(
                r.status in (EvidenceStatus.UNAVAILABLE_BY_POLICY, EvidenceStatus.COLLECTION_FAILED, EvidenceStatus.INVALID_CALL)
                for r in prior_same
            )
            if has_failed_or_unavail:
                continue

            has_fresh_available = any(
                is_valid_for_current_state(r)
                for r in prior_same
            )
            has_stale_or_superseded = any(
                r.status == EvidenceStatus.AVAILABLE and (r.is_stale or r.is_superseded)
                for r in prior_same
            )

            needs_conflict_reverify = any(
                c.requires_reverification and c.resolved_by_evidence_id is None
                for c in active_conflicts
            ) and spec.evidence_source == "live_probe" and len(prior_same) < 2

            if has_fresh_available and not needs_conflict_reverify:
                continue

            same_source_unavail = spec.evidence_source in unavailable_sources
            availability_factor, reliability_factor, normalized_cost = self._compute_factors(
                spec_cost=cost,
                spec_reliability=spec.reliability,
                spec_evidence_source=spec.evidence_source,
                same_source_unavailable=same_source_unavail,
            )

            dist_score, disjoint_pairs, total_pairs, reason_parts = self._compute_distinguishing_score(
                check_name=check_name,
                params=params,
                app_id=app_id,
                incident=incident,
                active_hyps=active_hyps,
                all_hypotheses=hypotheses,
                recommended_strs=recommended_strs,
                interface=interface,
                investigating_additional=investigating_additional,
            )

            staleness_bonus = 0.0
            if has_stale_or_superseded:
                staleness_bonus = 0.25
                reason_parts.append("stale_evidence_refresh(+0.25)")
            elif needs_conflict_reverify and prior_same:
                staleness_bonus = 0.20
                reason_parts.append("conflict_reverification(+0.20)")

            raw_numerator = (dist_score + staleness_bonus) * availability_factor * reliability_factor
            final_score = round(raw_numerator / normalized_cost, 4)

            explanation = (
                f"U={final_score:.4f} [D={dist_score:.3f} ({disjoint_pairs:.1f}/{total_pairs} pairs), "
                f"avail={availability_factor:.2f}, rel={reliability_factor:.2f}, "
                f"cost={cost} (norm={normalized_cost:.1f})]: " + ", ".join(reason_parts)
            )

            scored_list.append(
                CandidateCheckScore(
                    check_name=check_name,
                    params=params,
                    distinguishing_score=round(dist_score, 4),
                    disjoint_pairs_count=round(disjoint_pairs, 2),
                    total_pairs_count=total_pairs,
                    availability_factor=round(availability_factor, 4),
                    reliability_factor=round(reliability_factor, 4),
                    staleness_refresh_bonus=round(staleness_bonus, 4),
                    cost_units=cost,
                    normalized_cost=normalized_cost,
                    final_utility_score=final_score,
                    explanation=explanation,
                )
            )

        if not scored_list:
            return None

        scored_list.sort(
            key=lambda s: (s.final_utility_score, -s.cost_units, s.distinguishing_score),
            reverse=True,
        )
        self.last_candidate_scores = scored_list
        best = scored_list[0]
        if best.final_utility_score <= 0.0:
            return None

        return DiagnosticCheckCall(
            check_name=best.check_name,
            params=best.params,
            rationale=f"[{self.variant}] Selected highest utility check ({best.explanation})",
        )

    def _compute_distinguishing_score(
        self,
        *,
        check_name: str,
        params: dict[str, Any],
        app_id: str,
        incident: IncidentContext,
        active_hyps: list[HypothesisState],
        all_hypotheses: list[HypothesisState],
        recommended_strs: set[str],
        interface: DiagnosticInterface,
        investigating_additional: bool = False,
    ) -> tuple[float, float, int, list[str]]:
        outcome_map = get_expected_outcomes_for_check_instance(check_name, params, app_id=app_id)
        reasons: list[str] = []

        if incident.http_status in (200, 201):
            svc = params.get("service", "")
            if check_name == "get_service_health" and svc in ("order-service", "database", "inventory-service", "inventory-db"):
                return 0.90, 1.0, 1, [f"verifies healthy readiness of {svc}"]
            if check_name in ("check_database_connectivity_from_order_service", "check_inventory_db_connectivity"):
                return 0.75, 1.0, 1, ["verifies live DB connectivity"]
            return 0.15, 0.0, 1, ["low priority on healthy status"]

        if investigating_additional and active_hyps:
            svc = str(params.get("service", "")).strip()
            target_services = {h.candidate_service for h in active_hyps}
            if check_name == "get_service_health" and svc in target_services:
                return 0.90, 1.0, max(1, len(active_hyps)), [f"probes_unverified_component({svc})"]

        if len(active_hyps) >= 2:
            n = len(active_hyps)
            total_pairs = (n * (n - 1)) // 2
            disjoint_sum = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    h_i = active_hyps[i].hypothesis_id
                    h_j = active_hyps[j].hypothesis_id
                    set_i = outcome_map.get(h_i, set())
                    set_j = outcome_map.get(h_j, set())
                    if not set_i or not set_j:
                        continue
                    inter = set_i & set_j
                    union = set_i | set_j
                    if not inter:
                        disjoint_sum += 1.0
                    elif set_i != set_j and union:
                        jaccard_dist = 1.0 - (len(inter) / len(union))
                        disjoint_sum += 0.5 * jaccard_dist

            base_score = disjoint_sum / float(total_pairs) if total_pairs > 0 else 0.0
            reasons.append(f"pairwise_separation={base_score:.3f}")

            supported_hyps = [h for h in active_hyps if h.stance == HypothesisStance.SUPPORTED]
            for sh in supported_hyps:
                corrob_bonus, corrob_note = self._corroboration_bonus(
                    sh, check_name, params, app_id, recommended_strs, interface
                )
                if corrob_bonus > 0:
                    base_score = min(1.0, base_score + corrob_bonus)
                    reasons.append(corrob_note)
                    break

            return base_score, disjoint_sum, total_pairs, reasons

        if len(active_hyps) == 1:
            target_h = active_hyps[0]
            h0_id = "IH0_NO_FAULT_HEALTHY" if app_id == "inventory_app" else "H0_NO_FAULT_HEALTHY"
            set_h = outcome_map.get(target_h.hypothesis_id, set())
            set_h0 = outcome_map.get(h0_id, set())
            separates_from_healthy = bool(set_h and set_h0 and (set_h & set_h0 == set()))
            base_score = 0.45 if separates_from_healthy else 0.10
            corrob_bonus, corrob_note = self._corroboration_bonus(
                target_h, check_name, params, app_id, recommended_strs, interface
            )
            score = min(1.0, base_score + corrob_bonus)
            if corrob_note:
                reasons.append(corrob_note)
            else:
                reasons.append(f"corroborates {target_h.hypothesis_id}")
            return score, (1.0 if separates_from_healthy else 0.0), 1, reasons

        # Zero active modeled hypotheses (e.g., all modeled hypotheses weakened/refuted -> check logs/config/db to confirm unknown_cause)
        svc = params.get("service", "")
        if check_name == "get_recent_logs" and svc in ("order-service", "inventory-service"):
            return 0.85, 1.0, 1, ["inspects application logs for unmodeled internal exception"]
        if check_name == "get_service_health" and svc in ("database", "order-service", "inventory-db", "inventory-cache", "inventory-service"):
            return 0.75, 1.0, 1, ["verifies dependency health for unknown-cause elimination"]
        if check_name in (
            "get_order_service_database_config",
            "check_database_connectivity_from_order_service",
            "get_inventory_service_config",
            "check_inventory_db_connectivity",
            "check_inventory_cache_connectivity",
        ):
            return 0.70, 1.0, 1, ["verifies dependency config/connectivity for unknown-cause elimination"]
        return 0.20, 0.0, 1, ["fallback exploratory check"]

    def _corroboration_bonus(
        self,
        target_h: HypothesisState,
        check_name: str,
        params: dict[str, Any],
        app_id: str,
        recommended_strs: set[str],
        interface: DiagnosticInterface,
    ) -> tuple[float, str]:
        hid = target_h.hypothesis_id
        svc = str(params.get("service", ""))

        for rec in recommended_strs:
            if check_name in rec and (not svc or svc in rec):
                return 0.45, f"gate_recommended_for_{hid}(+0.45)"

        if hid == "H1_ORDER_DB_CONFIG_ENDPOINT":
            if check_name == "get_service_health" and svc == "database":
                return 0.50, "verifies_db_reachability_and_multi_fault(+0.50)"
            if check_name == "get_order_service_database_config":
                return 0.45, "directly_inspects_db_host_config(+0.45)"
            if check_name == "get_recent_logs" and svc == "order-service":
                return 0.40, "corroborates_hostname_error_in_logs(+0.40)"

        if hid == "H2_DATABASE_UNAVAILABLE":
            if check_name == "get_service_health" and svc == "database":
                return 0.55, "directly_probes_database_port(+0.55)"
            if check_name == "get_order_service_database_config":
                return 0.35, "checks_whether_fault_a_also_present(+0.35)"

        if hid == "H3_ORDER_DB_AUTH_FAILURE":
            if check_name == "get_service_health" and svc == "database":
                return 0.50, "confirms_db_reachable_for_auth_fault(+0.50)"
            if check_name == "get_recent_logs" and svc == "order-service":
                return 0.45, "corroborates_auth_failure_in_logs(+0.45)"
            if check_name == "get_order_service_database_config":
                return 0.40, "confirms_valid_db_host_for_auth_fault(+0.40)"

        if hid == "H4_DATABASE_SCHEMA_MISSING":
            if check_name == "get_service_health" and svc == "database":
                return 0.55, "confirms_missing_table_on_db_health(+0.55)"
            if check_name == "get_recent_logs" and svc == "order-service":
                return 0.45, "corroborates_missing_table_in_logs(+0.45)"

        if hid == "H5_DATABASE_OPERATION_DELAY":
            if check_name == "get_service_health" and svc == "database":
                return 0.55, "confirms_db_operation_timeout(+0.55)"
            if check_name == "get_service_metrics" and svc == "order-service":
                return 0.45, "corroborates_timeout_latency_metrics(+0.45)"
            if check_name == "get_recent_logs" and svc == "order-service":
                return 0.45, "corroborates_timeout_in_logs(+0.45)"

        if hid == "H6_ORDER_SERVICE_UNAVAILABLE":
            if check_name == "get_service_health" and svc == "database":
                return 0.55, "confirms_db_healthy_while_order_service_down(+0.55)"
            if check_name == "get_service_health" and svc == "gateway":
                return 0.40, "corroborates_gateway_upstream_unreachable(+0.40)"

        if hid == "IH1_INV_DB_UNAVAILABLE" and check_name == "get_service_health" and svc == "inventory-db":
            return 0.55, "directly_probes_inventory_db(+0.55)"
        if hid == "IH2_INV_CACHE_UNAVAILABLE" and check_name in ("get_service_health", "check_inventory_cache_connectivity"):
            if svc == "inventory-cache" or check_name == "check_inventory_cache_connectivity":
                return 0.55, "directly_probes_inventory_cache(+0.55)"
        if hid == "IH3_INV_DB_CONFIG_ENDPOINT":
            if check_name == "get_service_health" and svc == "inventory-db":
                return 0.50, "confirms_inventory_db_reachable(+0.50)"
            if check_name == "get_inventory_service_config":
                return 0.50, "inspects_inventory_db_host_config(+0.50)"
        if hid == "IH4_INV_DB_OPERATION_DELAY":
            if check_name == "get_service_health" and svc == "inventory-db":
                return 0.55, "confirms_inventory_db_timeout(+0.55)"

        return 0.0, ""
