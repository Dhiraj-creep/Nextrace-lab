# NexTrace Experiment Suite Summary (`exp-phase2-comparative-20261020T215409Z-e1764e`)

## 1. Execution & Reproducibility Metadata
- **NexTrace Version**: `0.2.0` (Git: `untracked_workspace`)
- **Methods Evaluated**: `deterministic_checklist_v1, improved_checklist_v1, rule_adaptive_v1`
- **Runtime / Backend**: `local` (`local_sqlite_tcp`)
- **Started (UTC)**: `2026-10-20T21:54:09.190734Z`
- **Completed (UTC)**: `2026-10-20T22:11:15.229367Z`
- **Total Suite Elapsed Time**: `1026038.59 ms`
- **Check Budgets**: `[4, 6, 8]`
- **Repetitions**: `2` (Base seed: `42`)
- **Development Scenarios**: `['healthy', 'fault_a', 'fault_b']`
- **Held-Out Scenarios**: `['fault_c', 'fault_d', 'fault_e', 'fault_f']`
- **Public Results Directory**: `D:\Avishkar Nextrace\nextrace\artifacts\experiments\exp-phase2-comparative-20261020T215409Z-e1764e`
- **Private Ground-Truth Directory**: `D:\Avishkar Nextrace\nextrace\var\ground_truth\exp-phase2-comparative-20261020T215409Z-e1764e`

## 2. Run Lifecycle Accounting & Aggregate Metrics
| Metric | Value |
| :--- | :--- |
| Attempted / Completed / Failed / Evaluated Runs | `504 / 504 / 0 / 504` |
| Answered Runs (Non-Inconclusive) | `330` |
| Inconclusive Runs (Abstentions) | `174` |
| Diagnosis Coverage Rate | `65.48%` |
| Accuracy Among Answered Cases | `100.00%` |
| **Overall Exact-Match Rate (All Evaluated Runs)** | **`65.48%`** (std: `0.4759`) |
| Fault Scenarios Coverage Rate | `61.57%` |
| Fault Service Accuracy (Overall) | `61.57%` |
| Fault Type Accuracy (Overall) | `61.57%` |
| Fault Exact-Match Rate (Overall) | `61.57%` |
| False Fault Diagnoses on Healthy Cases | `0 / 72` |
| Wrong Confident Diagnoses on Ambiguous Cases | `0` |
| Mean Checks Used (Std) | `5.18` (`1.90`) |
| Mean Wall-Clock / Summed Tool Duration (ms) | `1279.13` / `1277.93` |
| Cited Evidence-ID Referential Integrity | `100.00%` |
| Verified Evidential Support Rate | `100.00%` |
| Budget Violations | `0` (Compliance: `100.00%`) |
| Setup / Execution / Recovery Failures | `0 / 0 / 0` |

## 3. Comparison by Method
| Method | Evaluated | Coverage | Inconclusive | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks | Mean Wall (ms) | Evidential Support |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deterministic_checklist_v1` | 168 | 52.38% | 47.62% | 100.00% | **52.38%** | **50.00%** | 6.00 | 1205.3 | 100.00% |
| `improved_checklist_v1` | 168 | 63.10% | 36.90% | 100.00% | **63.10%** | **56.94%** | 6.00 | 1503.6 | 100.00% |
| `rule_adaptive_v1` | 168 | 80.95% | 19.05% | 100.00% | **80.95%** | **77.78%** | 3.54 | 1128.5 | 100.00% |

## 4. Comparison by Method and Check Budget
| Method @ Budget | Evaluated | Coverage | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `deterministic_checklist_v1@budget=4` | 56 | 14.29% | 100.00% | **14.29%** | **16.67%** | 4.00 |
| `deterministic_checklist_v1@budget=6` | 56 | 60.71% | 100.00% | **60.71%** | **54.17%** | 6.00 |
| `deterministic_checklist_v1@budget=8` | 56 | 82.14% | 100.00% | **82.14%** | **79.17%** | 8.00 |
| `improved_checklist_v1@budget=4` | 56 | 39.29% | 100.00% | **39.29%** | **29.17%** | 4.00 |
| `improved_checklist_v1@budget=6` | 56 | 67.86% | 100.00% | **67.86%** | **62.50%** | 6.00 |
| `improved_checklist_v1@budget=8` | 56 | 82.14% | 100.00% | **82.14%** | **79.17%** | 8.00 |
| `rule_adaptive_v1@budget=4` | 56 | 78.57% | 100.00% | **78.57%** | **75.00%** | 3.25 |
| `rule_adaptive_v1@budget=6` | 56 | 82.14% | 100.00% | **82.14%** | **79.17%** | 3.68 |
| `rule_adaptive_v1@budget=8` | 56 | 82.14% | 100.00% | **82.14%** | **79.17%** | 3.68 |

## 5. Breakdown by Split (Development vs. Held-Out)
| Split | Evaluated | Coverage | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `development` | 216 | 66.67% | 100.00% | 66.67% | 55.56% | 5.25 |
| `held_out` | 288 | 64.58% | 100.00% | 64.58% | 64.58% | 5.12 |

## 6. Breakdown by Evidence Condition
| Evidence Condition | Evaluated | Coverage | Inconclusive | Accuracy (Answered) | Overall Exact-Match | Fault Exact-Match | Mean Checks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `E0` | 126 | 82.54% | 17.46% | 100.00% | 82.54% | 81.48% | 5.00 |
| `E1` | 126 | 77.78% | 22.22% | 100.00% | 77.78% | 75.93% | 5.00 |
| `E2` | 126 | 26.98% | 73.02% | 100.00% | 26.98% | 16.67% | 5.51 |
| `E3` | 126 | 74.60% | 25.40% | 100.00% | 74.60% | 72.22% | 5.21 |

## 7. Per-Run Results
| Run ID | Method | Split | Scenario | Condition | Budget | Checks | Outcome | Predicted | Exact Match | Support Verified | Stop Reason | Wall (ms) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :---: | :---: | :--- | :---: |
| `run-0001-c7e57fc8` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 153.946 |
| `run-0002-6b84d150` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 171.091 |
| `run-0003-84b22b5b` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 172.494 |
| `run-0004-cbcaeea0` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 223.516 |
| `run-0005-f3fbe75c` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 216.176 |
| `run-0006-f8534941` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 175.516 |
| `run-0007-7f7cde39` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 268.236 |
| `run-0008-a34d35b0` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 241.111 |
| `run-0009-94c96cf2` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 183.292 |
| `run-0010-d6db273b` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 134.981 |
| `run-0011-f1ba51f7` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 163.252 |
| `run-0012-2b271555` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 190.821 |
| `run-0013-339a4ac1` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 178.426 |
| `run-0014-80590b21` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 239.771 |
| `run-0015-4b4edd2b` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 209.629 |
| `run-0016-bd6c52ed` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 223.937 |
| `run-0017-4ec18fc9` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 237.602 |
| `run-0018-677ddc03` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 150.68 |
| `run-0019-2d3163f3` | `deterministic_checklist_v1` | `development` | `healthy` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 120.375 |
| `run-0020-2a74575a` | `improved_checklist_v1` | `development` | `healthy` | `E2` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 175.935 |
| `run-0021-992c594c` | `rule_adaptive_v1` | `development` | `healthy` | `E2` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 190.161 |
| `run-0022-e7515ca4` | `deterministic_checklist_v1` | `development` | `healthy` | `E2` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 163.601 |
| `run-0023-c94153a0` | `improved_checklist_v1` | `development` | `healthy` | `E2` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 216.616 |
| `run-0024-59cf8b35` | `rule_adaptive_v1` | `development` | `healthy` | `E2` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 241.954 |
| `run-0025-f777e0a7` | `deterministic_checklist_v1` | `development` | `healthy` | `E2` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 178.546 |
| `run-0026-ac734726` | `improved_checklist_v1` | `development` | `healthy` | `E2` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 133.36 |
| `run-0027-38b93949` | `rule_adaptive_v1` | `development` | `healthy` | `E2` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 175.518 |
| `run-0028-bd426d56` | `deterministic_checklist_v1` | `development` | `healthy` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 158.679 |
| `run-0029-7722ddb9` | `improved_checklist_v1` | `development` | `healthy` | `E3` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 216.99 |
| `run-0030-fc705e34` | `rule_adaptive_v1` | `development` | `healthy` | `E3` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 177.885 |
| `run-0031-08ecb1f0` | `deterministic_checklist_v1` | `development` | `healthy` | `E3` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 238.322 |
| `run-0032-6a056217` | `improved_checklist_v1` | `development` | `healthy` | `E3` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 217.024 |
| `run-0033-ce7d1a50` | `rule_adaptive_v1` | `development` | `healthy` | `E3` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 171.665 |
| `run-0034-ef3e1592` | `deterministic_checklist_v1` | `development` | `healthy` | `E3` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 193.181 |
| `run-0035-e23e866e` | `improved_checklist_v1` | `development` | `healthy` | `E3` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 210.214 |
| `run-0036-966ae233` | `rule_adaptive_v1` | `development` | `healthy` | `E3` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 188.943 |
| `run-0037-78f821fd` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 84.363 |
| `run-0038-18cba2a4` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 197.594 |
| `run-0039-de9820ef` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 94.123 |
| `run-0040-c7e4fe06` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 114.944 |
| `run-0041-bc6ba139` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 186.725 |
| `run-0042-2cbae37d` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 94.303 |
| `run-0043-37e9e1c1` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 194.98 |
| `run-0044-0aab7afe` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 224.747 |
| `run-0045-0bdd5f85` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 8 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 98.188 |
| `run-0046-a4bbb16c` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 150.959 |
| `run-0047-44c79803` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 93.802 |
| `run-0048-2692b2ac` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 50.455 |
| `run-0049-bc8303a0` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 151.114 |
| `run-0050-cae70c64` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 194.12 |
| `run-0051-afddf8a5` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 65.111 |
| `run-0052-4d22ce24` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 214.302 |
| `run-0053-37b8a669` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 206.553 |
| `run-0054-40a7dc73` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 8 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 90.046 |
| `run-0055-b0d9e234` | `deterministic_checklist_v1` | `development` | `fault_a` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 101.535 |
| `run-0056-db87263f` | `improved_checklist_v1` | `development` | `fault_a` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 195.586 |
| `run-0057-68657cf6` | `rule_adaptive_v1` | `development` | `fault_a` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 76.334 |
| `run-0058-56ddc54b` | `deterministic_checklist_v1` | `development` | `fault_a` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 179.036 |
| `run-0059-102eee2b` | `improved_checklist_v1` | `development` | `fault_a` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 172.939 |
| `run-0060-f5da6c36` | `rule_adaptive_v1` | `development` | `fault_a` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 98.655 |
| `run-0061-b3c934f0` | `deterministic_checklist_v1` | `development` | `fault_a` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 137.379 |
| `run-0062-3c6986af` | `improved_checklist_v1` | `development` | `fault_a` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 151.17 |
| `run-0063-7edb69ac` | `rule_adaptive_v1` | `development` | `fault_a` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 94.906 |
| `run-0064-9394cbf1` | `deterministic_checklist_v1` | `development` | `fault_a` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 103.01 |
| `run-0065-56c3be0d` | `improved_checklist_v1` | `development` | `fault_a` | `E3` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 154.248 |
| `run-0066-07bbd20d` | `rule_adaptive_v1` | `development` | `fault_a` | `E3` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 68.068 |
| `run-0067-115df11a` | `deterministic_checklist_v1` | `development` | `fault_a` | `E3` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 174.483 |
| `run-0068-d3032f93` | `improved_checklist_v1` | `development` | `fault_a` | `E3` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 133.013 |
| `run-0069-4fbf4001` | `rule_adaptive_v1` | `development` | `fault_a` | `E3` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 77.57 |
| `run-0070-279333c8` | `deterministic_checklist_v1` | `development` | `fault_a` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 163.123 |
| `run-0071-b5b678ca` | `improved_checklist_v1` | `development` | `fault_a` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 176.165 |
| `run-0072-f7101e29` | `rule_adaptive_v1` | `development` | `fault_a` | `E3` | 8 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 75.528 |
| `run-0073-3b91d8fe` | `deterministic_checklist_v1` | `development` | `fault_b` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1143.484 |
| `run-0074-aa91a038` | `improved_checklist_v1` | `development` | `fault_b` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2183.717 |
| `run-0075-958124e7` | `rule_adaptive_v1` | `development` | `fault_b` | `E0` | 4 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3121.345 |
| `run-0076-50fa278e` | `deterministic_checklist_v1` | `development` | `fault_b` | `E0` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2156.35 |
| `run-0077-4c88d8c7` | `improved_checklist_v1` | `development` | `fault_b` | `E0` | 6 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3231.201 |
| `run-0078-a1986655` | `rule_adaptive_v1` | `development` | `fault_b` | `E0` | 6 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3052.484 |
| `run-0079-2a339af9` | `deterministic_checklist_v1` | `development` | `fault_b` | `E0` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3183.483 |
| `run-0080-fb1f04f2` | `improved_checklist_v1` | `development` | `fault_b` | `E0` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3230.392 |
| `run-0081-02c795db` | `rule_adaptive_v1` | `development` | `fault_b` | `E0` | 8 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3113.868 |
| `run-0082-8e24dff0` | `deterministic_checklist_v1` | `development` | `fault_b` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1135.956 |
| `run-0083-008707a3` | `improved_checklist_v1` | `development` | `fault_b` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2212.274 |
| `run-0084-be1a363b` | `rule_adaptive_v1` | `development` | `fault_b` | `E1` | 4 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3101.318 |
| `run-0085-7ed330c2` | `deterministic_checklist_v1` | `development` | `fault_b` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2148.38 |
| `run-0086-0d08b1f1` | `improved_checklist_v1` | `development` | `fault_b` | `E1` | 6 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3223.463 |
| `run-0087-2398c637` | `rule_adaptive_v1` | `development` | `fault_b` | `E1` | 6 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3127.802 |
| `run-0088-f3295057` | `deterministic_checklist_v1` | `development` | `fault_b` | `E1` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3193.969 |
| `run-0089-56be9b01` | `improved_checklist_v1` | `development` | `fault_b` | `E1` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3205.24 |
| `run-0090-b59ac19d` | `rule_adaptive_v1` | `development` | `fault_b` | `E1` | 8 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3109.199 |
| `run-0091-59b536ac` | `deterministic_checklist_v1` | `development` | `fault_b` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1170.489 |
| `run-0092-4ae06244` | `improved_checklist_v1` | `development` | `fault_b` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2207.589 |
| `run-0093-20cf7e63` | `rule_adaptive_v1` | `development` | `fault_b` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2090.811 |
| `run-0094-e5d738f3` | `deterministic_checklist_v1` | `development` | `fault_b` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2199.89 |
| `run-0095-201e3cab` | `improved_checklist_v1` | `development` | `fault_b` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2222.12 |
| `run-0096-42103b56` | `rule_adaptive_v1` | `development` | `fault_b` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2119.932 |
| `run-0097-071e00d1` | `deterministic_checklist_v1` | `development` | `fault_b` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2208.591 |
| `run-0098-d254ed43` | `improved_checklist_v1` | `development` | `fault_b` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2206.981 |
| `run-0099-3226a0eb` | `rule_adaptive_v1` | `development` | `fault_b` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2109.573 |
| `run-0100-11dc75c2` | `deterministic_checklist_v1` | `development` | `fault_b` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1147.33 |
| `run-0101-bbcb5f5c` | `improved_checklist_v1` | `development` | `fault_b` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2164.155 |
| `run-0102-780fbfcc` | `rule_adaptive_v1` | `development` | `fault_b` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2114.846 |
| `run-0103-e563bd3b` | `deterministic_checklist_v1` | `development` | `fault_b` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2196.958 |
| `run-0104-aac137a3` | `improved_checklist_v1` | `development` | `fault_b` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2167.852 |
| `run-0105-8e88848d` | `rule_adaptive_v1` | `development` | `fault_b` | `E3` | 6 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2129.522 |
| `run-0106-f31b9f1c` | `deterministic_checklist_v1` | `development` | `fault_b` | `E3` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2140.064 |
| `run-0107-f04ca130` | `improved_checklist_v1` | `development` | `fault_b` | `E3` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2112.52 |
| `run-0108-c6f43d02` | `rule_adaptive_v1` | `development` | `fault_b` | `E3` | 8 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2086.134 |
| `run-0109-d01744d7` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 104.335 |
| `run-0110-fd0bd00a` | `improved_checklist_v1` | `held_out` | `fault_c` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 265.752 |
| `run-0111-4764868e` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E0` | 4 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 149.161 |
| `run-0112-5e8bb06b` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 202.957 |
| `run-0113-c42c5717` | `improved_checklist_v1` | `held_out` | `fault_c` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 227.071 |
| `run-0114-c7191ad3` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E0` | 6 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 124.796 |
| `run-0115-9c99cdf7` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 211.326 |
| `run-0116-3b1fbe4f` | `improved_checklist_v1` | `held_out` | `fault_c` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 305.428 |
| `run-0117-ee9b55ee` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E0` | 8 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 159.299 |
| `run-0118-e4d76bf6` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 185.067 |
| `run-0119-040ac443` | `improved_checklist_v1` | `held_out` | `fault_c` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 234.623 |
| `run-0120-5ba8e574` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E1` | 4 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 146.718 |
| `run-0121-c54e441f` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 218.312 |
| `run-0122-eecd0033` | `improved_checklist_v1` | `held_out` | `fault_c` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 231.394 |
| `run-0123-bc0a7041` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E1` | 6 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 138.145 |
| `run-0124-932a7119` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 290.245 |
| `run-0125-09185f88` | `improved_checklist_v1` | `held_out` | `fault_c` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 283.351 |
| `run-0126-20ca0d63` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E1` | 8 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 145.144 |
| `run-0127-c6b36ec9` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 181.12 |
| `run-0128-6ae8a5fb` | `improved_checklist_v1` | `held_out` | `fault_c` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 192.8 |
| `run-0129-e2d60c34` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 130.438 |
| `run-0130-7aa6cf81` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 174.669 |
| `run-0131-55b518ef` | `improved_checklist_v1` | `held_out` | `fault_c` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 206.117 |
| `run-0132-06811508` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 148.224 |
| `run-0133-3cb87c30` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 204.885 |
| `run-0134-c20c524b` | `improved_checklist_v1` | `held_out` | `fault_c` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 186.717 |
| `run-0135-4e6fdbfe` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 143.659 |
| `run-0136-a1564e96` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 120.883 |
| `run-0137-ff4aaff9` | `improved_checklist_v1` | `held_out` | `fault_c` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 199.726 |
| `run-0138-6cc8edba` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E3` | 4 | 4 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 103.924 |
| `run-0139-c5ad4089` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E3` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 212.958 |
| `run-0140-1e3205d8` | `improved_checklist_v1` | `held_out` | `fault_c` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 250.019 |
| `run-0141-59c6b02d` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E3` | 6 | 4 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 160.326 |
| `run-0142-9113b5f8` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 228.046 |
| `run-0143-a70c41a0` | `improved_checklist_v1` | `held_out` | `fault_c` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 178.743 |
| `run-0144-065bff16` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E3` | 8 | 4 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 153.624 |
| `run-0145-c6fc2325` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 196.281 |
| `run-0146-8eb3470f` | `improved_checklist_v1` | `held_out` | `fault_d` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 217.624 |
| `run-0147-64f9fdb7` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E0` | 4 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 126.706 |
| `run-0148-8ac724f4` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E0` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 208.569 |
| `run-0149-dbe22bc1` | `improved_checklist_v1` | `held_out` | `fault_d` | `E0` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 229.864 |
| `run-0150-694fc40a` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E0` | 6 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 179.925 |
| `run-0151-7d5fea31` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E0` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 317.517 |
| `run-0152-f04b41e9` | `improved_checklist_v1` | `held_out` | `fault_d` | `E0` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 302.055 |
| `run-0153-966c7e97` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E0` | 8 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 158.435 |
| `run-0154-51e568c7` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 175.457 |
| `run-0155-fa27bd49` | `improved_checklist_v1` | `held_out` | `fault_d` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 203.588 |
| `run-0156-0c65d72c` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E1` | 4 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 140.184 |
| `run-0157-596e68cf` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 210.908 |
| `run-0158-1313a0d6` | `improved_checklist_v1` | `held_out` | `fault_d` | `E1` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 249.659 |
| `run-0159-413a62dc` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E1` | 6 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 190.305 |
| `run-0160-24913e7e` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E1` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 301.401 |
| `run-0161-63e034b5` | `improved_checklist_v1` | `held_out` | `fault_d` | `E1` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 250.635 |
| `run-0162-4aec634f` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E1` | 8 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 189.294 |
| `run-0163-a3c4a3c9` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 137.317 |
| `run-0164-b5bf416c` | `improved_checklist_v1` | `held_out` | `fault_d` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 205.368 |
| `run-0165-6c43c1ac` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 146.391 |
| `run-0166-ffbf6635` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 251.177 |
| `run-0167-b5679a15` | `improved_checklist_v1` | `held_out` | `fault_d` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 217.21 |
| `run-0168-82680359` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 156.018 |
| `run-0169-c8316cd6` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 239.678 |
| `run-0170-789e5803` | `improved_checklist_v1` | `held_out` | `fault_d` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 219.062 |
| `run-0171-25d09e37` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 158.127 |
| `run-0172-2fdd00a2` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 126.069 |
| `run-0173-968b9e43` | `improved_checklist_v1` | `held_out` | `fault_d` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 158.991 |
| `run-0174-484c0dd6` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E3` | 4 | 4 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 134.245 |
| `run-0175-6495b7d9` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E3` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 214.344 |
| `run-0176-5f9ed349` | `improved_checklist_v1` | `held_out` | `fault_d` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 189.747 |
| `run-0177-c67d7eda` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E3` | 6 | 4 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 192.34 |
| `run-0178-67f24a52` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E3` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 219.816 |
| `run-0179-e2931ede` | `improved_checklist_v1` | `held_out` | `fault_d` | `E3` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 186.889 |
| `run-0180-098640b8` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E3` | 8 | 4 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 160.067 |
| `run-0181-307ec330` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1159.599 |
| `run-0182-f1fa7bdc` | `improved_checklist_v1` | `held_out` | `fault_e` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2180.912 |
| `run-0183-82effdcb` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E0` | 4 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3092.224 |
| `run-0184-9f5e3ff5` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E0` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2203.642 |
| `run-0185-1bccc134` | `improved_checklist_v1` | `held_out` | `fault_e` | `E0` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3244.934 |
| `run-0186-bac1e2e8` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E0` | 6 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3153.566 |
| `run-0187-5b1c0982` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E0` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3252.308 |
| `run-0188-534d3e39` | `improved_checklist_v1` | `held_out` | `fault_e` | `E0` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3240.606 |
| `run-0189-db5e39a5` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E0` | 8 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3158.025 |
| `run-0190-3cbd44ed` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1140.632 |
| `run-0191-878bcd7c` | `improved_checklist_v1` | `held_out` | `fault_e` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2185.478 |
| `run-0192-5a768e88` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E1` | 4 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3149.508 |
| `run-0193-46b959d7` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2183.228 |
| `run-0194-bd64ae42` | `improved_checklist_v1` | `held_out` | `fault_e` | `E1` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3218.753 |
| `run-0195-4988c6f3` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E1` | 6 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3138.434 |
| `run-0196-9352c44c` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E1` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3221.531 |
| `run-0197-ada6077d` | `improved_checklist_v1` | `held_out` | `fault_e` | `E1` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3265.023 |
| `run-0198-530edab0` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E1` | 8 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3171.587 |
| `run-0199-3c2a4e04` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1132.717 |
| `run-0200-4662c672` | `improved_checklist_v1` | `held_out` | `fault_e` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2215.086 |
| `run-0201-878ba6b8` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2143.834 |
| `run-0202-24618b43` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2183.586 |
| `run-0203-fe7daf35` | `improved_checklist_v1` | `held_out` | `fault_e` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2183.813 |
| `run-0204-8d0095da` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2139.305 |
| `run-0205-6288dfc2` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2174.855 |
| `run-0206-5a7b70ff` | `improved_checklist_v1` | `held_out` | `fault_e` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2148.263 |
| `run-0207-619302ea` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2135.186 |
| `run-0208-374d3e8a` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1092.548 |
| `run-0209-e799686d` | `improved_checklist_v1` | `held_out` | `fault_e` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2165.563 |
| `run-0210-c1a5ad04` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E3` | 4 | 4 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2114.355 |
| `run-0211-08fc0170` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E3` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2176.636 |
| `run-0212-0b90e950` | `improved_checklist_v1` | `held_out` | `fault_e` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2227.567 |
| `run-0213-687e1bf3` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E3` | 6 | 4 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2133.054 |
| `run-0214-b459c6f9` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E3` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2175.823 |
| `run-0215-5a272384` | `improved_checklist_v1` | `held_out` | `fault_e` | `E3` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2232.875 |
| `run-0216-602b7eac` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E3` | 8 | 4 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2144.367 |
| `run-0217-2088e4ff` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2087.541 |
| `run-0218-f9487a8f` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4091.431 |
| `run-0219-9a5d3f26` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2052.327 |
| `run-0220-94d7e6c2` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4089.11 |
| `run-0221-9bb41a64` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5598.253 |
| `run-0222-bbc3a551` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2092.043 |
| `run-0223-cf6ce275` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5611.892 |
| `run-0224-f8e3fd77` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5659.73 |
| `run-0225-a97c539c` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2086.389 |
| `run-0226-37787f13` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2093.577 |
| `run-0227-984d4286` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4105.892 |
| `run-0228-5032386a` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2085.538 |
| `run-0229-cbbf8b18` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4100.48 |
| `run-0230-2397194f` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5627.444 |
| `run-0231-16c1a9e1` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2067.948 |
| `run-0232-7291374b` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5629.628 |
| `run-0233-67d5f8e6` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5661.534 |
| `run-0234-6f5f0287` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2055.354 |
| `run-0235-5ecc441a` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E2` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2063.649 |
| `run-0236-8ec76d60` | `improved_checklist_v1` | `held_out` | `fault_f` | `E2` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4123.805 |
| `run-0237-54c0c84e` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E2` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2064.238 |
| `run-0238-01007e3d` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E2` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4094.383 |
| `run-0239-a2ab0232` | `improved_checklist_v1` | `held_out` | `fault_f` | `E2` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4119.336 |
| `run-0240-ee844243` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E2` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2076.922 |
| `run-0241-35060d8a` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E2` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4099.41 |
| `run-0242-14890f7a` | `improved_checklist_v1` | `held_out` | `fault_f` | `E2` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4091.516 |
| `run-0243-55192dec` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E2` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2087.44 |
| `run-0244-291cea14` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E3` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2084.705 |
| `run-0245-1ca7cb0e` | `improved_checklist_v1` | `held_out` | `fault_f` | `E3` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4099.257 |
| `run-0246-7571a26b` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E3` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2063.376 |
| `run-0247-35702499` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E3` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4093.916 |
| `run-0248-2c10326f` | `improved_checklist_v1` | `held_out` | `fault_f` | `E3` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4107.233 |
| `run-0249-6b1c1847` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E3` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2094.22 |
| `run-0250-75949b83` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E3` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4079.601 |
| `run-0251-1c771b99` | `improved_checklist_v1` | `held_out` | `fault_f` | `E3` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4109.858 |
| `run-0252-6bf11b5e` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E3` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2092.737 |
| `run-0253-bfb34d99` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 150.655 |
| `run-0254-bbb54684` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 190.716 |
| `run-0255-e516d141` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 191.159 |
| `run-0256-a840aa9f` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 204.61 |
| `run-0257-029b6b94` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 217.626 |
| `run-0258-53e87dfb` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 144.512 |
| `run-0259-232b9f97` | `deterministic_checklist_v1` | `development` | `healthy` | `E0` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 223.076 |
| `run-0260-341d3e10` | `improved_checklist_v1` | `development` | `healthy` | `E0` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 180.948 |
| `run-0261-c0a5ccc8` | `rule_adaptive_v1` | `development` | `healthy` | `E0` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 193.553 |
| `run-0262-68e3ad8a` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 133.07 |
| `run-0263-e6ef9dff` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 190.219 |
| `run-0264-c5968eba` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 206.831 |
| `run-0265-cfd975ff` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 180.556 |
| `run-0266-8f6559f6` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 233.214 |
| `run-0267-ff37098e` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 205.931 |
| `run-0268-4c279c94` | `deterministic_checklist_v1` | `development` | `healthy` | `E1` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 223.341 |
| `run-0269-9ef0d762` | `improved_checklist_v1` | `development` | `healthy` | `E1` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 250.288 |
| `run-0270-b72b34df` | `rule_adaptive_v1` | `development` | `healthy` | `E1` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 128.985 |
| `run-0271-2f66f30a` | `deterministic_checklist_v1` | `development` | `healthy` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 118.531 |
| `run-0272-3cb47728` | `improved_checklist_v1` | `development` | `healthy` | `E2` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 177.579 |
| `run-0273-ffec887f` | `rule_adaptive_v1` | `development` | `healthy` | `E2` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 160.96 |
| `run-0274-0043ac9f` | `deterministic_checklist_v1` | `development` | `healthy` | `E2` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 147.054 |
| `run-0275-b60ff02c` | `improved_checklist_v1` | `development` | `healthy` | `E2` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 193.239 |
| `run-0276-0caa3b85` | `rule_adaptive_v1` | `development` | `healthy` | `E2` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 204.666 |
| `run-0277-5daf1e63` | `deterministic_checklist_v1` | `development` | `healthy` | `E2` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 148.051 |
| `run-0278-0a75243e` | `improved_checklist_v1` | `development` | `healthy` | `E2` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 176.762 |
| `run-0279-20bb4fd8` | `rule_adaptive_v1` | `development` | `healthy` | `E2` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 186.754 |
| `run-0280-63d36eb5` | `deterministic_checklist_v1` | `development` | `healthy` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 117.57 |
| `run-0281-94637f1d` | `improved_checklist_v1` | `development` | `healthy` | `E3` | 4 | 4 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 189.197 |
| `run-0282-5d5718cd` | `rule_adaptive_v1` | `development` | `healthy` | `E3` | 4 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 207.378 |
| `run-0283-9fa12288` | `deterministic_checklist_v1` | `development` | `healthy` | `E3` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 222.6 |
| `run-0284-9e501420` | `improved_checklist_v1` | `development` | `healthy` | `E3` | 6 | 6 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 173.39 |
| `run-0285-30386b85` | `rule_adaptive_v1` | `development` | `healthy` | `E3` | 6 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 142.625 |
| `run-0286-2567afee` | `deterministic_checklist_v1` | `development` | `healthy` | `E3` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 209.08 |
| `run-0287-dc46393a` | `improved_checklist_v1` | `development` | `healthy` | `E3` | 8 | 8 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 180.827 |
| `run-0288-f61d0ade` | `rule_adaptive_v1` | `development` | `healthy` | `E3` | 8 | 3 | `healthy` | `-` | `True` | `True` | `healthy_confirmed` | 179.565 |
| `run-0289-634c4c78` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 81.637 |
| `run-0290-b08ebc33` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 141.931 |
| `run-0291-3cb6cd95` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 85.759 |
| `run-0292-e8d1491b` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 159.03 |
| `run-0293-31f67a30` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 252.621 |
| `run-0294-ef7375e4` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 95.95 |
| `run-0295-184c95b5` | `deterministic_checklist_v1` | `development` | `fault_a` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 164.148 |
| `run-0296-3639fd18` | `improved_checklist_v1` | `development` | `fault_a` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 181.407 |
| `run-0297-5d9e8515` | `rule_adaptive_v1` | `development` | `fault_a` | `E0` | 8 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 95.54 |
| `run-0298-ba61cec5` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 131.449 |
| `run-0299-88a6da32` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 156.002 |
| `run-0300-af1def1b` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 76.213 |
| `run-0301-bb4836e8` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 135.935 |
| `run-0302-b51602ab` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 263.308 |
| `run-0303-5436fa41` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 94.516 |
| `run-0304-12eb4395` | `deterministic_checklist_v1` | `development` | `fault_a` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 192.044 |
| `run-0305-44ab8852` | `improved_checklist_v1` | `development` | `fault_a` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 234.88 |
| `run-0306-039cf355` | `rule_adaptive_v1` | `development` | `fault_a` | `E1` | 8 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 67.438 |
| `run-0307-65271bd0` | `deterministic_checklist_v1` | `development` | `fault_a` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 108.208 |
| `run-0308-6990604a` | `improved_checklist_v1` | `development` | `fault_a` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 163.374 |
| `run-0309-355246f9` | `rule_adaptive_v1` | `development` | `fault_a` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 67.752 |
| `run-0310-bf6680cb` | `deterministic_checklist_v1` | `development` | `fault_a` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 128.009 |
| `run-0311-4b3591be` | `improved_checklist_v1` | `development` | `fault_a` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 147.016 |
| `run-0312-e015b89e` | `rule_adaptive_v1` | `development` | `fault_a` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 69.934 |
| `run-0313-5dfeb625` | `deterministic_checklist_v1` | `development` | `fault_a` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 185.793 |
| `run-0314-0d00c316` | `improved_checklist_v1` | `development` | `fault_a` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 152.815 |
| `run-0315-1cbf3423` | `rule_adaptive_v1` | `development` | `fault_a` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 97.564 |
| `run-0316-5b8899c4` | `deterministic_checklist_v1` | `development` | `fault_a` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 155.138 |
| `run-0317-7dd74a66` | `improved_checklist_v1` | `development` | `fault_a` | `E3` | 4 | 4 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 184.955 |
| `run-0318-2c0edc88` | `rule_adaptive_v1` | `development` | `fault_a` | `E3` | 4 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 63.106 |
| `run-0319-4a495187` | `deterministic_checklist_v1` | `development` | `fault_a` | `E3` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 153.518 |
| `run-0320-3b7a91b8` | `improved_checklist_v1` | `development` | `fault_a` | `E3` | 6 | 6 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 155.0 |
| `run-0321-6f76a583` | `rule_adaptive_v1` | `development` | `fault_a` | `E3` | 6 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 114.22 |
| `run-0322-f54b1882` | `deterministic_checklist_v1` | `development` | `fault_a` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 176.892 |
| `run-0323-2b5bf2de` | `improved_checklist_v1` | `development` | `fault_a` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 165.159 |
| `run-0324-fdf0746e` | `rule_adaptive_v1` | `development` | `fault_a` | `E3` | 8 | 3 | `diagnosed` | `order-service:db_endpoint_misconfiguration` | `True` | `True` | `diagnosis_reached` | 82.399 |
| `run-0325-e7b3bd3b` | `deterministic_checklist_v1` | `development` | `fault_b` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1121.242 |
| `run-0326-1678a98a` | `improved_checklist_v1` | `development` | `fault_b` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2137.536 |
| `run-0327-ed4afc2f` | `rule_adaptive_v1` | `development` | `fault_b` | `E0` | 4 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3115.343 |
| `run-0328-16af5144` | `deterministic_checklist_v1` | `development` | `fault_b` | `E0` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2151.206 |
| `run-0329-919fae54` | `improved_checklist_v1` | `development` | `fault_b` | `E0` | 6 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3198.651 |
| `run-0330-fc3f1001` | `rule_adaptive_v1` | `development` | `fault_b` | `E0` | 6 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3127.881 |
| `run-0331-36b6bd52` | `deterministic_checklist_v1` | `development` | `fault_b` | `E0` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3233.444 |
| `run-0332-af694701` | `improved_checklist_v1` | `development` | `fault_b` | `E0` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3214.75 |
| `run-0333-6e3e91ac` | `rule_adaptive_v1` | `development` | `fault_b` | `E0` | 8 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3107.961 |
| `run-0334-f7254c21` | `deterministic_checklist_v1` | `development` | `fault_b` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1149.701 |
| `run-0335-7125fdaf` | `improved_checklist_v1` | `development` | `fault_b` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2214.576 |
| `run-0336-a6f73d76` | `rule_adaptive_v1` | `development` | `fault_b` | `E1` | 4 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3115.055 |
| `run-0337-15f59080` | `deterministic_checklist_v1` | `development` | `fault_b` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2176.307 |
| `run-0338-85d3cefd` | `improved_checklist_v1` | `development` | `fault_b` | `E1` | 6 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3224.096 |
| `run-0339-51324481` | `rule_adaptive_v1` | `development` | `fault_b` | `E1` | 6 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3094.587 |
| `run-0340-f0734a88` | `deterministic_checklist_v1` | `development` | `fault_b` | `E1` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3138.756 |
| `run-0341-435bb8c8` | `improved_checklist_v1` | `development` | `fault_b` | `E1` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3243.575 |
| `run-0342-4b5a5793` | `rule_adaptive_v1` | `development` | `fault_b` | `E1` | 8 | 4 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 3131.885 |
| `run-0343-ad3c240f` | `deterministic_checklist_v1` | `development` | `fault_b` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1138.958 |
| `run-0344-d4643626` | `improved_checklist_v1` | `development` | `fault_b` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2144.378 |
| `run-0345-7fe751ee` | `rule_adaptive_v1` | `development` | `fault_b` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2104.642 |
| `run-0346-08207071` | `deterministic_checklist_v1` | `development` | `fault_b` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2146.139 |
| `run-0347-d17218a9` | `improved_checklist_v1` | `development` | `fault_b` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2206.67 |
| `run-0348-686ca063` | `rule_adaptive_v1` | `development` | `fault_b` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2088.206 |
| `run-0349-1c5d2d40` | `deterministic_checklist_v1` | `development` | `fault_b` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2210.8 |
| `run-0350-cd1bf474` | `improved_checklist_v1` | `development` | `fault_b` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2152.133 |
| `run-0351-8e9d76e5` | `rule_adaptive_v1` | `development` | `fault_b` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2104.504 |
| `run-0352-b78603a0` | `deterministic_checklist_v1` | `development` | `fault_b` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1163.642 |
| `run-0353-2bb61e5e` | `improved_checklist_v1` | `development` | `fault_b` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2212.716 |
| `run-0354-a1aa10ab` | `rule_adaptive_v1` | `development` | `fault_b` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2079.221 |
| `run-0355-67535cce` | `deterministic_checklist_v1` | `development` | `fault_b` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2168.544 |
| `run-0356-8d8c8fbf` | `improved_checklist_v1` | `development` | `fault_b` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2163.179 |
| `run-0357-de7e6cf6` | `rule_adaptive_v1` | `development` | `fault_b` | `E3` | 6 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2106.604 |
| `run-0358-a8c1815a` | `deterministic_checklist_v1` | `development` | `fault_b` | `E3` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2201.587 |
| `run-0359-e607e95d` | `improved_checklist_v1` | `development` | `fault_b` | `E3` | 8 | 8 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2190.252 |
| `run-0360-d1c9e193` | `rule_adaptive_v1` | `development` | `fault_b` | `E3` | 8 | 6 | `diagnosed` | `database:db_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2099.989 |
| `run-0361-fb0fb2ab` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 156.989 |
| `run-0362-301c2d65` | `improved_checklist_v1` | `held_out` | `fault_c` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 213.011 |
| `run-0363-194fd88c` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E0` | 4 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 156.445 |
| `run-0364-791e1300` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 257.783 |
| `run-0365-1a11001e` | `improved_checklist_v1` | `held_out` | `fault_c` | `E0` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 212.491 |
| `run-0366-415a9d67` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E0` | 6 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 171.99 |
| `run-0367-8afcd11f` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 320.565 |
| `run-0368-57f46d25` | `improved_checklist_v1` | `held_out` | `fault_c` | `E0` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 230.52 |
| `run-0369-498b8563` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E0` | 8 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 177.032 |
| `run-0370-d135301d` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 195.901 |
| `run-0371-5fe3c695` | `improved_checklist_v1` | `held_out` | `fault_c` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 220.137 |
| `run-0372-f0521301` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E1` | 4 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 173.961 |
| `run-0373-8f969e9f` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 150.331 |
| `run-0374-bffd0fd8` | `improved_checklist_v1` | `held_out` | `fault_c` | `E1` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 269.076 |
| `run-0375-84fa4e2b` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E1` | 6 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 159.315 |
| `run-0376-be579cb0` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 214.783 |
| `run-0377-b6f8ea62` | `improved_checklist_v1` | `held_out` | `fault_c` | `E1` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 220.493 |
| `run-0378-2bb722ea` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E1` | 8 | 3 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 143.959 |
| `run-0379-1b60a837` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 149.206 |
| `run-0380-2ac3b33c` | `improved_checklist_v1` | `held_out` | `fault_c` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 221.521 |
| `run-0381-33623294` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 116.025 |
| `run-0382-beaa6fbd` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 187.546 |
| `run-0383-ebdf4247` | `improved_checklist_v1` | `held_out` | `fault_c` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 229.667 |
| `run-0384-8de9f8fb` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 177.058 |
| `run-0385-79b12671` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 250.988 |
| `run-0386-a0589828` | `improved_checklist_v1` | `held_out` | `fault_c` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 192.982 |
| `run-0387-23423a16` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 115.731 |
| `run-0388-87066bb8` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 179.532 |
| `run-0389-3135968c` | `improved_checklist_v1` | `held_out` | `fault_c` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 247.79 |
| `run-0390-dc661bc7` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E3` | 4 | 4 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 134.046 |
| `run-0391-e0b6c2dd` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E3` | 6 | 6 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 208.54 |
| `run-0392-611972ca` | `improved_checklist_v1` | `held_out` | `fault_c` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 269.438 |
| `run-0393-11e14d50` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E3` | 6 | 4 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 149.196 |
| `run-0394-54c47b86` | `deterministic_checklist_v1` | `held_out` | `fault_c` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 271.998 |
| `run-0395-d48b3e1a` | `improved_checklist_v1` | `held_out` | `fault_c` | `E3` | 8 | 8 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 225.756 |
| `run-0396-7492e9ba` | `rule_adaptive_v1` | `held_out` | `fault_c` | `E3` | 8 | 4 | `diagnosed` | `order-service:db_auth_failure` | `True` | `True` | `diagnosis_reached` | 169.112 |
| `run-0397-c1a566a9` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 131.887 |
| `run-0398-bbd7f9c6` | `improved_checklist_v1` | `held_out` | `fault_d` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 207.513 |
| `run-0399-6b7e42cc` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E0` | 4 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 165.623 |
| `run-0400-7d7bf3da` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E0` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 244.407 |
| `run-0401-bf202602` | `improved_checklist_v1` | `held_out` | `fault_d` | `E0` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 259.563 |
| `run-0402-109904fb` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E0` | 6 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 170.871 |
| `run-0403-f311f717` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E0` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 313.52 |
| `run-0404-9950f976` | `improved_checklist_v1` | `held_out` | `fault_d` | `E0` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 311.382 |
| `run-0405-ed2da615` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E0` | 8 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 156.287 |
| `run-0406-e63e1645` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 124.54 |
| `run-0407-bdb661f3` | `improved_checklist_v1` | `held_out` | `fault_d` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 206.369 |
| `run-0408-72fb54b8` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E1` | 4 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 172.956 |
| `run-0409-ed0421e8` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 237.226 |
| `run-0410-91f5019b` | `improved_checklist_v1` | `held_out` | `fault_d` | `E1` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 248.309 |
| `run-0411-00cda2c4` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E1` | 6 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 189.188 |
| `run-0412-77228190` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E1` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 320.047 |
| `run-0413-bf956624` | `improved_checklist_v1` | `held_out` | `fault_d` | `E1` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 236.045 |
| `run-0414-8c8fd965` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E1` | 8 | 3 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 189.866 |
| `run-0415-e12ec042` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 125.182 |
| `run-0416-5ceac896` | `improved_checklist_v1` | `held_out` | `fault_d` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 221.687 |
| `run-0417-0f0fe564` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 129.319 |
| `run-0418-8829e278` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 191.883 |
| `run-0419-b3cf6401` | `improved_checklist_v1` | `held_out` | `fault_d` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 254.291 |
| `run-0420-789f14d6` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 176.057 |
| `run-0421-4805f219` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 172.507 |
| `run-0422-e0a269e3` | `improved_checklist_v1` | `held_out` | `fault_d` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 208.495 |
| `run-0423-dd9fadf9` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 157.19 |
| `run-0424-fee45ec7` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 167.64 |
| `run-0425-c33ce9a5` | `improved_checklist_v1` | `held_out` | `fault_d` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 220.646 |
| `run-0426-26d9e8fd` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E3` | 4 | 4 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 163.963 |
| `run-0427-2c52ce11` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E3` | 6 | 6 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 281.158 |
| `run-0428-06b3ff04` | `improved_checklist_v1` | `held_out` | `fault_d` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 217.24 |
| `run-0429-cc030f9f` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E3` | 6 | 4 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 164.519 |
| `run-0430-6d413878` | `deterministic_checklist_v1` | `held_out` | `fault_d` | `E3` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 275.436 |
| `run-0431-7ea9be6b` | `improved_checklist_v1` | `held_out` | `fault_d` | `E3` | 8 | 8 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 260.098 |
| `run-0432-22563da2` | `rule_adaptive_v1` | `held_out` | `fault_d` | `E3` | 8 | 4 | `diagnosed` | `database:db_schema_missing_table` | `True` | `True` | `diagnosis_reached` | 162.388 |
| `run-0433-56a7a3c1` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1147.401 |
| `run-0434-21a640ac` | `improved_checklist_v1` | `held_out` | `fault_e` | `E0` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2181.949 |
| `run-0435-87316b47` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E0` | 4 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3153.008 |
| `run-0436-785e9023` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E0` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2221.096 |
| `run-0437-5b6685e2` | `improved_checklist_v1` | `held_out` | `fault_e` | `E0` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3243.097 |
| `run-0438-e9e5b6ab` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E0` | 6 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3142.029 |
| `run-0439-a0d6e4db` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E0` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3238.352 |
| `run-0440-1d307302` | `improved_checklist_v1` | `held_out` | `fault_e` | `E0` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3309.546 |
| `run-0441-f29fc819` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E0` | 8 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3131.197 |
| `run-0442-cf64be27` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1118.179 |
| `run-0443-f5ec3bb6` | `improved_checklist_v1` | `held_out` | `fault_e` | `E1` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2175.29 |
| `run-0444-a031a4c7` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E1` | 4 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3131.48 |
| `run-0445-3f195daa` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E1` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2155.801 |
| `run-0446-5ff203c2` | `improved_checklist_v1` | `held_out` | `fault_e` | `E1` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3275.662 |
| `run-0447-6a51267b` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E1` | 6 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3157.707 |
| `run-0448-a19d6385` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E1` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3285.192 |
| `run-0449-b0d4a831` | `improved_checklist_v1` | `held_out` | `fault_e` | `E1` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3264.872 |
| `run-0450-377321f2` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E1` | 8 | 3 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 3136.167 |
| `run-0451-816dc389` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1129.049 |
| `run-0452-628d5439` | `improved_checklist_v1` | `held_out` | `fault_e` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2233.994 |
| `run-0453-4d1fc58d` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E2` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2088.806 |
| `run-0454-650514ea` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2127.485 |
| `run-0455-f59a3606` | `improved_checklist_v1` | `held_out` | `fault_e` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2125.339 |
| `run-0456-5cbbae52` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E2` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2086.243 |
| `run-0457-ebbbe7b9` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2132.662 |
| `run-0458-bf728919` | `improved_checklist_v1` | `held_out` | `fault_e` | `E2` | 8 | 8 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2162.37 |
| `run-0459-7d96bbc1` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E2` | 8 | 6 | `inconclusive` | `-` | `False` | `True` | `insufficient_distinguishing_evidence` | 2106.201 |
| `run-0460-897a713f` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 1136.631 |
| `run-0461-53edb8aa` | `improved_checklist_v1` | `held_out` | `fault_e` | `E3` | 4 | 4 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2241.476 |
| `run-0462-f1240048` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E3` | 4 | 4 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2111.346 |
| `run-0463-e84ecbdc` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E3` | 6 | 6 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2223.07 |
| `run-0464-7d18edf0` | `improved_checklist_v1` | `held_out` | `fault_e` | `E3` | 6 | 6 | `inconclusive` | `-` | `False` | `True` | `budget_exhausted` | 2216.147 |
| `run-0465-8b6052dc` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E3` | 6 | 4 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2145.884 |
| `run-0466-69646c52` | `deterministic_checklist_v1` | `held_out` | `fault_e` | `E3` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2155.348 |
| `run-0467-767ae200` | `improved_checklist_v1` | `held_out` | `fault_e` | `E3` | 8 | 8 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2179.972 |
| `run-0468-712d2cfa` | `rule_adaptive_v1` | `held_out` | `fault_e` | `E3` | 8 | 4 | `diagnosed` | `database:db_operation_delay` | `True` | `True` | `diagnosis_reached` | 2113.558 |
| `run-0469-2840a3b7` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2092.641 |
| `run-0470-943f8187` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4107.474 |
| `run-0471-4f2e66b0` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2054.525 |
| `run-0472-c3f3674a` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4118.1 |
| `run-0473-f150c286` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5636.226 |
| `run-0474-c7619ae1` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2097.152 |
| `run-0475-52e108b6` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E0` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5664.386 |
| `run-0476-0836b281` | `improved_checklist_v1` | `held_out` | `fault_f` | `E0` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5629.879 |
| `run-0477-bc7a7f18` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E0` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2207.051 |
| `run-0478-96e62017` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2083.398 |
| `run-0479-4604925b` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4078.788 |
| `run-0480-73dad3f3` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2046.784 |
| `run-0481-2cef38a5` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4090.341 |
| `run-0482-86b9fb8a` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5627.347 |
| `run-0483-c48b7235` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2088.59 |
| `run-0484-a8792f57` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E1` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5640.054 |
| `run-0485-258bcfd8` | `improved_checklist_v1` | `held_out` | `fault_f` | `E1` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 5614.247 |
| `run-0486-09de379e` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E1` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2076.692 |
| `run-0487-a6ca6b9f` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E2` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2076.226 |
| `run-0488-5e6674ba` | `improved_checklist_v1` | `held_out` | `fault_f` | `E2` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4100.49 |
| `run-0489-3a6be9a9` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E2` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2091.752 |
| `run-0490-38b848f0` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E2` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4096.716 |
| `run-0491-c5490d9e` | `improved_checklist_v1` | `held_out` | `fault_f` | `E2` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4105.044 |
| `run-0492-9c3e4f33` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E2` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2091.589 |
| `run-0493-d193c3cf` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E2` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4081.308 |
| `run-0494-687f4073` | `improved_checklist_v1` | `held_out` | `fault_f` | `E2` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4106.649 |
| `run-0495-5b025810` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E2` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2067.389 |
| `run-0496-76c46edf` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E3` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2075.215 |
| `run-0497-1ebfad99` | `improved_checklist_v1` | `held_out` | `fault_f` | `E3` | 4 | 4 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4110.801 |
| `run-0498-79cb8c7a` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E3` | 4 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2104.036 |
| `run-0499-e7c6ef15` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E3` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4116.777 |
| `run-0500-8d7610b2` | `improved_checklist_v1` | `held_out` | `fault_f` | `E3` | 6 | 6 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4102.061 |
| `run-0501-31808e7c` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E3` | 6 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2084.73 |
| `run-0502-c24c9c4e` | `deterministic_checklist_v1` | `held_out` | `fault_f` | `E3` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4109.709 |
| `run-0503-9de14ebf` | `improved_checklist_v1` | `held_out` | `fault_f` | `E3` | 8 | 8 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 4129.667 |
| `run-0504-4c83b70d` | `rule_adaptive_v1` | `held_out` | `fault_f` | `E3` | 8 | 2 | `diagnosed` | `order-service:order_service_unavailable` | `True` | `True` | `diagnosis_reached` | 2080.96 |

## 8. Methodological Caveats & Interpretation Notes
1. **Evidential Support vs. Evidence-ID Validity**: `all_evidence_ids_valid` checks only that cited `evidence_id`s exist in the run's audit log, whereas `evidential_support_verified` independently runs the `EvidenceGate` on collected observations to ensure the cited evidence actually establishes the diagnosed fault.
2. **Ambiguous Evidence Conditions (`E2`)**: Under `E2`, `fault_a` through `fault_e` cannot be distinguished by permitted observations. Any method returning a confident diagnosis on those cases is penalized via `wrong_confident_diagnosis_on_ambiguous` rather than rewarded for a lucky guess.
3. **Generalization Limits**: Results are measured on a controlled 3-component microservice testbed (`gateway -> order-service -> database`) with 6 reproducible single-fault scenarios and 4 evidence policies (`E0, E1, E2, E3`); they do not claim production generalization across arbitrary distributed systems.
