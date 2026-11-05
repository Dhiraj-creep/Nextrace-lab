# NexTrace Orders Docker Fault A Validation

This document records the empirical validation of the first controlled Docker fault-diagnosis scenario in NexTrace: **Orders Fault A (Order Service Database Endpoint Misconfiguration)**.

The scenario evaluates NexTrace's ability to inject a dynamic database endpoint misconfiguration into a containerized microservice running on Docker Compose with real PostgreSQL, detect and diagnose the failure under full observability (`E0`), adaptively diagnose under missing log evidence (`E1`), cleanly restore healthy operations, and maintain ground-truth isolation throughout.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `fault_a` (`db_endpoint_misconfiguration`) | Order Service configured to unresolvable DB host |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + FastAPI microservices |
| **Container Targets** | `nextrace-order-service`, `nextrace-postgres`, `nextrace-gateway` | Preserves all existing volumes and Inventory services |
| **Healthy Baseline** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Order `ord-7756148550` persisted in PostgreSQL table |
| **Fault Injection** | Dynamically applied via volume override | Config host changed to `invalid-db-host.internal` |
| **Gateway Traffic** | HTTP 503 (`order_processing_failed`) | Upstream dependency failure truthfully returned |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` in 3 steps (Budget: 3/8) | Service: `order-service`, Fault: `db_endpoint_misconfiguration` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` in 3 steps (Budget: 3/8) | Policy blocks logs; alternative live probes corroborate |
| **Reset & Recovery** | Verified (HTTP 201, direct PostgreSQL row confirmed) | New order `ord-ab4d5d3aea` persisted; diagnosis returns `no_fault_found` |
| **Automated Tests** | 37 Unit Tests passed; Integration test passed | Local substitute mode preserved; zero regression |

---

## 2. Docker & Runtime Configuration

### 2.1 Service Topology and Port Allocation

```
+-----------------------------------------------------------------------------------------+
|                                      HOST SYSTEM                                        |
|                                                                                         |
|  [Gateway Port: 18000]          [Order Port: 18001]           [Postgres Port: 15432]    |
+----------+------------------------------+-------------------------------+---------------+
           |                              |                               |
           v                              v                               v
+--------------------+         +-----------------------+         +------------------------+
|  nextrace-gateway  | ------> | nextrace-order-service| ------> |   nextrace-postgres    |
| (Uvicorn / FastAPI)|         |  (Uvicorn / FastAPI)  |         | (PostgreSQL 16 Alpine) |
+--------------------+         +-----------+-----------+         +------------------------+
                                           |
                                  Mounted Volume:
                        ./var/runtime:/app/var/runtime
                                           |
                      +--------------------+---------------------+
                      | Dynamic override file:                   |
                      | order_service_override.json (ro/transient)|
                      +------------------------------------------+
```

### 2.2 Docker Compose Configuration (`docker-compose.yml`)

The Order Service container was configured to enable dynamic, non-destructive fault injection via mounted runtime overrides without requiring container teardown or volume erasure:

```yaml
  order-service:
    build: .
    container_name: nextrace-order-service
    command: ["uvicorn", "services.order_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
    environment:
      NEXTRACE_DB_DRIVER: postgresql
      DB_HOST: ${ORDER_SERVICE_DB_HOST:-postgres}
      DB_PORT: "5432"
      DB_NAME: ${DB_NAME:-nextrace_orders}
      DB_USER: ${DB_USER:-nextrace_user}
      DB_PASSWORD: ${DB_PASSWORD:-nextrace_local_dev_pw}
      DB_CONNECT_TIMEOUT_SEC: "1.5"
      DB_STATEMENT_TIMEOUT_MS: "1500"
      DB_LOCK_TIMEOUT_MS: "1000"
      NEXTRACE_LOG_DIR: /app/var/logs
      NEXTRACE_ORDER_CONFIG_OVERRIDE_FILE: /app/var/runtime/order_service_override.json
    ports:
      - "${HOST_ORDER_PORT:-18001}:8001"
    volumes:
      - ./var/logs:/app/var/logs
      - ./var/runtime:/app/var/runtime
    depends_on:
      - postgres
```

---

## 3. Healthy Baseline Verification

Before applying any fault, all services were verified in a healthy, steady state.

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
Gateway: {"service": "gateway", "status": "ready", "upstream_order_service": "reachable", "latency_ms": 90.25, "timestamp": "2026-10-31T21:06:22.670976Z"}
Order-Service: {"service": "order-service", "status": "ready", "database_connectivity": "ok", "latency_ms": 100.85, "timestamp": "2026-10-31T21:06:22.791836Z"}
```

### 3.2 Baseline Order Submission

```powershell
python -c "
from nextrace_lab.controller import submit_order, verify_order_persisted_independently
status, body = submit_order('sku-router-01', 2, 'req-baseline-test-01')
print('Status:', status)
print('Body:', body)
v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Verification:', v)
"
```

**Observed Output:**
```text
Status: 201
Body: {'order_id': 'ord-7756148550', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-test-01', 'created_at': '2026-10-31 21:06:22.861453+00'}
Verification: {'verified': True, 'order_id': 'ord-7756148550', 'product_id': 'sku-router-01', 'quantity': 2, 'request_id': 'req-baseline-test-01', 'created_at': '2026-10-31 21:06:22.861453+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
```

Both API lookups and independent direct SQL queries into `nextrace-postgres` confirmed the order was correctly written to the persistent PostgreSQL database.

---

## 4. Docker Fault Injection Support (`fault_a`)

### 4.1 Controller Implementation

`nextrace_lab/controller.py` was updated to support Docker runtime execution for `fault_a`:
- When `mode == "docker"`, the controller writes `order_service_override.json` directly into the mounted runtime directory:
  ```json
  {
    "db_host": "invalid-db-host.internal",
    "db_port": 5432,
    "db_name": "nextrace_orders"
  }
  ```
- No local subprocesses are spawned.
- The Order Service immediately picks up the override on its next request via `load_db_config()`.
- The controller polls `wait_for_service_state()` expecting `order_service_ready=False` and `database_reachable=True`.

### 4.2 Injection Command & Observed Status

```powershell
python -m nextrace_lab --runtime docker apply-fault --fault fault_a
```

**Observed Controller Response:**
```json
{
  "fault": "fault_a",
  "runtime": "docker",
  "backend": "docker_postgresql",
  "applied_at_utc": "2026-10-31T21:07:46.511859Z",
  "state": {
    "gateway_live": true,
    "gateway_ready": true,
    "order_service_live": true,
    "order_service_ready": false,
    "database_reachable": true
  }
}
```

### 4.3 Evidence the Endpoint Changed in the Running Container

Querying the Order Service diagnostic config endpoint inside the container:

```powershell
python -c "
import httpx
print(httpx.get('http://127.0.0.1:18001/internal/diagnostics/db-config').json())
"
```

**Observed Output:**
```json
{
  "service": "order-service",
  "sanitized_config": {
    "db_driver": "postgresql",
    "db_host": "invalid-db-host.internal",
    "db_port": 5432,
    "db_name": "nextrace_orders",
    "db_user": "nextrace_user",
    "db_password_redacted": "***REDACTED***",
    "connect_timeout_sec": 1.5,
    "statement_timeout_ms": 1500,
    "lock_timeout_ms": 1000
  },
  "timestamp": "2026-10-31T21:07:46.560400Z"
}
```

Querying the Order Service readiness probe:

```powershell
python -c "
import httpx
r = httpx.get('http://127.0.0.1:18001/health/ready')
print(r.status_code, r.json())
"
```

**Observed Output:**
```text
503 {'service': 'order-service', 'status': 'not_ready', 'database_connectivity': 'failed', 'error_category': 'hostname_resolution_failed', 'latency_ms': 0.02, 'timestamp': '2026-10-31T21:07:46.595290Z'}
```

### 4.4 Gateway Failure Behavior

Submitting an order through the Gateway during the fault:

```powershell
python -c "
from nextrace_lab.controller import submit_order
status, body = submit_order('sku-router-01', 1, 'req-fault-test-01')
print('Gateway HTTP status:', status)
print('Gateway response:', body)
"
```

**Observed Output:**
```text
Gateway HTTP status: 503
Gateway response: {'error': 'order_processing_failed', 'message': 'Unable to process order at this time.', 'request_id': 'req-fault-test-01', 'status_code': 503}
```

---

## 5. Fault Diagnosis Under Full Observability (`E0`)

Under evidence condition `E0`, all diagnostic tools in the check catalog are available without policy restrictions.

### 5.1 Diagnostic Run Parameters
- **Scenario:** `fault_a`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E0`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

### 5.2 Observed Investigation Trace

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False, error_category=hostname_resolution_failed` |
| 2 | `ev-02` | `get_recent_logs` | `service: order-service, limit: 20` | `available` | 1 | `Retrieved recent log entries for order-service` |
| 3 | `ev-03` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) direct health check on 127.0.0.1:15432: reachable=True, schema_usable=True.` |

### 5.3 Diagnostic Outcome
- **Outcome:** `SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `order-service`
- **Candidate Fault Type:** `db_endpoint_misconfiguration`
- **Budget Used:** 3 / 8 units
- **Joint Root-Cause Accurate:** `True`
- **Evidence Gate Reason:** `Confirmed order-service DB endpoint misconfiguration via invalid DB host / hostname_resolution_failed evidence.`
- **Cited Evidence IDs:** `['ev-01', 'ev-03']`

### 5.4 Ground-Truth Isolation
The diagnostic selector receives only the incident symptom (`POST /orders returned HTTP 503`), available check definitions, and collected results. Ground truth labels (`FAULT_CATALOG`) are strictly quarantined from the selector and used exclusively post-investigation by the scoring evaluator.

---

## 6. Fault Diagnosis Under Missing Evidence (`E1`)

Under evidence condition `E1`, Order Service log retrieval is blocked by policy (`Policy E1 blocks order-service log retrieval`). The diagnostic agent must reach an evidence-supported conclusion through alternative observability tools without treating blocked logs as evidence of health.

### 6.1 Diagnostic Run Parameters
- **Scenario:** `fault_a`
- **Method:** `scored_adaptive_v2`
- **Evidence Condition:** `EvidenceCondition.E1`
- **Budget Limit:** 8 check units
- **Runtime Mode:** `docker` (`docker_postgresql`)

### 6.2 Observed Investigation Trace

| Step | Evidence ID | Diagnostic Check | Parameters | Status | Cost | Summary |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| 1 | `ev-01` | `get_service_health` | `service: order-service` | `available` | 1 | `Service order-service health: live=True, ready=False, error_category=hostname_resolution_failed` |
| 2 | `ev-02` | `get_recent_logs` | `service: order-service, limit: 20` | `unavailable_by_policy` | 1 | `Unavailable under evidence condition E1: Policy E1 (E1_v2) blocks order-service log retrieval.` |
| 3 | `ev-03` | `get_service_health` | `service: database` | `available` | 1 | `PostgreSQL (database) direct health check on 127.0.0.1:15432: reachable=True, schema_usable=True.` |

### 6.3 Handling of Missing Evidence
1. **No Phantom Health Inference:** The blocked log result (`ev-02`) returns `EvidenceStatus.UNAVAILABLE_BY_POLICY`. The evidence gate and hypothesis scorer strictly treat this as missing evidence, not absence of errors.
2. **Alternative Corroboration:** The selector uses `get_service_health(order-service)` (`ev-01`), which exposes `error_category="hostname_resolution_failed"`, coupled with `get_service_health(database)` (`ev-03`), which proves the physical database is healthy and reachable.
3. **Hypothesis Resolution:** This combination satisfies hypothesis `H1_ORDER_DB_CONFIG_ENDPOINT`: the database itself is running normally, but the Order Service cannot resolve its configured endpoint.
4. **Diagnostic Outcome:**
   - **Outcome:** `SUPPORTED_DIAGNOSIS`
   - **Candidate Service:** `order-service`
   - **Candidate Fault Type:** `db_endpoint_misconfiguration`
   - **Budget Used:** 3 / 8 units
   - **Joint Root-Cause Accurate:** `True`
   - **Cited Evidence IDs:** `['ev-01', 'ev-03']`

---

## 7. Reset and Recovery Verification

### 7.1 Reset Execution

```powershell
python -m nextrace_lab --runtime docker reset-faults
```

**Observed Reset Result:**
```json
{
  "reset": true,
  "restored_at_utc": "2026-10-31T21:07:47.440454Z",
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

The reset removed `order_service_override.json`. The Order Service immediately restored connection to PostgreSQL (`postgres:5432`).

### 7.2 Post-Reset Readiness & Traffic Verification

```powershell
python -c "
import httpx
from nextrace_lab.controller import submit_order, verify_order_persisted_independently

r = httpx.get('http://127.0.0.1:18001/health/ready')
print('Readiness:', r.status_code, r.json())

status, body = submit_order('sku-router-01', 3, 'req-post-reset-01')
print('Submit:', status, body)

v = verify_order_persisted_independently(body['order_id'], runtime='docker')
print('Persistence:', v)
"
```

**Observed Output:**
```text
Readiness: 200 {'service': 'order-service', 'status': 'ready', 'database_connectivity': 'ok', 'latency_ms': 7.45, 'timestamp': '2026-10-31T21:12:25.010412Z'}
Submit: 201 {'order_id': 'ord-ab4d5d3aea', 'product_id': 'sku-router-01', 'quantity': 3, 'request_id': 'req-post-reset-01', 'created_at': '2026-10-31 21:12:25.081312+00'}
Persistence: {'verified': True, 'order_id': 'ord-ab4d5d3aea', 'product_id': 'sku-router-01', 'quantity': 3, 'request_id': 'req-post-reset-01', 'created_at': '2026-10-31 21:12:25.081312+00', 'direct_storage_verified': True, 'backend': 'docker_postgresql'}
```

### 7.3 Follow-up Diagnosis on Recovered Environment

Running `scored_adaptive_v2` on the recovered state confirmed that NexTrace no longer reports the old fault:

- **Scenario:** `healthy`
- **Outcome:** `no_fault_found`
- **Candidate Service:** `None`
- **Candidate Fault Type:** `None`
- **Evidence Gate Reason:** `Entry request succeeded (HTTP 201) and fresh, non-superseded service health checks confirmed normal operation.`
- **Joint Root-Cause Accurate:** `True`

---

## 8. Automated Test Coverage

### 8.1 Unit Tests (`tests/test_unit.py`)

A new focused controller unit test was added (`test_fault_a_docker_controller_support`):
- Confirms runtime mode resolution (`resolve_runtime_mode`) sets `NEXTRACE_RUNTIME_ACTIVE="docker"`.
- Confirms `apply_fault("fault_a", runtime="docker")` writes dynamic override with `invalid-db-host.internal` without starting local processes.
- Confirms `reset_faults(runtime="docker")` clears override and restores healthy state.
- Preserves all existing unit tests across local mode, error mapping, and secret redaction.

```powershell
python -m pytest tests/test_unit.py
```
**Result:** `37 passed, 1 warning in 1.10s` (100% passing).

### 8.2 Integration Tests (`tests/test_integration.py`)

A new live Docker integration test was added (`test_docker_fault_a_e0_and_e1_live_diagnosis`):
- Executes full live end-to-end `fault_a` under both `E0` and `E1` in Docker mode.
- Validates budget compliance (`budget_used <= 8`).
- Validates joint root-cause accuracy (`joint_root_cause_accurate == True`).

```powershell
python -m pytest tests/test_integration.py -k test_docker_fault_a_e0_and_e1_live_diagnosis -v
```
**Result:** `1 passed, 6 deselected in 36.28s` (100% passing).

---

## 9. Scope, Limitations & Verification Boundary

1. **Focused Scope:** This validation strictly addresses Orders `fault_a` (Order Service database endpoint misconfiguration) under Docker Compose with real PostgreSQL.
2. **Local Mode Preserved:** The original local SQLite/JSON-over-TCP substitute mode remains completely intact and functional.
3. **Other Fault Scenarios:** Faults B through F and Inventory faults in Docker mode will be evaluated in subsequent controlled validation steps.
4. **Credential Isolation:** Database credentials remain strictly redacted (`***REDACTED***`) in all diagnostic traces, logs, and artifacts.
5. **Protocol Stability:** Evaluation protocol `v0.4.0` stopping rules and budget models were strictly obeyed without modification.

---

## 10. Container Status and Volume Preservation

All Docker services and persistent database volumes were preserved:

```powershell
docker ps
```

**Observed Container Table:**
```text
CONTAINER ID   IMAGE                        COMMAND                  CREATED             STATUS                       PORTS                                           NAMES
097c7834ab9f   nextrace-order-service       "uvicorn services.or…"   16 minutes ago      Up 16 minutes                0.0.0.0:18001->8001/tcp, [::]:18001->8001/tcp   nextrace-order-service
8820e24027a1   postgres:16-alpine           "docker-entrypoint.s…"   16 minutes ago      Up 16 minutes (healthy)      0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp   nextrace-postgres
b79040c77705   nextrace-inventory-api       "uvicorn services.in…"   About an hour ago   Up About an hour             0.0.0.0:18010->8010/tcp, [::]:18010->8010/tcp   nextrace-inventory-api
76dbc3bf6159   nextrace-inventory-service   "uvicorn services.in…"   About an hour ago   Up About an hour             0.0.0.0:18011->8011/tcp, [::]:18011->8011/tcp   nextrace-inventory-service
b86d2ffa7bc5   nextrace-gateway             "uvicorn services.ga…"   2 hours ago         Up 2 hours                   0.0.0.0:18000->8000/tcp, [::]:18000->8000/tcp   nextrace-gateway
23d2aa4c6834   postgres:16-alpine           "docker-entrypoint.s…"   3 hours ago         Up About an hour (healthy)   0.0.0.0:15433->5432/tcp, [::]:15433->5432/tcp   nextrace-inventory-db
35e09f8df950   redis:7-alpine               "docker-entrypoint.s…"   3 hours ago         Up 2 hours (healthy)         0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp   nextrace-inventory-cache
```

- Persistent volumes `nextrace_nextrace_pgdata` and `nextrace_nextrace_inv_pgdata` remain intact.
- Inventory services (`nextrace-inventory-*`) remained undisturbed throughout the validation.
- All seven containers are running and operational. PostgreSQL and Redis containers are Docker-healthchecked; Gateway, Order Service, Inventory API, and Inventory Service were verified through their HTTP readiness endpoints.
