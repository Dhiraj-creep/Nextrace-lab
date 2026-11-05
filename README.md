# NexTrace — Multi-Application Evidence-Based Root Cause Diagnosis Lab

**Aavishkar Engineering & Technology Research Prototype (`v0.4.0`)**  
**Team**: Dhiraj (Project Leader), Vidhi, Rekha, Pooja, and Mahenoor  
**Areas**: Artificial Intelligence, Software Engineering, Cloud Computing, and Distributed Systems  
**Frozen Protocol**: [`artifacts/protocols/v0.4.0_frozen_protocol.json`](file:///D:/Avishkar%20Nextrace/nextrace/artifacts/protocols/v0.4.0_frozen_protocol.json)  
**Cryptographic Source Content Manifest Digest (SHA-256)**: `857542095a090c6fb040654dd4fbe8f0f5e345131d367f62b931c1817fe493de`  

---

## 1. Research Question & Scope

**NexTrace** investigates whether choosing diagnostic checks by their estimated ability to distinguish remaining candidate explanations relative to their cost (`scored_adaptive_v2`) improves root-cause diagnosis accuracy, supported diagnosis coverage, or diagnostic budget efficiency compared with fixed checklists (including fair early-stopping checklists) and rule-based selectors under limited budgets and incomplete, stale, or changing monitoring evidence.

Team research, scenario-design, and evaluation contributions have been reconciled with the repository in [Team Deliverables Integration](docs/TEAM_DELIVERABLES_INTEGRATION.md). The frozen protocol and implemented catalogue remain the source of truth for runtime identifiers and experiment claims.

> **Research Integrity Statement**:
> - This repository is an **experimental research prototype and controlled benchmark environment**. It is not a production monitoring platform, nor do we claim prior proof that any adaptive or AI-guided method universally dominates well-ordered domain checklists.
> - Every diagnostic method executes through the **exact same controlled `DiagnosticInterface`**, updates the same hypothesis state representation (`nextrace_lab/hypotheses.py`), and is governed by the **same Evidence Sufficiency Gate** (`nextrace_lab/evidence_gate.py`).
> - Offline mock AI adapter runs (`--ai-provider mock-deterministic`) are strictly for pipeline/schema verification and are explicitly labeled `is_mock_ai: true` (`mock_pipeline_verification_only`), never presented as real LLM benchmarks.

---

## 2. Two-Application Architecture

### Application 1: `orders_app` (Primary Application)
1. **Gateway Service (`services/gateway/app.py`)** — FastAPI HTTP entry point (`POST /orders`, `GET /orders/{order_id}`, `GET /health/live`, `GET /health/ready`, `GET /internal/metrics`) on `127.0.0.1:18000`.
2. **Order Service (`services/order_service/app.py`)** — FastAPI downstream service (`POST /orders`, `GET /health/live`, `GET /health/ready`, `GET /internal/diagnostics/db-config`, `GET /internal/diagnostics/db-connectivity`, `GET /internal/metrics`) on `127.0.0.1:18001`.
3. **Database Service (`nextrace_lab/local_db_server.py` / PostgreSQL)** — Persistent storage on `127.0.0.1:15432` (`local_sqlite_tcp` when Docker is absent; `docker_postgresql` when Docker is available).

### Application 2: `inventory_app` (Second Application for Generalization Evaluation)
1. **Inventory API (`services/inventory_app/api_app.py`)** — FastAPI entry point (`POST /inventory/reserve`, `GET /health/live`, `GET /health/ready`, `GET /internal/metrics`) on `127.0.0.1:18010`.
2. **Inventory Service (`services/inventory_app/inventory_service_app.py`)** — FastAPI core service on `127.0.0.1:18011` coordinating stock reservation across both a database and a reservation cache. Supports dual backends: local TCP substitute (`local_sqlite_tcp_and_local_tcp_cache_substitute`) and containerized PostgreSQL 16 + Redis 7 (`docker_postgresql_and_redis_cache` with RESP protocol).
3. **Inventory Database (`127.0.0.1:15433`)** — SQLite-over-TCP database (`var/data/inventory.sqlite3`) or containerized PostgreSQL (`inventory-db`).
4. **Inventory Cache (`nextrace_lab/local_cache_server.py`, `127.0.0.1:16379`)** — Stateful TCP key-value cache daemon or containerized Redis (`inventory-cache`).

---

## 3. Controlled Scenarios Across Six Splits (23 Scenarios Total)

| Split | App | Scenario | Expected Service | Expected Fault Type / Cause Set |
|---|---|---|---|---|
| `development` | `orders_app` | `healthy` | `None` | `[]` (`no_fault_found`) |
| `development` | `orders_app` | `fault_a` | `order-service` | `["order-service:db_endpoint_misconfiguration"]` |
| `development` | `orders_app` | `fault_b` | `database` | `["database:db_service_unavailable"]` |
| `held_out` | `orders_app` | `fault_c` | `order-service` | `["order-service:db_auth_failure"]` |
| `held_out` | `orders_app` | `fault_d` | `database` | `["database:db_schema_missing_table"]` (disposable schema) |
| `held_out` | `orders_app` | `fault_e` | `database` | `["database:db_operation_delay"]` (`1800ms > 1000ms` timeout) |
| `held_out` | `orders_app` | `fault_f` | `order-service` | `["order-service:order_service_unavailable"]` |
| `stress_challenging` | `orders_app` | `challenging_recovery_mid_run` | `order-service` | Window cause: `order-service:db_endpoint_misconfiguration`; recovers after step #1 to `current_health_status="healthy_now"` |
| `stress_challenging` | `orders_app` | `challenging_diag_endpoint_failure` | `None` | `[]` (`no_fault_found`); diagnostic DB-config endpoint fails (HTTP 500) while user traffic is healthy |
| `stress_challenging` | `orders_app` | `challenging_historical_logs_healthy_now` | `None` | `[]` (`no_fault_found`); 15m-old historical error logs exist while current live probes are healthy |
| `stress_challenging` | `orders_app` | `challenging_unknown_app_error` | `None` | `["unknown_cause"]` (`DiagnosticOutcome.UNKNOWN_CAUSE`); unmodeled serialization bug while all dependencies are healthy |
| `stress_challenging` | `orders_app` | `unknown_order_validation_contract_error` | `None` | `["unknown_cause"]`; unmodeled payload validator crash while dependencies are healthy |
| `multi_fault` | `orders_app` | `multi_fault_a_and_b` | `order-service+database` | `["database:db_service_unavailable", "order-service:db_endpoint_misconfiguration"]` |
| `multi_fault` | `orders_app` | `multi_fault_c_and_d` | `order-service+database` | `["database:db_schema_missing_table", "order-service:db_auth_failure"]` |
| `multi_fault` | `orders_app` | `multi_fault_f_masks_b` | `order-service+database` | `["database:db_service_unavailable", "order-service:order_service_unavailable"]` (Masking fault) |
| `second_app` | `inventory_app` | `inv_healthy` | `None` | `[]` (`no_fault_found`) |
| `second_app` | `inventory_app` | `inv_fault_db_unavailable` | `inventory-db` | `["inventory-db:db_service_unavailable"]` |
| `second_app` | `inventory_app` | `inv_fault_cache_unavailable` | `inventory-cache` | `["inventory-cache:cache_service_unavailable"]` |
| `second_app` | `inventory_app` | `inv_fault_bad_db_config` | `inventory-service` | `["inventory-service:db_endpoint_misconfiguration"]` |
| `second_app` | `inventory_app` | `inv_fault_upstream_timeout` | `inventory-db` | `["inventory-db:db_operation_delay"]` |
| `second_app` | `inventory_app` | `inv_unknown_sku_parser_exception` | `None` | `["unknown_cause"]`; unmodeled SKU parser crash |
| `second_app` | `inventory_app` | `inv_multi_fault_db_and_cache` | `inventory-db+inventory-cache` | `["inventory-cache:cache_service_unavailable", "inventory-db:db_service_unavailable"]` |
| `reserved_eval` | `orders_app` | `unknown_order_currency_rounding_crash` | `None` | `["unknown_cause"]`; reserved evaluation fixture for unseen arithmetic crash |

---

## 4. Diagnostic Check Catalog & Evidence Conditions (`E0`–`E5`)

| Check Name | Cost | Source Type | Freshness TTL | Description |
|---|---:|---|---:|---|
| `get_recent_logs(service, limit)` | `1` | `historical_log` | `60s` | Retrieve recent sanitized JSONL log entries |
| `get_service_health(service)` | `1` | `live_probe` | `30s` | Liveness and readiness check (`gateway`, `order-service`, `database`, `inventory-*`) |
| `get_service_metrics(service)` | `1` | `metric_window` | `20s` | Request count, error rate, dependency failures/timeouts, latency (`sample_sufficient >= 2`) |
| `check_database_connectivity_from_order_service()` | `2` | `live_probe` | `30s` | Active DB connectivity probe from `order-service` |
| `get_order_service_database_config()` | `2` | `config_snapshot` | `45s` | Sanitized DB connection configuration on `order-service` |
| `check_inventory_db_connectivity()` | `2` | `live_probe` | `30s` | Active DB probe from `inventory-service` |
| `check_inventory_cache_connectivity()` | `2` | `live_probe` | `30s` | Active cache probe from `inventory-service` |
| `get_inventory_service_config()` | `2` | `config_snapshot` | `45s` | Sanitized DB and cache config on `inventory-service` |

### Evidence Conditions (Attempt-Charged Model: `attempt_charged_v2`)
Under `attempt_charged_v2`, admitted checks consume catalog cost units even if blocked by policy:
- **`E0`**: Full observability.
- **`E1`**: `order-service` / `inventory-service` logs blocked by policy.
- **`E2`**: Active DB connectivity probe blocked by policy.
- **`E3`**: Service logs AND database config inspection blocked by policy.
- **`E4` (`E4_METRICS_UNAVAILABLE`)**: `get_service_metrics` blocked by policy.
- **`E5` (`E5_METRICS_STALE`)**: `get_service_metrics` returns a stale snapshot (`is_stale=True`, `600s` old) below the minimum sample threshold (`sample_sufficient=False`).

---

## 5. CLI Commands (Windows PowerShell)

```powershell
cd "D:\Avishkar Nextrace\nextrace"
$env:PYTHONPATH="."

# 1. Start healthy environments (orders_app and inventory_app)
python -m nextrace_lab start --app orders_app
python -m nextrace_lab start --app inventory_app

# 2. Check cross-process LabExecutionLock status
python -m nextrace_lab lock-status

# 3. Verify healthy order creation and direct database persistence
python -m nextrace_lab verify-healthy

# 4. Inject a fault or challenging scenario and run the scored adaptive selector
python -m nextrace_lab inject-fault multi_fault_a_and_b
python -m nextrace_lab diagnose --evidence E0 --budget 8 --method scored_adaptive_v2
python -m nextrace_lab reset-faults

# 5. Launch local Streamlit research dashboard
python -m nextrace_lab dashboard --port 8501

# 6. Run automated test suites
python -m pytest tests/test_unit.py
python -m pytest tests/test_integration.py
```

---

## 6. Project Documentation & Research Artifacts

- **Team Deliverables Integration**: [`docs/TEAM_DELIVERABLES_INTEGRATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/TEAM_DELIVERABLES_INTEGRATION.md)
- **Frozen Protocol**: [`artifacts/protocols/v0.4.0_frozen_protocol.json`](file:///D:/Avishkar%20Nextrace/nextrace/artifacts/protocols/v0.4.0_frozen_protocol.json)
- **Technical Specification**: [`docs/SPECIFICATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/SPECIFICATION.md)
- **Evaluation Protocol**: [`docs/EVALUATION_PROTOCOL.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/EVALUATION_PROTOCOL.md)
- **Verification & Experimental Report**: [`docs/VERIFICATION_REPORT.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/VERIFICATION_REPORT.md)
- **Milestone Checklist**: [`docs/MILESTONE_CHECKLIST.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/MILESTONE_CHECKLIST.md)
- **Historical & Validated Experiments**: [`artifacts/experiments/`](file:///D:/Avishkar%20Nextrace/nextrace/artifacts/experiments/)

### Docker Fault Scenarios Validation

- **Orders Subsystem**:
  - Fault A (Bad DB Endpoint): [`docs/ORDERS_DOCKER_FAULT_A_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_A_VALIDATION.md)
  - Fault B (PostgreSQL Outage): [`docs/ORDERS_DOCKER_FAULT_B_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_B_VALIDATION.md)
  - Fault C (DB Auth Failure): [`docs/ORDERS_DOCKER_FAULT_C_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_C_VALIDATION.md)
  - Fault D (Missing Orders Table): [`docs/ORDERS_DOCKER_FAULT_D_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_D_VALIDATION.md)
  - Fault E (DB Delay / Timeout): [`docs/ORDERS_DOCKER_FAULT_E_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_E_VALIDATION.md)
  - Fault F (Order Service Outage): [`docs/ORDERS_DOCKER_FAULT_F_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/ORDERS_DOCKER_FAULT_F_VALIDATION.md)
- **Inventory Subsystem**:
  - PostgreSQL & Redis Backend Integration: [`docs/INVENTORY_DOCKER_POSTGRES_REDIS_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_POSTGRES_REDIS_VALIDATION.md)
  - Database Outage: [`docs/INVENTORY_DOCKER_FAULT_DB_UNAVAILABLE_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_DB_UNAVAILABLE_VALIDATION.md)
  - Cache Outage: [`docs/INVENTORY_DOCKER_FAULT_CACHE_UNAVAILABLE_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_CACHE_UNAVAILABLE_VALIDATION.md)
  - Bad DB Configuration: [`docs/INVENTORY_DOCKER_FAULT_BAD_DB_CONFIG_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_BAD_DB_CONFIG_VALIDATION.md)
  - Upstream DB Delay / Timeout: [`docs/INVENTORY_DOCKER_FAULT_UPSTREAM_TIMEOUT_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_FAULT_UPSTREAM_TIMEOUT_VALIDATION.md)
  - Multi-Fault (DB and Cache Outage): [`docs/INVENTORY_DOCKER_MULTI_FAULT_DB_AND_CACHE_VALIDATION.md`](file:///D:/Avishkar%20Nextrace/nextrace/docs/INVENTORY_DOCKER_MULTI_FAULT_DB_AND_CACHE_VALIDATION.md)
