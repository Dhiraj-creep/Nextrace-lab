"""Allowlisted diagnostic check catalog with explicit costs, freshness TTLs, and set-valued outcome models (Stages 2, 5 & 8)."""

from __future__ import annotations

from typing import Any

from nextrace_lab.schemas import DiagnosticCheckSpec

CHECK_CATALOG_VERSION: str = "check_catalog_v2"


CHECK_CATALOG: dict[str, DiagnosticCheckSpec] = {
    "get_recent_logs": DiagnosticCheckSpec(
        name="get_recent_logs",
        description=(
            "Retrieve recent structured JSON log entries for a service "
            "(orders_app: 'gateway' or 'order-service'; inventory_app: 'inventory-api' or 'inventory-service')."
        ),
        cost_units=1,
        estimated_duration_ms=80,
        reliability=0.95,
        freshness_ttl_sec=60.0,
        evidence_source="historical_log",
        allowed_params={
            "service": ["gateway", "order-service", "inventory-api", "inventory-service"],
            "limit": ["5", "10", "20", "50"],
        },
        default_params={"service": "order-service", "limit": 20},
        informative_for=[
            "H1_ORDER_DB_CONFIG_ENDPOINT",
            "H2_DATABASE_UNAVAILABLE",
            "H3_ORDER_DB_AUTH_FAILURE",
            "H4_DATABASE_SCHEMA_MISSING",
            "H5_DATABASE_OPERATION_DELAY",
            "H6_ORDER_SERVICE_UNAVAILABLE",
            "IH1_INV_DB_UNAVAILABLE",
            "IH2_INV_CACHE_UNAVAILABLE",
            "IH3_INV_DB_CONFIG_ENDPOINT",
            "IH4_INV_DB_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "H0_NO_FAULT_HEALTHY": ["no_errors"],
            "H1_ORDER_DB_CONFIG_ENDPOINT": ["hostname_resolution_failed", "upstream_503"],
            "H2_DATABASE_UNAVAILABLE": ["connection_refused", "upstream_503"],
            "H3_ORDER_DB_AUTH_FAILURE": ["authentication_failed", "upstream_503"],
            "H4_DATABASE_SCHEMA_MISSING": ["missing_table", "upstream_503"],
            "H5_DATABASE_OPERATION_DELAY": ["operation_timeout", "upstream_503", "upstream_timeout"],
            "H6_ORDER_SERVICE_UNAVAILABLE": ["upstream_unreachable", "no_recent_order_logs"],
        },
        supported_apps=["orders_app", "inventory_app"],
    ),
    "get_service_health": DiagnosticCheckSpec(
        name="get_service_health",
        description=(
            "Check liveness and readiness status of a target component "
            "(orders_app: 'gateway', 'order-service', 'database'; "
            "inventory_app: 'inventory-api', 'inventory-service', 'inventory-db', 'inventory-cache')."
        ),
        cost_units=1,
        estimated_duration_ms=120,
        reliability=0.99,
        freshness_ttl_sec=15.0,
        evidence_source="live_probe",
        allowed_params={
            "service": [
                "gateway",
                "order-service",
                "database",
                "inventory-api",
                "inventory-service",
                "inventory-db",
                "inventory-cache",
            ]
        },
        default_params={"service": "order-service"},
        informative_for=[
            "H0_NO_FAULT_HEALTHY",
            "H1_ORDER_DB_CONFIG_ENDPOINT",
            "H2_DATABASE_UNAVAILABLE",
            "H3_ORDER_DB_AUTH_FAILURE",
            "H4_DATABASE_SCHEMA_MISSING",
            "H5_DATABASE_OPERATION_DELAY",
            "H6_ORDER_SERVICE_UNAVAILABLE",
            "IH0_NO_FAULT_HEALTHY",
            "IH1_INV_DB_UNAVAILABLE",
            "IH2_INV_CACHE_UNAVAILABLE",
            "IH3_INV_DB_CONFIG_ENDPOINT",
            "IH4_INV_DB_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "H0_NO_FAULT_HEALTHY": ["live_and_ready", "db_reachable"],
            "H1_ORDER_DB_CONFIG_ENDPOINT": ["live_not_ready_hostname", "db_reachable"],
            "H2_DATABASE_UNAVAILABLE": ["live_not_ready_conn_refused", "db_unreachable"],
            "H3_ORDER_DB_AUTH_FAILURE": ["live_not_ready_auth", "db_reachable"],
            "H4_DATABASE_SCHEMA_MISSING": ["live_not_ready_schema", "db_reachable"],
            "H5_DATABASE_OPERATION_DELAY": ["live_not_ready_timeout", "db_reachable_slow"],
            "H6_ORDER_SERVICE_UNAVAILABLE": ["service_unreachable", "db_reachable"],
        },
        supported_apps=["orders_app", "inventory_app"],
    ),
    "get_service_metrics": DiagnosticCheckSpec(
        name="get_service_metrics",
        description=(
            "Retrieve in-process request count, error rate, latency summary, dependency failures, "
            "and dependency timeouts for a service (Stage 5)."
        ),
        cost_units=1,
        estimated_duration_ms=90,
        reliability=0.94,
        freshness_ttl_sec=20.0,
        evidence_source="metric_window",
        allowed_params={
            "service": ["gateway", "order-service", "inventory-api", "inventory-service"],
        },
        default_params={"service": "order-service"},
        informative_for=[
            "H0_NO_FAULT_HEALTHY",
            "H1_ORDER_DB_CONFIG_ENDPOINT",
            "H2_DATABASE_UNAVAILABLE",
            "H3_ORDER_DB_AUTH_FAILURE",
            "H4_DATABASE_SCHEMA_MISSING",
            "H5_DATABASE_OPERATION_DELAY",
            "H6_ORDER_SERVICE_UNAVAILABLE",
            "IH0_NO_FAULT_HEALTHY",
            "IH1_INV_DB_UNAVAILABLE",
            "IH2_INV_CACHE_UNAVAILABLE",
            "IH3_INV_DB_CONFIG_ENDPOINT",
            "IH4_INV_DB_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "H0_NO_FAULT_HEALTHY": ["metrics_zero_errors_normal_latency"],
            "H1_ORDER_DB_CONFIG_ENDPOINT": ["metrics_dep_failures_fast"],
            "H2_DATABASE_UNAVAILABLE": ["metrics_dep_failures_fast"],
            "H3_ORDER_DB_AUTH_FAILURE": ["metrics_dep_failures_fast"],
            "H4_DATABASE_SCHEMA_MISSING": ["metrics_dep_failures_fast"],
            "H5_DATABASE_OPERATION_DELAY": ["metrics_dep_timeouts_high_latency"],
            "H6_ORDER_SERVICE_UNAVAILABLE": ["metrics_service_unreachable", "metrics_gateway_dep_failures"],
        },
        supported_apps=["orders_app", "inventory_app"],
    ),
    "check_database_connectivity_from_order_service": DiagnosticCheckSpec(
        name="check_database_connectivity_from_order_service",
        description=(
            "Trigger an active database connectivity and schema probe from order-service "
            "and return error category, configured target, and latency."
        ),
        cost_units=2,
        estimated_duration_ms=220,
        reliability=0.98,
        freshness_ttl_sec=15.0,
        evidence_source="live_probe",
        allowed_params={},
        default_params={},
        informative_for=[
            "H0_NO_FAULT_HEALTHY",
            "H1_ORDER_DB_CONFIG_ENDPOINT",
            "H2_DATABASE_UNAVAILABLE",
            "H3_ORDER_DB_AUTH_FAILURE",
            "H4_DATABASE_SCHEMA_MISSING",
            "H5_DATABASE_OPERATION_DELAY",
            "H6_ORDER_SERVICE_UNAVAILABLE",
        ],
        expected_outcomes_by_hypothesis={
            "H0_NO_FAULT_HEALTHY": ["probe_ok"],
            "H1_ORDER_DB_CONFIG_ENDPOINT": ["probe_hostname_resolution_failed"],
            "H2_DATABASE_UNAVAILABLE": ["probe_connection_refused"],
            "H3_ORDER_DB_AUTH_FAILURE": ["probe_authentication_failed"],
            "H4_DATABASE_SCHEMA_MISSING": ["probe_missing_table"],
            "H5_DATABASE_OPERATION_DELAY": ["probe_operation_timeout"],
            "H6_ORDER_SERVICE_UNAVAILABLE": ["order_service_unreachable"],
        },
        supported_apps=["orders_app"],
    ),
    "get_order_service_database_config": DiagnosticCheckSpec(
        name="get_order_service_database_config",
        description=(
            "Inspect sanitized database connection configuration currently loaded by order-service "
            "(db_host, db_port, db_name, db_user, connect_timeout_sec; credentials redacted)."
        ),
        cost_units=2,
        estimated_duration_ms=110,
        reliability=0.97,
        freshness_ttl_sec=45.0,
        evidence_source="config_snapshot",
        allowed_params={},
        default_params={},
        informative_for=[
            "H1_ORDER_DB_CONFIG_ENDPOINT",
            "H2_DATABASE_UNAVAILABLE",
            "H3_ORDER_DB_AUTH_FAILURE",
            "H4_DATABASE_SCHEMA_MISSING",
            "H5_DATABASE_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "H0_NO_FAULT_HEALTHY": ["config_host_valid"],
            "H1_ORDER_DB_CONFIG_ENDPOINT": ["config_host_invalid"],
            "H2_DATABASE_UNAVAILABLE": ["config_host_valid"],
            "H3_ORDER_DB_AUTH_FAILURE": ["config_host_valid"],
            "H4_DATABASE_SCHEMA_MISSING": ["config_host_valid"],
            "H5_DATABASE_OPERATION_DELAY": ["config_host_valid"],
            "H6_ORDER_SERVICE_UNAVAILABLE": ["order_service_unreachable"],
        },
        supported_apps=["orders_app"],
    ),
    # Second application (`inventory_app`) specialized probes (Stage 8)
    "check_inventory_db_connectivity": DiagnosticCheckSpec(
        name="check_inventory_db_connectivity",
        description="Trigger an active database connectivity probe from inventory-service to inventory-db.",
        cost_units=2,
        estimated_duration_ms=200,
        reliability=0.98,
        freshness_ttl_sec=15.0,
        evidence_source="live_probe",
        allowed_params={},
        default_params={},
        informative_for=[
            "IH0_NO_FAULT_HEALTHY",
            "IH1_INV_DB_UNAVAILABLE",
            "IH2_INV_CACHE_UNAVAILABLE",
            "IH3_INV_DB_CONFIG_ENDPOINT",
            "IH4_INV_DB_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "IH0_NO_FAULT_HEALTHY": ["probe_ok"],
            "IH1_INV_DB_UNAVAILABLE": ["probe_connection_refused"],
            "IH2_INV_CACHE_UNAVAILABLE": ["probe_ok"],
            "IH3_INV_DB_CONFIG_ENDPOINT": ["probe_hostname_resolution_failed"],
            "IH4_INV_DB_OPERATION_DELAY": ["probe_operation_timeout"],
        },
        supported_apps=["inventory_app"],
    ),
    "check_inventory_cache_connectivity": DiagnosticCheckSpec(
        name="check_inventory_cache_connectivity",
        description="Trigger an active cache connectivity probe from inventory-service to inventory-cache.",
        cost_units=2,
        estimated_duration_ms=150,
        reliability=0.98,
        freshness_ttl_sec=15.0,
        evidence_source="live_probe",
        allowed_params={},
        default_params={},
        informative_for=[
            "IH0_NO_FAULT_HEALTHY",
            "IH1_INV_DB_UNAVAILABLE",
            "IH2_INV_CACHE_UNAVAILABLE",
            "IH3_INV_DB_CONFIG_ENDPOINT",
            "IH4_INV_DB_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "IH0_NO_FAULT_HEALTHY": ["cache_probe_ok"],
            "IH1_INV_DB_UNAVAILABLE": ["cache_probe_ok"],
            "IH2_INV_CACHE_UNAVAILABLE": ["cache_probe_connection_refused"],
            "IH3_INV_DB_CONFIG_ENDPOINT": ["cache_probe_ok"],
            "IH4_INV_DB_OPERATION_DELAY": ["cache_probe_ok"],
        },
        supported_apps=["inventory_app"],
    ),
    "get_inventory_service_config": DiagnosticCheckSpec(
        name="get_inventory_service_config",
        description="Inspect sanitized DB and cache configuration loaded by inventory-service.",
        cost_units=2,
        estimated_duration_ms=110,
        reliability=0.97,
        freshness_ttl_sec=45.0,
        evidence_source="config_snapshot",
        allowed_params={},
        default_params={},
        informative_for=[
            "IH0_NO_FAULT_HEALTHY",
            "IH1_INV_DB_UNAVAILABLE",
            "IH2_INV_CACHE_UNAVAILABLE",
            "IH3_INV_DB_CONFIG_ENDPOINT",
            "IH4_INV_DB_OPERATION_DELAY",
        ],
        expected_outcomes_by_hypothesis={
            "IH0_NO_FAULT_HEALTHY": ["config_host_valid"],
            "IH1_INV_DB_UNAVAILABLE": ["config_host_valid"],
            "IH2_INV_CACHE_UNAVAILABLE": ["config_host_valid"],
            "IH3_INV_DB_CONFIG_ENDPOINT": ["config_host_invalid"],
            "IH4_INV_DB_OPERATION_DELAY": ["config_host_valid"],
        },
        supported_apps=["inventory_app"],
    ),
}


# Set-valued outcome models per parameterized check instance (Stage 2)
# Keyed by (app_id, check_name, param_service_or_empty) -> {hypothesis_id: set_of_expected_outcomes}
PARAMETERIZED_OUTCOME_MODELS: dict[tuple[str, str, str], dict[str, set[str]]] = {
    # ---------------- orders_app ----------------
    ("orders_app", "get_service_health", "gateway"): {
        "H0_NO_FAULT_HEALTHY": {"gw_live_ready"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"gw_live_ready"},
        "H2_DATABASE_UNAVAILABLE": {"gw_live_ready"},
        "H3_ORDER_DB_AUTH_FAILURE": {"gw_live_ready"},
        "H4_DATABASE_SCHEMA_MISSING": {"gw_live_ready"},
        "H5_DATABASE_OPERATION_DELAY": {"gw_live_ready"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"gw_live_not_ready_upstream_unreachable"},
    },
    ("orders_app", "get_service_health", "order-service"): {
        "H0_NO_FAULT_HEALTHY": {"ord_live_ready"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"ord_not_ready_hostname_resolution_failed"},
        "H2_DATABASE_UNAVAILABLE": {"ord_not_ready_connection_refused"},
        "H3_ORDER_DB_AUTH_FAILURE": {"ord_not_ready_authentication_failed"},
        "H4_DATABASE_SCHEMA_MISSING": {"ord_not_ready_missing_table"},
        "H5_DATABASE_OPERATION_DELAY": {"ord_not_ready_operation_timeout"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"ord_unreachable"},
    },
    ("orders_app", "get_service_health", "database"): {
        "H0_NO_FAULT_HEALTHY": {"db_reachable_ok"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"db_reachable_ok"},
        "H2_DATABASE_UNAVAILABLE": {"db_unreachable_connection_refused"},
        "H3_ORDER_DB_AUTH_FAILURE": {"db_reachable_ok"},
        "H4_DATABASE_SCHEMA_MISSING": {"db_reachable_missing_table"},
        "H5_DATABASE_OPERATION_DELAY": {"db_reachable_slow_or_timeout"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"db_reachable_ok"},
    },
    ("orders_app", "get_recent_logs", "gateway"): {
        "H0_NO_FAULT_HEALTHY": {"gw_logs_ok"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"gw_logs_upstream_503"},
        "H2_DATABASE_UNAVAILABLE": {"gw_logs_upstream_503"},
        "H3_ORDER_DB_AUTH_FAILURE": {"gw_logs_upstream_503"},
        "H4_DATABASE_SCHEMA_MISSING": {"gw_logs_upstream_503"},
        "H5_DATABASE_OPERATION_DELAY": {"gw_logs_upstream_503", "gw_logs_upstream_timeout"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"gw_logs_upstream_unreachable"},
    },
    ("orders_app", "get_recent_logs", "order-service"): {
        "H0_NO_FAULT_HEALTHY": {"ord_logs_ok"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"ord_logs_hostname_resolution_failed"},
        "H2_DATABASE_UNAVAILABLE": {"ord_logs_connection_refused"},
        "H3_ORDER_DB_AUTH_FAILURE": {"ord_logs_authentication_failed"},
        "H4_DATABASE_SCHEMA_MISSING": {"ord_logs_missing_table"},
        "H5_DATABASE_OPERATION_DELAY": {"ord_logs_operation_timeout"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"ord_logs_none_while_down", "ord_logs_ok"},
    },
    ("orders_app", "get_service_metrics", "gateway"): {
        "H0_NO_FAULT_HEALTHY": {"gw_metrics_low_error_normal_latency"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"gw_metrics_dep_failures_fast"},
        "H2_DATABASE_UNAVAILABLE": {"gw_metrics_dep_failures_fast"},
        "H3_ORDER_DB_AUTH_FAILURE": {"gw_metrics_dep_failures_fast"},
        "H4_DATABASE_SCHEMA_MISSING": {"gw_metrics_dep_failures_fast"},
        "H5_DATABASE_OPERATION_DELAY": {"gw_metrics_dep_failures_high_latency"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"gw_metrics_dep_failures_fast"},
    },
    ("orders_app", "get_service_metrics", "order-service"): {
        "H0_NO_FAULT_HEALTHY": {"ord_metrics_low_error_normal_latency"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"ord_metrics_dep_failures_fast"},
        "H2_DATABASE_UNAVAILABLE": {"ord_metrics_dep_failures_fast"},
        "H3_ORDER_DB_AUTH_FAILURE": {"ord_metrics_dep_failures_fast"},
        "H4_DATABASE_SCHEMA_MISSING": {"ord_metrics_dep_failures_fast"},
        "H5_DATABASE_OPERATION_DELAY": {"ord_metrics_dep_timeouts_high_latency"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"ord_metrics_unreachable"},
    },
    ("orders_app", "check_database_connectivity_from_order_service", ""): {
        "H0_NO_FAULT_HEALTHY": {"probe_ok"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"probe_hostname_resolution_failed"},
        "H2_DATABASE_UNAVAILABLE": {"probe_connection_refused"},
        "H3_ORDER_DB_AUTH_FAILURE": {"probe_authentication_failed"},
        "H4_DATABASE_SCHEMA_MISSING": {"probe_missing_table"},
        "H5_DATABASE_OPERATION_DELAY": {"probe_operation_timeout"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"probe_order_service_unreachable"},
    },
    ("orders_app", "get_order_service_database_config", ""): {
        "H0_NO_FAULT_HEALTHY": {"config_host_valid"},
        "H1_ORDER_DB_CONFIG_ENDPOINT": {"config_host_invalid"},
        "H2_DATABASE_UNAVAILABLE": {"config_host_valid"},
        "H3_ORDER_DB_AUTH_FAILURE": {"config_host_valid"},
        "H4_DATABASE_SCHEMA_MISSING": {"config_host_valid"},
        "H5_DATABASE_OPERATION_DELAY": {"config_host_valid"},
        "H6_ORDER_SERVICE_UNAVAILABLE": {"config_order_service_unreachable"},
    },
    # ---------------- inventory_app ----------------
    ("inventory_app", "get_service_health", "inventory-api"): {
        "IH0_NO_FAULT_HEALTHY": {"api_live_ready"},
        "IH1_INV_DB_UNAVAILABLE": {"api_live_ready"},
        "IH2_INV_CACHE_UNAVAILABLE": {"api_live_ready"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"api_live_ready"},
        "IH4_INV_DB_OPERATION_DELAY": {"api_live_ready"},
    },
    ("inventory_app", "get_service_health", "inventory-service"): {
        "IH0_NO_FAULT_HEALTHY": {"inv_live_ready"},
        "IH1_INV_DB_UNAVAILABLE": {"inv_not_ready_db_conn_refused"},
        "IH2_INV_CACHE_UNAVAILABLE": {"inv_not_ready_cache_conn_refused"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"inv_not_ready_db_hostname_failed"},
        "IH4_INV_DB_OPERATION_DELAY": {"inv_not_ready_db_timeout"},
    },
    ("inventory_app", "get_service_health", "inventory-db"): {
        "IH0_NO_FAULT_HEALTHY": {"inv_db_reachable_ok"},
        "IH1_INV_DB_UNAVAILABLE": {"inv_db_unreachable"},
        "IH2_INV_CACHE_UNAVAILABLE": {"inv_db_reachable_ok"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"inv_db_reachable_ok"},
        "IH4_INV_DB_OPERATION_DELAY": {"inv_db_reachable_slow"},
    },
    ("inventory_app", "get_service_health", "inventory-cache"): {
        "IH0_NO_FAULT_HEALTHY": {"inv_cache_reachable_ok"},
        "IH1_INV_DB_UNAVAILABLE": {"inv_cache_reachable_ok"},
        "IH2_INV_CACHE_UNAVAILABLE": {"inv_cache_unreachable"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"inv_cache_reachable_ok"},
        "IH4_INV_DB_OPERATION_DELAY": {"inv_cache_reachable_ok"},
    },
    ("inventory_app", "get_recent_logs", "inventory-api"): {
        "IH0_NO_FAULT_HEALTHY": {"api_logs_ok"},
        "IH1_INV_DB_UNAVAILABLE": {"api_logs_upstream_503"},
        "IH2_INV_CACHE_UNAVAILABLE": {"api_logs_upstream_503"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"api_logs_upstream_503"},
        "IH4_INV_DB_OPERATION_DELAY": {"api_logs_upstream_503", "api_logs_upstream_timeout"},
    },
    ("inventory_app", "get_recent_logs", "inventory-service"): {
        "IH0_NO_FAULT_HEALTHY": {"inv_logs_ok"},
        "IH1_INV_DB_UNAVAILABLE": {"inv_logs_db_connection_refused"},
        "IH2_INV_CACHE_UNAVAILABLE": {"inv_logs_cache_connection_refused"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"inv_logs_db_hostname_failed"},
        "IH4_INV_DB_OPERATION_DELAY": {"inv_logs_db_operation_timeout"},
    },
    ("inventory_app", "get_service_metrics", "inventory-api"): {
        "IH0_NO_FAULT_HEALTHY": {"api_metrics_normal"},
        "IH1_INV_DB_UNAVAILABLE": {"api_metrics_dep_failures_fast"},
        "IH2_INV_CACHE_UNAVAILABLE": {"api_metrics_dep_failures_fast"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"api_metrics_dep_failures_fast"},
        "IH4_INV_DB_OPERATION_DELAY": {"api_metrics_dep_failures_high_latency"},
    },
    ("inventory_app", "get_service_metrics", "inventory-service"): {
        "IH0_NO_FAULT_HEALTHY": {"inv_metrics_normal"},
        "IH1_INV_DB_UNAVAILABLE": {"inv_metrics_dep_failures_fast"},
        "IH2_INV_CACHE_UNAVAILABLE": {"inv_metrics_dep_failures_fast"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"inv_metrics_dep_failures_fast"},
        "IH4_INV_DB_OPERATION_DELAY": {"inv_metrics_dep_timeouts_high_latency"},
    },
    ("inventory_app", "check_inventory_db_connectivity", ""): {
        "IH0_NO_FAULT_HEALTHY": {"probe_ok"},
        "IH1_INV_DB_UNAVAILABLE": {"probe_connection_refused"},
        "IH2_INV_CACHE_UNAVAILABLE": {"probe_ok"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"probe_hostname_resolution_failed"},
        "IH4_INV_DB_OPERATION_DELAY": {"probe_operation_timeout"},
    },
    ("inventory_app", "check_inventory_cache_connectivity", ""): {
        "IH0_NO_FAULT_HEALTHY": {"cache_probe_ok"},
        "IH1_INV_DB_UNAVAILABLE": {"cache_probe_ok"},
        "IH2_INV_CACHE_UNAVAILABLE": {"cache_probe_connection_refused"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"cache_probe_ok"},
        "IH4_INV_DB_OPERATION_DELAY": {"cache_probe_ok"},
    },
    ("inventory_app", "get_inventory_service_config", ""): {
        "IH0_NO_FAULT_HEALTHY": {"config_host_valid"},
        "IH1_INV_DB_UNAVAILABLE": {"config_host_valid"},
        "IH2_INV_CACHE_UNAVAILABLE": {"config_host_valid"},
        "IH3_INV_DB_CONFIG_ENDPOINT": {"config_host_invalid"},
        "IH4_INV_DB_OPERATION_DELAY": {"config_host_valid"},
    },
}


def get_candidate_check_instances(app_id: str = "orders_app") -> list[tuple[str, dict[str, Any]]]:
    """Return the ordered list of allowlisted (check_name, params) candidate check instances for an application."""
    if app_id == "inventory_app":
        return [
            ("get_service_health", {"service": "inventory-api"}),
            ("get_service_health", {"service": "inventory-service"}),
            ("get_service_health", {"service": "inventory-db"}),
            ("get_service_health", {"service": "inventory-cache"}),
            ("get_service_metrics", {"service": "inventory-service"}),
            ("get_service_metrics", {"service": "inventory-api"}),
            ("get_recent_logs", {"service": "inventory-service", "limit": 20}),
            ("get_recent_logs", {"service": "inventory-api", "limit": 20}),
            ("check_inventory_db_connectivity", {}),
            ("check_inventory_cache_connectivity", {}),
            ("get_inventory_service_config", {}),
        ]
    return [
        ("get_service_health", {"service": "gateway"}),
        ("get_service_health", {"service": "order-service"}),
        ("get_service_health", {"service": "database"}),
        ("get_service_metrics", {"service": "order-service"}),
        ("get_service_metrics", {"service": "gateway"}),
        ("get_recent_logs", {"service": "order-service", "limit": 20}),
        ("get_recent_logs", {"service": "gateway", "limit": 20}),
        ("check_database_connectivity_from_order_service", {}),
        ("get_order_service_database_config", {}),
    ]


def get_expected_outcomes_for_check_instance(
    check_name: str,
    params: dict[str, Any],
    app_id: str = "orders_app",
) -> dict[str, set[str]]:
    """Return set-valued expected outcomes per hypothesis for a specific parameterized check instance (Stage 2)."""
    svc = str(params.get("service", ""))
    key = (app_id, check_name, svc)
    if key in PARAMETERIZED_OUTCOME_MODELS:
        return PARAMETERIZED_OUTCOME_MODELS[key]
    spec = CHECK_CATALOG.get(check_name)
    if spec is None:
        return {}
    return {hid: set(outcomes) for hid, outcomes in spec.expected_outcomes_by_hypothesis.items()}


def validate_check_call(check_name: str, params: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """Validate check name and parameters against the allowlisted catalog."""
    if check_name not in CHECK_CATALOG:
        return False, f"Unknown or disallowed diagnostic check: '{check_name}'", {}

    spec = CHECK_CATALOG[check_name]
    normalized_params = dict(spec.default_params)
    normalized_params.update(params or {})

    for k, v in normalized_params.items():
        if k not in spec.allowed_params:
            return False, f"Disallowed parameter '{k}' for check '{check_name}'", {}
        if k == "limit":
            try:
                limit_int = int(v)
                if limit_int < 1 or limit_int > 50:
                    return False, f"Parameter 'limit' out of bounds [1, 50]: {v}", {}
                normalized_params[k] = limit_int
            except (TypeError, ValueError):
                return False, f"Invalid integer value for 'limit': {v}", {}
        else:
            allowed_vals = spec.allowed_params[k]
            if str(v) not in allowed_vals:
                return False, f"Invalid value '{v}' for parameter '{k}'; allowed={allowed_vals}", {}
            normalized_params[k] = str(v)

    return True, "ok", normalized_params
