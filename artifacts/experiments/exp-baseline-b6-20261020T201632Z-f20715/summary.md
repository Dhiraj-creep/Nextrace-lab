# NexTrace Phase 1 — Experiment Suite Summary (`exp-baseline-b6-20261020T201632Z-f20715`)

## 1. Execution Metadata
- **Method**: `deterministic_checklist_v1`
- **Runtime Mode**: `local`
- **Started (UTC)**: `2026-10-20T20:16:32.927310Z`
- **Completed (UTC)**: `2026-10-20T20:17:30.412782Z`
- **Total Suite Elapsed Time**: `57483.42 ms`
- **Check Budget per Run**: `6`
- **Repetitions per Condition**: `1`
- **Public Results Directory**: `C:\Users\dhiraj\.gemini\antigravity\scratch\nextrace\artifacts\experiments\exp-baseline-b6-20261020T201632Z-f20715`
- **Private Ground-Truth Directory**: `C:\Users\dhiraj\.gemini\antigravity\scratch\nextrace\var\ground_truth\exp-baseline-b6-20261020T201632Z-f20715`

## 2. Aggregate Evaluation Metrics
| Metric | Value |
| :--- | :--- |
| Total Runs | `9` |
| Answered Runs (Non-Inconclusive) | `3` |
| Inconclusive Runs (Abstentions) | `6` |
| Diagnosis Coverage Rate | `33.33%` |
| Accuracy Among Answered Cases | `100.00%` |
| **Overall Exact-Match Rate (All Runs)** | **`33.33%`** |
| Fault Scenarios Coverage Rate | `0.00%` |
| Fault Service Accuracy (Overall) | `0.00%` |
| Fault Type Accuracy (Overall) | `0.00%` |
| False Fault Diagnoses on Healthy Cases | `0 / 3` |
| Cited Evidence-ID Referential Integrity | `100.00%` |
| Budget Compliance Rate | `100.00%` |
| Setup / Recovery Failures | `0 / 0` |

## 3. Breakdown by Evidence Condition
| Evidence Condition | Total Runs | Coverage Rate | Inconclusive Rate | Accuracy (Answered) | Overall Exact-Match Rate | Fault Exact-Match (Overall) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `E0` | 3 | 33.33% | 66.67% | 100.00% | 33.33% | 0.00% |
| `E1` | 3 | 33.33% | 66.67% | 100.00% | 33.33% | 0.00% |
| `E2` | 3 | 33.33% | 66.67% | 100.00% | 33.33% | 0.00% |

## 4. Per-Run Results
| Run ID | Scenario | Condition | Budget | Checks | Outcome | Predicted Service | Predicted Fault | Exact Match | Stop Reason | Duration (ms) | Bytes |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| `run-0001-564e0906` | `healthy` | `E0` | 6 | 6 | `DiagnosticOutcome.HEALTHY` | `-` | `-` | `True` | `StopReason.HEALTHY_CONFIRMED` | 165.348 | 2935 |
| `run-0002-2733cb48` | `healthy` | `E1` | 6 | 6 | `DiagnosticOutcome.HEALTHY` | `-` | `-` | `True` | `StopReason.HEALTHY_CONFIRMED` | 208.087 | 960 |
| `run-0003-709daaad` | `healthy` | `E2` | 6 | 6 | `DiagnosticOutcome.HEALTHY` | `-` | `-` | `True` | `StopReason.HEALTHY_CONFIRMED` | 202.19 | 855 |
| `run-0004-19c2673a` | `fault_a` | `E0` | 6 | 6 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.BUDGET_EXHAUSTED` | 177.227 | 3330 |
| `run-0005-e84729d2` | `fault_a` | `E1` | 6 | 6 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.BUDGET_EXHAUSTED` | 130.447 | 1000 |
| `run-0006-a5c3b94c` | `fault_a` | `E2` | 6 | 6 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.BUDGET_EXHAUSTED` | 102.116 | 857 |
| `run-0007-e2ea1feb` | `fault_b` | `E0` | 6 | 6 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.BUDGET_EXHAUSTED` | 2176.334 | 3308 |
| `run-0008-70d7d043` | `fault_b` | `E1` | 6 | 6 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.BUDGET_EXHAUSTED` | 2167.861 | 992 |
| `run-0009-98501dbc` | `fault_b` | `E2` | 6 | 6 | `DiagnosticOutcome.INCONCLUSIVE` | `-` | `-` | `False` | `StopReason.BUDGET_EXHAUSTED` | 2135.334 | 857 |

## 5. Methodological Caveats & Interpretation Notes
1. **E1 Interpretation**: A successful diagnosis under `E1` (logs unavailable) when `budget >= 8` does **not** prove general robustness across missing-data scenarios; it shows that after wasting 2 check attempts on unavailable log sources (`get_recent_logs`), sufficient alternative evidence (`get_order_service_database_config` and `get_service_health('database')`) still remained within the 8-check budget. When the check budget is constrained (e.g., `budget=6`), those 2 wasted log checks exhaust the budget before `get_service_health('database')` can be called.
2. **E2 Interpretation**: Under `E2`, critical distinguishing checks (`get_order_service_database_config`, `get_service_health('database')`, and `get_recent_logs`) are masked as `unavailable` and connectivity is coarsened to `reachable`/`unreachable`. Returning `inconclusive` for `fault_a` and `fault_b` reflects honest epistemic abstention rather than guessing.
3. **Evidence-ID Integrity**: `all_evidence_ids_valid` verifies only that cited `evidence_id` strings exist in the run's audited tool records; it is not proof that a method's causal reasoning is logically valid.
4. **Sample Size**: These controlled runs verify functional reproducibility and baseline mechanics; they are not a claim of statistical significance.
