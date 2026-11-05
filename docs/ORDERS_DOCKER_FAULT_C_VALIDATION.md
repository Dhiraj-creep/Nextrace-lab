# NexTrace Orders Docker Fault C Validation

This document records the empirical validation of the controlled Docker fault-diagnosis scenario: **Orders Fault C (Order Service Database Authentication Failure)**.

The scenario evaluates NexTrace's ability to inject a dynamic database authentication failure into a containerized microservice running on Docker Compose with real PostgreSQL, detect and diagnose the failure under full observability (`E0`), adaptively diagnose under missing log evidence (`E1`), cleanly restore healthy operations, and maintain ground-truth isolation throughout.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `fault_c` (`db_auth_failure`) | Order Service configured with invalid database password |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + FastAPI microservices |
| **Container Targets** | `nextrace-order-service`, `nextrace-postgres`, `nextrace-gateway` | Preserves all existing volumes and Inventory services |
| **PostgreSQL State** | Running, healthy, unmodified | PostgreSQL user/password and container remain unchanged |
| **Healthy Baseline** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Order `ord-e0e7aa399a` persisted in PostgreSQL table |
| **Fault Injection** | Dynamically applied via volume override | Password overridden to `wrong_invalid_password_fault_c` |
| **Gateway Traffic** | HTTP 503 (`order_processing_failed`) | Upstream dependency failure truthfully returned |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` in 4 steps (Budget: 5/8) | Service: `order-service`, Fault: `db_auth_failure` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` in 4 steps (Budget: 5/8) | Policy blocks logs; alternative live probes corroborate |
| **Reset & Recovery** | Verified (HTTP 201, direct PostgreSQL row confirmed) | New order `ord-7e721deb69` persisted; diagnosis returns `no_fault_found` |
| **Automated Tests** | 38 Unit Tests passed; Integration test passed | Local substitute mode preserved; zero regression |

---

## 2. Docker & Runtime Configuration

### 2.1 Service Topology and Authentication Fault Mechanism

```
+-----------------------------------------------------------------------------------------+
|                                      HOST SYSTEM                                        |
|                                                                                         |
|  [Gateway Port: 18000]          [Order Port: 18001]           [Postgres Port: 15432]    |
+----------+------------------------------+-------------------------------+---------------+
           |                              |                               |
           |                              | Direct DB Health Check        |
           |                              | (Valid nextrace_user pw)      |
           |                              +-------------------------------+
           |                              |                               |
           v                              v                               v
+--------------------+         +-----------------------+         +------------------------+
|  nextrace-gateway  | ------> | nextrace-order-service| ----X-> |   nextrace-postgres    |
| (Uvicorn / FastAPI)|         |  (Uvicorn / FastAPI)  | (28P01) | (PostgreSQL 16 Alpine) |
+--------------------+         +-----------+-----------+         +------------------------+
                                           |
                                  Mounted Volume:
                        ./var/runtime:/app/var/runtime
                                           |
                      +--------------------+---------------------+
                      | Dynamic override file:                   |
                      | order_service_override.json (ro/transient)|
                      | db_password: wrong_invalid_password...   |
                      +------------------------------------------+
```

### 2.2 Controlled Fault Mechanism & Credential Redaction

1. **Volume Mount:** `order-service` mounts `./var/runtime:/app/var/runtime` and sets `NEXTRACE_ORDER_CONFIG_OVERRIDE_FILE: /app/var/runtime/order_service_override.json`.
2. **Targeted Override:** In Docker mode, `apply_fault("fault_c", runtime="docker")` writes only:
   ```json
   {
     "db_password": "wrong_invalid_password_fault_c"
   }
   ```
   The database host remains `postgres`, port remains `5432`, user remains `nextrace_user`, and database name remains `nextrace_orders`. Real PostgreSQL credentials in `nextrace-postgres` are unchanged.
3. **No Local Process Spawning:** The controller branches on `if mode == "docker":` and avoids spawning local SQLite/Uvicorn subprocesses.
4. **Credential Redaction:** The invalid password is never exposed:
   - `sanitized_dict()` returns `"db_password_redacted": "***REDACTED***"`.
   - Log events record `event="database_write_failed"` with `error_category="authentication_failed"` and user `'nextrace_user'`, omitting the password.
   - Diagnostic probes and exception mappings redact passwords from error details.

---

## 3. Healthy Baseline Verification

Before applying `fault_c`, baseline health was verified across all Orders services.

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
Gateway: {"service": "gateway", "status": "ready", "upstream_order_service": "reachable", "latency_ms": 18.16, "timestamp": "2026-10-31T21:50:39.972719Z"}
Order-Service: {"service": "order-service", "status": "ready", "database_connectivity": "ok", "latency_ms": 8.91, "timestamp": "2026-10-31T21:50:39.997534Z"}
```

### 3.2 Baseline Order Submission & Storage Verification

```powershell
python -c "
from nextrace_lab.controller import submit_order, verify_order_persisted_independently
status, body = submit_order('sku-router-01', 2, 'req-baseline-fault-c-01')
print('Status:', status)
print('Body:', body)
v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Verification:', v)
"
```

**Observed Output:**
```text
Status: 201
Body: {'order_id': 'ord-e0e7aa399a', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-fault-c-01', 'created_at': '2026-10-31 21:50:40.064276+00'}
Verification: {'verified': True, 'order_id': 'ord-e0e7aa399a', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-fault-c-01', 'created_at': '2026-10-31 21:50:40.064276+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
```

---

## 4. Fault Injection & Observability Under Full Observability (`E0`)

### 4.1 Injection Command & Observed Controller State

```powershell
python -m nextrace_lab --runtime docker apply-fault --fault fault_c
```

**Observed Controller Response:**
```json
{
  "fault": "fault_c",
  "runtime": "docker",
  "backend": "docker_postgresql",
  "applied_at_utc": "2026-10-31T21:50:52.195762Z",
  "state": {
    "gateway_live": true,
    "gateway_ready": true,
    "order_service_live": true,
    "order_service_ready": false,
    "database_reachable": true
  }
}
```

### 4.2 Endpoint Evidence in the Running Container

1. **Order Service Readiness (`GET /health/ready`):** Returns HTTP 503:
   ```json
   {
     "service": "order-service",
     "status": "not_ready",
     "database_connectivity": "failed",
     "error_category": "authentication_failed",
     "latency_ms": 6.51,
     "timestamp": "2026-10-31T21:50:52.222116Z"
   }
   ```
2. **Order Service Sanitized Config (`GET /internal/diagnostics/db-config`):** Returns HTTP 200 with password redacted:
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
       "lock_timeout_ms": 1000
     },
     "timestamp": "2026-10-31T21:50:52.270584Z"
   }
   ```
3. **Order Service DB Connectivity Probe (`GET /internal/diagnostics/db-connectivity`):** Returns HTTP 200:
   ```json
   {
     "service": "order-service",
     "probe": {
       "ok": false,
       "configured_host": "postgres",
       "configured_port": 5432,
       "dbname": "nextrace_orders",
       "latency_ms": 5.36,
       "error_category": "authentication_failed",
       "detail": "PostgreSQL authentication failed for user 'nextrace_user' on database 'nextrace_orders'"
     },
     "timestamp": "2026-10-31T21:50:52.294727Z"
   }
   ```
4. **Direct PostgreSQL Direct Health:** PostgreSQL container itself remains reachable and healthy:
   ```text
   PostgreSQL (database) direct health check on 127.0.0.1:15432: reachable=True, schema_usable=True.
   ```
5. **Gateway Order Submission (`POST /orders`):** Fails with HTTP 503:
   ```json
   {
     "error": "order_processing_failed",
     "message": "Unable to process order at this time.",
     "request_id": "req-fault-c-test-01",
     "status_code": 503
   }
   ```

### 4.3 Diagnostic Run Parameters & Investigation Trace (`E0`)
- **Scenario:** `fault_c`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E0`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False, error_category=authentication_failed` |
| 2 | `ev-02` | `get_recent_logs` | `service: order-service, limit: 20` | `available` | 1 | `Retrieved 0 recent log entries for order-service` |
| 3 | `ev-03` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) direct health check on 127.0.0.1:15432: reachable=True, schema_usable=True.` |
| 4 | `ev-04` | `check_database_connectivity_from_order_service` | `{}` | `available` | 2 | `Order-service DB connectivity probe: ok=False, target=postgres:5432, error_category=authentication_failed, latency_ms=5.07` |

### 4.4 Diagnostic Outcome (`E0`)
- **Outcome:** `SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `order-service`
- **Candidate Fault Type:** `db_auth_failure`
- **Budget Used:** 5 / 8 units (1 + 1 + 1 + 2)
- **Joint Root-Cause Accurate:** `True`
- **Evidence Gate Reason:** `Confirmed order-service fails database authentication across corroborating checks.`
- **Cited Evidence IDs:** `['ev-01', 'ev-03', 'ev-04']`
- **Ground-Truth Isolation:** Evaluator verified the diagnosis came strictly from symptom observation and check results; ground truth (`FAULT_CATALOG`) was quarantined from the selector.

---

## 5. Fault Diagnosis Under Missing Evidence (`E1`)

Under evidence condition `E1`, Order Service log retrieval is blocked by policy (`Policy E1 blocks order-service log retrieval`). The diagnostic agent must reach an evidence-supported conclusion through alternative live observability checks without treating blocked logs as evidence of health.

### 5.1 Diagnostic Run Parameters (`E1`)
- **Scenario:** `fault_c`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E1`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

### 5.2 Observed Investigation Trace (`E1`)

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False, error_category=authentication_failed` |
| 2 | `ev-02` | `get_recent_logs` | `service: order-service, limit: 20` | `unavailable_by_policy` | 1 | `Unavailable under evidence condition E1: Policy E1 (E1_v2) blocks order-service log retrieval.` |
| 3 | `ev-03` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) direct health check on 127.0.0.1:15432: reachable=True, schema_usable=True.` |
| 4 | `ev-04` | `check_database_connectivity_from_order_service` | `{}` | `available` | 2 | `Order-service DB connectivity probe: ok=False, target=postgres:5432, error_category=authentication_failed, latency_ms=5.83` |

### 5.3 Handling of Missing Evidence
1. **No Phantom Health Inference:** Step 2 returns `EvidenceStatus.UNAVAILABLE_BY_POLICY`. The evidence gate and hypothesis scorer strictly treat this as missing evidence, never as absence of errors.
2. **Alternative Corroboration:** The selector relies on `get_service_health(order-service)` (`ev-01`, `error_category="authentication_failed"`), `get_service_health(database)` (`ev-03`, `reachable=True`), and `check_database_connectivity_from_order_service` (`ev-04`, `error_category="authentication_failed"`).
3. **Hypothesis Resolution:** This combination satisfies hypothesis `H3_ORDER_DB_AUTH_FAILURE`: the database service is reachable and healthy, but the Order Service credentials fail authentication.
4. **Diagnostic Outcome (`E1`):**
   - **Outcome:** `SUPPORTED_DIAGNOSIS`
   - **Candidate Service:** `order-service`
   - **Candidate Fault Type:** `db_auth_failure`
   - **Budget Used:** 5 / 8 units
   - **Joint Root-Cause Accurate:** `True`
   - **Cited Evidence IDs:** `['ev-01', 'ev-03', 'ev-04']`

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
  "restored_at_utc": "2026-10-31T21:51:36.598293Z",
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

The reset removed `order_service_override.json`. The Order Service immediately restored its default database credentials and re-established valid connections to PostgreSQL.

### 6.2 Post-Reset Readiness & Traffic Verification

```powershell
python -c "
import httpx
from nextrace_lab.controller import submit_order, verify_order_persisted_independently

r = httpx.get('http://127.0.0.1:18001/health/ready')
print('Readiness:', r.status_code, r.json())

status, body = submit_order('sku-router-01', 5, 'req-recovery-fault-c-01')
print('Submit:', status, body)

v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Persistence:', v)
"
```

**Observed Output:**
```text
Readiness: 200 {'service': 'order-service', 'status': 'ready', 'database_connectivity': 'ok', 'latency_ms': 7.96, 'timestamp': '2026-10-31T21:51:36.622245Z'}
Submit: 201 {'order_id': 'ord-7e721deb69', 'product_id': 'sku-router-01', 'quantity': 5, 'request_id': 'req-recovery-fault-c-01', 'created_at': '2026-10-31 21:51:36.697207+00'}
Persistence: {'verified': True, 'order_id': 'ord-7e721deb69', 'product_id': 'sku-router-01', 'quantity': 5, 'request_id': 'req-recovery-fault-c-01', 'created_at': '2026-10-31 21:51:36.697207+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
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

A focused controller unit test was added (`test_fault_c_docker_controller_support`):
- Confirms `apply_fault("fault_c", runtime="docker")` writes dynamic override with `db_password: "wrong_invalid_password_fault_c"`.
- Confirms local processes (`_start_local_database`, `_start_local_gateway`, `_start_local_order_service`) are not started in Docker mode.
- Confirms `load_db_config().sanitized_dict()` strictly redacts passwords to `"***REDACTED***"`.
- Confirms `reset_faults(runtime="docker")` clears the override.

```powershell
python -m pytest tests/test_unit.py
```
**Result:** `38 passed, 1 warning in 1.17s` (100% passing).

### 7.3 Integration Tests (`tests/test_integration.py`)

A live Docker integration test was added (`test_docker_fault_c_e0_and_e1_live_diagnosis`):
- Executes full live end-to-end `fault_c` under both `E0` and `E1` in Docker mode.
- Validates budget compliance (`budget_used <= 8`).
- Validates joint root-cause accuracy (`joint_root_cause_accurate == True`).

```powershell
python -m pytest tests/test_integration.py -k test_docker_fault_c_e0_and_e1_live_diagnosis -v
```
**Result:** `1 passed, 7 deselected in 37.23s` (100% passing).

---

## 8. Scope, Limitations & Verification Boundary

1. **Focused Scope:** This validation strictly covers Orders `fault_c` (Order Service database authentication failure) under Docker Compose with real PostgreSQL.
2. **Local Mode Preserved:** The original local SQLite/JSON-over-TCP substitute mode remains completely intact and functional.
3. **No Unrelated Changes:** Unrelated fault scenarios, selector heuristics, stopping rules, and frozen protocol `v0.4.0` were untouched.
4. **Credential Isolation:** Passwords remain strictly redacted (`***REDACTED***`) across all diagnostic traces, logs, and artifacts.

---

## 9. Container Status and Volume Preservation

All Docker services and persistent database volumes were preserved:

```powershell
docker ps
```

**Observed Container Table:**
```text
CONTAINER ID   IMAGE                        COMMAND                  CREATED          STATUS                    PORTS                                           NAMES
097c7834ab9f   nextrace-order-service       "uvicorn services.or…"   48 minutes ago   Up 48 minutes             0.0.0.0:18001->8001/tcp, [::]:18001->8001/tcp   nextrace-order-service
8820e24027a1   postgres:16-alpine           "docker-entrypoint.s…"   48 minutes ago   Up 48 minutes (healthy)   0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp   nextrace-postgres
b79040c77705   nextrace-inventory-api       "uvicorn services.in…"   2 hours ago      Up 2 hours                0.0.0.0:18010->8010/tcp, [::]:18010->8010/tcp   nextrace-inventory-api
76dbc3bf6159   nextrace-inventory-service   "uvicorn services.in…"   2 hours ago      Up 2 hours                0.0.0.0:18011->8011/tcp, [::]:18011->8011/tcp   nextrace-inventory-service
b86d2ffa7bc5   nextrace-gateway             "uvicorn services.ga…"   3 hours ago      Up 3 hours                0.0.0.0:18000->8000/tcp, [::]:18000->8000/tcp   nextrace-gateway
23d2aa4c6834   postgres:16-alpine           "docker-entrypoint.s…"   3 hours ago      Up 2 hours (healthy)      0.0.0.0:15433->5432/tcp, [::]:15433->5432/tcp   nextrace-inventory-db
35e09f8df950   redis:7-alpine               "docker-entrypoint.s…"   3 hours ago      Up 2 hours (healthy)      0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp   nextrace-inventory-cache
```

- Persistent volumes `nextrace_nextrace_pgdata` and `nextrace_nextrace_inv_pgdata` remain intact.
- Inventory services (`nextrace-inventory-*`) remained undisturbed throughout the validation.
- All seven containers are running and operational. PostgreSQL and Redis containers are Docker-healthchecked; Gateway, Order Service, Inventory API, and Inventory Service were verified through their HTTP readiness endpoints.
