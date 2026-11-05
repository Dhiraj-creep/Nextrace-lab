# NexTrace Inventory Docker Fault: `inv_fault_cache_unavailable` Validation

This document records the empirical design, implementation, and validation of the controlled Docker fault-diagnosis scenario: **Inventory Fault: Redis Cache Outage (`inv_fault_cache_unavailable`)**.

The scenario evaluates NexTrace's ability to inject a non-destructive cache outage fault into the Stage 8 second application (`inventory_app`), isolate the failure to `inventory-cache` (Redis 7) while PostgreSQL database (`inventory-db`), domain service (`inventory-service`), API gateway (`inventory-api`), and all Orders services remain operating, diagnose the failure under full observability (`E0`) and missing logs (`E1`), cleanly restore operations, and prove complete data preservation across the entire fault lifecycle.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `inv_fault_cache_unavailable` | Inventory Redis container stopped via Docker Compose |
| **Application** | `inventory_app` (Stage 8) | Second application evaluation split |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + Redis 7 Alpine + FastAPI microservices |
| **Backend** | `docker_postgres_redis` | Real multi-dependency backend |
| **Target Service** | `inventory-cache` (`nextrace-inventory-cache`) | Stopped via `docker compose -f docker-compose.yml stop inventory-cache` |
| **Non-Target Services** | Unaffected & running continuously | `inventory-db` (PostgreSQL), `inventory-service`, `inventory-api`, and all Orders containers |
| **Data Safety & DDL** | 100% Non-Destructive | PostgreSQL database, persistent volumes, and table `inventory_reservations` never altered |
| **Volume Preservation** | Intact | `nextrace_inv_pgdata` and `nextrace_pgdata` preserved |
| **Healthy Baseline** | Verified (HTTP 201) | Baseline reservation independently verified in PostgreSQL & Redis |
| **Direct DB Connectivity** | Reachable & Healthy (Port 15433) | Direct PostgreSQL query succeeds continuously during Redis fault |
| **Direct Cache Connectivity** | Unreachable (Port 16379) | Direct Redis connection refused while stopped |
| **API Entry Traffic** | HTTP 503 (`inventory_reservation_failed`) | Upstream cache failure safely returned to caller |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` (Budget $\le$ 8) | Service: `inventory-cache`, Fault: `cache_service_unavailable` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` (Budget $\le$ 8) | Service: `inventory-cache`, Fault: `cache_service_unavailable` |
| **Reset & Recovery** | Verified (`reset_faults(runtime="docker", app_id="inventory_app")`) | `inventory-cache` restored via `up -d` without `--build`; Orders services untouched |
| **Data Preservation** | 100% Verified | Baseline reservation preserved across both DB and Redis; new post-recovery reservation persisted |
| **Post-Recovery Health** | `NO_FAULT_FOUND` | `inv_healthy` diagnosis confirms clean recovery |

---

## 2. Docker Architecture & Fault Boundary

```
                     [ Client / Diagnostic Agent ]
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │     nextrace-inventory-api (Port 18010)      │  (RUNNING)
           │          HTTP Gateway Entrypoint             │  GET /health/live -> 200
           │        POST /inventory/reserve -> 503        │  GET /health/ready -> 200
           └──────────────────────┬───────────────────────┘
                                  │
                                  ▼
           ┌──────────────────────────────────────────────┐
           │   nextrace-inventory-service (Port 18011)    │  (RUNNING)
           │            Domain Business Logic             │  GET /health/live -> 200
           │    Required cache lock before DB insert      │  GET /health/ready -> 503
           └──────────────┬────────────────┬──────────────┘
                          │                │
            [ CONTINUOUSLY RUNNING ]      │ [ FAULT TARGET: STOPPED ]
                          │                │
                          ▼                ▼
           ┌────────────────────────┐    ┌────────────────────────┐
           │ nextrace-inventory-db  │    │ nextrace-inventory-cache│
           │  PostgreSQL 16 Alpine  │    │     Redis 7 Alpine     │
           │     (Port 15433)       │    │      (Port 16379)      │
           │ [ HEALTHY & REACHABLE ]│    │  [ CONTAINER STOPPED ] │
           │  Volume: inv_pgdata    │    │   Connection Refused   │
           └────────────────────────┘    └────────────────────────┘
```

### Orders Subsystem Isolation (Completely Untouched)

```
[ nextrace-gateway (18000) ] ────▶ [ nextrace-order-service (18001) ] ────▶ [ nextrace-postgres (15432) ]
                                      (All operating continuously)
```

---

## 3. Fault Injection Mechanism

### 3.1 Controlled Stop Command
The fault stops strictly `inventory-cache` through Compose without container removal, image removal, volume deletion, or process killing:

```powershell
docker compose -f docker-compose.yml stop inventory-cache
```

### 3.2 Prohibited Actions Avoided
- `docker compose down` was **never** invoked.
- No containers were deleted (`rm`).
- No Docker images were rebuilt or removed (`--build` omitted).
- No volumes were deleted (`docker volume rm` or `docker compose down -v`).
- Host-level process killing (`Stop-Process`, `kill -9`) was not used for containerized services.
- Non-target containers (`inventory-db`, `inventory-service`, `inventory-api`, `postgres`, `order-service`, `gateway`) were not stopped, restarted, or altered.

---

## 4. Empirical Verification

### 4.1 Healthy Baseline Verification
Before fault injection, the environment is confirmed healthy:
1. Submit baseline reservation through `inventory-api`:
   ```http
   POST http://127.0.0.1:18010/inventory/reserve
   Content-Type: application/json

   {"sku": "sku-baseline-inv-cache", "quantity": 3}
   ```
   **Response:** HTTP 201 Created
   ```json
   {
     "reservation_id": "<baseline_reservation_id>",
     "sku": "sku-baseline-inv-cache",
     "quantity": 3,
     "status": "reserved",
     "created_at": "2026-11-02T13:00:00Z"
   }
   ```
   *(Note: `<baseline_reservation_id>` is dynamically generated on each run, e.g. `res-baseline-cache-001` in illustrative examples).*

2. Direct PostgreSQL query against port `15433`:
   ```sql
   SELECT reservation_id, sku, quantity, status FROM inventory_reservations WHERE reservation_id = '<baseline_reservation_id>';
   ```
   *Row confirmed.*
3. Direct Redis query against port `16379`:
   ```text
   GET reservation:<baseline_reservation_id>
   -> "sku-baseline-inv-cache:3"
   ```
   *Key confirmed in Redis cache.*

### 4.2 Post-Injection State
After running `docker compose -f docker-compose.yml stop inventory-cache`:

| Service / Port | Live Endpoint | Ready Endpoint | Observed Status |
|:---|:---|:---|:---|
| `inventory-api` (18010) | HTTP 200 (`live`) | HTTP 200 (`ready`) | Operating (upstream service is live) |
| `inventory-service` (18011) | HTTP 200 (`live`) | HTTP 503 (`not_ready`) | Operating; reports `database_connectivity: ok`, `cache_connectivity: failed` |
| `inventory-db` (15433) | TCP Open | `pg_isready` OK | Reachable & Healthy |
| `inventory-cache` (16379) | TCP Closed | Connection Refused | Stopped |
| Orders Gateway (18000) | HTTP 200 | HTTP 200 | Operating |
| Order Service (18001) | HTTP 200 | HTTP 200 | Operating |
| Orders PostgreSQL (15432) | TCP Open | `pg_isready` OK | Operating |

### 4.3 Direct PostgreSQL Reachability During Redis Outage
While `inventory-cache` is stopped:
```python
import psycopg
with psycopg.connect(
    host="127.0.0.1",
    port=15433,
    dbname="nextrace_inventory",
    user="nextrace_user",
    password="nextrace_local_dev_pw",
    connect_timeout=2,
) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1;")
        assert cur.fetchone() == (1,)
```
*Confirmed: Inventory PostgreSQL remains 100% healthy, connected, and queryable.*

### 4.4 Gateway Reserve Request During Fault
```http
POST http://127.0.0.1:18010/inventory/reserve
Content-Type: application/json

{"sku": "sku-fail-during-cache-fault", "quantity": 1}
```
**Response:** HTTP 503 Service Unavailable
```json
{
  "error": "inventory_reservation_failed",
  "message": "Unable to reserve inventory at this time.",
  "request_id": "exp-inv_fault_cache_unavailable-...",
  "status_code": 503
}
```

---

## 5. Diagnostic Investigation Traces

### 5.1 Full Observability (`E0`)
The `scored_adaptive_v2` selector investigates the incident using cost-benefit scoring and hypotheses corroboration:

```text
Step 1: get_service_health(service="inventory-service")
  -> status: "not_ready"
  -> database_connectivity: "ok"
  -> cache_connectivity: "failed"
  -> Corroborates cache failure hypothesis, refutes database failure

Step 2: get_service_health(service="inventory-cache")
  -> reachable: False
  -> Corroborates IH2_INV_CACHE_UNAVAILABLE (inventory-cache:cache_service_unavailable)
  -> Evidence gate passed. Stopping policy: first_supported_cause triggered.
```

- **Diagnosis Outcome:** `DiagnosticOutcome.SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `inventory-cache`
- **Candidate Fault Type:** `cache_service_unavailable`
- **Joint Root Cause Accurate:** `True`
- **Budget Used:** 2 / 8

### 5.2 Missing Logs Observability (`E1_v2`)
Under condition `E1_v2`, `get_recent_logs` is restricted by policy:

- The scored selector queries `get_service_health(inventory-service)` and `get_service_health(inventory-cache)`.
- It corroborates `inventory-cache:cache_service_unavailable` in 2 steps without attempting to query service logs.
- Therefore, in the scored diagnostic trace, logs were restricted by policy but not queried before reaching the supported diagnosis.
- **Diagnosis Outcome:** `DiagnosticOutcome.SUPPORTED_DIAGNOSIS`
- **Budget Used:** 2 / 8

#### Isolated Log Policy Verification (`E1_v2`)
In a separate, isolated policy-check using [`DiagnosticInterface`](file:///D:/Avishkar%20Nextrace/nextrace/nextrace_lab/diagnostic_interface.py), attempting to retrieve logs directly demonstrates policy enforcement:
```python
from nextrace_lab.diagnostic_interface import DiagnosticInterface
from nextrace_lab.schemas import EvidenceCondition, EvidenceStatus

diag = DiagnosticInterface(evidence_condition=EvidenceCondition.E1, budget_limit=4, app_id="inventory_app")
res = diag.execute_check("get_recent_logs", {"service": "inventory-service"})
assert res.status == EvidenceStatus.UNAVAILABLE_BY_POLICY
```

---

## 6. Reset, Recovery & Data Preservation

### 6.1 Safe Reset Command
Inventory recovery is scoped explicitly through:
```python
reset_faults(runtime="docker", app_id="inventory_app")
```
Key recovery guarantees:
- **Orders reset is not used for this task:** `app_id="orders_app"` is neither targeted nor invoked.
- **Explicit Scoping:** Inventory recovery is scoped strictly through `app_id="inventory_app"`.
- **Target Isolation:** The reset starts only required Inventory services (`inventory-db`, `inventory-cache`, `inventory-service`, `inventory-api`) and does not restart, stop, or target Orders services (`postgres`, `order-service`, `gateway`).
- **Scoped Override Cleanup & Isolation:** `_clear_all_fault_overrides(app_id="inventory_app")` removes only Inventory override files (`inv_service_override.json`, `inv_db_fault_override.json`, `cache_fault_override.json`) and strictly preserves Orders override files (`order_service_override.json`, `db_fault_override.json`). Verified by `test_reset_isolation_preserves_cross_application_overrides`.
- **Underlying Compose Execution:**
```powershell
docker compose -f docker-compose.yml up -d inventory-db inventory-cache inventory-service inventory-api
```
- Restores `inventory-cache` into the existing network.
- Images are not rebuilt (`--build` omitted).
- Volumes are preserved intact.

### 6.2 Data Preservation Proof
1. **Re-verification of Baseline Reservation:**
   - Calling `verify_inventory_persisted_independently("<baseline_reservation_id>", runtime="docker")` returns:
     - `verified == True`
     - `direct_storage_verified == True`
     - `cache_verified == True`
   - Proves the baseline record survived the cache outage and container restart intact across both PostgreSQL and Redis.
2. **Post-Recovery Reservation Creation:**
   - Calling `submit_inventory_reservation("sku-post-inv-cache", 2)` returns HTTP 201 Created.
   - Calling `verify_inventory_persisted_independently` for the new reservation returns:
     - `verified == True`
     - `direct_storage_verified == True`
     - `cache_verified == True`
3. **Clean Healthy Diagnosis:**
   - Running `inv_healthy` under `scored_adaptive_v2` confirms:
     - Outcome: `DiagnosticOutcome.NO_FAULT_FOUND`
     - Candidate Service: `None`
     - Candidate Fault Type: `None`

---

## 7. Verification Results

### 7.1 Unit Tests
```powershell
python -m pytest tests/test_unit.py -k "inv_fault_cache_unavailable" -v
```
**Result:** `2 passed, 59 deselected in 0.52s` (100% passing)
- `test_inv_fault_cache_unavailable_docker_controller_support`: PASSED
- `test_inv_fault_cache_unavailable_local_mode_preserved`: PASSED

Full unit test suite:
```powershell
python -m pytest tests/test_unit.py -q
```
**Result:** `61 passed, 1 warning in 1.72s` (100% passing)

### 7.2 Live Docker Integration Test (`tests/test_integration.py`)
A live Docker integration test was added (`test_docker_inventory_cache_unavailable_e0_and_e1_live_diagnosis`):
- Creates and verifies a baseline reservation in PostgreSQL and Redis (`verified == True`, `direct_storage_verified == True`, `cache_verified == True`).
- Explicitly confirms the live reserve request fails with HTTP 503 (`error: inventory_reservation_failed`) while `inventory-cache` is stopped.
- Independently confirms PostgreSQL remains reachable during the cache outage via a direct connection probe to port 15433.
- Safely resets Inventory via `reset_faults(runtime="docker", app_id="inventory_app")` before running diagnosis.
- Executes full live end-to-end `inv_fault_cache_unavailable` under both `E0` and `E1` with `scored_adaptive_v2`.
- Validates budget compliance (`budget_used <= 8`).
- Validates joint root-cause accuracy (`joint_root_cause_accurate == True`).
- Re-verifies the same baseline reservation in PostgreSQL and Redis after recovery (`cache_verified == True`).
- Verifies a new reservation after recovery in both PostgreSQL and Redis.
- Confirms a clean healthy diagnosis (`inv_healthy`) yields `NO_FAULT_FOUND`.
- Skips cleanly when Docker Desktop daemon is not available (`is_docker_available() == False`).

```powershell
python -m pytest tests/test_integration.py -k test_docker_inventory_cache_unavailable_e0_and_e1_live_diagnosis -v
```
**Result (when Docker daemon is unavailable):** `1 skipped, 16 deselected in 0.05s` (clean skip; recorded as *live Docker verification pending*).

---

## 8. Container Status and Volume Preservation

**Historical Container Status (Observed Post-Recovery State):**
```text
CONTAINER ID   IMAGE                    COMMAND                  STATUS                    PORTS                                           NAMES
894e96c2d796   nextrace-inventory-api   "uvicorn services.in..." Up 2 hours                0.0.0.0:18010->8010/tcp, [::]:18010->8010/tcp   nextrace-inventory-api
ac5e6042e923   nextrace-inventory-service "uvicorn services.in..." Up 2 hours                0.0.0.0:18011->8011/tcp, [::]:18011->8011/tcp   nextrace-inventory-service
8820e24027a1   postgres:16-alpine       "docker-entrypoint.s..." Up About an hour          0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp   nextrace-postgres
097c7834ab9f   nextrace-order-service   "uvicorn services.or..." Up About an hour          0.0.0.0:18001->8001/tcp, [::]:18001->8001/tcp   nextrace-order-service
b86d2ffa7bc5   nextrace-gateway         "uvicorn services.ga..." Up 3 hours                0.0.0.0:18000->8000/tcp, [::]:18000->8000/tcp   nextrace-gateway
23d2aa4c6834   postgres:16-alpine       "docker-entrypoint.s..." Up 2 hours (healthy)      0.0.0.0:15433->5432/tcp, [::]:15433->5432/tcp   nextrace-inventory-db
35e09f8df950   redis:7-alpine           "docker-entrypoint.s..." Up 10 minutes (healthy)   0.0.0.0:16379->6379/tcp, [::]:16379->6379/tcp   nextrace-inventory-cache
```

- Persistent volumes `nextrace_inv_pgdata` and `nextrace_pgdata` remain intact.
- Orders services (`nextrace-postgres`, `nextrace-order-service`, `nextrace-gateway`) remained undisturbed throughout the validation.
- In the recorded historical validation state, all seven containers were running and operational. PostgreSQL and Redis containers are Docker-healthchecked; Gateway, Order Service, Inventory API, and Inventory Service were verified through their HTTP readiness endpoints.

> [!NOTE]
> **Daemon Availability Notice:** At the time of this documentation update, the Docker Desktop daemon was not running (`is_docker_available() == False`). Current live runtime status could not be refreshed because the Docker daemon was unavailable. This section truthfully preserves the historical container state observed during Docker validation without inventing unobserved runtime state.
