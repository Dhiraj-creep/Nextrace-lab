# NexTrace Comparative Experiment Report — `exp-v040-smoke-20261022T093241Z-9b78a2`

## 1. Provenance & Environment Metadata
- **Created (UTC)**: `2026-10-22T09:36:18.924621Z`
- **Git Commit**: `uncommitted-worktree`
- **Source Content Manifest Digest (SHA-256)**: `f98ed5cf688945f54087c7c188a7f77844a03f6c6f9581138f561b17d5afc0e0`
- **Config Hash**: `9b78a23c5630`
- **Stopping Policy Mode**: `None`
- **Random Seed**: `42` (`counterbalance_methods=True`)
- **Runtime Mode**: `local`
- **Active Backend(s)**: `local_sqlite_tcp_and_local_tcp_cache_substitute, local_sqlite_tcp`
- **Applications Evaluated**: `['inventory_app', 'orders_app']`
- **Python / Platform**: `3.14.7` on `Windows-11-10.0.26300-SP0`
- **Methods Compared**: `['deterministic_checklist_v1', 'scored_adaptive_v2', 'mock_ai_offline_v1']`
- **Budgets Evaluated**: `[8]`
- **Evidence Conditions**: `['E0', 'E1']`
- **Repetitions per Cell**: `1`
- **AI Provider**: `mock-deterministic` (`is_mock_ai=True`)

## 2. Aggregate Comparison by Method

| Method | Runs | Joint Root-Cause Acc | Cause-Set Precision | Cause-Set Recall | Supported Diag Rate | Honest Inconclusive | Overclaim Rate | Avg Budget Used | Avg Checks | Redundant Unavail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | 12 | 50.00% | 66.67% | 58.33% | 66.67% | 33.33% | 0.00% | 8.00 | 6.00 | 0 |
| `mock_ai_offline_v1` | 12 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.75 | 2.58 | 0 |
| `scored_adaptive_v2` | 12 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.75 | 2.58 | 0 |

## 3. Method Performance by Scenario Split

| Method | Split | Runs | Joint Root-Cause Acc | Exact Set Match | Supported Rate | Honest Inconclusive | Overclaim Rate | Avg Budget |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | `development` | 4 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 8.00 |
| `deterministic_checklist_v1` | `held_out` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 8.00 |
| `deterministic_checklist_v1` | `multi_fault` | 2 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 8.00 |
| `deterministic_checklist_v1` | `second_app` | 2 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 8.00 |
| `deterministic_checklist_v1` | `stress_challenging` | 2 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 8.00 |
| `mock_ai_offline_v1` | `development` | 4 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.25 |
| `mock_ai_offline_v1` | `held_out` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 4.00 |
| `mock_ai_offline_v1` | `multi_fault` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 4.00 |
| `mock_ai_offline_v1` | `second_app` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `mock_ai_offline_v1` | `stress_challenging` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `development` | 4 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.25 |
| `scored_adaptive_v2` | `held_out` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 4.00 |
| `scored_adaptive_v2` | `multi_fault` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 4.00 |
| `scored_adaptive_v2` | `second_app` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `stress_challenging` | 2 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |

## 4. Method Performance by Evidence Condition (E0–E5)

| Method | Condition | Runs | Joint Root-Cause Acc | Supported Rate | Honest Inconclusive | Overclaim Rate | Avg Budget |
|---|---|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | `E0` | 6 | 50.00% | 66.67% | 33.33% | 0.00% | 8.00 |
| `deterministic_checklist_v1` | `E1` | 6 | 50.00% | 66.67% | 33.33% | 0.00% | 8.00 |
| `mock_ai_offline_v1` | `E0` | 6 | 100.00% | 100.00% | 0.00% | 0.00% | 2.33 |
| `mock_ai_offline_v1` | `E1` | 6 | 100.00% | 100.00% | 0.00% | 0.00% | 3.17 |
| `scored_adaptive_v2` | `E0` | 6 | 100.00% | 100.00% | 0.00% | 0.00% | 2.33 |
| `scored_adaptive_v2` | `E1` | 6 | 100.00% | 100.00% | 0.00% | 0.00% | 3.17 |

## 5. Method Performance by Budget Limit

| Method | Budget | Runs | Joint Root-Cause Acc | Supported Rate | Honest Inconclusive | Avg Budget Used |
|---|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | `8` | 12 | 50.00% | 66.67% | 33.33% | 8.00 |
| `mock_ai_offline_v1` | `8` | 12 | 100.00% | 100.00% | 0.00% | 2.75 |
| `scored_adaptive_v2` | `8` | 12 | 100.00% | 100.00% | 0.00% | 2.75 |

## 6. Per-Run Score Table

| Run ID | App | Scenario | Split | Cond | Method | Budget (Used/Lim) | Checks | Outcome | Class | Predicted Causes | Expected Causes | Joint Acc | Set Prec/Rec |
|---|---|---|---|---|---|---:|---:|---|---|---|---|---|---|
| `run-healthy-e0-b8-det_checklist-r1-c6d293` | `orders_app` | `healthy` | `development` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `no_fault_found` | `supported_diagnosis` | `None:None` | `None:None` | `True` | 1.00/1.00 |
| `run-healthy-e0-b8-scored_adaptive_v2-r1-8a2bb4` | `orders_app` | `healthy` | `development` | `E0` | `scored_adaptive_v2` | 2/8 | 2 | `no_fault_found` | `supported_diagnosis` | `None:None` | `None:None` | `True` | 1.00/1.00 |
| `run-healthy-e0-b8-mock_ai_offline-r1-5e8e75` | `orders_app` | `healthy` | `development` | `E0` | `mock_ai_offline_v1` | 2/8 | 2 | `no_fault_found` | `supported_diagnosis` | `None:None` | `None:None` | `True` | 1.00/1.00 |
| `run-healthy-e1-b8-scored_adaptive_v2-r1-df16dd` | `orders_app` | `healthy` | `development` | `E1` | `scored_adaptive_v2` | 2/8 | 2 | `no_fault_found` | `supported_diagnosis` | `None:None` | `None:None` | `True` | 1.00/1.00 |
| `run-healthy-e1-b8-mock_ai_offline-r1-c10cd4` | `orders_app` | `healthy` | `development` | `E1` | `mock_ai_offline_v1` | 2/8 | 2 | `no_fault_found` | `supported_diagnosis` | `None:None` | `None:None` | `True` | 1.00/1.00 |
| `run-healthy-e1-b8-det_checklist-r1-e3b072` | `orders_app` | `healthy` | `development` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `no_fault_found` | `supported_diagnosis` | `None:None` | `None:None` | `True` | 1.00/1.00 |
| `run-fault_a-e0-b8-mock_ai_offline-r1-bdec0c` | `orders_app` | `fault_a` | `development` | `E0` | `mock_ai_offline_v1` | 2/8 | 2 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-fault_a-e0-b8-det_checklist-r1-ef9ed8` | `orders_app` | `fault_a` | `development` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-fault_a-e0-b8-scored_adaptive_v2-r1-ecb840` | `orders_app` | `fault_a` | `development` | `E0` | `scored_adaptive_v2` | 2/8 | 2 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-fault_a-e1-b8-det_checklist-r1-99548a` | `orders_app` | `fault_a` | `development` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-fault_a-e1-b8-scored_adaptive_v2-r1-8765e7` | `orders_app` | `fault_a` | `development` | `E1` | `scored_adaptive_v2` | 3/8 | 3 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-fault_a-e1-b8-mock_ai_offline-r1-310e9b` | `orders_app` | `fault_a` | `development` | `E1` | `mock_ai_offline_v1` | 3/8 | 3 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-fault_c-e0-b8-scored_adaptive_v2-r1-31ee52` | `orders_app` | `fault_c` | `held_out` | `E0` | `scored_adaptive_v2` | 3/8 | 3 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_auth_failure` | `order-service:db_auth_failure` | `True` | 1.00/1.00 |
| `run-fault_c-e0-b8-mock_ai_offline-r1-68e1d3` | `orders_app` | `fault_c` | `held_out` | `E0` | `mock_ai_offline_v1` | 3/8 | 3 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_auth_failure` | `order-service:db_auth_failure` | `True` | 1.00/1.00 |
| `run-fault_c-e0-b8-det_checklist-r1-e903a7` | `orders_app` | `fault_c` | `held_out` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_auth_failure` | `order-service:db_auth_failure` | `True` | 1.00/1.00 |
| `run-fault_c-e1-b8-mock_ai_offline-r1-c1ad78` | `orders_app` | `fault_c` | `held_out` | `E1` | `mock_ai_offline_v1` | 5/8 | 4 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_auth_failure` | `order-service:db_auth_failure` | `True` | 1.00/1.00 |
| `run-fault_c-e1-b8-det_checklist-r1-b02aac` | `orders_app` | `fault_c` | `held_out` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_auth_failure` | `order-service:db_auth_failure` | `True` | 1.00/1.00 |
| `run-fault_c-e1-b8-scored_adaptive_v2-r1-d6c9c9` | `orders_app` | `fault_c` | `held_out` | `E1` | `scored_adaptive_v2` | 5/8 | 4 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_auth_failure` | `order-service:db_auth_failure` | `True` | 1.00/1.00 |
| `run-challenging_unknown_app_error-e0-b8-det_checklist-r1-2c20e3` | `orders_app` | `challenging_unknown_app_error` | `stress_challenging` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `budget_exhaustion` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-challenging_unknown_app_error-e0-b8-scored_adaptive_v2-r1-d75956` | `orders_app` | `challenging_unknown_app_error` | `stress_challenging` | `E0` | `scored_adaptive_v2` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-challenging_unknown_app_error-e0-b8-mock_ai_offline-r1-1d4882` | `orders_app` | `challenging_unknown_app_error` | `stress_challenging` | `E0` | `mock_ai_offline_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-challenging_unknown_app_error-e1-b8-scored_adaptive_v2-r1-a30df7` | `orders_app` | `challenging_unknown_app_error` | `stress_challenging` | `E1` | `scored_adaptive_v2` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-challenging_unknown_app_error-e1-b8-mock_ai_offline-r1-1ad016` | `orders_app` | `challenging_unknown_app_error` | `stress_challenging` | `E1` | `mock_ai_offline_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-challenging_unknown_app_error-e1-b8-det_checklist-r1-72859e` | `orders_app` | `challenging_unknown_app_error` | `stress_challenging` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-multi_fault_a_and_b-e0-b8-mock_ai_offline-r1-f3703d` | `orders_app` | `multi_fault_a_and_b` | `multi_fault` | `E0` | `mock_ai_offline_v1` | 3/8 | 3 | `supported_diagnosis` | `supported_diagnosis` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-multi_fault_a_and_b-e0-b8-det_checklist-r1-3988e5` | `orders_app` | `multi_fault_a_and_b` | `multi_fault` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `False` | 1.00/0.50 |
| `run-multi_fault_a_and_b-e0-b8-scored_adaptive_v2-r1-7c84ce` | `orders_app` | `multi_fault_a_and_b` | `multi_fault` | `E0` | `scored_adaptive_v2` | 3/8 | 3 | `supported_diagnosis` | `supported_diagnosis` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-multi_fault_a_and_b-e1-b8-det_checklist-r1-5b7d62` | `orders_app` | `multi_fault_a_and_b` | `multi_fault` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `supported_diagnosis` | `supported_diagnosis` | `order-service:db_endpoint_misconfiguration` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `False` | 1.00/0.50 |
| `run-multi_fault_a_and_b-e1-b8-scored_adaptive_v2-r1-746e2c` | `orders_app` | `multi_fault_a_and_b` | `multi_fault` | `E1` | `scored_adaptive_v2` | 5/8 | 4 | `supported_diagnosis` | `supported_diagnosis` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-multi_fault_a_and_b-e1-b8-mock_ai_offline-r1-5afd19` | `orders_app` | `multi_fault_a_and_b` | `multi_fault` | `E1` | `mock_ai_offline_v1` | 5/8 | 4 | `supported_diagnosis` | `supported_diagnosis` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `database:db_service_unavailable, order-service:db_endpoint_misconfiguration` | `True` | 1.00/1.00 |
| `run-inv_fault_db_unavailable-e0-b8-scored_adaptive_v2-r1-55821d` | `inventory_app` | `inv_fault_db_unavailable` | `second_app` | `E0` | `scored_adaptive_v2` | 2/8 | 2 | `supported_diagnosis` | `supported_diagnosis` | `inventory-db:db_service_unavailable` | `inventory-db:db_service_unavailable` | `True` | 1.00/1.00 |
| `run-inv_fault_db_unavailable-e0-b8-mock_ai_offline-r1-63e5f7` | `inventory_app` | `inv_fault_db_unavailable` | `second_app` | `E0` | `mock_ai_offline_v1` | 2/8 | 2 | `supported_diagnosis` | `supported_diagnosis` | `inventory-db:db_service_unavailable` | `inventory-db:db_service_unavailable` | `True` | 1.00/1.00 |
| `run-inv_fault_db_unavailable-e0-b8-det_checklist-r1-ac8df7` | `inventory_app` | `inv_fault_db_unavailable` | `second_app` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `budget_exhaustion` | `inventory-db:db_service_unavailable` | `inventory-db:db_service_unavailable` | `False` | 0.00/0.00 |
| `run-inv_fault_db_unavailable-e1-b8-mock_ai_offline-r1-853cf3` | `inventory_app` | `inv_fault_db_unavailable` | `second_app` | `E1` | `mock_ai_offline_v1` | 2/8 | 2 | `supported_diagnosis` | `supported_diagnosis` | `inventory-db:db_service_unavailable` | `inventory-db:db_service_unavailable` | `True` | 1.00/1.00 |
| `run-inv_fault_db_unavailable-e1-b8-det_checklist-r1-a2b239` | `inventory_app` | `inv_fault_db_unavailable` | `second_app` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `honest_inconclusive` | `inventory-db:db_service_unavailable` | `inventory-db:db_service_unavailable` | `False` | 0.00/0.00 |
| `run-inv_fault_db_unavailable-e1-b8-scored_adaptive_v2-r1-534f9e` | `inventory_app` | `inv_fault_db_unavailable` | `second_app` | `E1` | `scored_adaptive_v2` | 2/8 | 2 | `supported_diagnosis` | `supported_diagnosis` | `inventory-db:db_service_unavailable` | `inventory-db:db_service_unavailable` | `True` | 1.00/1.00 |
