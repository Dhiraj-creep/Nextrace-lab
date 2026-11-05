"""Command-line interface for the NexTrace research environment (Stages 1–10)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any
import uuid

from nextrace_lab.baseline import SUPPORTED_METHODS, run_diagnostic_investigation
from nextrace_lab.controller import (
    FAULT_CATALOG,
    ROOT_DIR,
    SUPPORTED_FAULT_NAMES,
    apply_fault,
    get_backend_name,
    get_evidence_condition,
    reset_faults,
    resolve_runtime_mode,
    set_evidence_condition,
    start_healthy_environment,
    start_healthy_inventory_environment,
    stop_environment,
    submit_inventory_reservation,
    submit_order,
    verify_inventory_persisted_independently,
    verify_order_persisted_independently,
)
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.experiment import run_experiment_suite
from nextrace_lab.lab_lock import get_lock_status
from nextrace_lab.logging_utils import utc_now_iso
from nextrace_lab.schemas import EvidenceCondition, IncidentContext


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def cmd_start(args: argparse.Namespace) -> int:
    if getattr(args, "app", "orders_app") == "inventory_app":
        res = start_healthy_inventory_environment(runtime=args.runtime)
    else:
        res = start_healthy_environment(runtime=args.runtime)
    _print_json({"command": "start", "status": "ok", **res})
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    res = stop_environment(runtime=args.runtime, app_id=getattr(args, "app", "all"))
    _print_json({"command": "stop", "status": "ok", **res})
    return 0


def cmd_lock_status(_args: argparse.Namespace) -> int:
    _print_json(get_lock_status())
    return 0


def cmd_verify_healthy(args: argparse.Namespace) -> int:
    app_choice = getattr(args, "app", "orders_app")
    if app_choice == "inventory_app":
        start_res = start_healthy_inventory_environment(runtime=args.runtime)
        req_id = f"verify-{uuid.uuid4().hex[:8]}"
        status_code, body = submit_inventory_reservation(sku=args.product_id, quantity=args.quantity, request_id=req_id)
        if status_code != 201 or "reservation_id" not in body:
            _print_json(
                {
                    "command": "verify-healthy",
                    "app": "inventory_app",
                    "status": "failed",
                    "http_status": status_code,
                    "response": body,
                }
            )
            return 1

        storage_check = verify_inventory_persisted_independently(reservation_id=body["reservation_id"], runtime=args.runtime)
        _print_json(
            {
                "command": "verify-healthy",
                "app": "inventory_app",
                "status": "ok",
                "runtime": start_res["runtime"],
                "backend": start_res["backend"],
                "http_status": status_code,
                "reservation_response": body,
                "independent_storage_verification": storage_check,
            }
        )
        return 0

    start_res = start_healthy_environment(runtime=args.runtime)
    req_id = f"verify-{uuid.uuid4().hex[:8]}"
    status_code, body = submit_order(product_id=args.product_id, quantity=args.quantity, request_id=req_id)
    if status_code != 201 or "order_id" not in body:
        _print_json(
            {
                "command": "verify-healthy",
                "app": "orders_app",
                "status": "failed",
                "http_status": status_code,
                "response": body,
            }
        )
        return 1

    storage_check = verify_order_persisted_independently(order_id=body["order_id"], runtime=args.runtime)
    _print_json(
        {
            "command": "verify-healthy",
            "app": "orders_app",
            "status": "ok",
            "runtime": start_res["runtime"],
            "backend": start_res["backend"],
            "http_status": status_code,
            "order_response": body,
            "independent_storage_verification": storage_check,
        }
    )
    return 0


def cmd_inject_fault(args: argparse.Namespace) -> int:
    res = apply_fault(fault_name=args.fault, runtime=args.runtime)
    is_inv = str(args.fault).startswith("inv_")
    req_id = f"probe-{args.fault}-{uuid.uuid4().hex[:6]}"
    if is_inv:
        status_code, body = submit_inventory_reservation(sku="sku-laptop-101", quantity=1, request_id=req_id)
    else:
        status_code, body = submit_order(product_id="sku-fault-probe", quantity=1, request_id=req_id)
    _print_json(
        {
            "command": "inject-fault",
            "status": "ok",
            **res,
            "user_symptom_probe": {
                "http_status": status_code,
                "response_body": body,
            },
        }
    )
    return 0


def cmd_reset_faults(args: argparse.Namespace) -> int:
    app_id = getattr(args, "app", "orders_app")
    res = reset_faults(runtime=args.runtime, app_id=app_id)
    _print_json({"command": "reset-faults", "status": "ok", **res})
    return 0


def cmd_set_evidence(args: argparse.Namespace) -> int:
    cond = set_evidence_condition(args.condition)
    _print_json({"command": "set-evidence", "evidence_condition": cond.value})
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    mode = resolve_runtime_mode(args.runtime)
    app_id = getattr(args, "app", "orders_app")
    backend = get_backend_name(mode, app_id=app_id)
    cond = EvidenceCondition(args.evidence) if args.evidence else get_evidence_condition()
    set_evidence_condition(cond)

    req_id = f"diag-{uuid.uuid4().hex[:8]}"
    if app_id == "inventory_app":
        submit_inventory_reservation(sku="sku-laptop-101", quantity=1, request_id=f"{req_id}-warmup")
        http_status, body = submit_inventory_reservation(sku="sku-laptop-101", quantity=2, request_id=req_id)
        entry_ep = "POST /inventory/reserve"
    else:
        submit_order(product_id="sku-diag-probe", quantity=1, request_id=f"{req_id}-warmup")
        http_status, body = submit_order(product_id="sku-diag-probe", quantity=1, request_id=req_id)
        entry_ep = "POST /orders"

    incident = IncidentContext(
        incident_id=f"inc-{uuid.uuid4().hex[:10]}",
        observed_at_utc=utc_now_iso(),
        app_id=app_id,
        entry_endpoint=entry_ep,
        request_id=req_id,
        http_status=http_status,
        symptom_summary=(
            f"{entry_ep} returned HTTP {http_status}"
            + (" (failed)" if http_status >= 400 else " (succeeded)")
        ),
        response_excerpt=body,
    )

    interface = DiagnosticInterface(evidence_condition=cond, budget_limit=args.budget, app_id=app_id)
    report = run_diagnostic_investigation(
        incident=incident,
        interface=interface,
        method_name=args.method,
        runtime_mode=mode,
        backend_name=backend,
        ai_provider=args.ai_provider,
        ai_model_name=args.ai_model,
    )
    _print_json(report.model_dump())
    return 0


def cmd_run_experiments(args: argparse.Namespace) -> int:
    conditions = [EvidenceCondition(c.strip()) for c in args.conditions.split(",") if c.strip()]
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    budgets = [int(b.strip()) for b in args.budgets.split(",") if b.strip()]
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    res = run_experiment_suite(
        scenarios=scenarios,  # type: ignore[arg-type]
        evidence_conditions=conditions,
        budgets=budgets,
        methods=methods,
        repetitions=args.repetitions,
        runtime=args.runtime,
        tag=args.tag,
        ai_provider=args.ai_provider,
        ai_model_name=args.ai_model,
        random_seed=args.seed,
        counterbalance_methods=not args.no_counterbalance,
        stopping_policy_mode=args.stopping_policy_mode,
    )
    _print_json(res)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    dashboard_script = ROOT_DIR / "nextrace_lab" / "dashboard.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_script),
        "--server.port",
        str(args.port),
    ]
    return subprocess.call(cmd, cwd=str(ROOT_DIR))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nextrace_lab",
        description="NexTrace Multi-Application Evidence-Based Root Cause Diagnosis Research Lab CLI",
    )
    parser.add_argument(
        "--runtime",
        choices=["auto", "local", "docker"],
        default=None,
        help="Runtime mode ('local' SQLite+FastAPI or 'docker' PostgreSQL+Docker Compose).",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_start = sub.add_parser("start", help="Start or restore healthy environment.")
    p_start.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_start.add_argument("--app", choices=["orders_app", "inventory_app"], default="orders_app")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop running services without deleting persistent data.")
    p_stop.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_stop.add_argument("--app", choices=["orders_app", "inventory_app", "all"], default="all")
    p_stop.set_defaults(func=cmd_stop)

    p_lock = sub.add_parser("lock-status", help="Inspect current cross-process LabExecutionLock status.")
    p_lock.set_defaults(func=cmd_lock_status)

    p_verify = sub.add_parser("verify-healthy", help="Run end-to-end healthy order creation and direct DB check.")
    p_verify.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_verify.add_argument("--app", choices=["orders_app", "inventory_app"], default="orders_app")
    p_verify.add_argument("--product-id", default="sku-laptop-101")
    p_verify.add_argument("--quantity", type=int, default=2)
    p_verify.set_defaults(func=cmd_verify_healthy)

    p_fault = sub.add_parser("inject-fault", help="Inject a controlled fault scenario.")
    p_fault.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_fault.add_argument("fault", choices=list(SUPPORTED_FAULT_NAMES))
    p_fault.set_defaults(func=cmd_inject_fault)

    p_reset = sub.add_parser("reset-faults", help="Clear injected faults and restore healthy state.")
    p_reset.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_reset.add_argument("--app", choices=["orders_app", "inventory_app"], default="orders_app")
    p_reset.set_defaults(func=cmd_reset_faults)

    p_ev = sub.add_parser("set-evidence", help="Set evidence availability condition (E0, E1, E2, E3, E4, E5).")
    p_ev.add_argument("condition", choices=["E0", "E1", "E2", "E3", "E4", "E5"])
    p_ev.set_defaults(func=cmd_set_evidence)

    p_diag = sub.add_parser("diagnose", help="Trigger an entry probe and run a diagnostic method.")
    p_diag.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_diag.add_argument("--app", choices=["orders_app", "inventory_app"], default="orders_app")
    p_diag.add_argument("--evidence", choices=["E0", "E1", "E2", "E3", "E4", "E5"], default=None)
    p_diag.add_argument("--budget", type=int, default=8)
    p_diag.add_argument("--method", choices=list(SUPPORTED_METHODS), default="scored_adaptive_v1")
    p_diag.add_argument(
        "--ai-provider",
        choices=["mock-deterministic", "gemini", "openai"],
        default="mock-deterministic",
    )
    p_diag.add_argument("--ai-model", default=None)
    p_diag.set_defaults(func=cmd_diagnose)

    p_exp = sub.add_parser("run-experiments", help="Execute comparative experiment matrix and save artifacts.")
    p_exp.add_argument("--runtime", choices=["auto", "local", "docker"], default=argparse.SUPPRESS, help="Runtime mode.")
    p_exp.add_argument(
        "--scenarios",
        default="healthy,fault_a,fault_b,fault_c,fault_d,fault_e,fault_f",
        help=f"Comma-separated scenarios from {list(FAULT_CATALOG.keys())}",
    )
    p_exp.add_argument("--conditions", default="E0,E1,E2,E3", help="Comma-separated conditions E0..E5")
    p_exp.add_argument("--budgets", default="4,6,8", help="Comma-separated budget limits (e.g., 3,4,6,8)")
    p_exp.add_argument(
        "--methods",
        default="deterministic_checklist_v1,deterministic_checklist_early_stop_v1,improved_checklist_v1,improved_checklist_early_stop_v1,rule_adaptive_v1,scored_adaptive_v1",
        help=f"Comma-separated methods from {list(SUPPORTED_METHODS)}",
    )
    p_exp.add_argument("--repetitions", type=int, default=1)
    p_exp.add_argument("--seed", type=int, default=42)
    p_exp.add_argument("--no-counterbalance", action="store_true")
    p_exp.add_argument(
        "--stopping-policy-mode",
        choices=["first_supported_cause", "investigate_additional_causes", "fixed_no_early_stop", "legacy_phase3_v1"],
        default=None,
        help="Optional uniform stopping policy mode override.",
    )
    p_exp.add_argument("--tag", default="phase3-comparative")
    p_exp.add_argument(
        "--ai-provider",
        choices=["mock-deterministic", "gemini", "openai"],
        default="mock-deterministic",
    )
    p_exp.add_argument("--ai-model", default=None)
    p_exp.set_defaults(func=cmd_run_experiments)

    p_dash = sub.add_parser("dashboard", help="Launch local Streamlit research dashboard.")
    p_dash.add_argument("--port", type=int, default=8501)
    p_dash.set_defaults(func=cmd_dashboard)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
