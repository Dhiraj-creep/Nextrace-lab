# NexTrace Experiment Suite Summary (`exp-phase2-smoke-20261020T214408Z-68fe4a`)

## 1. Execution & Reproducibility Metadata
- **NexTrace Version**: `0.2.0` (Git: `untracked_workspace`)
- **Methods Evaluated**: `deterministic_checklist_v1, improved_checklist_v1, rule_adaptive_v1`
- **Runtime / Backend**: `local` (`local_sqlite_tcp`)
- **Started (UTC)**: `2026-10-20T21:44:08.074302Z`
- **Completed (UTC)**: `2026-10-20T21:48:41.618720Z`
- **Total Suite Elapsed Time**: `273544.39 ms`
- **Check Budgets**: `[4, 6]`
- **Repetitions**: `1` (Base seed: `42`)
- **Development Scenarios**: `['healthy', 'fault_a']`
- **Held-Out Scenarios**: `['fault_f']`
- **Public Results Directory**: `D:\Avishkar Nextrace\nextrace\artifacts\experiments\exp-phase2-smoke-20261020T214408Z-68fe4a`
- **Private Ground-Truth Directory**: `D:\Avishkar Nextrace\nextrace\var\ground_truth\exp-phase2-smoke-20261020T214408Z-68fe4a`

## 2. Run Lifecycle Accounting & Aggregate Metrics
| Metric | Value |
| :--- | :--- |
| Attempted / Completed / Failed / Evaluated Runs | `36 / 36 / 0 / 36` |
| Answered Runs (Non-Inconclusive) | `32` |
| Inconclusive Runs (Abstentions) | `4` |
| Diagnosis Coverage Rate | `88.89%` |
| Accuracy Among Answered Cases | `100.00%` |
| **Overall Exact-Match Rate (All Evaluated Runs)** | **`88.89%`** (std: `0.3187`) |
| Fault Scenarios Coverage Rate | `91.67%` |
| Fault Service Accuracy (Overall) | `91.67%` |
| Fault Type Accuracy (Overall) | `91.67%` |
| Fault Exact-Match Rate (Overall) | `91.67%` |
| False Fault Diagnoses on Healthy Cases | `0 / 12` |
| Wrong Confident Diagnoses on Ambiguous Cases | `0` |
| Mean Checks Used (Std) | `4.22` (`1.42`) |
| Mean Wall-Clock / Summed Tool Duration (ms) | `1221.75` / `1220.68` |
| Cited Evidence-ID Referential Integrity | `100.00%` |
| Verified Evidential Support Rate | `100.00%` |
| Budget Violations | `0` (Compliance: `100.00%`) |
| Setup / Execution / Recovery Failures | `0 / 0 / 0` |

## 3. Comparison by Method
| Method | Evaluated | Coverage | Inconclusive | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks | Mean Wall (ms) | Evidential Support |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deterministic_checklist_v1` | 12 | 66.67% | 33.33% | 100.00% | **66.67%** | **75.00%** | 5.00 | 1137.9 | 100.00% |
| `improved_checklist_v1` | 12 | 100.00% | 0.00% | 100.00% | **100.00%** | **100.00%** | 5.00 | 1742.8 | 100.00% |
| `rule_adaptive_v1` | 12 | 100.00% | 0.00% | 100.00% | **100.00%** | **100.00%** | 2.67 | 784.5 | 100.00% |

## 4. Comparison by Method and Check Budget
| Method @ Budget | Evaluated | Coverage | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `deterministic_checklist_v1@budget=4` | 6 | 33.33% | 100.00% | **33.33%** | **50.00%** | 4.00 |
| `deterministic_checklist_v1@budget=6` | 6 | 100.00% | 100.00% | **100.00%** | **100.00%** | 6.00 |
| `improved_checklist_v1@budget=4` | 6 | 100.00% | 100.00% | **100.00%** | **100.00%** | 4.00 |
| `improved_checklist_v1@budget=6` | 6 | 100.00% | 100.00% | **100.00%** | **100.00%** | 6.00 |
| `rule_adaptive_v1@budget=4` | 6 | 100.00% | 100.00% | **100.00%** | **100.00%** | 2.67 |
| `rule_adaptive_v1@budget=6` | 6 | 100.00% | 100.00% | **100.00%** | **100.00%** | 2.67 |

## 5. Breakdown by Split (Development vs. Held-Out)
| Split | Evaluated | Coverage | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `development` | 24 | 83.33% | 100.00% | 83.33% | 83.33% | 4.33 |
| `held_out` | 12 | 100.00% | 100.00% | 100.00% | 100.00% | 4.00 |

## 6. Breakdown by Evidence Condition
| Evidence Condition | Evaluated | Coverage | Inconclusive | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `E0` | 18 | 88.89% | 11.11% | 100.00% | 88.89% | 91.67% | 4.22 |
| `E1` | 18 | 88.89% | 11.11% | 100.00% | 88.89% | 91.67% | 4.22 |

## 7. Per-Run Results
| Run ID | Method | Split | Scenario | Condition | Budget | Checks | Outcome | Predicted | Exact Match | Support Verified | Stop Reason | Wall (ms) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :---: | :---: | :--- | :---: |
| `run-0001-b68f6305` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 181.837 |
| `run-0002-07aa558a` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 151.757 |
| `run-0003-1f81f7ef` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 168.986 |
| `run-0004-fcbb7438` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 152.957 |
| `run-0005-1ca7145e` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 209.131 |
| `run-0006-bc3eaef3` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 210.612 |
| `run-0007-4003d015` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 145.499 |
| `run-0008-de9b8790` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 192.75 |
| `run-0009-388b0bb3` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 219.748 |
| `run-0010-2c94fa9f` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 173.786 |
| `run-0011-f3ec505f` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 214.563 |
| `run-0012-54f03c35` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 170.207 |
| `run-0013-016070d4` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 122.542 |
| `run-0014-725c9067` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 159.307 |
| `run-0015-070f591f` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 72.377 |
| `run-0016-cf2aaf55` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 189.503 |
| `run-0017-955fde5c` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 192.711 |
| `run-0018-8a96d89e` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 92.399 |
| `run-0019-9bebade8` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 125.261 |
| `run-0020-087daaf2` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 113.513 |
| `run-0021-75cd2b31` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 84.128 |
| `run-0022-41e0d6c0` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 152.777 |
| `run-0023-37ba005a` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 198.501 |
| `run-0024-6eae4ae2` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 61.653 |
| `run-0025-a013c78b` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2088.767 |
| `run-0026-ec6b0521` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4108.736 |
| `run-0027-07942ff4` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2091.136 |
| `run-0028-533408c9` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4108.668 |
| `run-0029-f5c7e005` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5624.043 |
| `run-0030-d89c3bc9` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2109.423 |
| `run-0031-075c17d3` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2101.757 |
| `run-0032-1dfe0575` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4107.627 |
| `run-0033-4c8dd6f4` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2069.709 |
| `run-0034-050a1a9d` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4111.881 |
| `run-0035-a88b481d` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5641.431 |
| `run-0036-42e405c7` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2063.315 |

## 8. Methodological Caveats & Interpretation Notes
1. **Evidential Support vs. Evidence-ID Validity**: `all_evidence_ids_valid` checks only that cited `evidence_id`s exist in the run's audit log, whereas `evidential_support_verified` independently runs the `EvidenceGate` on collected observations to ensure the cited evidence actually establishes the diagnosed fault.
2. **Ambiguous Evidence Conditions (`E2`)**: Under `E2`, `fault_a` through `fault_e` cannot be distinguished by permitted observations. Any method returning a confident diagnosis on those cases is penalized via `wrong_confident_diagnosis_on_ambiguous` rather than rewarded for a lucky guess.
3. **Generalization Limits**: Results are measured on a controlled 3-component microservice testbed (`gateway -> order-service -> database`) with 6 reproducible single-fault scenarios and 4 evidence policies (`E0, E1, E2, E3`); they do not claim production generalization across arbitrary distributed systems.
