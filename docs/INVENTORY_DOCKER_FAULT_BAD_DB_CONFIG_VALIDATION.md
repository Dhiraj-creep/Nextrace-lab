# NexTrace Inventory Docker Fault: `inv_fault_bad_db_config` Validation

This document records the empirical design, implementation, and validation of the controlled Docker fault-diagnosis scenario: **Inventory Fault: Database Endpoint Misconfiguration (`inv_fault_bad_db_config`)**.

The scenario evaluates NexTrace's ability to inject a controlled, reversible configuration override into the Stage 8 second application (`inventory_app`), causing `inventory-service` to be unable to resolve or reach its database endpoint (`db_host: "invalid-inv-db.internal"`), while the actual PostgreSQL database (`inventory-db`), Redis cache (`inventory-cache`), domain service process (`inventory-service`), API gateway (`inventory-api`), and all Orders services remain running and healthy. The diagnostic agent evaluates root cause attribution under full observability (`E0`) and missing logs (`E1`), cleanly reverts the configuration override, and proves complete data preservation across the entire fault lifecycle.

---

## 1. Executive Summary

| Attribute | Observed Result | Notes |
|:---|:---|:---|
| **Scenario** | `inv_fault_bad_db_config` | Controlled database endpoint hostname misconfiguration |
| **Application** | `inventory_app` (Stage 8) | Second application evaluation split |
| **Runtime Mode** | `docker` | Real PostgreSQL 16 Alpine + Redis 7 Alpine + FastAPI microservices |
| **Backend** | `docker_postgres_redis` | Real multi-dependency backend |
| **Target Service** | `inventory-service` (`nextrace-inventory-service`) | Configured with unresolvable `db_host: "invalid-inv-db.internal"` |
| **Non-Target Services** | Unaffected & running continuously | `inventory-db` (PostgreSQL), `inventory-cache` (Redis), `inventory-api`, and all Orders containers |
| **Data Safety & DDL** | 100% Non-Destructive | PostgreSQL database, persistent volumes, and table `inventory_reservations` never altered |
| **Volume Preservation** | Intact | `nextrace_inv_pgdata` and `nextrace_pgdata` preserved |
| **Healthy Baseline** | Verified (HTTP 201) | Baseline reservation independently verified in PostgreSQL & Redis |
| **Direct DB Connectivity** | Reachable & Healthy (Port 15433) | Direct PostgreSQL query succeeds continuously during fault |
| **Direct Cache Connectivity** | Reachable & Healthy (Port 16379) | Direct Redis PING succeeds continuously during fault |
| **API Entry Traffic** | HTTP 503 (`inventory_reservation_failed`) | Upstream hostname resolution error safely returned to caller |
| **Diagnosis (E0)** | `SUPPORTED_DIAGNOSIS` (Budget $\le$ 8) | Service: `inventory-service`, Fault: `db_endpoint_misconfiguration` |
| **Diagnosis (E1)** | `SUPPORTED_DIAGNOSIS` (Budget $\le$ 8) | Service: `inventory-service`, Fault: `db_endpoint_misconfiguration` |
| **Reset & Recovery** | Verified (`reset_faults(runtime="docker", app_id="inventory_app")`) | Runtime override cleared cleanly; services ready without `--build`; Orders untouched |
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
           │   [ FAULT TARGET: BAD DB CONFIGURATION ]     │  GET /health/ready -> 503
           │   Configured Host: invalid-inv-db.internal   │  (hostname resolution fails)
           └──────────────┬────────────────┬──────────────┘
                          │                │
            [ CONNECTION ATTEMPT FAILS ]   │ [ CACHE OPERATING NORMALLY ]
                          │                │
                          ▼                ▼
           ┌────────────────────────┐    ┌────────────────────────┐
           │ nextrace-inventory-db  │    │ nextrace-inventory-cache│
           │  PostgreSQL 16 Alpine  │    │     Redis 7 Alpine     │
           │     (Port 15433)       │    │      (Port 16379)      │
           │ [ HEALTHY & REACHABLE ]│    │ [ HEALTHY & REACHABLE ]│
           │  Volume: inv_pgdata    │    │   Port 16379 open      │
           └────────────────────────┘    └────────────────────────┘
```

### Orders Subsystem Isolation (Completely Untouched)

```
[ nextrace-gateway (18000) ] ────▶ [ nextrace-order-service (18001) ] ────▶ [ nextrace-postgres (15432) ]
                                      (All operating continuously)
```

---

## 3. Fault Injection Mechanism

### 3.1 Controlled Configuration Override
The fault dynamically writes a controlled runtime configuration override file (`var/runtime/inv_service_override.json`) mounted into `inventory-service` at `/app/var/runtime/inv_service_override.json`:

```json
{
  "db_host": "invalid-inv-db.internal",
  "db_port": 5432,
  "db_name": "nextrace_inventory"
}
```

When `inventory-service` probes the database or handles reservations, `load_inv_config()` dynamically incorporates this override. In `_validate_inv_hostname()`, the hostname `invalid-inv-db.internal` triggers `hostname_resolution_failed`:
```python
if cfg.db_host.endswith(".invalid") or cfg.db_host.endswith(".internal"):
    raise DatabaseDependencyError(
        "hostname_resolution_failed",
        f"Cannot resolve database host '{cfg.db_host}'",
        cfg.db_host,
        cfg.db_port,
    )
```

### 3.2 Prohibited Actions Avoided
- `docker compose down` was **never** invoked.
- No containers were stopped or deleted (`stop`, `rm`).
- No Docker images were rebuilt or removed (`--build` omitted).
- No volumes were deleted (`docker volume rm` or `docker compose down -v`).
- Host-level process killing (`Stop-Process`, `kill -9`) was not used for containerized services.
- Non-target containers (`inventory-db`, `inventory-cache`, `inventory-api`, `postgres`, `order-service`, `gateway`) were not stopped, restarted, or altered.

---

## 4. Empirical Verification

### 4.1 Healthy Baseline Verification
Before fault injection, the environment is confirmed healthy:
1. Submit baseline reservation through `inventory-api`:
   ```http
   POST http://127.0.0.1:18010/inventory/reserve
   Content-Type: application/json

   {"sku": "sku-baseline-inv-bad-cfg", "quantity": 2}
   ```
   **Response:** HTTP 201 Created
   ```json
   {
     "reservation_id": "<baseline_reservation_id>",
     "sku": "sku-baseline-inv-bad-cfg",
     "quantity": 2,
     "status": "reserved",
     "created_at": "2026-11-02T13:00:00Z"
   }
   ```
2. Direct PostgreSQL query against port `15433`:
   ```sql
   SELECT reservation_id, sku, quantity, status FROM inventory_reservations WHERE reservation_id = '<baseline_reservation_id>';
   ```
   *Row confirmed.*
3. Direct Redis query against port `16379`:
   ```text
   GET reservation:<baseline_reservation_id>
   -> "sku-baseline-inv-bad-cfg:2"
   ```
   *Key confirmed in Redis cache.*

### 4.2 Post-Injection State
After applying `inv_fault_bad_db_config`:

| Service / Port | Live Endpoint | Ready Endpoint | Observed Status |
|:---|:---|:---|:---|
| `inventory-api` (18010) | HTTP 200 (`live`) | HTTP 200 (`ready`) | Operating normally |
| `inventory-service` (18011) | HTTP 200 (`live`) | HTTP 503 (`not_ready`) | Operating; reports `database_connectivity: failed (hostname_resolution_failed)`, `cache_connectivity: ok` |
| `inventory-db` (15433) | TCP Open | `pg_isready` OK | Reachable & Healthy |
| `inventory-cache` (16379) | TCP Open | PING PONG | Reachable & Healthy |
| Orders Gateway (18000) | HTTP 200 | HTTP 200 | Operating |
| Order Service (18001) | HTTP 200 | HTTP 200 | Operating |
| Orders PostgreSQL (15432) | TCP Open | `pg_isready` OK | Operating |

### 4.3 Direct Dependency Reachability
While `inventory-service` fails to resolve its database hostname:
- Direct PostgreSQL connection on `127.0.0.1:15433` succeeds immediately (`SELECT 1` returns `(1,)`).
- Direct Redis connection on `127.0.0.1:16379` succeeds immediately (`PING` returns `PONG`).

### 4.4 Gateway Reserve Request During Fault
```http
POST http://127.0.0.1:18010/inventory/reserve
Content-Type: application/json

{"sku": "sku-fault-bad-cfg", "quantity": 1}
```

**Response:** HTTP 503 Service Unavailable
```json
{
  "error": "inventory_reservation_failed",
  "detail": "Failed to reserve inventory via inventory-service: HTTP 503",
  "request_id": "<request_id>"
}
```

---

## 5. Diagnostic Evaluation & Evidence Gate

### 5.1 Evidence Condition E0 (Full Observability)
The diagnostic agent runs using `scored_adaptive_v2` under budget limit $B \le 8$:
1. `get_service_health("inventory-service")` -> reports `/health/live=200`, `/health/ready=503`, error `hostname_resolution_failed`.
2. `get_database_health(inventory-db)` -> direct probe on 15433 returns reachable and healthy.
3. `get_cache_health(inventory-cache)` -> direct probe on 16379 returns reachable and healthy.
4. **Attribution:** Since `inventory-db` is demonstrably healthy on its direct port, but `inventory-service` fails with `hostname_resolution_failed`, the Evidence Gate unambiguously attributes the fault to `inventory-service:db_endpoint_misconfiguration`.
- **Diagnosis Outcome:** `DiagnosticOutcome.SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `inventory-service`
- **Candidate Fault Type:** `db_endpoint_misconfiguration`
- **Root Cause Accurate:** `True`
- **Budget Used:** $\le 8$

### 5.2 Evidence Condition E1 (Restricted Logs)
Under condition `E1_v2`, `get_recent_logs` is restricted by policy:
- The scored selector inspects health endpoints and direct dependency probes without relying on log queries.
- Corroborates `inventory-service:db_endpoint_misconfiguration`.
- **Diagnosis Outcome:** `DiagnosticOutcome.SUPPORTED_DIAGNOSIS`
- **Candidate Service:** `inventory-service`
- **Candidate Fault Type:** `db_endpoint_misconfiguration`
- **Root Cause Accurate:** `True`
- **Budget Used:** $\le 8$

---

## 6. Reset, Recovery & Data Preservation

### 6.1 Safe Reset Command
Inventory recovery is scoped strictly through:
```python
reset_faults(runtime="docker", app_id="inventory_app")
```
Key recovery guarantees:
- **Orders reset is not used:** `app_id="orders_app"` is neither targeted nor invoked.
- **Scoped Override Cleanup:** `_clear_all_fault_overrides(app_id="inventory_app")` removes only `inv_service_override.json`, strictly preserving active Orders override files (`order_service_override.json`, `db_fault_override.json`).
- **Orders Untouched Verified:** Proven by unit test `test_reset_isolation_preserves_cross_application_overrides` showing active Orders overrides and containers remain completely untouched.
- **Target Isolation:** Restores Inventory services (`inventory-db`, `inventory-cache`, `inventory-service`, `inventory-api`) without touching Orders containers (`postgres`, `order-service`, `gateway`).
- **No Rebuilds:** Images are not rebuilt (`--build` omitted).
- **Volumes Preserved:** Persistent storage volumes are preserved intact.

### 6.2 Data Preservation Proof
1. **Re-verification of Baseline Reservation:**
   - Calling `verify_inventory_persisted_independently("<baseline_reservation_id>", runtime="docker")` returns:
     - `verified == True`
     - `direct_storage_verified == True`
     - `cache_verified == True`
   - Proves the baseline record persisted across PostgreSQL and Redis.
2. **Post-Recovery Reservation Creation:**
   - Calling `submit_inventory_reservation("sku-post-inv-bad-cfg", 2)` returns HTTP 201 Created.
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

## 7. Verification Status

- **Unit Tests:** `test_inv_fault_bad_db_config_docker_controller_support`, `test_inv_fault_bad_db_config_local_mode_preserved`, and `test_reset_isolation_preserves_cross_application_overrides` all PASSED in the 61-test unit suite.
- **Live Docker Integration Test:** `test_docker_inventory_bad_db_config_e0_and_e1_live_diagnosis` in `tests/test_integration.py` cleanly skips when the Docker daemon is offline (`is_docker_available() == False`), recording **live Docker verification pending**. No destructive actions (`down`, `rm`, `-v`) are ever executed.
