# NexTrace Comparative Experiment Report — `exp-v040-reserved-evaluation-20261022T193316Z-8872a4`

## 1. Provenance & Environment Metadata
- **Created (UTC)**: `2026-10-22T19:36:09.460509Z`
- **Git Commit**: `uncommitted-worktree`
- **Source Content Manifest Digest (SHA-256)**: `cfdce351767b8e00fb3a329f825c0c7b8c5dd4f36fd681015c3cbe285d89be01`
- **Config Hash**: `8872a4c633c7`
- **Stopping Policy Mode**: `None`
- **Random Seed**: `42` (`counterbalance_methods=True`)
- **Runtime Mode**: `local`
- **Active Backend(s)**: `local_sqlite_tcp`
- **Applications Evaluated**: `['orders_app']`
- **Python / Platform**: `3.14.7` on `Windows-11-10.0.26300-SP0`
- **Methods Compared**: `['deterministic_checklist_v1', 'improved_checklist_v1', 'rule_adaptive_v1', 'scored_adaptive_v2', 'mock_ai_offline_v1']`
- **Budgets Evaluated**: `[6, 8]`
- **Evidence Conditions**: `['E0', 'E1', 'E2', 'E3']`
- **Repetitions per Cell**: `1`
- **AI Provider**: `mock-deterministic` (`is_mock_ai=True`)

## 2. Aggregate Comparison by Method

| Method | Runs | Joint Root-Cause Acc | Cause-Set Precision | Cause-Set Recall | Supported Diag Rate | Honest Inconclusive | Overclaim Rate | Avg Budget Used | Avg Checks | Redundant Unavail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | 8 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 7.00 | 5.50 | 0 |
| `improved_checklist_v1` | 8 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 7.00 | 5.50 | 0 |
| `mock_ai_offline_v1` | 8 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 | 2.00 | 0 |
| `rule_adaptive_v1` | 8 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 | 2.00 | 0 |
| `scored_adaptive_v2` | 8 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 | 2.00 | 0 |

## 3. Method Performance by Scenario Split

| Method | Split | Runs | Joint Root-Cause Acc | Exact Set Match | Supported Rate | Honest Inconclusive | Overclaim Rate | Avg Budget |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | `reserved_eval` | 8 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | 7.00 |
| `improved_checklist_v1` | `reserved_eval` | 8 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 7.00 |
| `mock_ai_offline_v1` | `reserved_eval` | 8 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `reserved_eval` | 8 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `reserved_eval` | 8 | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |

## 4. Method Performance by Evidence Condition (E0–E5)

| Method | Condition | Runs | Joint Root-Cause Acc | Supported Rate | Honest Inconclusive | Overclaim Rate | Avg Budget |
|---|---|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | `E0` | 2 | 0.00% | 0.00% | 100.00% | 0.00% | 7.00 |
| `deterministic_checklist_v1` | `E1` | 2 | 0.00% | 0.00% | 100.00% | 0.00% | 7.00 |
| `deterministic_checklist_v1` | `E2` | 2 | 0.00% | 0.00% | 100.00% | 0.00% | 7.00 |
| `deterministic_checklist_v1` | `E3` | 2 | 0.00% | 0.00% | 100.00% | 0.00% | 7.00 |
| `improved_checklist_v1` | `E0` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 7.00 |
| `improved_checklist_v1` | `E1` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 7.00 |
| `improved_checklist_v1` | `E2` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 7.00 |
| `improved_checklist_v1` | `E3` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 7.00 |
| `mock_ai_offline_v1` | `E0` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `mock_ai_offline_v1` | `E1` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `mock_ai_offline_v1` | `E2` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `mock_ai_offline_v1` | `E3` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `E0` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `E1` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `E2` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `E3` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `E0` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `E1` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `E2` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `E3` | 2 | 100.00% | 100.00% | 0.00% | 0.00% | 2.00 |

## 5. Method Performance by Budget Limit

| Method | Budget | Runs | Joint Root-Cause Acc | Supported Rate | Honest Inconclusive | Avg Budget Used |
|---|---:|---:|---:|---:|---:|---:|
| `deterministic_checklist_v1` | `6` | 4 | 0.00% | 0.00% | 100.00% | 6.00 |
| `deterministic_checklist_v1` | `8` | 4 | 0.00% | 0.00% | 100.00% | 8.00 |
| `improved_checklist_v1` | `6` | 4 | 100.00% | 100.00% | 0.00% | 6.00 |
| `improved_checklist_v1` | `8` | 4 | 100.00% | 100.00% | 0.00% | 8.00 |
| `mock_ai_offline_v1` | `6` | 4 | 100.00% | 100.00% | 0.00% | 2.00 |
| `mock_ai_offline_v1` | `8` | 4 | 100.00% | 100.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `6` | 4 | 100.00% | 100.00% | 0.00% | 2.00 |
| `rule_adaptive_v1` | `8` | 4 | 100.00% | 100.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `6` | 4 | 100.00% | 100.00% | 0.00% | 2.00 |
| `scored_adaptive_v2` | `8` | 4 | 100.00% | 100.00% | 0.00% | 2.00 |

## 6. Per-Run Score Table

| Run ID | App | Scenario | Split | Cond | Method | Budget (Used/Lim) | Checks | Outcome | Class | Predicted Causes | Expected Causes | Joint Acc | Set Prec/Rec |
|---|---|---|---|---|---|---:|---:|---|---|---|---|---|---|
| `run-unknown_order_currency_rounding_crash-e0-b6-det_checklist-r1-cb099e` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `deterministic_checklist_v1` | 6/6 | 5 | `inconclusive` | `budget_exhaustion` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e0-b6-improved_checklist-r1-8207cf` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `improved_checklist_v1` | 6/6 | 5 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b6-rule_adaptive-r1-70532d` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `rule_adaptive_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b6-scored_adaptive_v2-r1-5b9325` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `scored_adaptive_v2` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b6-mock_ai_offline-r1-1ad6ce` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `mock_ai_offline_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b8-improved_checklist-r1-6b9fb8` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `improved_checklist_v1` | 8/8 | 6 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b8-rule_adaptive-r1-18be35` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `rule_adaptive_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b8-scored_adaptive_v2-r1-b82379` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `scored_adaptive_v2` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b8-mock_ai_offline-r1-045f0f` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `mock_ai_offline_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e0-b8-det_checklist-r1-805ab2` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E0` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `budget_exhaustion` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e1-b6-rule_adaptive-r1-178da6` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `rule_adaptive_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b6-scored_adaptive_v2-r1-95c125` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `scored_adaptive_v2` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b6-mock_ai_offline-r1-33ebd3` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `mock_ai_offline_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b6-det_checklist-r1-9be6ed` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `deterministic_checklist_v1` | 6/6 | 5 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e1-b6-improved_checklist-r1-88f9bb` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `improved_checklist_v1` | 6/6 | 5 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b8-scored_adaptive_v2-r1-efa221` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `scored_adaptive_v2` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b8-mock_ai_offline-r1-3ff3d5` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `mock_ai_offline_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b8-det_checklist-r1-ae6fc1` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e1-b8-improved_checklist-r1-ecbe4e` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `improved_checklist_v1` | 8/8 | 6 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e1-b8-rule_adaptive-r1-e76da5` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E1` | `rule_adaptive_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b6-mock_ai_offline-r1-f72d8b` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `mock_ai_offline_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b6-det_checklist-r1-f9480b` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `deterministic_checklist_v1` | 6/6 | 5 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e2-b6-improved_checklist-r1-1adbba` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `improved_checklist_v1` | 6/6 | 5 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b6-rule_adaptive-r1-7912bb` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `rule_adaptive_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b6-scored_adaptive_v2-r1-3d4209` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `scored_adaptive_v2` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b8-det_checklist-r1-edb323` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e2-b8-improved_checklist-r1-3be6c5` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `improved_checklist_v1` | 8/8 | 6 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b8-rule_adaptive-r1-c62e4a` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `rule_adaptive_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b8-scored_adaptive_v2-r1-3448af` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `scored_adaptive_v2` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e2-b8-mock_ai_offline-r1-d5e69a` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E2` | `mock_ai_offline_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b6-improved_checklist-r1-3671c9` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `improved_checklist_v1` | 6/6 | 5 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b6-rule_adaptive-r1-480482` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `rule_adaptive_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b6-scored_adaptive_v2-r1-3947e9` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `scored_adaptive_v2` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b6-mock_ai_offline-r1-0fe77e` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `mock_ai_offline_v1` | 2/6 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b6-det_checklist-r1-64669c` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `deterministic_checklist_v1` | 6/6 | 5 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e3-b8-rule_adaptive-r1-bc6d15` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `rule_adaptive_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b8-scored_adaptive_v2-r1-6b2394` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `scored_adaptive_v2` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b8-mock_ai_offline-r1-6a057b` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `mock_ai_offline_v1` | 2/8 | 2 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
| `run-unknown_order_currency_rounding_crash-e3-b8-det_checklist-r1-a2d3d3` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `deterministic_checklist_v1` | 8/8 | 6 | `inconclusive` | `honest_inconclusive` | `None:None` | `unknown_cause` | `False` | 0.00/0.00 |
| `run-unknown_order_currency_rounding_crash-e3-b8-improved_checklist-r1-45dc8a` | `orders_app` | `unknown_order_currency_rounding_crash` | `reserved_eval` | `E3` | `improved_checklist_v1` | 8/8 | 6 | `unknown_cause` | `unknown_cause` | `unknown_cause` | `unknown_cause` | `True` | 1.00/1.00 |
