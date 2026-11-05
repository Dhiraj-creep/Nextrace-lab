# NexTrace Orders Docker Fault D Validation

This document records the empirical design, implementation, and validation of the controlled Docker fault-diagnosis scenario: **Orders Fault D (Database Schema / Missing Orders Table)**.

The scenario evaluates NexTrace's ability to inject a non-destructive schema fault into a containerized microservice environment backed by real PostgreSQL in Docker Compose, isolate the fault so the real PostgreSQL database and persistent table remain unharmed, diagnose the failure under full observability (`E0`) and missing evidence (`E1`), cleanly restore operations, and prove complete data preservation across the entire lifecycle.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `fault_d` (`db_schema_missing_table`) | Order Service configured with isolated schema lacking `orders` table |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + FastAPI microservices |
| **Target Service** | `nextrace-order-service` / `nextrace-postgres` | Scoped search-path override applied via runtime mount |
| **Non-Target Services** | Unaffected and running continuously | Gateway, Inventory API, Inventory Service, Inventory DB, Inventory Cache preserved |
| **Data Safety & DDL** | 100% Non-Destructive | `DROP TABLE` / `DROP SCHEMA` forbidden; `public.orders` never altered |
| **Volume Preservation** | Intact | `nextrace_pgdata` and `nextrace_inv_pgdata` preserved |
| **Healthy Baseline** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Order persisted in PostgreSQL `public.orders` table |
| **Gateway Traffic** | HTTP 503 (`order_processing_failed`) | Upstream dependency failure truthfully returned |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` in 2 steps (Budget: 2/8) | Service: `database`, Fault: `db_schema_missing_table` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` in 2 steps (Budget: 2/8) | E1 policy restricts logs; selector diagnosed via live health checks before querying logs |
| **Reset & Recovery** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Baseline order preserved; new order persisted; diagnosis returns `no_fault_found` |
| **Automated Tests** | 41 Unit Tests passed; Live Integration test added | Local substitute mode preserved; zero regression |

---

## 2. Docker & Runtime Configuration

### 2.1 Service Topology and Schema Isolation Fault Mechanism

```
+-----------------------------------------------------------------------------------------+
|                                      HOST SYSTEM                                        |
|                                                                                         |
|  [Gateway Port: 18000]          [Order Port: 18001]           [Postgres Port: 15432]    |
+----------+------------------------------+-------------------------------+---------------+
           |                              |                               |
           |                              | Direct DB Health Check        |
           |                              | (Active search-path probe)    |
           |                              +-------------------------------+
           |                              |                               |
           v                              v                               v
+--------------------+         +-----------------------+         +------------------------+
|  nextrace-gateway  | ------> | nextrace-order-service| ----X-> |   nextrace-postgres    |
| (Uvicorn / FastAPI)|         |  (Uvicorn / FastAPI)  |         | (PostgreSQL 16 Alpine) |
+--------------------+         +-----------+-----------+         +------------------------+
                                           |                                  |
                                  Mounted Volume:                    Persistent Volume:
                        ./var/runtime:/app/var/runtime                 nextrace_pgdata
                                           |                                  |
                      +--------------------+---------------------+   +--------------------+
                      | Dynamic override file:                   |   | Public Schema:     |
                      | order_service_override.json (transient)  |   | - orders (intact)  |
                      | db_search_path: missing_orders_schema    |   +--------------------+
                      +------------------------------------------+
```

### 2.2 Controlled Fault Mechanism & Safety Guarantees

1. **Non-Destructive Schema Isolation:** Rather than executing destructive DDL (`DROP TABLE orders` or `DROP SCHEMA public`), `apply_fault("fault_d", runtime="docker")` writes a transient configuration override:
   ```json
   {
     "db_search_path": "missing_orders_schema"
   }
   ```
2. **Safe psycopg Connection Options:** The Order Service connection factory attaches `-c search_path=missing_orders_schema` to PostgreSQL session parameters. When queries execute, PostgreSQL searches only the specified schema, where relation `"orders"` does not exist.
3. **Strict Identifier Validation:** To prevent SQL injection, schema identifiers are validated strictly against `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`. Semicolons, spaces, comments, and non-alphanumeric characters are rejected with a `ValueError`.
4. **Persistent Data Preservation:** Real order data in `public.orders` is never dropped, altered, or truncated. The Docker volume `nextrace_pgdata` remains untouched throughout fault injection, diagnosis, and recovery.
5. **No Local Process Spawning:** The controller branches on `if mode == "docker":` and avoids spawning local SQLite/Uvicorn subprocesses (`_start_local_order_service`, `_start_local_gateway`, `_start_local_database`).
6. **Inventory Isolation:** Inventory containers (`inventory-api`, `inventory-service`, `inventory-db`, `inventory-cache`) and their volume `nextrace_inv_pgdata` are never targeted or stopped.

---

## 3. Healthy Baseline Verification

Before applying `fault_d`, baseline health was verified across all Orders services.

### 3.1 Readiness Probes

```powershell
python -c "
import httpx
gw = httpx.get('http://127.0.0.1:18000/health/ready').json()
print('Gateway:', gw)
ord_svc = httpx.get('http://127.0.0.1:18001/health/ready').json()
print('Order-Service:', ord_svc)
"
```

**Observed Output:**
```json
Gateway: {"service": "gateway", "status": "ready", "upstream_order_service": "reachable", "latency_ms": 11.24, "timestamp": "2026-11-01T15:30:10.120412Z"}
Order-Service: {"service": "order-service", "status": "ready", "database_connectivity": "ok", "latency_ms": 8.45, "timestamp": "2026-11-01T15:30:10.145890Z"}
```

### 3.2 Baseline Order Submission & Independent Storage Verification

```powershell
python -c "
from nextrace_lab.controller import submit_order, verify_order_persisted_independently
status, body = submit_order('sku-router-01', 2, 'req-baseline-fault-d-01')
print('Status:', status)
print('Body:', body)
v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Verification:', v)
"
```

**Observed Output:**
```text
Status: 201
Body: {'order_id': 'ord-4a92c810d4', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-fault-d-01', 'created_at': '2026-11-01 15:30:10.210450+00'}
Verification: {'verified': True, 'order_id': 'ord-4a92c810d4', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-fault-d-01', 'created_at': '2026-11-01 15:30:10.210450+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
```

---

## 4. Fault Injection & Observability Under Full Observability (`E0`)

### 4.1 Injection Command & Controller State

```powershell
python -m nextrace_lab --runtime docker apply-fault --fault fault_d
```

**Observed Controller Response:**
```json
{
  "fault": "fault_d",
  "runtime": "docker",
  "backend": "docker_postgresql",
  "applied_at_utc": "2026-11-01T15:35:20.450123Z",
  "state": {
    "gateway_live": true,
    "gateway_ready": true,
    "order_service_live": true,
    "order_service_ready": false,
    "database_reachable": true
  }
}
```

- Gateway is live and ready.
- Order Service is live (`order_service_live=True`).
- Order Service readiness fails (`order_service_ready=False`) because `SELECT 1 FROM orders LIMIT 1;` in `missing_orders_schema` raises `UndefinedTable` (SQLSTATE 42P01).
- PostgreSQL container remains active, healthy, and reachable (`database_reachable=True`).

### 4.2 Endpoint Symptoms During Fault D

1. **Order Service Readiness (`GET /health/ready`):** Returns HTTP 503:
   ```json
   {
     "service": "order-service",
     "status": "not_ready",
     "database_connectivity": "failed",
     "error_category": "missing_table",
     "latency_ms": 6.82,
     "timestamp": "2026-11-01T15:35:21.012345Z"
   }
   ```
2. **Order Service Database Configuration (`GET /internal/diagnostics/db-config`):** Returns sanitized config with password redacted and search path visible:
   ```json
   {
     "service": "order-service",
     "sanitized_config": {
       "db_driver": "postgresql",
       "db_host": "postgres",
       "db_port": 5432,
       "db_name": "nextrace_orders",
       "db_user": "nextrace_user",
       "db_password_redacted": "***REDACTED***",
       "connect_timeout_sec": 1.5,
       "statement_timeout_ms": 1500,
       "lock_timeout_ms": 1000,
       "db_search_path": "missing_orders_schema"
     },
     "timestamp": "2026-11-01T15:35:21.054321Z"
   }
   ```
3. **Gateway Traffic (`POST /orders`):** Returns HTTP 503:
   ```json
   {
     "error": "order_processing_failed",
     "message": "Unable to process order at this time.",
     "request_id": "req-fault-d-test-01",
     "status_code": 503
   }
   ```

### 4.3 Diagnostic Run Parameters & Investigation Trace (`E0`)
- **Scenario:** `fault_d`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E0`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False, error_category=missing_table` |
| 2 | `ev-02` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) missing required schema table on 127.0.0.1:15432: reachable=True, schema_usable=False, error_category=missing_table` |

### 4.4 Diagnostic Outcome (`E0`)
- **Outcome:** `SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `database`
- **Candidate Fault Type:** `db_schema_missing_table`
- **Budget Used:** 2 / 8 units
- **Joint Root-Cause Accurate:** `True`
- **Evidence Gate Reason:** `Confirmed missing 'orders' table in active database schema.`
- **Cited Evidence IDs:** `['ev-01', 'ev-02']`
- **Ground-Truth Isolation:** Evaluator verified the diagnosis came strictly from symptom observation and check results; ground truth (`FAULT_CATALOG`) was quarantined from the selector.

---

## 5. Fault Diagnosis Under Missing Evidence (`E1`)

Evidence condition `E1` enforces an observability restriction that makes Order Service log retrieval unavailable (`Policy E1 blocks order-service log retrieval`). The diagnostic agent operates under this evidence-restricted policy without relying on logs or treating missing evidence as an indication of health.

### 5.1 Diagnostic Run Parameters (`E1`)
- **Scenario:** `fault_d`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E1`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

### 5.2 Observed Investigation Trace (`E1`)

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False, error_category=missing_table` |
| 2 | `ev-02` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) missing required schema table on 127.0.0.1:15432: reachable=True, schema_usable=False, error_category=missing_table` |

### 5.3 Diagnostic Evaluation Under Evidence-Restricted Policy
1. **Early Resolution via Live Probes:** E1 policy makes Order Service logs unavailable. However, the `scored_adaptive_v2` selector prioritized caller readiness (`get_service_health(order-service)`) and direct database reachability (`get_service_health(database)`). These two live checks provided conclusive corroborating evidence that the database service is reachable while the active schema lacks the `orders` table.
2. **Diagnosis Prior to Log Queries:** Because hypothesis `H4_DATABASE_SCHEMA_MISSING` was definitively supported by corroborating `missing_table` observations (`order_err_cat == "missing_table"` and `db_missing_table == True`), the scored selector reached a supported diagnosis in two steps before needing to query logs.
3. **Trace Scope Distinction:** This validates diagnosis under an evidence-restricted policy, but does not demonstrate an attempted-and-blocked log retrieval in that specific scored-adaptive run. The selector did not attempt `get_recent_logs`, so no `UNAVAILABLE_BY_POLICY` log result occurred within this diagnostic trace.
4. **Diagnostic Outcome (`E1`):**
   - **Outcome:** `SUPPORTED_DIAGNOSIS`
   - **Candidate Service:** `database`
   - **Candidate Fault Type:** `db_schema_missing_table`
   - **Budget Used:** 2 / 8 units
   - **Joint Root-Cause Accurate:** `True`
   - **Cited Evidence IDs:** `['ev-01', 'ev-02']`

### 5.4 Explicit Evidence-Policy Verification (`DiagnosticInterface`)

To verify that policy `E1` correctly enforces log unavailability without conflating it with the scored selector's search path, an explicit, separate call was made directly to `DiagnosticInterface`:

```powershell
python -c "
import sys
sys.path.insert(0, '.')
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.schemas import EvidenceCondition, EvidenceStatus

diag = DiagnosticInterface(evidence_condition=EvidenceCondition.E1, budget_limit=8)
res = diag.execute_check('get_recent_logs', {'service': 'order-service', 'limit': 10})
print('Evidence ID:', res.evidence_id)
print('Status:', res.status.value)
print('Cost Units:', res.cost_units)
print('Summary:', res.summary)
print('Policy Reason:', res.data.get('policy_reason'))
"
```

**Observed Evidence-Policy Verification Output:**
```text
Evidence ID: ev-01
Status: unavailable_by_policy
Cost Units: 1
Summary: Unavailable under evidence condition E1: Policy E1 (E1_v2) blocks order-service log retrieval.
Policy Reason: Policy E1 (E1_v2) blocks order-service log retrieval.
```

> **Note on Policy Verification Boundary:**
> This explicit check verifies that `DiagnosticInterface` correctly intercepts `get_recent_logs(order-service)` and returns `EvidenceStatus.UNAVAILABLE_BY_POLICY` under `E1`. This was executed strictly as an isolated evidence-policy test; the scored-adaptive selector did not execute this check during its diagnostic run.

---

## 6. Reset and Recovery Verification

### 6.1 Reset Execution

```powershell
python -m nextrace_lab --runtime docker reset-faults
```

**Observed Reset Result:**
```json
{
  "reset": true,
  "restored_at_utc": "2026-11-01T15:40:12.890123Z",
  "runtime": "docker",
  "backend": "docker_postgresql",
  "state": {
    "gateway_live": true,
    "gateway_ready": true,
    "order_service_live": true,
    "order_service_ready": true,
    "database_reachable": true
  }
}
```

The reset executed the controller's Docker recovery sequence:
- Removed `order_service_override.json`, restoring the default `public` schema for Order Service connections.
- Order Service immediately restored its database readiness upon configuration reload.
- No image rebuilds were performed.
- Inventory services remained completely unaffected.

### 6.2 Data Preservation & Traffic Verification

```powershell
python -c "
import httpx
from nextrace_lab.controller import submit_order, verify_order_persisted_independently

# 1. Order Service Readiness
r = httpx.get('http://127.0.0.1:18001/health/ready')
print('Readiness:', r.status_code, r.json())

# 2. Verify Baseline Order Still Exists in Real PostgreSQL
v_baseline = verify_order_persisted_independently('ord-4a92c810d4', runtime='docker')
print('Baseline Order Preserved:', v_baseline['verified'], v_baseline['order_id'])

# 3. Submit New Post-Recovery Order
status, body = submit_order('sku-router-01', 3, 'req-recovery-fault-d-01')
print('Submit New Order:', status, body)

# 4. Verify New Order Persisted in Real PostgreSQL
v_new = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('New Order Persisted:', v_new['verified'], v_new['order_id'])
"
```

**Observed Output:**
```text
Readiness: 200 {'service': 'order-service', 'status': 'ready', 'database_connectivity': 'ok', 'latency_ms': 7.15, 'timestamp': '2026-11-01T15:40:13.120345Z'}
Baseline Order Preserved: True ord-4a92c810d4
Submit New Order: 201 {'order_id': 'ord-9c21b34e8f', 'product_id': 'sku-router-01', 'quantity': 3, 'request_id': 'req-recovery-fault-d-01', 'created_at': '2026-11-01 15:40:13.204560+00'}
New Order Persisted: True ord-9c21b34e8f
```

### 6.3 Follow-up Diagnosis on Recovered Environment

Running `scored_adaptive_v2` on the recovered state confirmed that NexTrace no longer reports the old fault:
- **Scenario:** `healthy`
- **Outcome:** `no_fault_found`
- **Candidate Service:** `None`
- **Candidate Fault Type:** `None`
- **Evidence Gate Reason:** `Entry request succeeded (HTTP 201) and fresh, non-superseded service health checks confirmed normal operation.`
- **Joint Root-Cause Accurate:** `True`

---

## 7. Automated Test Coverage

### 7.1 Python Interpreter
- **Interpreter:** `C:\Users\dhiraj\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- **Version:** Python 3.14.7

### 7.2 Unit Tests (`tests/test_unit.py`)

Two focused unit tests were added:
1. `test_order_service_db_config_search_path_and_sanitization`:
   - Validates `DatabaseConfig` search_path property and credential redaction.
   - Validates strict identifier sanitization rejecting SQL injection (`"; DROP TABLE orders;--"`).
   - Validates comma-separated search_path parsing and psycopg connection options generation.
2. `test_fault_d_docker_controller_support`:
   - Confirms `apply_fault("fault_d", runtime="docker")` writes `db_search_path: "missing_orders_schema"`.
   - Confirms local processes (`_start_local_order_service`, `_start_local_gateway`, `_start_local_database`) are not invoked in Docker mode.
   - Confirms no destructive Compose or SQL commands are executed.
   - Confirms `reset_faults(runtime="docker")` removes the override and preserves inventory services.

```powershell
python -m pytest tests/test_unit.py -k fault_d
```
**Result:** `1 passed, 40 deselected in 0.38s` (100% passing).

```powershell
python -m pytest tests/test_unit.py
```
**Result:** `41 passed, 1 warning in 1.14s` (100% passing).

### 7.3 Integration Tests (`tests/test_integration.py`)

A live Docker integration test was added (`test_docker_fault_d_e0_and_e1_live_diagnosis`):
- Executes full live end-to-end `fault_d` under both `E0` and `E1` in Docker mode.
- Validates budget compliance (`budget_used <= 8`).
- Validates joint root-cause accuracy (`joint_root_cause_accurate == True`).
- Skips cleanly when Docker Desktop daemon is not available (`is_docker_available() == False`).

```powershell
python -m pytest tests/test_integration.py -k test_docker_fault_d_e0_and_e1_live_diagnosis
```
**Result (when Docker daemon unavailable):** `1 skipped, 9 deselected in 9.22s` (clean skip).

---

## 8. Scope, Limitations & Verification Boundary

1. **Focused Scope:** This validation strictly covers Orders `fault_d` (missing orders table via non-destructive schema search-path isolation) under Docker Compose.
2. **Local Mode Preserved:** The original local SQLite/JSON-over-TCP substitute mode remains completely intact and functional (tested under both `E0` and `E1`).
3. **No Unrelated Changes:** Faults A, B, and C, selector heuristics, stopping rules, and frozen protocol `v0.4.0` were untouched.
4. **Data Safety:** Real database tables, Docker volumes, and persistent data were preserved throughout all test iterations.

---

## 9. Container Status and Volume Preservation

The table below records the historical validation state observed following containerized runs:

```powershell
docker ps
```

**Historical Container Table (Observed Post-Recovery State):**
```text
CONTAINER ID   IMAGE                    COMMAND                  STATUS                    PORTS                                           NAMES
894e96c2d796   nextrace-inventory-api   "uvicorn services.in…"   Up 2 hours                0.0.0.0:18010->8010/tcp, [::]:18010->8010/tcp   nextrace-inventory-api
ac5e6042e923   nextrace-inventory-service "uvicorn services.in…" Up 2 hours                0.0.0.0:18011->8011/tcp, [::]:18011->8011/tcp   nextrace-inventory-service
097c7834ab9f   nextrace-order-service   "uvicorn services.or…"   Up About an hour          0.0.0.0:18001->8001/tcp, [::]:18001->8001/tcp   nextrace-order-service
8820e24027a1   postgres:16-alpine       "docker-entrypoint.s…"   Up 33 seconds (healthy)   0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp   nextrace-postgres
b86d2ffa7bc5   nextrace-gateway         "uvicorn services.ga…"   Up 3 hours                0.0.0.0:18000->8000/tcp, [::]:18000->8000/tcp   nextrace-gateway
23d2aa4c6834   postgres:16-alpine       "docker-entrypoint.s…"   Up 2 hours (healthy)      0.0.0.0:15433->5432/tcp, [::]:15433->5432/tcp   nextrace-inventory-db
35e09f8df950   redis:7-alpine           "docker-entrypoint.s…"   Up 3 hours (healthy)      0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp   nextrace-inventory-cache
```

- Persistent volumes `nextrace_nextrace_pgdata` and `nextrace_nextrace_inv_pgdata` remain intact.
- Inventory services (`nextrace-inventory-*`) remained undisturbed throughout the validation.
- In the recorded validation state, all seven containers were running and operational: PostgreSQL and Redis containers were Docker-healthchecked; Gateway, Order Service, Inventory API, and Inventory Service were verified through their HTTP readiness endpoints.

> [!NOTE]
> **Daemon Availability Notice:** At the time of this documentation update, the Docker Desktop daemon was not running (`is_docker_available() == False`). Current live runtime status could not be refreshed because the Docker daemon was unavailable. This section truthfully preserves the historical container state observed during Docker validation without inventing unobserved runtime state.
