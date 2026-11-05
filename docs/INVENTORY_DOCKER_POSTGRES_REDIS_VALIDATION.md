# NexTrace Inventory Application Docker (PostgreSQL & Redis) Validation Record

**Validation Date:** 2026-11-01  
**Application:** `inventory_app` (Stage 8 Second Application)  
**Execution Mode:** `docker`  
**Backend:** `docker_postgres_redis` (`PostgreSQL 16` + `Redis 7`)  
**Status:** **LIVE DOCKER VALIDATION COMPLETED & VERIFIED**

---

## 1. Overview and Architecture

The Inventory Application operates as a 4-tier microservice architecture:
1. **`inventory-api`** (Port 18010, container `nextrace-inventory-api`):
   - External-facing FastAPI gateway.
   - Forwards stock reservation requests (`POST /inventory/reserve`) and lookups (`GET /inventory/reservations/{reservation_id}`) to `inventory-service`.
2. **`inventory-service`** (Port 18011, container `nextrace-inventory-service`):
   - Core domain service coordinating stock reservation locks in Redis and persistent transactional reservation records in PostgreSQL.
   - Configured with bounded query statement timeout (`INV_DB_STATEMENT_TIMEOUT_MS: 1500`) and lock timeout (`INV_DB_LOCK_TIMEOUT_MS: 1000`).
   - Implements best-effort cache compensation: if a required cache write fails, the request stops immediately before touching PostgreSQL. If database probe or insertion fails after the cache write, a best-effort `DEL` operation removes the orphan reservation key.
3. **`inventory-db`** (Port 15433, container `nextrace-inventory-db`, image `postgres:16-alpine`):
   - Database: `nextrace_inventory`.
   - Table: `inventory_reservations` (`reservation_id`, `sku`, `quantity`, `request_id`, `status`, `created_at`).
   - Persistent volume: `nextrace_inv_pgdata`.
   - Healthcheck: `pg_isready` (Docker-healthchecked).
4. **`inventory-cache`** (Port 16379, container `nextrace-inventory-cache`, image `redis:7-alpine`):
   - Redis key-value cache providing fast reservation locks and stock tracking via RESP protocol.
   - Healthcheck: `redis-cli ping` (Docker-healthchecked).

> [!NOTE]
> Cache compensation is a best-effort application-level cleanup, not a distributed transaction. If Redis is unavailable during cleanup, an orphan reservation key may remain until a later compensating cleanup or manual operator cleanup removes it. Validating the Inventory application verifies real multi-dependency backend support for the second application under Docker. Orders services remain running and decoupled.

---

## 2. Prerequisites & Host Environment

- **Operating System:** Windows 11 (`10.0.26300`)
- **Host Python:** Python 3.14.7
- **Docker Desktop:** Version 4.97.0
  - Docker Engine: `29.9.2`
  - Docker Compose: `v5.6.1`
  - Binary location: `C:\Users\dhiraj\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`

---

## 3. Implementation Details & Consistency Safeguards

1. **Required Cache Write Enforcement & Exact Response Validation (`services/inventory_app/inventory_service_app.py`)**:
   - `_write_cache_reservation` treats Redis SET as successful **only** when its stripped RESP response is exactly `+OK` (`clean == "+OK"`).
   - Any Redis error response (`-ERR`, `-WRONGTYPE`), empty string, whitespace-only reply, malformed reply (e.g. `+OKunexpected`, `+OK extra text`, `:1`, `$4\r\nPONG`), timeout, or socket failure is treated as a cache-write failure (raises `RuntimeError`) and stops execution when `cache_mode="required"`.
   - Returns HTTP 503 (`cache_unavailable`) with the mapped error category (`cache_timeout`, `cache_connection_refused`, or `cache_error`).
   - Increments failure metrics (`failure_count`, `dependency_failures`) and logs `cache_reservation_write_failed`.
   - Does **not** proceed to PostgreSQL insertion.
   - Degraded fallback (`cache_write_failed_fallback_db`) is allowed only when `cache_mode="fallback_db"`.
2. **Defensive Cache Key Compensation (`services/inventory_app/inventory_service_app.py`)**:
   - When the reservation key is written to cache, but subsequent database operations fail (either `probe_inv_db` fails or PostgreSQL insertion raises), `_delete_cache_reservation` triggers a compensating deletion:
     - In Redis: sends RESP `DEL reservation:<reservation_id>`. Treated as successful cleanup **only** when Redis returns a valid integer response starting with `:` (e.g. `:1` for key deleted, or `:0` if key was already absent). Error responses (`-ERR`), empty, malformed, timeout, or socket errors return `cleanup_success = False`.
     - In local substitute mode: sends `{"action": "delete", "key": "reservation:<reservation_id>"}`.
   - Structured log event `cache_compensation_cleanup` records `cleanup_success` (`True` / `False`) and the `reason`.
   - The original database failure (`database_unavailable`) is preserved and returned to the caller; cleanup failure never masks the root database error.
3. **Local Cache Delete Support (`nextrace_lab/local_cache_server.py`)**:
   - Added support for `action in ("delete", "del")` to `_CacheTCPHandler`, allowing local substitute mode to cleanly remove keys during compensation.
4. **Credential Sanitization**:
   - Passwords and connection secrets are strictly redacted across all error responses and logs (`***REDACTED***`).

---

## 4. Live Verification Evidence & Observed Outputs

### 4.1 Running Containers Status
Command:
```powershell
docker compose ps
```
Output:
```text
NAME                         IMAGE                    COMMAND                  SERVICE             STATUS                        PORTS
nextrace-inventory-api       nextrace-inventory-api   "uvicorn services.in..." inventory-api       Up 3 minutes                  0.0.0.0:18010->8010/tcp
nextrace-inventory-service   nextrace-inventory-service "uvicorn services.in..." inventory-service   Up 3 minutes                  0.0.0.0:18011->8011/tcp
nextrace-inventory-db        postgres:16-alpine       "docker-entrypoint.s..." inventory-db        Up About a minute (healthy)   0.0.0.0:15433->5432/tcp
nextrace-inventory-cache     redis:7-alpine           "docker-entrypoint.s..." inventory-cache     Up 18 minutes (healthy)       0.0.0.0:16379->6379/tcp
nextrace-gateway             nextrace-gateway         "uvicorn services.ga..." gateway             Up 47 minutes                 0.0.0.0:18000->8000/tcp
nextrace-order-service       nextrace-order-service   "uvicorn services.or..." order-service       Up 47 minutes                 0.0.0.0:18001->8001/tcp
nextrace-postgres            postgres:16-alpine       "docker-entrypoint.s..." postgres            Up 47 minutes (healthy)       0.0.0.0:15432->5432/tcp
```
*(Status breakdown: `nextrace-inventory-db`, `nextrace-inventory-cache`, and `nextrace-postgres` are Docker-healthchecked. Application service and API containers are running and HTTP-ready).*

### 4.2 Readiness and Diagnostics

#### A. Inventory Service Config
Command: `GET http://127.0.0.1:18011/internal/diagnostics/db-config`  
Output (HTTP 200 OK):
```json
{
  "service": "inventory-service",
  "sanitized_config": {
    "db_driver": "postgresql",
    "db_host": "inventory-db",
    "db_port": 5432,
    "db_name": "nextrace_inventory",
    "db_user": "nextrace_user",
    "db_password_redacted": "***REDACTED***",
    "connect_timeout_sec": 1.0,
    "statement_timeout_ms": 1500,
    "lock_timeout_ms": 1000,
    "cache_driver": "redis",
    "cache_host": "inventory-cache",
    "cache_port": 6379,
    "cache_mode": "required",
    "cache_timeout_sec": 0.8
  },
  "timestamp": "2026-10-31T20:01:02.871588Z"
}
```

#### B. Inventory Service Readiness
Command: `GET http://127.0.0.1:18011/health/ready`  
Output (HTTP 200 OK):
```json
{
  "service": "inventory-service",
  "status": "ready",
  "database_connectivity": "ok",
  "cache_connectivity": "ok",
  "latency_ms": 10.33,
  "timestamp": "2026-10-31T20:01:02.871588Z"
}
```

#### C. Inventory API Readiness
Command: `GET http://127.0.0.1:18010/health/ready`  
Output (HTTP 200 OK):
```json
{
  "service": "inventory-api",
  "status": "ready",
  "upstream_inventory_service": "reachable",
  "latency_ms": 8.04,
  "timestamp": "2026-10-31T20:01:02.936303Z"
}
```

---

### 4.3 Successful Reservation Verification Across Layers

#### A. Reservation Creation
Request:
```http
POST http://127.0.0.1:18010/inventory/reserve
Content-Type: application/json
X-Request-ID: req-docker-inv-step1

{
  "sku": "sku-gpu-cluster-500",
  "quantity": 4
}
```
Response (HTTP 201 Created):
```json
{
  "reservation_id": "rsv-9b3accaa86",
  "sku": "sku-gpu-cluster-500",
  "quantity": 4,
  "request_id": "req-docker-inv-step1",
  "created_at": "2026-10-31T19:58:34.403215Z"
}
```

#### B. API Reservation Lookup
Request: `GET http://127.0.0.1:18010/inventory/reservations/rsv-9b3accaa86`  
Response (HTTP 200 OK):
```json
{
  "reservation_id": "rsv-9b3accaa86",
  "sku": "sku-gpu-cluster-500",
  "quantity": 4,
  "request_id": "req-docker-inv-step1",
  "status": "RESERVED",
  "created_at": "2026-10-31 19:58:34.383295+00"
}
```

#### C. Direct PostgreSQL Query Inside Container
Command:
```powershell
docker exec nextrace-inventory-db psql -U nextrace_user -d nextrace_inventory -c "SELECT reservation_id, sku, quantity, request_id, status, created_at FROM inventory_reservations WHERE reservation_id = 'rsv-9b3accaa86';"
```
Output:
```text
 reservation_id |         sku         | quantity |      request_id      |  status  |          created_at           
----------------+---------------------+----------+----------------------+----------+-------------------------------
 rsv-9b3accaa86 | sku-gpu-cluster-500 |        4 | req-docker-inv-step1 | RESERVED | 2026-10-31 19:58:34.383295+00
(1 row)
```

#### D. Direct Redis Cache Query Inside Container
Command:
```powershell
docker exec nextrace-inventory-cache redis-cli get reservation:rsv-9b3accaa86
```
Output:
```text
sku-gpu-cluster-500:4
```

*(Additional validation with hardened Redis RESP response checking)*:
- Reservation ID: `rsv-4fef7fb574` (`sku-ai-accelerator-800`, qty `2`, request ID `req-docker-inv-final-001`).
- API lookup: HTTP 200 OK (`status: RESERVED`).
- PostgreSQL row: verified persisted (`rsv-4fef7fb574 | sku-ai-accelerator-800 | 2 | req-docker-inv-final-001 | RESERVED`).
- Redis key: verified present via `redis-cli get reservation:rsv-4fef7fb574` returning `sku-ai-accelerator-800:2`.

---

### 4.4 Controlled Database Failure & Cache Compensation Evidence

To verify that a database failure triggers compensation and does not leave an orphan Redis key:
1. `nextrace-inventory-db` was temporarily stopped (`docker compose stop inventory-db`), while `nextrace-inventory-cache` (Redis) remained running.
2. A reservation was submitted to `inventory-api`:
   ```http
   POST http://127.0.0.1:18010/inventory/reserve
   Headers: X-Request-ID: req-docker-fail-test-001
   Body: {"sku": "sku-fail-test-999", "quantity": 1}
   ```
3. **Response**: HTTP 503 (`database_unavailable`).
4. **Structured Log Verification (`var/logs/inventory-service.jsonl`)**:
   ```json
   {"timestamp": "2026-10-31T19:59:11.990266Z", "service": "inventory-service", "level": "INFO", "event": "cache_reservation_written", "request_id": "req-docker-fail-test-001", "reservation_id": "rsv-8e20e0beac", "sku": "sku-fail-test-999", "quantity": 1}
   {"timestamp": "2026-10-31T19:59:16.001944Z", "service": "inventory-service", "level": "INFO", "event": "cache_compensation_cleanup", "request_id": "req-docker-fail-test-001", "reservation_id": "rsv-8e20e0beac", "cleanup_success": true, "reason": "db_probe_failed"}
   {"timestamp": "2026-10-31T19:59:16.013527Z", "service": "inventory-service", "level": "ERROR", "event": "database_write_failed", "request_id": "req-docker-fail-test-001", "reservation_id": "rsv-8e20e0beac", "error_category": "hostname_resolution_failed"}
   ```
5. **Direct Redis Key Inspection**:
   Command:
   ```powershell
   docker exec nextrace-inventory-cache redis-cli get reservation:rsv-8e20e0beac
   ```
   Output: *(nil / empty string - verified removed)*
6. `nextrace-inventory-db` was restarted (`docker compose start inventory-db`), returning all containers to a healthy state.

---

### 4.5 End-to-End CLI Verification After Recovery
Command:
```powershell
python -m nextrace_lab --runtime docker verify-healthy --app inventory_app
```
Output:
```json
{
  "command": "verify-healthy",
  "app": "inventory_app",
  "status": "ok",
  "runtime": "docker",
  "backend": "docker_postgres_redis",
  "http_status": 201,
  "reservation_response": {
    "reservation_id": "rsv-a09e4610c6",
    "sku": "sku-laptop-101",
    "quantity": 2,
    "request_id": "verify-9d50af4d",
    "created_at": "2026-10-31T20:01:43.826223Z"
  },
  "independent_storage_verification": {
    "verified": true,
    "reservation_id": "rsv-a09e4610c6",
    "sku": "sku-laptop-101",
    "quantity": 2,
    "request_id": "verify-9d50af4d",
    "created_at": "2026-10-31 20:01:43.812762+00",
    "direct_storage_verified": true,
    "cache_verified": true,
    "cache_raw": "$16\r\nsku-laptop-101:2",
    "backend": "docker_postgres_redis"
  }
}
```

---

## 5. Automated Regression Test Suite

Execution environment: Python 3.14.7 on Windows 11.

- **Unit tests:** **36 / 36 passed** in `1.32s` (`python -m pytest tests/test_unit.py`).
  - Covers required cache write failure, database probe failure compensation, PostgreSQL insert rollback and cleanup, cleanup failure logging without masking root cause, successful reservation, local TCP substitute mode deletion, and defensive Redis RESP validation (`+OK`, `-ERR`, empty, malformed, `:1`, `:0`, socket errors).
- **Local integration tests:** **6 / 6 passed** in `113.98s` (`python -m pytest tests/test_integration.py` when local TCP port 15432 is unobstructed).

---

## 6. Container Lifecycle and Data Preservation

All containers remain running.

To stop the Inventory containers **without deleting database volumes** (`nextrace_nextrace_inv_pgdata`):
```powershell
cd "D:\Avishkar Nextrace\nextrace"
python -m nextrace_lab --runtime docker stop --app inventory_app
# Or directly via Compose:
docker compose stop inventory-db inventory-cache inventory-service inventory-api
```

To stop Orders containers:
```powershell
docker compose stop postgres order-service gateway
```

> [!CAUTION]
> Never run `docker compose down -v`. Doing so will destroy the PostgreSQL data volumes (`nextrace_nextrace_pgdata` and `nextrace_nextrace_inv_pgdata`).
