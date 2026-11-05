"""Typed schemas for NexTrace diagnostic checks, temporal evidence layer, stopping policies, and reports (v0.4.0)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator

# Standard schema versions (v0.4.0 milestone)
STOPPING_POLICY_VERSION: str = "stopping_policy_v2"
EVIDENCE_POLICY_VERSION: str = "E0_v2"
APP_ADAPTER_VERSION: str = "adapter_v2"


class EvidenceStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE_BY_POLICY = "unavailable_by_policy"
    COLLECTION_FAILED = "collection_failed"
    NOT_APPLICABLE = "not_applicable"
    INVALID_CALL = "invalid_call"


class EvidenceCondition(str, Enum):
    E0 = "E0"  # Full local observability
    E1 = "E1"  # Primary service logs unavailable by policy
    E2 = "E2"  # Active database connectivity probe unavailable by policy
    E3 = "E3"  # Primary service logs AND DB config inspection unavailable by policy
    E4 = "E4"  # Service metrics unavailable by policy (E4_METRICS_UNAVAILABLE)
    E5 = "E5"  # Service metrics stale or below sample threshold (E5_METRICS_STALE)


EVIDENCE_CONDITION_LABELS: dict[str, str] = {
    "E0": "E0_FULL_OBSERVABILITY_v2",
    "E1": "E1_SERVICE_LOGS_UNAVAILABLE_v2",
    "E2": "E2_ACTIVE_DB_PROBE_UNAVAILABLE_v2",
    "E3": "E3_LOGS_AND_CONFIG_UNAVAILABLE_v2",
    "E4": "E4_METRICS_UNAVAILABLE_v2",
    "E5": "E5_METRICS_STALE_LOW_SAMPLE_v2",
}

HISTORICAL_EVIDENCE_POLICY_VERSIONS: dict[str, dict[str, Any]] = {
    "E0_v2": {
        "condition": "E0",
        "version": "E0_v2",
        "blocked_checks": [],
        "description": "Full local observability across all registered diagnostic checks.",
    },
    "E1_v2": {
        "condition": "E1",
        "version": "E1_v2",
        "blocked_checks": ["get_recent_logs(order-service)", "get_recent_logs(inventory-service)"],
        "description": "Primary application service logs (order-service, inventory-service) blocked by policy.",
    },
    "E2_v2": {
        "condition": "E2",
        "version": "E2_v2",
        "blocked_checks": [
            "check_database_connectivity_from_order_service",
            "check_inventory_db_connectivity",
        ],
        "description": "Active service-to-database connectivity probe blocked by policy (Phase 3/4 E2).",
    },
    "E2_phase2_minimal_v1": {
        "condition": "E2",
        "version": "E2_phase2_minimal_v1",
        "blocked_checks": [
            "get_recent_logs",
            "get_order_service_database_config",
            "check_database_connectivity_from_order_service",
            "get_service_metrics",
        ],
        "description": "Historical Phase 2 E2 policy where external checks were restricted and readiness categories masked.",
    },
    "E3_v2": {
        "condition": "E3",
        "version": "E3_v2",
        "blocked_checks": [
            "get_recent_logs(order-service)",
            "get_recent_logs(inventory-service)",
            "get_order_service_database_config",
            "get_inventory_service_config",
        ],
        "description": "Both primary service logs and service database configuration inspection blocked by policy.",
    },
    "E4_v2": {
        "condition": "E4",
        "version": "E4_v2",
        "blocked_checks": ["get_service_metrics"],
        "description": "In-process service metrics endpoint blocked by policy (E4_METRICS_UNAVAILABLE).",
    },
    "E5_v2": {
        "condition": "E5",
        "version": "E5_v2",
        "blocked_checks": [],
        "degraded_checks": ["get_service_metrics (stale=True, sample_sufficient=False)"],
        "description": "Service metrics snapshot returned as stale (600s old) and below minimum sample threshold (E5_METRICS_STALE).",
    },
}


class DiagnosticOutcome(str, Enum):
    SUPPORTED_DIAGNOSIS = "supported_diagnosis"
    INCONCLUSIVE = "inconclusive"
    NO_FAULT_FOUND = "no_fault_found"
    UNKNOWN_CAUSE = "unknown_cause"
    EXECUTION_FAILURE = "execution_failure"


class RunFailureClassification(str, Enum):
    """Explicit classification of run outcome and failure modes."""

    SUPPORTED_DIAGNOSIS = "supported_diagnosis"
    HONEST_INCONCLUSIVE = "honest_inconclusive"
    UNKNOWN_CAUSE = "unknown_cause"
    SELECTOR_FAILURE = "selector_failure"
    DIAGNOSTIC_TOOL_FAILURE = "diagnostic_tool_failure"
    SETUP_FAILURE = "setup_failure"
    RECOVERY_FAILURE = "recovery_failure"
    BUDGET_EXHAUSTION = "budget_exhaustion"


class HypothesisStance(str, Enum):
    PLAUSIBLE = "plausible"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    REFUTED = "refuted"


StoppingPolicyMode = Literal[
    "first_supported_cause",
    "investigate_additional_causes",
    "legacy_phase3_v1",
    "fixed_no_early_stop",
]

CostModelVersion = Literal[
    "attempt_charged_v2",
    "legacy_free_unavailable_v1",
]

ScenarioName = Literal[
    # Primary orders_app scenarios (Phase 1 & 2)
    "healthy",
    "fault_a",
    "fault_b",
    "fault_c",
    "fault_d",
    "fault_e",
    "fault_f",
    # Challenging, Temporal & Unknown-Cause scenarios on orders_app
    "challenging_recovery_mid_run",
    "challenging_diag_endpoint_failure",
    "challenging_historical_logs_healthy_now",
    "challenging_unknown_app_error",
    "unknown_order_validation_contract_error",
    "unknown_order_currency_rounding_crash",
    # Multi-Fault scenarios on orders_app
    "multi_fault_a_and_b",
    "multi_fault_c_and_d",
    "multi_fault_f_masks_b",
    # Second application scenarios on inventory_app
    "inv_healthy",
    "inv_fault_db_unavailable",
    "inv_fault_cache_unavailable",
    "inv_fault_bad_db_config",
    "inv_fault_upstream_timeout",
    "inv_unknown_sku_parser_exception",
    "inv_multi_fault_db_and_cache",
]

ScenarioSplit = Literal[
    "development",
    "held_out",
    "stress_challenging",
    "multi_fault",
    "second_app",
    "reserved_eval",
]


class IncidentContext(BaseModel):
    incident_id: str
    observed_at_utc: str
    incident_window_start_utc: Optional[str] = None
    incident_window_end_utc: Optional[str] = None
    clock_skew_tolerance_sec: float = 2.0
    app_id: str = "orders_app"
    entry_endpoint: str = "POST /orders"
    request_id: Optional[str] = None
    http_status: int
    symptom_summary: str
    response_excerpt: dict[str, Any] = Field(default_factory=dict)


class DiagnosticCheckSpec(BaseModel):
    name: str
    description: str
    cost_units: int = Field(ge=1)
    estimated_duration_ms: int = Field(ge=1, default=150)
    reliability: float = Field(ge=0.0, le=1.0, default=0.98)
    freshness_ttl_sec: float = Field(ge=1.0, default=30.0)
    evidence_source: Literal["live_probe", "historical_log", "config_snapshot", "metric_window"] = "live_probe"
    allowed_params: dict[str, list[str]] = Field(default_factory=dict)
    default_params: dict[str, Any] = Field(default_factory=dict)
    informative_for: list[str] = Field(default_factory=list)
    expected_outcomes_by_hypothesis: dict[str, list[str]] = Field(default_factory=dict)
    supported_apps: list[str] = Field(default_factory=lambda: ["orders_app"])


class DiagnosticCheckCall(BaseModel):
    check_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class DiagnosticCheckResult(BaseModel):
    evidence_id: str
    step_number: int
    check_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: EvidenceStatus
    cost_units: int = Field(ge=0)
    latency_ms: float
    timestamp_utc: str
    event_time_utc: Optional[str] = None
    collection_time_utc: Optional[str] = None
    evaluation_time_utc: Optional[str] = None
    observation_interval_sec: Optional[float] = None
    observation_interval_start_utc: Optional[str] = None
    observation_interval_end_utc: Optional[str] = None
    freshness_ttl_sec: float = 30.0
    freshness_status: Literal["fresh", "stale", "not_applicable"] = "fresh"
    is_stale: bool = False
    is_superseded: bool = False
    superseded_by_evidence_id: Optional[str] = None
    timestamp_uncertain: bool = False
    timestamp_uncertainty_reason: Optional[str] = None
    in_incident_window: Optional[bool] = None
    evidence_source: str = "live_probe"
    repeat_index: int = 1
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _backfill_temporal_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            ts = values.get("timestamp_utc") or values.get("event_time_utc") or values.get("collection_time_utc")
            if ts:
                if not values.get("timestamp_utc"):
                    values["timestamp_utc"] = ts
                if not values.get("event_time_utc"):
                    values["event_time_utc"] = ts
                if not values.get("collection_time_utc"):
                    values["collection_time_utc"] = ts
                if not values.get("evaluation_time_utc"):
                    values["evaluation_time_utc"] = ts
        return values


class ConflictRecord(BaseModel):
    """Explicit record of conflicting observations detected during an investigation."""

    conflict_id: str
    conflict_type: Literal[
        "within_run_repeat_change",
        "historical_vs_live_probe",
        "metric_vs_probe_disagreement",
        "simultaneous_source_disagreement",
        "stale_vs_fresh_override",
    ]
    summary: str
    earlier_evidence_id: Optional[str] = None
    later_evidence_id: Optional[str] = None
    detected_at_step: int
    requires_reverification: bool = True
    resolved_by_evidence_id: Optional[str] = None


class CandidateCheckScore(BaseModel):
    """Per-candidate check score breakdown emitted by the transparent scored selector."""

    check_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    distinguishing_score: float
    disjoint_pairs_count: float
    total_pairs_count: int
    availability_factor: float
    reliability_factor: float
    staleness_refresh_bonus: float = 0.0
    cost_units: int
    normalized_cost: float
    final_utility_score: float
    explanation: str


class HypothesisState(BaseModel):
    hypothesis_id: str
    candidate_service: Optional[str] = None
    candidate_fault_type: Optional[str] = None
    description: str
    stance: HypothesisStance = HypothesisStance.PLAUSIBLE
    confidence_level: Literal["low", "medium", "high"] = "low"
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    refuting_evidence_ids: list[str] = Field(default_factory=list)
    expired_or_superseded_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence_notes: list[str] = Field(default_factory=list)


class DecisionLogEntry(BaseModel):
    step_number: int
    timestamp_utc: str
    plausible_hypotheses_before: list[str]
    chosen_check: Optional[str] = None
    chosen_params: dict[str, Any] = Field(default_factory=dict)
    selection_rationale: str
    evidence_id: Optional[str] = None
    evidence_status: Optional[EvidenceStatus] = None
    observation_summary: Optional[str] = None
    hypothesis_updates: dict[str, str] = Field(default_factory=dict)
    candidate_scores: list[CandidateCheckScore] = Field(default_factory=list)
    conflicts_active: list[str] = Field(default_factory=list)
    budget_used: int
    budget_remaining: int
    stop_decision: bool = False
    stop_reason: Optional[str] = None
    ai_usage: Optional[dict[str, Any]] = None


class StructuredLogRecord(BaseModel):
    timestamp_utc: str
    service: str
    request_id: Optional[str] = None
    event: str
    outcome: Literal["success", "failure", "info"] = "info"
    duration_ms: Optional[float] = None
    error_category: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class DiagnosticReport(BaseModel):
    run_id: str
    method_name: str
    method_version: str = "v2"
    stopping_policy_mode: StoppingPolicyMode = "first_supported_cause"
    stopping_policy_version: str = "stopping_policy_v2"
    evidence_gate_version: str = "evidence_gate_v2"
    evidence_policy_version: str = "E0_v2"
    check_catalog_version: str = "check_catalog_v2"
    cost_model_version: CostModelVersion = "attempt_charged_v2"
    outcome_model_version: str = "outcome_model_v2"
    app_adapter_version: str = "app_adapter_v2"
    app_id: str = "orders_app"
    started_at_utc: str
    completed_at_utc: str
    evaluation_time_utc: Optional[str] = None
    runtime_mode: Literal["local", "docker"]
    backend_name: str
    evidence_condition: EvidenceCondition
    budget_limit: int
    budget_used: int
    checks_executed: int
    attempts_admitted: int = 0
    successful_observations_count: int = 0
    rejected_pre_dispatch_count: int = 0
    unavailable_checks_count: int
    failed_checks_count: int = 0
    invalid_checks_count: int = 0
    redundant_unavailable_checks: int
    incident: IncidentContext
    outcome: DiagnosticOutcome
    failure_classification: RunFailureClassification = RunFailureClassification.HONEST_INCONCLUSIVE
    candidate_service: Optional[str] = None
    candidate_fault_type: Optional[str] = None
    predicted_causes: list[str] = Field(default_factory=list)
    unresolved_possible_causes: list[str] = Field(default_factory=list)
    investigation_completion_state: Literal[
        "one_cause_supported",
        "additional_causes_unresolved",
        "investigation_complete_within_modeled_scope",
        "inconclusive_or_abstained",
        "healthy_verified",
    ] = "inconclusive_or_abstained"
    window_diagnosis: Optional[str] = None
    current_health_status: Literal["healthy_now", "degraded_or_failing", "unknown"] = "unknown"
    recovery_observed: bool = False
    confidence_level: Literal["low", "medium", "high"]
    uncertainty_summary: str
    remaining_uncertainty: list[str] = Field(default_factory=list)
    evidence_cited: list[str] = Field(default_factory=list)
    evidence_records: list[DiagnosticCheckResult] = Field(default_factory=list)
    conflicts_detected: list[ConflictRecord] = Field(default_factory=list)
    stale_evidence_ids: list[str] = Field(default_factory=list)
    superseded_evidence_ids: list[str] = Field(default_factory=list)
    final_hypotheses: list[HypothesisState] = Field(default_factory=list)
    decision_log: list[DecisionLogEntry] = Field(default_factory=list)
    evidence_gate_passed: bool = False
    evidence_gate_reason: str = ""
    recommended_next_checks: list[str] = Field(default_factory=list)
    ai_metadata: Optional[dict[str, Any]] = None
    ai_budget_snapshot: Optional[dict[str, Any]] = None
    monotonic_elapsed_sec: Optional[float] = None
    monotonic_deadline_sec: Optional[float] = None
    execution_error: Optional[str] = None


class GroundTruthLabel(BaseModel):
    scenario: ScenarioName
    app_id: str = "orders_app"
    split: ScenarioSplit = "development"
    expected_is_faulty: bool
    expected_service: Optional[str] = None
    expected_fault_type: Optional[str] = None
    expected_causes: list[str] = Field(default_factory=list)
    identifiable_causes: list[str] = Field(default_factory=list)
    masked_causes: list[str] = Field(default_factory=list)
    is_multi_fault: bool = False
    is_unknown_cause: bool = False
    expected_current_health: Optional[Literal["healthy_now", "degraded_or_failing"]] = None
    expected_window_cause: Optional[str] = None
    expected_recovery_observed: bool = False
    description: str


class EvaluationScore(BaseModel):
    run_id: str
    scenario: ScenarioName
    app_id: str = "orders_app"
    split: ScenarioSplit = "development"
    evidence_condition: EvidenceCondition
    method_name: str
    method_version: str = "v2"
    stopping_policy_mode: str = "first_supported_cause"
    cost_model_version: str = "attempt_charged_v2"
    budget_limit: int
    budget_used: int
    checks_executed: int
    attempts_admitted: int = 0
    successful_observations_count: int = 0
    rejected_pre_dispatch_count: int = 0
    outcome: DiagnosticOutcome
    failure_classification: RunFailureClassification = RunFailureClassification.HONEST_INCONCLUSIVE
    predicted_service: Optional[str] = None
    predicted_fault_type: Optional[str] = None
    predicted_causes: list[str] = Field(default_factory=list)
    unresolved_possible_causes: list[str] = Field(default_factory=list)
    expected_service: Optional[str] = None
    expected_fault_type: Optional[str] = None
    expected_causes: list[str] = Field(default_factory=list)
    identifiable_causes: list[str] = Field(default_factory=list)
    masked_causes: list[str] = Field(default_factory=list)
    service_correct: bool
    fault_type_correct: bool
    joint_root_cause_accurate: bool
    cause_set_precision: float = 0.0
    cause_set_recall: float = 0.0
    identifiable_cause_recall: float = 0.0
    exact_set_match: bool = False
    identifiable_set_match: bool = False
    is_multi_fault_scenario: bool = False
    is_unknown_cause_scenario: bool = False
    unknown_cause_avoided_false_certainty: Optional[bool] = None
    window_vs_current_separated_correctly: Optional[bool] = None
    temporal_attribution_error_flag: bool = False
    supported_diagnosis: bool
    inconclusive_outcome: bool
    honest_inconclusive: bool
    unsupported_confident_claim: bool
    overclaim_under_insufficient_evidence: bool
    false_attribution_rate_flag: bool
    execution_failure_flag: bool
    redundant_unavailable_count: int
    wall_clock_ms: float
    ai_tokens_total: int = 0
    ai_estimated_cost_usd: float = 0.0
    ai_fallback_count: int = 0
    scoring_notes: str
