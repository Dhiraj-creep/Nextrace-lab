# NexTrace Evaluation Protocol (`v0.4.0`)

**Project**: NexTrace — AI-Guided Root Cause Diagnosis for Cloud Applications  
**Competition**: Aavishkar Engineering & Technology Competition  
**Milestone**: Correctness, Reproducibility & Validation Milestone (`v0.4.0`)  
**Frozen Protocol Artifact**: [`artifacts/protocols/v0.4.0_frozen_protocol.json`](file:///D:/Avishkar%20Nextrace/nextrace/artifacts/protocols/v0.4.0_frozen_protocol.json)  
**Source Content Manifest Digest (SHA-256)**: `857542095a090c6fb040654dd4fbe8f0f5e345131d367f62b931c1817fe493de`  
**Repository**: `D:\Avishkar Nextrace\nextrace`  

---

## 1. Experimental Research Question

> **Research Question**: Does scored adaptive diagnostic-check selection (`scored_adaptive_v2`) improve supported root-cause diagnosis accuracy, diagnostic coverage, or budget efficiency compared with reasonable fixed checklists (with and without fair early stopping) and rule-based policies when tools, evidence access, budgets, and stopping rules are equal?

This question is treated strictly as an empirical investigation. Neither the scored method nor AI policies are assumed to outperform simpler baselines.

---

## 2. Multi-Application Scenario Splits & Partitioning

Scenarios are partitioned into five evaluation splits and one reserved evaluation fixture across two distributed applications:

| Split Name | Application (`app_id`) | Scenarios Included | Evaluation Purpose |
|---|---|---|---|
| `development` | `orders_app` | `healthy`, `fault_a`, `fault_b` | Calibration of basic health, log, configuration, and database probes |
| `held_out` | `orders_app` | `fault_c`, `fault_d`, `fault_e`, `fault_f` | Evaluation on unseen fault types (DB auth failure, missing table schema, DB operation delay, upstream service stop) |
| `stress_challenging` | `orders_app` | `challenging_recovery_mid_run`, `challenging_diag_endpoint_failure`, `challenging_historical_logs_healthy_now`, `challenging_unknown_app_error`, `unknown_order_validation_contract_error` | Changing evidence (mid-run recovery), diagnostic endpoint failure during healthy traffic, historical log contamination, and unmodeled application errors |
| `multi_fault` | `orders_app` | `multi_fault_a_and_b`, `multi_fault_c_and_d`, `multi_fault_f_masks_b` | Concurrent multi-faults and masking faults evaluated using cause-set precision, recall, and exact-set match |
| `second_app` | `inventory_app` | `inv_healthy`, `inv_fault_db_unavailable`, `inv_fault_cache_unavailable`, `inv_fault_bad_db_config`, `inv_fault_upstream_timeout`, `inv_unknown_sku_parser_exception`, `inv_multi_fault_db_and_cache` | Cross-architecture generalization on a 4-component service topology (`inventory-api` -> `inventory-service` -> `inventory-db` + `inventory-cache`) |
| `reserved_eval` | `orders_app` | `unknown_order_currency_rounding_crash` | Reserved unmodeled failure fixture never exposed during heuristic design |

---

## 3. Versioned Evidence Availability Policies (`E0_v2`–`E5_v2`)

Under `cost_model_version="attempt_charged_v2"`, each admitted check attempt consumes its declared catalog cost units regardless of whether the check returns `AVAILABLE`, `UNAVAILABLE_BY_POLICY`, or `COLLECTION_FAILED`:

| Condition | Policy Label | Blocked or Degraded Evidence |
|---|---|---|
| `E0` | `E0_FULL_OBSERVABILITY` | Full allowlisted diagnostic observability |
| `E1` | `E1_ORDER_LOGS_UNAVAILABLE` | Primary service logs (`get_recent_logs`) blocked by policy |
| `E2` | `E2_DB_PROBE_UNAVAILABLE` | Database direct connectivity probe (`check_database_connectivity_from_order_service`, `check_inventory_db_connectivity`) blocked by policy |
| `E3` | `E3_ORDER_LOGS_AND_CONFIG_UNAVAILABLE` | Both service logs AND database configuration inspection blocked by policy |
| `E4` | `E4_METRICS_UNAVAILABLE` | Service metrics collection endpoint blocked by policy across all services |
| `E5` | `E5_METRICS_STALE` | Service metrics return stale snapshot (600s old) below minimum sample threshold (`sample_sufficient=False`) |

---

## 4. Diagnostic Methods Evaluated

1. **`deterministic_checklist_v1`**: Historical fixed checklist executed to sequence completion or budget exhaustion.
2. **`deterministic_checklist_early_stop_v1`**: Fair early-stopping baseline following the identical check sequence but stopping immediately upon evidence gate satisfaction.
3. **`improved_checklist_v1`**: Domain-ordered fixed checklist prioritizing 1-cost component health checks first.
4. **`improved_checklist_early_stop_v1`**: Fair early-stopping domain checklist.
5. **`rule_adaptive_v1`**: Rule-based selector with branching logic conditioned on hypothesis stances and unavailable responses.
6. **`scored_adaptive_v1`**: Preserved Phase 3 utility-scored selector.
7. **`scored_adaptive_v2`**: Standard Phase 4 utility-scored selector with distinguishing-value, availability, reliability, and cost balancing.
8. **`scored_no_cost_v2`**: Strictly isolated ablation setting `normalized_cost = 1.0` (ignoring check cost differences).
9. **`scored_no_avail_v2`**: Strictly isolated ablation setting `availability_factor = 1.0` (ignoring known availability constraints).
10. **`scored_no_reliability_v2`**: Strictly isolated ablation setting `reliability_factor = 1.0` (ignoring check reliability differences).
11. **`mock_ai_offline_v1`**: Deterministic offline mock AI adapter for automated prompt and JSON schema regression testing.
12. **`ai_live_v1`**: Pure live LLM selector (`allow_fallback=False`) with verified pricing and zero SDK retries.
13. **`ai_hybrid_fallback_v1`**: Explicitly labeled hybrid selector with fallback to `scored_adaptive_v2`.

---

## 5. Centralized Stopping Policy Modes

All selectors operate under identical stopping policies in `nextrace_lab/stopping_policy.py`:
- `first_supported_cause`: Stops immediately when the first root cause is confirmed by the evidence gate.
- `investigate_additional_causes`: Continues investigation after confirming a fault to discover concurrent or masked faults across unprobed components.
- `fixed_no_early_stop`: Continues along a static checklist until budget exhaustion.

---

## 6. Execution Controls & Statistical Integrity

1. **Cross-Process Protection**: All suites acquire `LabExecutionLock` (`var/runtime/lab_execution.lock`).
2. **Counterbalancing**: Method execution orders within each `(scenario, condition, budget)` cell are cyclically counterbalanced and shuffled with recorded random seeds.
3. **Environment Resets**: Service logs are truncated and metrics cleared between runs to prevent cross-run evidence leakage.
4. **Monotonic Deadlines**: Each run enforces a monotonic deadline (`DeadlineTracker`).
5. **Cryptographic Manifest**: Source content digest is computed across all 36 source files before execution and recorded in each `manifest.json`.
