# NexTrace Technical Specification (`v0.4.0`)

**Repository**: `D:\Avishkar Nextrace\nextrace`  
**Phase**: Phase 4 — Correctness, Reproducibility & Validation Milestone  
**Frozen Protocol**: [`artifacts/protocols/v0.4.0_frozen_protocol.json`](file:///D:/Avishkar%20Nextrace/nextrace/artifacts/protocols/v0.4.0_frozen_protocol.json)  
**Source Manifest Digest (SHA-256)**: `857542095a090c6fb040654dd4fbe8f0f5e345131d367f62b931c1817fe493de`  

---

## 1. System Architecture & Dual Application Topology

NexTrace evaluates evidence-based fault localization across two connected distributed application topologies:

### 1A. Application 1 (`orders_app`)
- **Gateway** (`services/gateway/app.py`, FastAPI :18000): Entry routing, validation, and forwarding.
- **Order Service** (`services/order_service/app.py`, FastAPI :18001): Business logic, order persistence, and database interactions.
- **Database Backend**:
  - Local mode: SQLite-over-TCP server (`nextrace_lab/local_db_server.py`, port 15432).
  - Docker mode: PostgreSQL 16 container (`docker-compose.yml`, port 15432) initialized with `db/init_orders.sql`.

### 1B. Application 2 (`inventory_app`)
- **Inventory API** (`services/inventory_app/api_app.py`, FastAPI :18010): Entry routing and inventory reservation endpoints.
- **Inventory Service** (`services/inventory_app/inventory_service_app.py`, FastAPI :18011): Stock validation, cache lookups, and database persistence.
- **Backends**:
  - Local mode: SQLite-over-TCP database (port 15433) and local TCP cache substitute (`nextrace_lab/local_cache_server.py`, port 16379).
  - Docker mode: PostgreSQL 16 (`inventory-db`, port 15433) initialized with `db/init_inventory.sql`, and Redis 7 Alpine (`inventory-cache`, port 16379) using raw RESP protocol parsing.

---

## 2. Temporal Evidence Representation & Evidence Gate

### 2A. Timestamped Evidence Model (`nextrace_lab/schemas.py`, `nextrace_lab/temporal.py`)
Every `DiagnosticCheckResult` records:
- `event_time_utc`: When the underlying event occurred (e.g. from service log header or snapshot metadata).
- `collection_time_utc`: When the diagnostic check probe executed.
- `evaluation_time_utc`: When the evidence evaluator processed the observation.
- `observation_interval_start_utc` / `observation_interval_end_utc`: Time span represented by the observation.
- `freshness_ttl_sec` and `is_stale`: Dynamically evaluated based on elapsed simulated/monotonic time.
- `is_superseded` and `superseded_by_evidence_id`: Explicitly marks earlier observations rendered obsolete by a fresher observation from the same source.
- `timestamp_uncertain`: Flags observations where clock synchronization or log formatting does not permit trustworthy temporal ordering.

### 2B. Incident Window Filtering & Current Health Separation
`IncidentContext` defines bounds `[incident_window_start - clock_skew, incident_window_end + clock_skew]` (default skew tolerance: 2.0s).
- **Incident-Window Cause Attribution**: Only log events, metrics, or traces with timestamps falling inside the incident window can be cited as supporting root causes.
- **Current Health Assessment**: Relies strictly on fresh, non-superseded probe results (`get_service_health`, `get_endpoint_health`).
- **Conflict Detection**: Explicitly detects `within_run_repeat_change` (mid-run recoveries) and `historical_vs_live_probe` (stale error logs vs healthy current state).

---

## 3. Centralized Stopping Policy (`nextrace_lab/stopping_policy.py`)

All diagnostic investigation stop/continue decisions are decoupled from selector implementations and centralized in `nextrace_lab/engine.py` using `evaluate_stopping_policy`:
- **`first_supported_cause`**: Halts investigation immediately when the evidence gate confirms a single supported root cause or honest inconclusive state.
- **`investigate_additional_causes`**: Continues investigation after identifying a supported cause to search for concurrent, secondary, or masked faults across unprobed components until the budget is exhausted or all components are verified.
- **`fixed_no_early_stop`**: Used by historical fixed checklists to execute the pre-configured sequence until sequence completion or budget exhaustion.
- **`legacy_phase3_v1`**: Preserves exact Phase 3 behavior for backward compatibility.

---

## 4. Cost Accounting & Versioning Framework

### 4A. Explicit Version Identifiers
All artifacts, schemas, and reports record:
- `method_version`: `v1` (historical) or `v2` (Phase 4).
- `cost_model_version`: `attempt_charged_v2` (charges declared catalog cost for all admitted attempts including unavailable and failed checks) or `legacy_free_unavailable_v1`.
- `stopping_policy_version`: `stopping_policy_v2`.
- `evidence_gate_version`: `evidence_gate_v2`.
- `evidence_policy_version`: `E0_v2` .. `E5_v2`.
- `content_manifest_digest_sha256`: SHA-256 digest of tracked codebase files.

### 4B. Isolated Single-Factor Ablations
- **`scored_adaptive_v2`**: Full utility scoring:
  $$U(c) = \frac{(D(c) + \text{staleness\_refresh\_bonus}) \times \text{availability\_factor} \times \text{reliability\_factor}}{\text{normalized\_cost}}$$
- **`scored_no_cost_v2`**: Isolates the cost term by setting `normalized_cost = 1.0` while preserving availability and reliability factors unchanged.
- **`scored_no_avail_v2`**: Isolates availability by setting `availability_factor = 1.0` while preserving cost and reliability factors unchanged.
- **`scored_no_reliability_v2`**: Isolates reliability by setting `reliability_factor = 1.0` while preserving cost and availability factors unchanged.

---

## 5. Honest & Bounded AI Evaluation (`nextrace_lab/ai_selector.py`)

- **Strict Method Separation**:
  - `ai_live_v1`: Pure live model calls without fallback (`allow_fallback=False`).
  - `ai_hybrid_fallback_v1`: Explicitly labeled hybrid method with fallback to `scored_adaptive_v2` upon provider budget or network failure.
  - `mock_ai_offline_v1`: Offline deterministic test adapter for schema validation and prompt regression testing without live provider calls.
- **Safety Ceilings & Ledger**:
  - Requires pre-configured model pricing before any run enforcing USD caps can proceed.
  - Configures `max_retries=0` on client SDKs to prevent hidden token consumption.
  - Protects against prompt-injection telemetry by using structured JSON schemas and strict allowlisted check validation.
