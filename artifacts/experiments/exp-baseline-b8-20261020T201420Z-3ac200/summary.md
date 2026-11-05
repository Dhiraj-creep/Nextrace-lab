# NexTrace Phase 1 — Experiment Suite Summary (`exp-baseline-b8-20261020T201420Z-3ac200`)

## 1. Execution Metadata
- **Method**: `deterministic_checklist_v1`
- **Runtime Mode**: `local`
- **Started (UTC)**: `2026-10-20T20:14:20.591062Z`
- **Completed (UTC)**: `2026-10-20T20:15:20.153815Z`
- **Total Suite Elapsed Time**: `59560.57 ms`
- **Check Budget per Run**: `8`
- **Repetitions per Condition**: `1`
- **Public Results Directory**: `C:\Users\dhiraj\.gemini\antigravity\scratch\nextrace\artifacts\experiments\exp-baseline-b8-20261020T201420Z-3ac200`
- **Private Ground-Truth Directory**: `C:\Users\dhiraj\.gemini\antigravity\scratch\nextrace\var\ground_truth\exp-baseline-b8-20261020T201420Z-3ac200`

## 2. Aggregate Evaluation Metrics
| Metric | Value |
| :--- | :--- |
| Total Runs | `9` |
| Answered Runs (Non-Inconclusive) | `7` |
| Inconclusive Runs (Abstentions) | `2` |
| Diagnosis Coverage Rate | `77.78%` |
| Accuracy Among Answered Cases | `100.00%` |
| **Overall Exact-Match Rate (All Runs)** | **`77.78%`** |
| Fault Scenarios Coverage Rate | `66.67%` |
| Fault Service Accuracy (Overall) | `66.67%` |
| Fault Type Accuracy (Overall) | `66.67%` |
| False Fault Diagnoses on Healthy Cases | `0 / 3` |
| Cited Evidence-ID Referential Integrity | `100.00%` |
| Budget Compliance Rate | `100.00%` |
| Setup / Recovery Failures | `0 / 0` |

## 3. Breakdown by Evidence Condition
| Evidence Condition | Total Runs | Coverage Rate | Inconclusive Rate | Accuracy (Answered) | Overall Exact-Match Rate | Fault Exact-Match (Overall) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `E0` | 3 | 100.00% | 0.00% | 100.00% | 100.00% | 100.00% |
| `E1` | 3 | 100.00% | 0.00% | 100.00% | 100.00% | 100.00% |
| `E2` | 3 | 33.33% | 66.67% | 100.00% | 33.33% | 0.00% |

## 4. Per-Run Results
| Run ID | Scenario | Condition | Budget | Checks | Outcome | Predicted Service | Predicted Fault | Exact Match | Stop Reason | Duration (ms) | Bytes |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| `run-0001-98a80ff5` | `healthy` | `E0` | 8 | 8 | `DiagnosticOutcome.HEALTHY` | `-` | `-` | `True` | `StopReason.HEALTHY_CONFIRMED` | 244.31 | 3109 |
| `run-0002-3d70d90f` | `healthy` | `E1` | 8 | 8 | `DiagnosticOutcome.HEALTHY` | `-` | `-` | `True` | `StopReason.HEALTHY_CONFIRMED` | 256.064 | 1133 |
| `run-0003-7239c542` | `healthy` | `E2` | 8 | 8 | `DiagnosticOutcome.HEALTHY` | `-` | `-` | `True` | `StopReason.HEALTHY_CONFIRMED` | 165.736 | 855 |
| `run-0004-613c0363` | `fault_a` | `E0` | 8 | 8 | `DiagnosticOutcome.DIAGNOSED` | `order-service` | `db_endpoint_misconfiguration` | `True` | `StopReason.DIAGNOSIS_REACHED` | 201.252 | 3520 |
| `run-0005-df65409c` | `fault_a` | `E1` | 8 | 8 | `DiagnosticOutcome.DIAGNOSED` | `order-service` | `db_endpoint_misconfiguration` | `True` | `StopReason.DIAGNOSIS_REACHED` | 241.45 | 1190 |
| `run-0006-2f0feaca` | `fault_a` | `E2` | 8 | 8 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.INSUFFICIENT_DISTINGUISHING_EVIDENCE` | 180.226 | 857 |
| `run-0007-1fb4aca5` | `fault_b` | `E0` | 8 | 8 | `DiagnosticOutcome.DIAGNOSED` | `database` | `db_service_unavailable` | `True` | `StopReason.DIAGNOSIS_REACHED` | 3201.405 | 3480 |
| `run-0008-bf34f137` | `fault_b` | `E1` | 8 | 8 | `DiagnosticOutcome.DIAGNOSED` | `database` | `db_service_unavailable` | `True` | `StopReason.DIAGNOSIS_REACHED` | 3157.626 | 1163 |
| `run-0009-7388ee4e` | `fault_b` | `E2` | 8 | 8 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.INSUFFICIENT_DISTINGUISHING_EVIDENCE` | 2212.144 | 857 |

## 5. Methodological Caveats & Interpretation Notes
1. **E1 Interpretation**: A successful diagnosis under `E1` (logs unavailable) when `budget >= 8` does **not** prove general robustness across missing-data scenarios; it shows that after wasting 2 check attempts on unavailable log sources (`get_recent_logs`), sufficient alternative evidence (`get_order_service_database_config` and `get_service_health('database')`) still remained within the 8-check budget. When the check budget is constrained (e.g., `budget=6`), those 2 wasted log checks exhaust the budget before `get_service_health('database')` can be called.
2. **E2 Interpretation**: Under `E2`, critical distinguishing checks (`get_order_service_database_config`, `get_service_health('database')`, and `get_recent_logs`) are masked as `unavailable` and connectivity is coarsened to `reachable`/`unreachable`. Returning `inconclusive` for `fault_a` and `fault_b` reflects honest epistemic abstention rather than guessing.
3. **Evidence-ID Integrity**: `all_evidence_ids_valid` verifies only that cited `evidence_id` strings exist in the run's audited tool records; it is not proof that a method's causal reasoning is logically valid.
4. **Sample Size**: These controlled runs verify functional reproducibility and baseline mechanics; they are not a claim of statistical significance.
