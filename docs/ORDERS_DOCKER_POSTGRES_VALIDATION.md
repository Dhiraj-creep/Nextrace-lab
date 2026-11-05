# NexTrace Orders Application Docker & PostgreSQL Implementation & Live Validation Record

**Document**: `docs/ORDERS_DOCKER_POSTGRES_VALIDATION.md`  
**Repository**: `D:\Avishkar Nextrace\nextrace`  
**Target Application**: `orders_app` (Gateway, Order Service, PostgreSQL)  
**Execution Timestamp**: `2026-11-01T00:46:35+05:30`  
**Status**: **LIVE DOCKER VALIDATION COMPLETED & VERIFIED**

---

## 1. Executive Summary & Verification Completion

All criteria for validating the Orders application with real PostgreSQL in Docker, bounded query execution timeouts, and SQLSTATE-based diagnostic error classification have been **fully achieved**:

1. **Real PostgreSQL Driver Integration with Bounded Query Timeouts**:
   - Implemented real PostgreSQL driver support using `psycopg` in `services/order_service/db.py`.
   - Separated connection timeout (`DB_CONNECT_TIMEOUT_SEC`, default `1.0s`, configured `1.5s`) from query execution timeouts (`DB_STATEMENT_TIMEOUT_MS`, default `1500ms`, `DB_LOCK_TIMEOUT_MS`, default `1000ms`).
   - Configured PostgreSQL session options (`-c statement_timeout=... -c lock_timeout=...`) at connection initialization so bounded execution applies to the actual SQL query across probe, insert, and fetch.
   - Guaranteed explicit write transaction rollback (`conn.rollback()`) and safe connection/cursor cleanup on write failure before error propagation.
   - Fully preserved the existing `local_tcp` / SQLite substitute mode and protocol credentials.
2. **Precise SQLSTATE Error Classification**:
   - Replaced fragile substring matching with psycopg exception types and PostgreSQL SQLSTATE codes.
   - Maps undefined `orders` table (`42P01` targeting table `"orders"`) to `missing_table`.
   - Ensures missing database (`3D000`), missing role (`28000`), missing schema (`3F000`), and non-orders undefined tables do **NOT** map to `missing_table` (they map to `database_error` or `authentication_failed`).
   - Maps statement timeout, lock timeout, and cancellation (`57014`, `55P03`) to `operation_timeout`.
   - Redacts all passwords and DSN credentials in diagnostic outputs, exceptions, and logs.
3. **Scoped Container Startup**:
   - `nextrace_lab/controller.py` starts and stops **only** `postgres`, `order-service`, and `gateway`, leaving database volumes (`nextrace_pgdata`) and Inventory containers intact.
4. **Live Container Execution & Readiness**:
   - Started `nextrace-postgres` (`postgres:16-alpine`), `nextrace-order-service`, and `nextrace-gateway`.
   - Probed Gateway readiness (`200 OK`, `upstream_order_service: reachable`).
   - Probed Order Service readiness (`200 OK`, `database_connectivity: ok` probing real PostgreSQL via `SELECT 1 FROM orders LIMIT 1;`).
   - Verified diagnostic DB config: `db_driver: postgresql`, `statement_timeout_ms: 1500`, `lock_timeout_ms: 1000`, `connect_timeout_sec: 1.5`, with passwords redacted.
5. **Live Order Submission & Verification**:
   - Submitted `product_id="sku-docker-pg-test-1"`, `quantity=3` through `POST http://127.0.0.1:18000/orders`. Gateway forwarded to Order Service, returning HTTP `201 Created` with `order_id="ord-e8082c0b9c"`.
6. **Direct PostgreSQL Storage Verification**:
   - Queried PostgreSQL directly inside the container via `docker exec nextrace-postgres psql`, confirming the exact row (`ord-e8082c0b9c`, `sku-docker-pg-test-1`, `quantity=3`, `req-003e5a65f045`) was persisted.
7. **Gateway Order Lookup Verification**:
   - Retrieved `GET http://127.0.0.1:18000/orders/ord-e8082c0b9c`, returning HTTP `200 OK` with the matching record.
8. **Live Timeout Cancellation & Classification Verification**:
   - Verified against the live PostgreSQL server that `options="-c statement_timeout=300"` cancels long-running queries (`SELECT pg_sleep(1)`) with `QueryCanceled` (SQLSTATE `57014`), correctly mapped to `operation_timeout`.

> [!NOTE]
> Testing and validating the Orders application in Docker does **not** mark the entire project's multi-application Docker milestone complete. Inventory application containerization and fault injection scenarios remain decoupled.

---

## 2. Docker Host Environment Details

- **Host OS**: Windows 11 (`10.0.26300`)
- **Host Python**: Python 3.14.7
- **Docker Engine Version**: `29.9.2` (build `a82e528`)
- **Docker Compose Version**: `v5.6.1`
- **Docker Desktop Version**: `4.97.0` (WSL 2 backend: Linux kernel `6.18.54.1-microsoft-standard-WSL2`)
- **CLI Binary Location**: `C:\Users\dhiraj\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`

---

## 3. Implementation Details

### 3.1 PostgreSQL Driver Integration & Query Timeouts (`services/order_service/db.py`)
- Dispatches based on `cfg.driver.lower()`:
  - Supports `local_tcp` / `sqlite_tcp` (preserving local mode).
  - Supports `postgresql` / `postgres` (using `psycopg`).
  - Rejects unsupported drivers explicitly with `ValueError`.
- Added configurable bounded query execution parameters to `DatabaseConfig`:
  - `connect_timeout_sec: float` (environment `DB_CONNECT_TIMEOUT_SEC`)
  - `statement_timeout_ms: int` (environment `DB_STATEMENT_TIMEOUT_MS`)
  - `lock_timeout_ms: int` (environment `DB_LOCK_TIMEOUT_MS`)
- PostgreSQL connection setup sets session options:
  ```python
  def _connect_postgresql(cfg: DatabaseConfig) -> psycopg.Connection:
      return psycopg.connect(
          host=cfg.host,
          port=cfg.port,
          dbname=cfg.dbname,
          user=cfg.user,
          password=cfg.password,
          connect_timeout=max(1, int(round(cfg.connect_timeout_sec))),
          options=f"-c statement_timeout={int(cfg.statement_timeout_ms)} -c lock_timeout={int(cfg.lock_timeout_ms)}",
      )
  ```
- Write transaction isolation and rollback:
  ```python
  try:
      with _connect_postgresql(cfg) as conn:
          with conn.cursor() as cur:
              cur.execute(...)
          conn.commit()
  except Exception as exc:
      try:
          conn.rollback()
      except Exception:
          pass
      raise _map_psycopg_exception(exc, cfg) from exc
  ```

### 3.2 SQLSTATE-Based Error Classification
- Exception mapper `_map_psycopg_exception(exc, cfg)` categorizes:
  - Undefined orders table: `sqlstate == "42P01"` and `"orders"` relation -> `missing_table`.
  - Non-orders undefined table: `sqlstate == "42P01"` -> `database_error`.
  - Missing database / schema: `sqlstate in ("3D000", "3F000")` -> `database_error`.
  - Authentication failure: `sqlstate in ("28000", "28P01")` or authentication message -> `authentication_failed`.
  - Query / Lock timeout: `sqlstate in ("57014", "55P03")` or cancel message -> `operation_timeout`.
  - Connection refused: `sqlstate in ("08001", "08006")` or socket error `10061` / `111` -> `connection_refused`.
  - DNS / Host resolution: `gaierror` / `Name or service not known` -> `hostname_resolution_failed`.
  - Passwords and connection secrets are strictly redacted across all error details.

### 3.3 Scoped Orders Startup in Controller (`nextrace_lab/controller.py`)
- Constrains Orders Docker startup to:
  ```powershell
  docker compose -f docker-compose.yml up -d --build postgres order-service gateway
  ```
- Constrains Orders Docker shutdown to:
  ```powershell
  docker compose -f docker-compose.yml stop postgres order-service gateway
  ```
  *(Preserves container states and persistent volumes without data loss).*

---

## 4. Live Verification Evidence & Command Outputs

### 4.1 Running Containers Status
Command executed:
```powershell
docker compose ps
```
Output:
```text
NAME                     IMAGE                    COMMAND                  SERVICE         STATUS                    PORTS
nextrace-gateway         nextrace-gateway:latest  "uvicorn services.ga..." gateway         Up 5 minutes              0.0.0.0:18000->8000/tcp
nextrace-order-service   nextrace-order-service   "uvicorn services.or..." order-service   Up 5 minutes              0.0.0.0:18001->8001/tcp
nextrace-postgres        postgres:16-alpine       "docker-entrypoint.s..." postgres        Up 5 minutes (healthy)    0.0.0.0:15432->5432/tcp
```

### 4.2 Gateway Readiness Probe
Command: `GET http://127.0.0.1:18000/health/ready`  
Output (HTTP 200):
```json
{
  "service": "gateway",
  "status": "ready",
  "upstream_order_service": "reachable",
  "latency_ms": 43.68,
  "timestamp": "2026-10-31T19:15:41.871187Z"
}
```

### 4.3 Order Service Readiness & Database Connectivity Probe
Command: `GET http://127.0.0.1:18001/health/ready`  
Output (HTTP 200):
```json
{
  "service": "order-service",
  "status": "ready",
  "database_connectivity": "ok",
  "latency_ms": 212.74,
  "timestamp": "2026-10-31T19:15:41.772360Z"
}
```

Command: `GET http://127.0.0.1:18001/internal/diagnostics/db-config`  
Output (HTTP 200):
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
  "timestamp": "2026-10-31T19:15:41.427653Z"
}
```

### 4.4 Order Submission Through Gateway
Request:
```http
POST http://127.0.0.1:18000/orders
Content-Type: application/json

{
  "product_id": "sku-docker-pg-test-1",
  "quantity": 3
}
```

Response (HTTP 201 Created):
```json
{
  "order_id": "ord-e8082c0b9c",
  "product_id": "sku-docker-pg-test-1",
  "quantity": 3,
  "request_id": "req-003e5a65f045",
  "created_at": "2026-10-31 19:16:17.813844+00"
}
```

### 4.5 Direct PostgreSQL Container Query
Command:
```powershell
docker exec nextrace-postgres psql -U nextrace_user -d nextrace_orders -c "SELECT order_id, product_id, quantity, request_id, created_at FROM orders WHERE order_id = 'ord-e8082c0b9c';"
```

Direct Output:
```text
    order_id    |      product_id      | quantity |    request_id    |          created_at           
----------------+----------------------+----------+------------------+-------------------------------
 ord-e8082c0b9c | sku-docker-pg-test-1 |        3 | req-003e5a65f045 | 2026-10-31 19:16:17.813844+00
(1 row)
```

### 4.6 Order Retrieval via Gateway
Request: `GET http://127.0.0.1:18000/orders/ord-e8082c0b9c`  
Response (HTTP 200 OK):
```json
{
  "order_id": "ord-e8082c0b9c",
  "product_id": "sku-docker-pg-test-1",
  "quantity": 3,
  "request_id": "req-003e5a65f045",
  "created_at": "2026-10-31 19:16:17.813844+00"
}
```

### 4.7 Live PostgreSQL Statement Timeout Cancellation
Command:
```powershell
cd "D:\Avishkar Nextrace\nextrace"
@'
import psycopg
from services.order_service.db import DatabaseConfig, _map_psycopg_exception

cfg = DatabaseConfig(
    driver="postgresql",
    host="127.0.0.1",
    port=15432,
    dbname="nextrace_orders",
    user="nextrace_user",
    password="nextrace_local_dev_pw",
    statement_timeout_ms=300,
    lock_timeout_ms=200,
)

try:
    with psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        options="-c statement_timeout=300 -c lock_timeout=200",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_sleep(1);")
except Exception as exc:
    err = _map_psycopg_exception(exc, cfg)
    print(f"exception_type: {type(exc).__name__}")
    print(f"sqlstate: {getattr(exc, 'sqlstate', None)}")
    print(f"error_category: {err.error_category}")
    print(f"detail: {err.detail}")
'@ | python
```

Output:
```text
exception_type: QueryCanceled
sqlstate: 57014
error_category: operation_timeout
detail: PostgreSQL operation exceeded timeout (statement_timeout=300ms, lock_timeout=200ms): canceling statement due to statement timeout
```

---

## 5. Automated Regression Test Suite

All unit and integration tests pass cleanly with 100% success rate on Python 3.14.7:
- **Unit tests**: **34 / 34 passed** in `0.83s` (`python -m pytest tests/test_unit.py`).
  - Includes tests for driver dispatch, SQLSTATE error classification, bounded timeout settings, transaction rollback on write error, and credential redaction.
- **Local integration tests**: **6 / 6 passed** in `113.98s` (`python -m pytest tests/test_integration.py`).
  - Verifies local mode fault scenarios (Faults A, B, C, D, E, F, Stage 6 recovery, and multi-fault) end-to-end.

---

## 6. How to Stop the Orders Containers (Preserving Data)

To stop the running Orders services without deleting the database volume (`nextrace_pgdata`):
```powershell
cd "D:\Avishkar Nextrace\nextrace"
docker compose stop postgres order-service gateway
```

To view container logs if needed:
```powershell
docker compose logs -f order-service
docker compose logs -f gateway
docker compose logs -f postgres
```
