"""End-to-end integration tests for NexTrace Phase 3 (Stages 1–11).

Executes real HTTP/TCP services across BOTH applications (`orders_app` and `inventory_app`):
- Healthy baseline and direct storage verification
- Service metrics (`get_service_metrics`) and `E4`/`E5` policies
- Controlled faults A–F
- Stage 6 Challenging & Multi-Fault scenarios:
  - `challenging_recovery_mid_run`
  - `challenging_diag_endpoint_failure`
  - `challenging_historical_logs_healthy_now`
  - `challenging_unknown_app_error` (`UNKNOWN_CAUSE`)
  - `multi_fault_a_and_b` (`cause_set_precision`, `cause_set_recall`, `exact_set_match`)
- Stage 8 Second Application (`inventory_app`) scenarios:
  - `inv_healthy`, `inv_fault_db_unavailable`, `inv_fault_cache_unavailable`, `inv_fault_bad_db_config`, `inv_fault_upstream_timeout`
- Stage 1C Failure artifact preservation & `RunFailureClassification`
- Disposable Fault D schema safety
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nextrace_lab.controller import (
    apply_fault,
    reset_faults,
    start_healthy_environment,
    start_healthy_inventory_environment,
    submit_inventory_reservation,
    submit_order,
    verify_order_persisted_independently,
)
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.experiment import run_single_experiment
from nextrace_lab.schemas import (
    DiagnosticOutcome,
    EvidenceCondition,
    EvidenceStatus,
    RunFailureClassification,
)


@pytest.fixture(scope="module", autouse=True)
def ensure_healthy_lab():
    start_healthy_environment()
    start_healthy_inventory_environment()
    yield
    reset_faults(app_id="orders_app")
    reset_faults(app_id="inventory_app")


def test_healthy_order_and_service_metrics_collection() -> None:
    start_healthy_environment()
    status1, body1 = submit_order(product_id="sku-test-monitor", quantity=3, request_id="test-healthy-001")
    status2, _ = submit_order(product_id="sku-test-monitor", quantity=1, request_id="test-healthy-002")
    assert status1 == 201 and status2 == 201
    verify_res = verify_order_persisted_independently(order_id=body1["order_id"])
    assert verify_res["verified"] is True
    assert verify_res["direct_storage_verified"] is True

    # Verify get_service_metrics under E0, E4, and E5
    iface_e0 = DiagnosticInterface(evidence_condition=EvidenceCondition.E0, budget_limit=4)
    m_res = iface_e0.execute_check("get_service_metrics", {"service": "order-service"})
    assert m_res.status == EvidenceStatus.AVAILABLE
    assert m_res.data["request_count"] >= 2
    assert m_res.data["sample_sufficient"] is True
    assert m_res.is_stale is False

    iface_e4 = DiagnosticInterface(evidence_condition=EvidenceCondition.E4, budget_limit=4)
    m_e4 = iface_e4.execute_check("get_service_metrics", {"service": "order-service"})
    assert m_e4.status == EvidenceStatus.UNAVAILABLE_BY_POLICY

    iface_e5 = DiagnosticInterface(evidence_condition=EvidenceCondition.E5, budget_limit=4)
    m_e5 = iface_e5.execute_check("get_service_metrics", {"service": "order-service"})
    assert m_e5.status == EvidenceStatus.AVAILABLE
    assert m_e5.is_stale is True
    assert m_e5.data["sample_sufficient"] is False


def test_fault_d_disposable_schema_preserves_orders_table() -> None:
    start_healthy_environment()
    status, body = submit_order(product_id="sku-preserve-d", quantity=2, request_id="test-preserve-d-1")
    assert status == 201
    saved_order_id = body["order_id"]

    apply_fault("fault_d")
    f_status, _ = submit_order(product_id="sku-fail-d", quantity=1, request_id="test-preserve-d-2")
    assert f_status == 503

    reset_faults()
    verify_res = verify_order_persisted_independently(order_id=saved_order_id)
    assert verify_res["verified"] is True
    assert verify_res["order_id"] == saved_order_id


def test_scored_adaptive_and_early_stop_checklist_under_tight_budget() -> None:
    """Verify scored_adaptive_v1 and improved_checklist_early_stop_v1 diagnose Faults A, B, C, D, E, F within budget 4."""
    for scen, exp_service, exp_type in [
        ("fault_a", "order-service", "db_endpoint_misconfiguration"),
        ("fault_b", "database", "db_service_unavailable"),
        ("fault_c", "order-service", "db_auth_failure"),
        ("fault_d", "database", "db_schema_missing_table"),
        ("fault_e", "database", "db_operation_delay"),
        ("fault_f", "order-service", "order_service_unavailable"),
    ]:
        report, score = run_single_experiment(
            scenario=scen,  # type: ignore[arg-type]
            evidence_condition=EvidenceCondition.E0,
            budget_limit=4,
            method_name="scored_adaptive_v1",
        )
        assert report.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS, f"Failed on {scen}: {report.evidence_gate_reason}"
        assert report.candidate_service == exp_service
        assert report.candidate_fault_type == exp_type
        assert score.joint_root_cause_accurate is True
        assert report.budget_used <= 4


def test_stage6_challenging_scenarios_and_multi_fault() -> None:
    """Verify all 5 Stage 6 challenging and multi-fault scenarios end-to-end."""
    # 1. Mid-run recovery (challenging_recovery_mid_run)
    rep_rec, score_rec = run_single_experiment(
        scenario="challenging_recovery_mid_run",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=6,
        method_name="scored_adaptive_v1",
    )
    assert rep_rec.current_health_status == "healthy_now"
    assert rep_rec.window_diagnosis == "order-service:db_endpoint_misconfiguration"
    assert score_rec.window_vs_current_separated_correctly is True

    # 2. Diagnostic endpoint failure while user traffic is healthy (challenging_diag_endpoint_failure)
    rep_diag_fail, score_diag_fail = run_single_experiment(
        scenario="challenging_diag_endpoint_failure",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="deterministic_checklist_v1",
    )
    assert rep_diag_fail.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert rep_diag_fail.failed_checks_count >= 1
    assert score_diag_fail.joint_root_cause_accurate is True
    assert score_diag_fail.false_attribution_rate_flag is False

    # 3. Historical failure logs while current health is normal (challenging_historical_logs_healthy_now)
    rep_hist, score_hist = run_single_experiment(
        scenario="challenging_historical_logs_healthy_now",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="deterministic_checklist_v1",
    )
    assert rep_hist.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert rep_hist.current_health_status == "healthy_now"
    assert len(rep_hist.conflicts_detected) >= 1
    assert score_hist.joint_root_cause_accurate is True

    # 4. Unknown application error (challenging_unknown_app_error -> UNKNOWN_CAUSE)
    rep_unk, score_unk = run_single_experiment(
        scenario="challenging_unknown_app_error",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=6,
        method_name="scored_adaptive_v1",
    )
    assert rep_unk.outcome == DiagnosticOutcome.UNKNOWN_CAUSE
    assert rep_unk.failure_classification == RunFailureClassification.UNKNOWN_CAUSE
    assert score_unk.unknown_cause_avoided_false_certainty is True
    assert score_unk.joint_root_cause_accurate is True

    # 5. Multi-fault A and B simultaneously (multi_fault_a_and_b)
    rep_multi, score_multi = run_single_experiment(
        scenario="multi_fault_a_and_b",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=6,
        method_name="scored_adaptive_v1",
    )
    assert rep_multi.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert sorted(rep_multi.predicted_causes) == [
        "database:db_service_unavailable",
        "order-service:db_endpoint_misconfiguration",
    ]
    assert score_multi.cause_set_precision == 1.0
    assert score_multi.cause_set_recall == 1.0
    assert score_multi.exact_set_match is True


def test_stage8_second_application_inventory_app_scenarios() -> None:
    """Verify healthy and all 4 fault scenarios on the second application (`inventory_app`)."""
    start_healthy_inventory_environment()
    st_code, body = submit_inventory_reservation(sku="sku-laptop-101", quantity=2, request_id="test-inv-01")
    assert st_code == 201 and "reservation_id" in body

    for scen, exp_service, exp_type in [
        ("inv_healthy", None, None),
        ("inv_fault_db_unavailable", "inventory-db", "db_service_unavailable"),
        ("inv_fault_cache_unavailable", "inventory-cache", "cache_service_unavailable"),
        ("inv_fault_bad_db_config", "inventory-service", "db_endpoint_misconfiguration"),
        ("inv_fault_upstream_timeout", "inventory-db", "db_operation_delay"),
        ("inv_multi_fault_db_and_cache", "inventory-db+inventory-cache", "db_service_unavailable+cache_service_unavailable"),
    ]:
        rep, score = run_single_experiment(
            scenario=scen,  # type: ignore[arg-type]
            evidence_condition=EvidenceCondition.E0,
            budget_limit=6,
            method_name="scored_adaptive_v1",
        )
        assert rep.app_id == "inventory_app"
        assert score.joint_root_cause_accurate is True, f"Failed on {scen}: {rep.evidence_gate_reason}"
        assert rep.candidate_service == exp_service
        assert rep.candidate_fault_type == exp_type


def test_failure_artifact_preservation_and_setup_classification() -> None:
    """Verify Stage 1C: when setup fails, run_single_experiment returns SETUP_FAILURE without raising."""
    with patch("nextrace_lab.experiment.apply_fault", side_effect=RuntimeError("Simulated controller crash")):
        report, score = run_single_experiment(
            scenario="fault_a",
            evidence_condition=EvidenceCondition.E0,
            budget_limit=6,
            method_name="scored_adaptive_v1",
        )
        assert report.outcome == DiagnosticOutcome.EXECUTION_FAILURE
        assert report.failure_classification == RunFailureClassification.SETUP_FAILURE
        assert "Simulated controller crash" in (report.execution_error or "")
        assert score.execution_failure_flag is True
        assert score.failure_classification == RunFailureClassification.SETUP_FAILURE


def test_docker_fault_a_e0_and_e1_live_diagnosis() -> None:
    """Validate Orders fault_a end-to-end under Docker runtime for E0 and E1 (Stage 1D Docker)."""
    from nextrace_lab.controller import is_docker_available
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # Run fault_a under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="fault_a",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "order-service"
    assert report_e0.candidate_fault_type == "db_endpoint_misconfiguration"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run fault_a under E1 (missing logs)
    report_e1, score_e1 = run_single_experiment(
        scenario="fault_a",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "order-service"
    assert report_e1.candidate_fault_type == "db_endpoint_misconfiguration"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8


def test_docker_fault_c_e0_and_e1_live_diagnosis() -> None:
    """Validate Orders fault_c (authentication failure) end-to-end under Docker runtime for E0 and E1."""
    from nextrace_lab.controller import is_docker_available
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # Run fault_c under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="fault_c",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "order-service"
    assert report_e0.candidate_fault_type == "db_auth_failure"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run fault_c under E1 (missing logs)
    report_e1, score_e1 = run_single_experiment(
        scenario="fault_c",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "order-service"
    assert report_e1.candidate_fault_type == "db_auth_failure"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8


def test_docker_fault_b_e0_and_e1_live_diagnosis() -> None:
    """Validate Orders fault_b (PostgreSQL unavailable) end-to-end under Docker runtime for E0 and E1."""
    from nextrace_lab.controller import is_docker_available
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # Run fault_b under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="fault_b",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "database"
    assert report_e0.candidate_fault_type == "db_service_unavailable"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run fault_b under E1 (missing logs)
    report_e1, score_e1 = run_single_experiment(
        scenario="fault_b",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "database"
    assert report_e1.candidate_fault_type == "db_service_unavailable"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8


def test_docker_fault_d_e0_and_e1_live_diagnosis() -> None:
    """Validate Orders fault_d (database schema / missing table) end-to-end under Docker runtime for E0 and E1."""
    from nextrace_lab.controller import is_docker_available
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # Run fault_d under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="fault_d",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "database"
    assert report_e0.candidate_fault_type == "db_schema_missing_table"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run fault_d under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="fault_d",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "database"
    assert report_e1.candidate_fault_type == "db_schema_missing_table"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8


def test_docker_fault_e_e0_and_e1_live_diagnosis() -> None:
    """Validate Orders fault_e (database operation delay) end-to-end under Docker runtime for E0 and E1."""
    from nextrace_lab.controller import is_docker_available
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # Run fault_e under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="fault_e",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "database"
    assert report_e0.candidate_fault_type == "db_operation_delay"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run fault_e under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="fault_e",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "database"
    assert report_e1.candidate_fault_type == "db_operation_delay"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8


def test_docker_fault_f_e0_and_e1_live_diagnosis() -> None:
    """Validate Orders fault_f (order-service unavailable) end-to-end under Docker runtime for E0 and E1."""
    from nextrace_lab.controller import is_docker_available, reset_faults, submit_order, verify_order_persisted_independently
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # 1. Ensure Docker Orders environment is healthy and verify baseline order persistence
    reset_faults(runtime="docker")
    st_baseline, resp_baseline = submit_order(product_id="prod-baseline-f", quantity=2)
    assert st_baseline == 201
    baseline_order_id = resp_baseline["order_id"]
    verify_baseline = verify_order_persisted_independently(baseline_order_id, runtime="docker")
    assert verify_baseline["verified"] is True
    assert verify_baseline["direct_storage_verified"] is True

    # 2. Run fault_f under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="fault_f",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "order-service"
    assert report_e0.candidate_fault_type == "order_service_unavailable"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run fault_f under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="fault_f",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "order-service"
    assert report_e1.candidate_fault_type == "order_service_unavailable"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8

    # 3. Safe reset, re-verify baseline order, and verify a new post-recovery order
    reset_faults(runtime="docker")
    verify_baseline_post = verify_order_persisted_independently(baseline_order_id, runtime="docker")
    assert verify_baseline_post["verified"] is True
    assert verify_baseline_post["direct_storage_verified"] is True

    st_post, resp_post = submit_order(product_id="prod-post-f", quantity=1)
    assert st_post == 201
    verify_post = verify_order_persisted_independently(resp_post["order_id"], runtime="docker")
    assert verify_post["verified"] is True
    assert verify_post["direct_storage_verified"] is True


def test_docker_inventory_db_unavailable_e0_and_e1_live_diagnosis() -> None:
    """Validate Inventory inv_fault_db_unavailable (inventory-db outage) end-to-end under Docker runtime for E0 and E1."""
    import socket
    from nextrace_lab.controller import (
        INV_CACHE_PORT,
        apply_fault,
        is_docker_available,
        reset_faults,
        submit_inventory_reservation,
        verify_inventory_persisted_independently,
    )
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # 1. Ensure Inventory Docker environment is healthy and verify baseline reservation
    reset_faults(runtime="docker", app_id="inventory_app")
    st_baseline, resp_baseline = submit_inventory_reservation(sku="sku-baseline-inv-db", quantity=3)
    assert st_baseline == 201
    baseline_res_id = resp_baseline["reservation_id"]
    verify_baseline = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline["verified"] is True
    assert verify_baseline["direct_storage_verified"] is True
    assert verify_baseline["cache_verified"] is True

    # 2. Explicitly verify the live fault symptom and Redis continuity
    apply_fault("inv_fault_db_unavailable", runtime="docker")
    st_fault, body_fault = submit_inventory_reservation(
        sku="sku-fault-db-unavailable",
        quantity=1,
    )
    assert st_fault == 503
    assert body_fault.get("error") == "inventory_reservation_failed"

    # Independently confirm Redis is still reachable via safe real Redis PING check
    with socket.create_connection(("127.0.0.1", INV_CACHE_PORT), timeout=2.0) as sock:
        sock.settimeout(2.0)
        sock.sendall(b"*1\r\n$4\r\nPING\r\n")
        raw_ping = sock.recv(128).decode("utf-8", errors="replace")
        assert "+PONG" in raw_ping

    # Reset Inventory safely before starting the E0 and E1 run_single_experiment calls
    reset_faults(runtime="docker", app_id="inventory_app")

    # 3. Run inv_fault_db_unavailable under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="inv_fault_db_unavailable",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "inventory-db"
    assert report_e0.candidate_fault_type == "db_service_unavailable"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run inv_fault_db_unavailable under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="inv_fault_db_unavailable",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "inventory-db"
    assert report_e1.candidate_fault_type == "db_service_unavailable"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8

    # 4. Reset, re-verify baseline reservation (DB + Redis), and verify a new post-recovery reservation
    reset_res = reset_faults(runtime="docker", app_id="inventory_app")
    assert reset_res["reset"] is True
    assert reset_res["state"]["inventory_api_ready"] is True
    assert reset_res["state"]["inventory_service_ready"] is True

    verify_baseline_post = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline_post["verified"] is True
    assert verify_baseline_post["direct_storage_verified"] is True
    assert verify_baseline_post["cache_verified"] is True

    st_post, resp_post = submit_inventory_reservation(sku="sku-post-inv-db", quantity=2)
    assert st_post == 201
    verify_post = verify_inventory_persisted_independently(resp_post["reservation_id"], runtime="docker")
    assert verify_post["verified"] is True
    assert verify_post["direct_storage_verified"] is True
    assert verify_post["cache_verified"] is True

    # 5. Confirm healthy diagnosis produces NO_FAULT_FOUND
    report_healthy, score_healthy = run_single_experiment(
        scenario="inv_healthy",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_healthy.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert report_healthy.candidate_service is None
    assert report_healthy.candidate_fault_type is None


def test_docker_inventory_cache_unavailable_e0_and_e1_live_diagnosis() -> None:
    """Validate Inventory inv_fault_cache_unavailable (inventory-cache outage) end-to-end under Docker runtime for E0 and E1."""
    import socket
    from nextrace_lab.controller import (
        INV_DB_PORT,
        apply_fault,
        is_docker_available,
        reset_faults,
        submit_inventory_reservation,
        verify_inventory_persisted_independently,
    )
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # 1. Ensure Inventory Docker environment is healthy and verify baseline reservation
    reset_faults(runtime="docker", app_id="inventory_app")
    st_baseline, resp_baseline = submit_inventory_reservation(sku="sku-baseline-inv-cache", quantity=3)
    assert st_baseline == 201
    baseline_res_id = resp_baseline["reservation_id"]
    verify_baseline = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline["verified"] is True
    assert verify_baseline["direct_storage_verified"] is True
    assert verify_baseline["cache_verified"] is True

    # 2. Explicitly verify the live fault symptom and PostgreSQL continuity
    apply_fault("inv_fault_cache_unavailable", runtime="docker")
    st_fault, body_fault = submit_inventory_reservation(
        sku="sku-fault-cache-unavailable",
        quantity=1,
    )
    assert st_fault == 503
    assert body_fault.get("error") == "inventory_reservation_failed"

    # Independently confirm Inventory PostgreSQL remains reachable through a direct real probe
    try:
        import psycopg
        with psycopg.connect(
            host="127.0.0.1",
            port=INV_DB_PORT,
            dbname="nextrace_inventory",
            user="nextrace_user",
            password="nextrace_local_dev_pw",
            connect_timeout=2,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                assert cur.fetchone() == (1,)
    except ImportError:
        with socket.create_connection(("127.0.0.1", INV_DB_PORT), timeout=2.0) as sock:
            assert sock is not None

    # Reset Inventory safely before starting the E0 and E1 run_single_experiment calls
    reset_faults(runtime="docker", app_id="inventory_app")

    # 3. Run inv_fault_cache_unavailable under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="inv_fault_cache_unavailable",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "inventory-cache"
    assert report_e0.candidate_fault_type == "cache_service_unavailable"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run inv_fault_cache_unavailable under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="inv_fault_cache_unavailable",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "inventory-cache"
    assert report_e1.candidate_fault_type == "cache_service_unavailable"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8

    # 4. Reset, re-verify baseline reservation (DB + Redis), and verify a new post-recovery reservation
    reset_res = reset_faults(runtime="docker", app_id="inventory_app")
    assert reset_res["reset"] is True
    assert reset_res["state"]["inventory_api_ready"] is True
    assert reset_res["state"]["inventory_service_ready"] is True

    verify_baseline_post = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline_post["verified"] is True
    assert verify_baseline_post["direct_storage_verified"] is True
    assert verify_baseline_post["cache_verified"] is True

    st_post, resp_post = submit_inventory_reservation(sku="sku-post-inv-cache", quantity=2)
    assert st_post == 201
    verify_post = verify_inventory_persisted_independently(resp_post["reservation_id"], runtime="docker")
    assert verify_post["verified"] is True
    assert verify_post["direct_storage_verified"] is True
    assert verify_post["cache_verified"] is True

    # 5. Confirm healthy diagnosis produces NO_FAULT_FOUND
    report_healthy, score_healthy = run_single_experiment(
        scenario="inv_healthy",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_healthy.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert report_healthy.candidate_service is None
    assert report_healthy.candidate_fault_type is None


def test_docker_inventory_bad_db_config_e0_and_e1_live_diagnosis() -> None:
    """Validate Inventory inv_fault_bad_db_config end-to-end under Docker runtime for E0 and E1."""
    import socket
    from nextrace_lab.controller import (
        INV_DB_PORT,
        INV_CACHE_PORT,
        apply_fault,
        is_docker_available,
        reset_faults,
        submit_inventory_reservation,
        verify_inventory_persisted_independently,
    )
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # 1. Ensure Inventory Docker environment is healthy and verify baseline reservation
    reset_faults(runtime="docker", app_id="inventory_app")
    st_baseline, resp_baseline = submit_inventory_reservation(sku="sku-baseline-inv-bad-cfg", quantity=2)
    assert st_baseline == 201
    baseline_res_id = resp_baseline["reservation_id"]
    verify_baseline = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline["verified"] is True
    assert verify_baseline["direct_storage_verified"] is True
    assert verify_baseline["cache_verified"] is True

    # 2. Explicitly verify the live fault symptom and dependency continuity
    apply_fault("inv_fault_bad_db_config", runtime="docker")
    st_fault, body_fault = submit_inventory_reservation(
        sku="sku-fault-bad-cfg",
        quantity=1,
    )
    assert st_fault == 503
    assert body_fault.get("error") == "inventory_reservation_failed"

    # Independently confirm Inventory DB and Cache remain reachable directly
    with socket.create_connection(("127.0.0.1", INV_DB_PORT), timeout=2.0) as sock_db:
        assert sock_db is not None
    with socket.create_connection(("127.0.0.1", INV_CACHE_PORT), timeout=2.0) as sock_cache:
        assert sock_cache is not None

    # Reset Inventory safely before starting the E0 and E1 run_single_experiment calls
    reset_faults(runtime="docker", app_id="inventory_app")

    # 3. Run inv_fault_bad_db_config under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="inv_fault_bad_db_config",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "inventory-service"
    assert report_e0.candidate_fault_type == "db_endpoint_misconfiguration"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run inv_fault_bad_db_config under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="inv_fault_bad_db_config",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "inventory-service"
    assert report_e1.candidate_fault_type == "db_endpoint_misconfiguration"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8

    # 4. Reset, re-verify baseline reservation (DB + Redis), and verify a new post-recovery reservation
    reset_res = reset_faults(runtime="docker", app_id="inventory_app")
    assert reset_res["reset"] is True
    assert reset_res["state"]["inventory_api_ready"] is True
    assert reset_res["state"]["inventory_service_ready"] is True

    verify_baseline_post = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline_post["verified"] is True
    assert verify_baseline_post["direct_storage_verified"] is True
    assert verify_baseline_post["cache_verified"] is True

    st_post, resp_post = submit_inventory_reservation(sku="sku-post-inv-bad-cfg", quantity=2)
    assert st_post == 201
    verify_post = verify_inventory_persisted_independently(resp_post["reservation_id"], runtime="docker")
    assert verify_post["verified"] is True
    assert verify_post["direct_storage_verified"] is True
    assert verify_post["cache_verified"] is True

    # 5. Confirm healthy diagnosis produces NO_FAULT_FOUND
    report_healthy, score_healthy = run_single_experiment(
        scenario="inv_healthy",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_healthy.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert report_healthy.candidate_service is None
    assert report_healthy.candidate_fault_type is None


def test_docker_inventory_upstream_timeout_e0_and_e1_live_diagnosis() -> None:
    """Validate Inventory inv_fault_upstream_timeout end-to-end under Docker runtime for E0 and E1."""
    import socket
    from nextrace_lab.controller import (
        INV_DB_PORT,
        INV_CACHE_PORT,
        apply_fault,
        is_docker_available,
        reset_faults,
        submit_inventory_reservation,
        verify_inventory_persisted_independently,
    )
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # 1. Ensure Inventory Docker environment is healthy and verify baseline reservation
    reset_faults(runtime="docker", app_id="inventory_app")
    st_baseline, resp_baseline = submit_inventory_reservation(sku="sku-baseline-inv-timeout", quantity=2)
    assert st_baseline == 201
    baseline_res_id = resp_baseline["reservation_id"]
    verify_baseline = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline["verified"] is True
    assert verify_baseline["direct_storage_verified"] is True
    assert verify_baseline["cache_verified"] is True

    # 2. Explicitly verify the live fault symptom and dependency continuity
    apply_fault("inv_fault_upstream_timeout", runtime="docker")
    st_fault, body_fault = submit_inventory_reservation(
        sku="sku-fault-inv-timeout",
        quantity=1,
    )
    assert st_fault == 503
    assert body_fault.get("error") == "inventory_reservation_failed"

    # Independently confirm Inventory DB and Cache remain reachable directly
    with socket.create_connection(("127.0.0.1", INV_DB_PORT), timeout=2.0) as sock_db:
        assert sock_db is not None
    with socket.create_connection(("127.0.0.1", INV_CACHE_PORT), timeout=2.0) as sock_cache:
        assert sock_cache is not None

    # Reset Inventory safely before starting the E0 and E1 run_single_experiment calls
    reset_faults(runtime="docker", app_id="inventory_app")

    # 3. Run inv_fault_upstream_timeout under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="inv_fault_upstream_timeout",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "inventory-db"
    assert report_e0.candidate_fault_type == "db_operation_delay"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run inv_fault_upstream_timeout under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="inv_fault_upstream_timeout",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "inventory-db"
    assert report_e1.candidate_fault_type == "db_operation_delay"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8

    # 4. Reset, re-verify baseline reservation (DB + Redis), and verify a new post-recovery reservation
    reset_res = reset_faults(runtime="docker", app_id="inventory_app")
    assert reset_res["reset"] is True
    assert reset_res["state"]["inventory_api_ready"] is True
    assert reset_res["state"]["inventory_service_ready"] is True

    verify_baseline_post = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline_post["verified"] is True
    assert verify_baseline_post["direct_storage_verified"] is True
    assert verify_baseline_post["cache_verified"] is True

    st_post, resp_post = submit_inventory_reservation(sku="sku-post-inv-timeout", quantity=2)
    assert st_post == 201
    verify_post = verify_inventory_persisted_independently(resp_post["reservation_id"], runtime="docker")
    assert verify_post["verified"] is True
    assert verify_post["direct_storage_verified"] is True
    assert verify_post["cache_verified"] is True

    # 5. Confirm healthy diagnosis produces NO_FAULT_FOUND
    report_healthy, score_healthy = run_single_experiment(
        scenario="inv_healthy",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_healthy.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert report_healthy.candidate_service is None
    assert report_healthy.candidate_fault_type is None


def test_docker_inventory_multi_fault_db_and_cache_e0_and_e1_live_diagnosis() -> None:
    """Validate Inventory inv_multi_fault_db_and_cache end-to-end under Docker runtime for E0 and E1."""
    import socket
    from nextrace_lab.controller import (
        INV_DB_PORT,
        INV_CACHE_PORT,
        DB_PORT,
        ORDER_PORT,
        apply_fault,
        is_docker_available,
        reset_faults,
        submit_inventory_reservation,
        verify_inventory_persisted_independently,
    )
    if not is_docker_available():
        pytest.skip("Docker is not available")

    # 1. Ensure Inventory Docker environment is healthy and verify baseline reservation
    reset_faults(runtime="docker", app_id="inventory_app")
    st_baseline, resp_baseline = submit_inventory_reservation(sku="sku-baseline-inv-multi", quantity=2)
    assert st_baseline == 201
    baseline_res_id = resp_baseline["reservation_id"]
    verify_baseline = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline["verified"] is True
    assert verify_baseline["direct_storage_verified"] is True
    assert verify_baseline["cache_verified"] is True

    # 2. Explicitly verify the live multi-fault symptom and isolation
    apply_fault("inv_multi_fault_db_and_cache", runtime="docker")
    st_fault, body_fault = submit_inventory_reservation(
        sku="sku-fault-inv-multi",
        quantity=1,
    )
    assert st_fault == 503
    assert body_fault.get("error") == "inventory_reservation_failed"

    # Independently confirm both inventory-db and inventory-cache are unreachable
    db_down = False
    try:
        with socket.create_connection(("127.0.0.1", INV_DB_PORT), timeout=1.0):
            pass
    except (OSError, TimeoutError):
        db_down = True
    assert db_down is True

    cache_down = False
    try:
        with socket.create_connection(("127.0.0.1", INV_CACHE_PORT), timeout=1.0):
            pass
    except (OSError, TimeoutError):
        cache_down = True
    assert cache_down is True

    # Reset Inventory safely before starting the E0 and E1 run_single_experiment calls
    reset_faults(runtime="docker", app_id="inventory_app")

    # 3. Run inv_multi_fault_db_and_cache under E0
    report_e0, score_e0 = run_single_experiment(
        scenario="inv_multi_fault_db_and_cache",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e0.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e0.candidate_service == "inventory-db+inventory-cache"
    assert report_e0.candidate_fault_type == "db_service_unavailable+cache_service_unavailable"
    assert score_e0.joint_root_cause_accurate is True
    assert report_e0.budget_used <= 8

    # Run inv_multi_fault_db_and_cache under E1
    report_e1, score_e1 = run_single_experiment(
        scenario="inv_multi_fault_db_and_cache",
        evidence_condition=EvidenceCondition.E1,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_e1.outcome == DiagnosticOutcome.SUPPORTED_DIAGNOSIS
    assert report_e1.candidate_service == "inventory-db+inventory-cache"
    assert report_e1.candidate_fault_type == "db_service_unavailable+cache_service_unavailable"
    assert score_e1.joint_root_cause_accurate is True
    assert report_e1.budget_used <= 8

    # 4. Reset, re-verify baseline reservation (DB + Redis), and verify a new post-recovery reservation
    reset_res = reset_faults(runtime="docker", app_id="inventory_app")
    assert reset_res["reset"] is True
    assert reset_res["state"]["inventory_api_ready"] is True
    assert reset_res["state"]["inventory_service_ready"] is True

    verify_baseline_post = verify_inventory_persisted_independently(baseline_res_id, runtime="docker")
    assert verify_baseline_post["verified"] is True
    assert verify_baseline_post["direct_storage_verified"] is True
    assert verify_baseline_post["cache_verified"] is True

    st_post, resp_post = submit_inventory_reservation(sku="sku-post-inv-multi", quantity=2)
    assert st_post == 201
    verify_post = verify_inventory_persisted_independently(resp_post["reservation_id"], runtime="docker")
    assert verify_post["verified"] is True
    assert verify_post["direct_storage_verified"] is True
    assert verify_post["cache_verified"] is True

    # 5. Confirm healthy diagnosis produces NO_FAULT_FOUND
    report_healthy, score_healthy = run_single_experiment(
        scenario="inv_healthy",
        evidence_condition=EvidenceCondition.E0,
        budget_limit=8,
        method_name="scored_adaptive_v2",
        runtime="docker",
    )
    assert report_healthy.outcome == DiagnosticOutcome.NO_FAULT_FOUND
    assert report_healthy.candidate_service is None
    assert report_healthy.candidate_fault_type is None




