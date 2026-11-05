# NexTrace Team Deliverables Integration

## Purpose

This document integrates the team research, scenario-design, and evaluation contributions with the implemented NexTrace v0.4.0 repository. It distinguishes verified repository behavior from proposed future work. The frozen execution rules remain in `docs/EVALUATION_PROTOCOL.md`.

## Integrated evaluation contribution

Pooja's evaluation deliverable is integrated as a review checklist, not as a competing protocol. Every reported run must record the evidence condition, method name, stopping-policy mode, cost model, admitted checks, budget consumption, evidence-gate result, predicted cause set, and outcome.

The repository-defined identifiers are authoritative:

| Category | Implemented identifiers |
|---|---|
| Evidence policies | `E0_FULL_OBSERVABILITY`, `E1_ORDER_LOGS_UNAVAILABLE`, `E2_DB_PROBE_UNAVAILABLE`, `E3_ORDER_LOGS_AND_CONFIG_UNAVAILABLE`, `E4_METRICS_UNAVAILABLE`, `E5_METRICS_STALE` |
| Cost model | `attempt_charged_v2` |
| Stopping modes | `first_supported_cause`, `investigate_additional_causes`, `fixed_no_early_stop`, `legacy_phase3_v1` |
| Standard scored method | `scored_adaptive_v2` |

Use exact single-fault service/fault matching, cause-set precision/recall/exact match for multi-fault cases, healthy `NO_FAULT_FOUND` accuracy, budget compliance, and separately reported execution failures. Do not count blocked, stale, empty, or uncollected evidence as healthy evidence.

## Integrated scenario and use-case contribution

The implemented scenario catalogue in `nextrace_lab/controller.py` is authoritative. Rekha's scenario material is integrated as an explanatory use-case guide with this mapping:

| Use case | Implemented NexTrace coverage |
|---|---|
| Bad Orders database endpoint | `fault_a` |
| Orders PostgreSQL unavailable | `fault_b` |
| Orders database authentication failure | `fault_c` |
| Missing Orders table/schema | `fault_d` |
| Orders database delay/timeout | `fault_e` |
| Orders service unavailable | `fault_f` |
| Inventory PostgreSQL unavailable | `inv_fault_db_unavailable` |
| Inventory Redis unavailable | `inv_fault_cache_unavailable` |
| Inventory bad database configuration | `inv_fault_bad_db_config` |
| Inventory database delay | `inv_fault_upstream_timeout` |
| Simultaneous Inventory DB and Redis outage | `inv_multi_fault_db_and_cache` |

The following design scenarios are valuable future work, but are not presented as implemented: connection-pool exhaustion, Orders-to-Inventory dependency tracing, concurrent lost updates, stale cache/replica reads, and SKU mapping failures beyond the current controlled configuration fault. The current architecture has separate `orders_app` and `inventory_app`; it does not implement Rekha's proposed synchronous Order Service to Inventory Service call.

## Integrated research contribution

Vidhi's review supports a conservative positioning statement. NexTrace does not claim generic novelty for hypothesis-driven RCA, topology-aware investigation, evidence-linked reporting, budget-aware search, or missing-telemetry handling. Existing systems and research already cover related capabilities.

NexTrace's demonstrated project focus is narrower: controlled, reproducible diagnosis across two applications; explicit evidence-policy states; attempt-charged budgets; timestamp/freshness handling; centralized stopping; and recovery verification. Its claims remain limited to the included controlled scenarios and recorded experiments.

Comparable systems include IBM Instana's agentic incident investigation, Google Cloud Assist investigations, Datadog Watchdog RCA, and the Cloud-OpsBench benchmark. IBM documents topology-aware, multi-entity investigation and hypothesis refinement; Google documents source-linked observations from logs, configuration, and metrics; Cloud-OpsBench evaluates both root-cause correctness and process-quality metrics. [IBM Instana](https://www.ibm.com/docs/en/instana-observability?topic=capabilities-intelligent-incident-investigation), [Google Cloud Assist](https://docs.cloud.google.com/cloud-assist/investigations), [Cloud-OpsBench](https://github.com/LLM4Ops/Cloud-OpsBench)

## Integration rules

1. Keep `docs/EVALUATION_PROTOCOL.md` frozen unless the project team deliberately versions a replacement.
2. Treat research comparison statements as literature review, not as product-performance proof.
3. Treat only captured test outputs and saved experiment artifacts as empirical NexTrace evidence.
4. Label Docker validations skipped when the daemon is unavailable; do not convert a skipped test into a passed claim.
5. Keep live paid-AI results separate from mock/offline results until an authorized key, model, and cost cap are supplied.

## Completion status and verification gates

- **Orders Docker Scenarios (A–F):** Fully implemented, verified with unit tests and dedicated validation documents ([`ORDERS_DOCKER_FAULT_A_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_A_VALIDATION.md) through [`ORDERS_DOCKER_FAULT_F_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_F_VALIDATION.md)).
- **Inventory Docker Scenarios:** Fully implemented, verified with unit tests and dedicated validation documents:
  - Database Outage: [`INVENTORY_DOCKER_FAULT_DB_UNAVAILABLE_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_DB_UNAVAILABLE_VALIDATION.md)
  - Cache Outage: [`INVENTORY_DOCKER_FAULT_CACHE_UNAVAILABLE_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_CACHE_UNAVAILABLE_VALIDATION.md)
  - Bad DB Configuration: [`INVENTORY_DOCKER_FAULT_BAD_DB_CONFIG_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_BAD_DB_CONFIG_VALIDATION.md)
  - Database Upstream Timeout: [`INVENTORY_DOCKER_FAULT_UPSTREAM_TIMEOUT_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_UPSTREAM_TIMEOUT_VALIDATION.md)
  - Multi-Fault DB and Cache: [`INVENTORY_DOCKER_MULTI_FAULT_DB_AND_CACHE_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_MULTI_FAULT_DB_AND_CACHE_VALIDATION.md)
- **Regression Suite:** Full unit test suite passes cleanly (59 passed).
- **Integration Test Execution:** Real local integration tests pass (6 passed); all Docker integration tests cleanly skip (11 skipped) when the Docker daemon is offline, accurately reporting actual test status without false claims.
