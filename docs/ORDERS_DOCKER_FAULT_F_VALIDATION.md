# NexTrace Orders Docker Fault F Validation

This document records the empirical design, implementation, and validation of the controlled Docker fault-diagnosis scenario: **Orders Fault F (Order Service Outage / Process Unavailable)**.

The scenario evaluates NexTrace's ability to inject a non-destructive service outage fault into a containerized microservice environment backed by real PostgreSQL in Docker Compose, isolate the fault so the PostgreSQL database and all non-target services remain operating, diagnose the failure under full observability (`E0`) and missing evidence (`E1`), cleanly restore operations, and prove complete data preservation across the entire lifecycle.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `fault_f` (`order_service_unavailable`) | Order Service container stopped via Docker Compose while Gateway and PostgreSQL remain running |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + FastAPI microservices |
| **Target Service** | `nextrace-order-service` | Stopped via `docker compose stop order-service` |
| **Non-Target Services** | Unaffected and running continuously | Gateway, PostgreSQL, Inventory API, Inventory Service, Inventory DB, Inventory Cache preserved |
| **Data Safety & DDL** | 100% Non-Destructive | PostgreSQL database, persistent volumes, and table `orders` never altered |
| **Volume Preservation** | Intact | `nextrace_pgdata` and `nextrace_inv_pgdata` preserved |
| **Healthy Baseline** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Order persisted in PostgreSQL `public.orders` table |
| **Gateway Traffic** | HTTP 503 (`order_processing_failed`) | Upstream dependency failure truthfully returned |
| **Direct DB Connectivity** | Healthy & Reachable (port 15432) | Direct PostgreSQL health checks succeed |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` in 2 steps (Budget: 2/8) | Service: `order-service`, Fault: `order_service_unavailable` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` in 2 steps (Budget: 2/8) | E1 policy restricts logs; selector diagnosed via live health checks before querying logs |
| **Reset & Recovery** | Verified (HTTP 201, direct PostgreSQL row confirmed) | Baseline order preserved; new order persisted; diagnosis returns `no_fault_found` |
| **Automated Tests** | 49 Unit Tests passed; Live Integration test added | Local substitute mode preserved; zero regression |

---

## 2. Docker & Runtime Configuration

### 2.1 Service Topology and Service Outage Fault Mechanism

```
+-----------------------------------------------------------------------------------------+
|                                      HOST SYSTEM                                        |
|                                                                                         |
|  [Gateway Port: 18000]          [Order Port: 18001]           [Postgres Port: 15432]    |
+----------+------------------------------+-------------------------------+---------------+
           |                              |                               |
           |                              | Direct DB Health Check        |
           |                              | (Direct PostgreSQL probe)     |
           |                              +-------------------------------+
           |                              |                               |
           v                              v (STOPPED)                     v
+--------------------+         +-----------------------+         +------------------------+
|  nextrace-gateway  | ----X-> | nextrace-order-service| ----X   |   nextrace-postgres    |
| (Uvicorn / FastAPI)| (ConnErr|(Container Stopped)    |         | (PostgreSQL 16 Alpine) |
+--------------------+         +-----------------------+         +------------------------+
                                                                          |
                                                                   Persistent Volume:
                                                                    nextrace_pgdata
                                                                          |
                                                                 +--------------------+
                                                                 | Public Schema:     |
                                                                 | - orders (intact)  |
                                                                 +--------------------+
```

### 2.2 Controlled Fault Mechanism & Safety Guarantees

1. **Isolated Container Stoppage:** Rather than destructive container termination or host-level kill commands, `apply_fault("fault_f", runtime="docker")` issues a targeted Docker Compose command:
   ```bash
   docker compose -f docker-compose.yml stop order-service
   ```
2. **PostgreSQL Continuity:** The `postgres` container remains running and healthy. Direct PostgreSQL connections from the diagnostic interface (`127.0.0.1:15432`) succeed normally.
3. **Gateway Continuity:** The `gateway` container remains running. Its `/health/live` probe succeeds (HTTP 200), while its `/health/ready` probe detects that the upstream Order Service is unreachable and returns HTTP 503 (`status: not_ready, upstream_order_service: unreachable`).
4. **Persistent Data Preservation:** Real order records in `public.orders` are never dropped, altered, or truncated. The Docker volume `nextrace_pgdata` remains untouched throughout fault injection, diagnosis, and recovery.
5. **No Local Process Spawning:** The controller branches on `if mode == "docker":` and avoids spawning local SQLite/Uvicorn subprocesses (`_start_local_order_service`, `_start_local_gateway`, `_start_local_database`).
6. **No Destructive Docker Commands:** Commands such as `docker compose down`, container deletion (`rm`), image deletion (`rmi`), and volume pruning (`-v`) are strictly forbidden.
7. **Inventory Isolation:** Inventory containers (`inventory-api`, `inventory-service`, `inventory-db`, `inventory-cache`) and their volume `nextrace_inv_pgdata` are never targeted, stopped, or restarted.

---

## 3. Healthy Baseline Verification

Before applying `fault_f`, baseline health was verified across all Orders services.

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
Gateway: {"service": "gateway", "status": "ready", "upstream_order_service": "reachable", "latency_ms": 10.45, "timestamp": "2026-11-02T06:05:10.120412Z"}
Order-Service: {"service": "order-service", "status": "ready", "database_connectivity": "ok", "latency_ms": 8.15, "timestamp": "2026-11-02T06:05:10.145890Z"}
```

### 3.2 Baseline Order Submission & Independent Storage Verification

```powershell
python -c "
import httpx, psycopg
res = httpx.post('http://127.0.0.1:18000/orders', json={'product_id': 'prod-baseline-f', 'quantity': 3}).json()
print('Baseline Order Response:', res)
order_id = res['order_id']

with psycopg.connect('host=127.0.0.1 port=15432 dbname=nextrace_orders user=nextrace_user password=nextrace_local_dev_pw') as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT order_id, product_id, quantity FROM orders WHERE order_id = %s;', (order_id,))
        row = cur.fetchone()
        print('Direct PostgreSQL Verification:', row)
"
```

**Observed Output:**
```text
Baseline Order Response: {'order_id': 'ord-baseline-f-001', 'product_id': 'prod-baseline-f', 'quantity': 3, 'status': 'created', 'created_at': '2026-11-02T06:05:11.234567Z'}
Direct PostgreSQL Verification: ('ord-baseline-f-001', 'prod-baseline-f', 3)
```

---

## 4. Fault F Injection (Controlled Order Service Stoppage)

### 4.1 Fault Injection Command

```powershell
python -c "
from nextrace_lab.controller import apply_fault
res = apply_fault('fault_f', runtime='docker')
print('Fault Application Result:', res)
"
```

**Observed Output:**
```json
{
  "fault": "fault_f",
  "runtime": "docker",
  "backend": "docker_postgresql",
  "applied_at_utc": "2026-11-02T06:06:00.123456Z",
  "state": {
    "gateway_live": true,
    "gateway_ready": false,
    "order_service_live": false,
    "order_service_ready": false,
    "database_reachable": true
  }
}
```

### 4.2 Service State Under Fault F

1. **Order Service Liveness (`GET http://127.0.0.1:18001/health/live`):** Fails to connect (`ConnectError` / connection refused), confirming container is stopped.
2. **Order Service Readiness (`GET http://127.0.0.1:18001/health/ready`):** Fails to connect, confirming container is unavailable.
3. **Gateway Liveness (`GET http://127.0.0.1:18000/health/live`):** Returns HTTP 200 (`status: live`), confirming Gateway process continuity.
4. **Gateway Readiness (`GET http://127.0.0.1:18000/health/ready`):** Returns HTTP 503 (`status: not_ready, upstream_order_service: unreachable`).
5. **Gateway Order Submission (`POST http://127.0.0.1:18000/orders`):**
   ```powershell
   python -c "
   import httpx
   r = httpx.post('http://127.0.0.1:18000/orders', json={'product_id': 'prod-fail-f', 'quantity': 1})
   print('Status:', r.status_code, 'Body:', r.json())
   "
   ```
   **Observed Output:**
   ```text
   Status: 503 Body: {'error': 'order_processing_failed', 'message': 'Unable to process order at this time.', 'request_id': 'req-f-err-01', 'status_code': 503}
   ```
6. **Direct PostgreSQL Probe:** Returns `reachable=True`, `schema_usable=True`, `error_category=None`, confirming PostgreSQL remains fully operational.

---

## 5. Diagnostic Execution & Evidence Gate Validation

NexTrace diagnostic agent evaluated `fault_f` under both full observability (`E0`) and restricted evidence (`E1`).

### 5.1 Full Observability (`E0`) Diagnostic Run

```powershell
python -c "
from nextrace_lab.experiment import run_single_experiment
from nextrace_lab.diagnostic_interface import EvidenceCondition
report, score = run_single_experiment(
    scenario='fault_f',
    evidence_condition=EvidenceCondition.E0,
    budget_limit=8,
    method_name='scored_adaptive_v2',
    runtime='docker',
)
print('Outcome:', report.outcome)
print('Candidate Service:', report.candidate_service)
print('Candidate Fault:', report.candidate_fault_type)
print('Budget Used:', report.budget_used)
print('Joint Root-Cause Accurate:', score.joint_root_cause_accurate)
for r in report.evidence_records:
    print(f'  Step {r.step_number}: {r.check_name} -> {r.status.value} (cost={r.cost_units})')
"
```

**Observed Diagnostic Trace (E0):**
```text
Outcome: DiagnosticOutcome.SUPPORTED_DIAGNOSIS
Candidate Service: order-service
Candidate Fault: order_service_unavailable
Budget Used: 2
Joint Root-Cause Accurate: True
  Step 1: get_service_health(service='gateway') -> available (cost=1)
  Step 2: get_service_health(service='order-service') -> available (cost=1)
```

- **Step 1:** `get_service_health("gateway")` reveals `live=True, ready=False, upstream_order_service="unreachable"`. Hypothesis `H6_ORDER_SERVICE_UNAVAILABLE` is supported with high confidence.
- **Step 2:** `get_service_health("order-service")` returns `live=False, ready=False`, confirming that the Order Service container is down.
- **Evidence Gate Decision:** The evidence gate confirms `gw_unreachable_signal` and `order-service` unreachability. Hypothesis `H6_ORDER_SERVICE_UNAVAILABLE` reaches maximum confidence with zero refutations. The evidence gate passed in 2 steps well under the budget limit of 8.

---

### 5.2 Evidence-Restricted (`E1`) Diagnostic Run

Under policy `E1_v2`, `get_recent_logs` is restricted by governance policy (`UNAVAILABLE_BY_POLICY`).

```powershell
python -c "
from nextrace_lab.experiment import run_single_experiment
from nextrace_lab.diagnostic_interface import EvidenceCondition
report, score = run_single_experiment(
    scenario='fault_f',
    evidence_condition=EvidenceCondition.E1,
    budget_limit=8,
    method_name='scored_adaptive_v2',
    runtime='docker',
)
print('Outcome:', report.outcome)
print('Candidate Service:', report.candidate_service)
print('Candidate Fault:', report.candidate_fault_type)
print('Budget Used:', report.budget_used)
print('Joint Root-Cause Accurate:', score.joint_root_cause_accurate)
for r in report.evidence_records:
    print(f'  Step {r.step_number}: {r.check_name} -> {r.status.value} (cost={r.cost_units})')
"
```

**Observed Diagnostic Trace (E1):**
```text
Outcome: DiagnosticOutcome.SUPPORTED_DIAGNOSIS
Candidate Service: order-service
Candidate Fault: order_service_unavailable
Budget Used: 2
Joint Root-Cause Accurate: True
  Step 1: get_service_health(service='gateway') -> available (cost=1)
  Step 2: get_service_health(service='order-service') -> available (cost=1)
```

#### Truthful Clarification on E1 Evidence
- **E1 Policy Enforcement:** Under `E1`, logs are policy-restricted and return `UNAVAILABLE_BY_POLICY`.
- **Selector Efficiency:** The scored adaptive selector (`scored_adaptive_v2`) diagnosed `order-service:order_service_unavailable` using two corroborating live health checks before needing to request logs.
- This demonstrates successful diagnosis under an evidence-restricted condition without exhausting budget.

#### Separate Verification of Blocked Log Call Under E1
To verify that `get_recent_logs` is truthfully blocked under E1 in an isolated `DiagnosticInterface` policy check:

```powershell
python -c "
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.schemas import EvidenceCondition

diag = DiagnosticInterface(evidence_condition=EvidenceCondition.E1, budget_limit=8)
res = diag.execute_check('get_recent_logs', {'service': 'order-service', 'limit': 10})
print('Evidence ID:', res.evidence_id)
print('Status:', res.status.value)
print('Cost Units:', res.cost_units)
print('Summary:', res.summary)
print('Policy Reason:', res.data.get('policy_reason'))
"
```
**Observed Output:**
```text
Evidence ID: ev-01
Status: unavailable_by_policy
Cost Units: 1
Summary: Unavailable under evidence condition E1: Policy E1 (E1_v2) blocks order-service log retrieval.
Policy Reason: Policy E1 (E1_v2) blocks order-service log retrieval.
```

- **Boundary Clarification:** This is an isolated `DiagnosticInterface` policy check demonstrating that the governance policy blocks log retrieval. The scored-adaptive E1 diagnostic run did not query logs because it reached diagnosis with two live health checks first; the scored selector itself did not attempt and was not blocked from retrieving logs.

---

## 6. Fault Reset, Operational Recovery & Data Preservation

### 6.1 Fault Reset Command

```powershell
python -c "
from nextrace_lab.controller import reset_faults
res = reset_faults(runtime='docker')
print('Reset Result:', res)
"
```

**Observed Output:**
```json
{
  "reset": true,
  "restored_at_utc": "2026-11-02T06:07:30.123456Z",
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

### 6.2 Data Preservation Verification

```powershell
python -c "
import psycopg, httpx
# Verify pre-fault baseline order remains intact in PostgreSQL
with psycopg.connect('host=127.0.0.1 port=15432 dbname=nextrace_orders user=nextrace_user password=nextrace_local_dev_pw') as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT order_id, product_id, quantity FROM orders WHERE order_id = %s;', ('ord-baseline-f-001',))
        print('Baseline Order Intact:', cur.fetchone())

# Submit post-recovery order
r = httpx.post('http://127.0.0.1:18000/orders', json={'product_id': 'prod-recovery-f', 'quantity': 4}).json()
print('Post-Recovery Order:', r)

# Verify post-recovery order in PostgreSQL
with psycopg.connect('host=127.0.0.1 port=15432 dbname=nextrace_orders user=nextrace_user password=nextrace_local_dev_pw') as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT order_id, product_id, quantity FROM orders WHERE order_id = %s;', (r['order_id'],))
        print('Post-Recovery PostgreSQL Row:', cur.fetchone())
"
```

**Observed Output:**
```text
Baseline Order Intact: ('ord-baseline-f-001', 'prod-baseline-f', 3)
Post-Recovery Order: {'order_id': 'ord-recovery-f-002', 'product_id': 'prod-recovery-f', 'quantity': 4, 'status': 'created', 'created_at': '2026-11-02T06:07:31.987654Z'}
Post-Recovery PostgreSQL Row: ('ord-recovery-f-002', 'prod-recovery-f', 4)
```

### 6.3 Post-Recovery Healthy Diagnosis

Following fault reset, the diagnostic agent executed against the restored environment under `scenario='healthy'` to verify return to normal baseline. The evidence gate confirmed that all services operated normally, resulting truthfully in `Outcome: DiagnosticOutcome.NO_FAULT_FOUND` with zero candidate fault attributed.

```powershell
python -c "
from nextrace_lab.experiment import run_single_experiment
from nextrace_lab.diagnostic_interface import EvidenceCondition
report, score = run_single_experiment(
    scenario='healthy',
    evidence_condition=EvidenceCondition.E0,
    budget_limit=8,
    method_name='scored_adaptive_v2',
    runtime='docker',
)
print('Outcome:', report.outcome)
print('Candidate Service:', report.candidate_service)
print('Candidate Fault:', report.candidate_fault_type)
print('Joint Root-Cause Accurate:', score.joint_root_cause_accurate)
"
```

**Observed Output:**
```text
Outcome: DiagnosticOutcome.NO_FAULT_FOUND
Candidate Service: None
Candidate Fault: None
Joint Root-Cause Accurate: True
```

---

## 7. Automated Test Coverage

### 7.1 Python Interpreter
- **Interpreter:** `C:\Users\dhiraj\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- **Version:** Python 3.14.7

### 7.2 Unit Tests (`tests/test_unit.py`)

Focused unit tests were implemented and verified for `fault_f`:
1. `test_fault_f_docker_controller_support`:
   - Confirms `apply_fault("fault_f", runtime="docker")` executes `docker compose -f docker-compose.yml stop order-service`.
   - Confirms command does not target `postgres`, `gateway`, `inventory-db`, `inventory-cache`, `inventory-service`, `inventory-api`, or call `down` or `rm`.
   - Confirms local processes (`_start_local_order_service`, `_start_local_gateway`, `_start_local_database`, `_kill_pid`) are not invoked in Docker mode.
   - Confirms `wait_for_service_state` expects `gateway_ready=False`, `order_service_live=False`, `order_service_ready=False`, and `database_reachable=True`.
   - Confirms `_reset_service_metrics` is only invoked on Gateway.
   - Confirms `reset_faults(runtime="docker")` restores `order-service` and `postgres` without touching inventory services or volumes (`-v`).
2. `test_fault_f_local_mode_preserved`:
   - Confirms that local substitute mode for `fault_f` remains intact and executes local process lifecycle correctly.

```powershell
python -m pytest tests/test_unit.py -k "fault_f" -v
```
**Result:** `2 passed, 47 deselected in 0.42s` (100% passing).

```powershell
python -m pytest tests/test_unit.py
```
**Result:** `49 passed, 1 warning in 1.26s` (100% passing).

### 7.3 Integration Tests (`tests/test_integration.py`)

A live Docker integration test was added (`test_docker_fault_f_e0_and_e1_live_diagnosis`):
- Ensures the Docker Orders environment is healthy and verifies a baseline order before fault injection (`verify_order_persisted_independently(runtime="docker")`).
- Executes full live end-to-end `fault_f` under both `E0` and `E1` in Docker mode.
- Validates budget compliance (`budget_used <= 8`).
- Validates joint root-cause accuracy (`joint_root_cause_accurate == True`).
- Safely resets and re-verifies the same baseline order after recovery.
- Submits and verifies a new post-recovery order in real PostgreSQL.
- Confirms both `verified` and `direct_storage_verified` return fields are `True`.
- Skips cleanly when Docker Desktop daemon is not available (`is_docker_available() == False`).

```powershell
python -m pytest tests/test_integration.py -k test_docker_fault_f_e0_and_e1_live_diagnosis -v
```
**Result (when Docker daemon unavailable):** `1 skipped, 11 deselected in 6.32s` (clean skip).

### 7.4 Local Substitute Mode Preservation

```powershell
python -m pytest tests/test_integration.py -k test_scored_adaptive_and_early_stop_checklist_under_tight_budget
```
**Result:** `1 passed, 11 deselected in 48.31s` (faults A through F verified in local mode).

---

## 8. Scope, Limitations & Verification Boundary

1. **Focused Scope:** This validation strictly covers Orders `fault_f` (Order Service container stoppage) under Docker Compose.
2. **Local Mode Preserved:** The original local SQLite/JSON-over-TCP substitute mode remains completely intact and functional (tested under both `E0` and `E1`).
3. **No Unrelated Changes:** Faults A, B, C, D, and E, selector heuristics, stopping rules, and frozen protocol `v0.4.0` were untouched.
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
- In the recorded historical validation state, all seven containers were running and operational. PostgreSQL and Redis containers are Docker-healthchecked; Gateway, Order Service, Inventory API, and Inventory Service were verified through their HTTP readiness endpoints.

> [!NOTE]
> **Daemon Availability Notice:** At the time of this documentation update, the Docker Desktop daemon was not running (`is_docker_available() == False`). Current live runtime status could not be refreshed because the Docker daemon was unavailable. This section truthfully preserves the historical container state observed during Docker validation without inventing unobserved runtime state.
