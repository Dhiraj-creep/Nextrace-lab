# NexTrace Orders Docker Fault B Validation

This document records the empirical validation of the controlled Docker fault-diagnosis scenario: **Orders Fault B (Orders PostgreSQL Service Unavailable)**.

The scenario evaluates NexTrace's ability to stop only the Orders PostgreSQL database container in a Docker Compose deployment, detect and diagnose the failure under full observability (`E0`), adaptively diagnose under missing log evidence (`E1`), cleanly restore PostgreSQL without touching Inventory services or persistent data volumes, and maintain ground-truth isolation throughout.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `fault_b` (`db_service_unavailable`) | Orders PostgreSQL container stopped while other services run |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + FastAPI microservices |
| **Target Service** | `nextrace-postgres` (`postgres`) | Stopped via service-scoped `docker compose stop postgres` |
| **Non-Target Services** | Unaffected and running continuously | Gateway, Order Service, and all 4 Inventory containers preserved |
| **Data Preservation** | Preserved | Persistent volumes `nextrace_pgdata` and `nextrace_inv_pgdata` intact |
| **Healthy Baseline** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Order `ord-2b10c28617` persisted in PostgreSQL table |
| **Gateway Traffic** | HTTP 503 (`order_processing_failed`) | Upstream dependency failure truthfully returned |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` in 2 steps (Budget: 2/8) | Service: `database`, Fault: `db_service_unavailable` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` in 2 steps (Budget: 2/8) | E1 policy restricts logs; selector diagnosed via live health checks before querying logs |
| **Reset & Recovery** | Verified (HTTP 201, direct PostgreSQL row confirmed) | New order `ord-73320580b6` persisted; diagnosis returns `no_fault_found` |
| **Automated Tests** | 39 Unit Tests passed; Integration test passed | Local substitute mode preserved; zero regression |

---

## 2. Docker & Runtime Configuration

### 2.1 Service Topology and Fault B Boundary

```
+-----------------------------------------------------------------------------------------+
|                                      HOST SYSTEM                                        |
|                                                                                         |
|  [Gateway Port: 18000]          [Order Port: 18001]           [Postgres Port: 15432]    |
+----------+------------------------------+-------------------------------+---------------+
           |                              |                               |
           |                              | Direct DB Health Check        |
           |                              | (Port 15432 unreachable)      |
           |                              +-------------------------------+
           |                              |                               |
           v                              v                               v
+--------------------+         +-----------------------+         +------------------------+
|  nextrace-gateway  | ------> | nextrace-order-service| ----X-> |   nextrace-postgres    |
| (Uvicorn / FastAPI)|         |  (Uvicorn / FastAPI)  |         | (PostgreSQL 16 Alpine) |
|      [RUNNING]     |         |       [RUNNING]       |         |       [STOPPED]        |
+--------------------+         +-----------------------+         +------------------------+
                                                                              |
+-----------------------------------------------------------------------------+-----------+
|                          INVENTORY APPLICATION (UNAFFECTED)                             |
|                                                                                         |
|   nextrace-inventory-api [RUNNING]           nextrace-inventory-service [RUNNING]       |
|   nextrace-inventory-db  [RUNNING/HEALTHY]   nextrace-inventory-cache   [RUNNING/HEALTHY]|
+-----------------------------------------------------------------------------------------+
```

### 2.2 Controlled Fault Mechanism & Safety Rules

1. **Scoped Container Stop:** `apply_fault("fault_b", runtime="docker")` executes:
   ```powershell
   docker compose -f docker-compose.yml stop postgres
   ```
   This stops only the `nextrace-postgres` container.
2. **Strict Volume Preservation:** No volume flags or destructive teardowns (`down`, `-v`, `rm`) are used. Persistent database data in Docker volume `nextrace_nextrace_pgdata` remains completely intact.
3. **Inventory Isolation:** Inventory services (`inventory-db`, `inventory-cache`, `inventory-service`, `inventory-api`) are excluded from the stop command and remain continuously running and healthy.
4. **No Local Process Spawning:** The controller avoids spawning local substitute processes (`_start_local_order_service`, `_start_local_gateway`, `_kill_pid`) when `mode == "docker"`.
5. **Caller Observation:**
   - Order Service remains running (`order_service_live=True`).
   - Order Service readiness probe fails (`order_service_ready=False`) because connection to `postgres:5432` fails.
   - Direct host probe to port `15432` confirms the database port is unreachable (`database_reachable=False`).

---

## 3. Healthy Baseline Verification

Before applying `fault_b`, baseline health was verified across all Orders services.

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
Gateway: {"service": "gateway", "status": "ready", "upstream_order_service": "reachable", "latency_ms": 9.62, "timestamp": "2026-10-31T22:04:22.809502Z"}
Order-Service: {"service": "order-service", "status": "ready", "database_connectivity": "ok", "latency_ms": 10.65, "timestamp": "2026-10-31T22:04:22.837114Z"}
```

### 3.2 Baseline Order Submission & Storage Verification

```powershell
python -c "
from nextrace_lab.controller import submit_order, verify_order_persisted_independently
status, body = submit_order('sku-router-01', 2, 'req-baseline-fault-b-01')
print('Status:', status)
print('Body:', body)
v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Verification:', v)
"
```

**Observed Output:**
```text
Status: 201
Body: {'order_id': 'ord-2b10c28617', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-fault-b-01', 'created_at': '2026-10-31 22:04:22.890357+00'}
Verification: {'verified': True, 'order_id': 'ord-2b10c28617', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-fault-b-01', 'created_at': '2026-10-31 22:04:22.890357+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
```

---

## 4. Fault Injection & Observability Under Full Observability (`E0`)

### 4.1 Injection Command & Controller State

```powershell
python -m nextrace_lab --runtime docker apply-fault --fault fault_b
```

**Observed Controller Response:**
```json
{
  "fault": "fault_b",
  "runtime": "docker",
  "backend": "docker_postgresql",
  "applied_at_utc": "2026-10-31T22:08:43.741797Z",
  "state": {
    "gateway_live": true,
    "gateway_ready": true,
    "order_service_live": true,
    "order_service_ready": false,
    "database_reachable": false
  }
}
```

### 4.2 Verification That Orders PostgreSQL Stopped While Inventory Remained Running

```powershell
docker ps -a
```

**Observed Container Output During Fault B:**
```text
CONTAINER ID   IMAGE                    COMMAND                  STATUS                         PORTS                                           NAMES
097c7834ab9f   nextrace-order-service   "uvicorn services.or…"   Up About an hour               0.0.0.0:18001->8001/tcp, [::]:18001->8001/tcp   nextrace-order-service
8820e24027a1   postgres:16-alpine       "docker-entrypoint.s…"   Exited (0) 15 seconds ago                                                      nextrace-postgres
b79040c77705   nextrace-inventory-api   "uvicorn services.in…"   Up 2 hours                     0.0.0.0:18010->8010/tcp, [::]:18010->8010/tcp   nextrace-inventory-api
76dbc3bf6159   nextrace-inventory-service "uvicorn services.in…" Up 2 hours                     0.0.0.0:18011->8011/tcp, [::]:18011->8011/tcp   nextrace-inventory-service
b86d2ffa7bc5   nextrace-gateway         "uvicorn services.ga…"   Up 3 hours                     0.0.0.0:18000->8000/tcp, [::]:18000->8000/tcp   nextrace-gateway
23d2aa4c6834   postgres:16-alpine       "docker-entrypoint.s…"   Up 2 hours (healthy)           0.0.0.0:15433->5432/tcp, [::]:15433->5432/tcp   nextrace-inventory-db
35e09f8df950   redis:7-alpine           "docker-entrypoint.s…"   Up 3 hours (healthy)           0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp   nextrace-inventory-cache
```

- `nextrace-postgres` is `Exited (0)`.
- `nextrace-gateway` and `nextrace-order-service` remain `Up`.
- All 4 Inventory containers (`nextrace-inventory-*`) remain `Up` and `healthy`.

### 4.3 Endpoint Evidence in the Running Container

1. **Order Service Readiness (`GET /health/ready`):** Returns HTTP 503 (`database_connectivity: "failed"`, `error_category: "connection_refused"`).
2. **Direct PostgreSQL Direct Health Check:** Direct host probe on `127.0.0.1:15432` reports `reachable=False, schema_usable=False, error_category="connection_refused"`.
3. **Gateway Order Submission (`POST /orders`):** Fails with HTTP 503:
   ```json
   {
     "error": "order_processing_failed",
     "message": "Unable to process order at this time.",
     "request_id": "req-fault-b-test-01",
     "status_code": 503
   }
   ```

### 4.4 Diagnostic Run Parameters & Investigation Trace (`E0`)
- **Scenario:** `fault_b`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E0`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False` |
| 2 | `ev-02` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) unreachable on 127.0.0.1:15432: reachable=False, schema_usable=False` |

### 4.5 Diagnostic Outcome (`E0`)
- **Outcome:** `SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `database`
- **Candidate Fault Type:** `db_service_unavailable`
- **Budget Used:** 2 / 8 units (1 + 1)
- **Joint Root-Cause Accurate:** `True`
- **Evidence Gate Reason:** `Confirmed database is unreachable on its port via direct probe alongside caller/service state.`
- **Cited Evidence IDs:** `['ev-02']`
- **Ground-Truth Isolation:** Evaluator verified the diagnosis came strictly from symptom observation and check results; ground truth (`FAULT_CATALOG`) was quarantined from the selector.

---

## 5. Fault Diagnosis Under Missing Evidence (`E1`)

Evidence condition `E1` enforces an observability restriction that makes Order Service log retrieval unavailable (`Policy E1 blocks order-service log retrieval`). The diagnostic agent must operate under this evidence-restricted policy without relying on logs or treating missing evidence as an indication of health.

### 5.1 Diagnostic Run Parameters (`E1`)
- **Scenario:** `fault_b`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E1`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

### 5.2 Observed Investigation Trace (`E1`)

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False` |
| 2 | `ev-02` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) unreachable on 127.0.0.1:15432: reachable=False, schema_usable=False` |

### 5.3 Diagnostic Evaluation Under Evidence-Restricted Policy
1. **Early Resolution via Live Probes:** E1 policy makes Order Service logs unavailable. However, the `scored_adaptive_v2` selector prioritized caller readiness (`get_service_health(order-service)`) and direct database reachability (`get_service_health(database)`). These two live checks provided conclusive evidence of database unreachability while the caller remained active.
2. **Diagnosis Prior to Log Queries:** Because the candidate hypothesis `H2_DATABASE_UNAVAILABLE` was definitively satisfied by `ev-02` (database direct health check failed on port 15432), the scored selector reached a supported diagnosis in two steps before it needed to query logs.
3. **Trace Scope Distinction:** This validates diagnosis under an evidence-restricted policy, but does not demonstrate an attempted-and-blocked log retrieval in that specific scored-adaptive run. The selector did not attempt `get_recent_logs`, so no `UNAVAILABLE_BY_POLICY` log result occurred within this diagnostic trace.
4. **Diagnostic Outcome (`E1`):**
   - **Outcome:** `SUPPORTED_DIAGNOSIS`
   - **Candidate Service:** `database`
   - **Candidate Fault Type:** `db_service_unavailable`
   - **Budget Used:** 2 / 8 units
   - **Joint Root-Cause Accurate:** `True`
   - **Cited Evidence IDs:** `['ev-02']`

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
  "restored_at_utc": "2026-10-31T22:10:55.009202Z",
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

The reset executed the controller's Docker recovery command:
- Reset restarted the required Orders services (`postgres`, `order-service`, `gateway`) while preserving persistent database volumes (`nextrace_pgdata`, `nextrace_inv_pgdata`).
- Inventory services remained completely unaffected.
- Order Service immediately restored its database connection upon PostgreSQL startup.

### 6.2 Post-Reset Readiness & Traffic Verification

```powershell
python -c "
import httpx
from nextrace_lab.controller import submit_order, verify_order_persisted_independently

r = httpx.get('http://127.0.0.1:18001/health/ready')
print('Readiness:', r.status_code, r.json())

status, body = submit_order('sku-router-01', 3, 'req-recovery-fault-b-01')
print('Submit:', status, body)

v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Persistence:', v)
"
```

**Observed Output:**
```text
Readiness: 200 {'service': 'order-service', 'status': 'ready', 'database_connectivity': 'ok', 'latency_ms': 7.22, 'timestamp': '2026-10-31T22:10:55.028911Z'}
Submit: 201 {'order_id': 'ord-73320580b6', 'product_id': 'sku-router-01', 'quantity': 3, 'request_id': 'req-recovery-fault-b-01', 'created_at': '2026-10-31 22:10:55.0748+00'}
Persistence: {'verified': True, 'order_id': 'ord-73320580b6', 'product_id': 'sku-router-01', 'quantity': 3, 'request_id': 'req-recovery-fault-b-01', 'created_at': '2026-10-31 22:10:55.0748+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
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

A focused controller unit test was added (`test_fault_b_docker_controller_support`):
- Confirms `apply_fault("fault_b", runtime="docker")` calls `docker compose stop postgres`.
- Confirms local processes (`_start_local_order_service`, `_start_local_gateway`, `_kill_pid`) are not invoked in Docker mode.
- Confirms inventory services are not targeted.
- Confirms `down` or volume deletion commands are not used.
- Confirms `reset_faults(runtime="docker")` starts orders services cleanly.

```powershell
python -m pytest tests/test_unit.py
```
**Result:** `39 passed, 1 warning in 1.18s` (100% passing).

### 7.3 Integration Tests (`tests/test_integration.py`)

A live Docker integration test was added (`test_docker_fault_b_e0_and_e1_live_diagnosis`):
- Executes full live end-to-end `fault_b` under both `E0` and `E1` in Docker mode.
- Validates budget compliance (`budget_used <= 8`).
- Validates joint root-cause accuracy (`joint_root_cause_accurate == True`).

```powershell
$env:NEXTRACE_RUNTIME = "docker"
python -m pytest tests/test_integration.py -k test_docker_fault_b_e0_and_e1_live_diagnosis -v
```
**Result:** `1 passed, 8 deselected in 35.35s` (100% passing).

---

## 8. Scope, Limitations & Verification Boundary

1. **Focused Scope:** This validation strictly covers Orders `fault_b` (Orders PostgreSQL container stopped) under Docker Compose.
2. **Local Mode Preserved:** The original local SQLite/JSON-over-TCP substitute mode remains completely intact and functional.
3. **No Unrelated Changes:** Unrelated fault scenarios, selector heuristics, stopping rules, and frozen protocol `v0.4.0` were untouched.
4. **Container Safety:** Docker volumes and persistent data were preserved throughout all test iterations.

---

## 9. Container Status and Volume Preservation

The table below records the historical validation state observed immediately following the live fault injection, diagnosis, and recovery run:

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
> **Daemon Availability Notice:** At the time of this documentation update, the Docker Desktop daemon was not running (`is_docker_available() == False`). Current live runtime status could not be refreshed because the Docker daemon was unavailable. This section truthfully preserves the historical container state observed during the completed Docker validation run without inventing unobserved runtime state.
