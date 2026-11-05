# NexTrace — Live Judge Presentation Runbook & Demo Guide

**Project:** NexTrace — Multi-Application Evidence-Based Root Cause Diagnosis Lab  
**Repository Directory:** `D:\Avishkar Nextrace\nextrace`  
**Host Environment:** Windows 11 (`Python 3.14.7`, `streamlit 1.49.1`, `fastapi 0.141.1`, `uvicorn 0.54.0`)  
**Recommended Demo Mode:** Local Runtime (`--runtime local`, fast, reliable, zero Docker dependency)  
**Interactive Dashboard URL:** [`http://localhost:8501`](http://localhost:8501)

---

## 1. Fast Setup & Launch (VS Code / PowerShell)

Open a PowerShell terminal in VS Code and execute:

```powershell
# 1. Navigate to project root
cd "D:\Avishkar Nextrace\nextrace"

# 2. Set PYTHONPATH to the current repository directory
$env:PYTHONPATH="."

# 3. Start the healthy Inventory application in local mode
python -m nextrace_lab start --runtime local --app inventory_app

# 4. Verify baseline health and database persistence
python -m nextrace_lab verify-healthy --runtime local --app inventory_app

# 5. Launch the Streamlit research dashboard
python -m streamlit run nextrace_lab/dashboard.py --server.port 8501
```

Once the terminal prints `Local URL: http://localhost:8501`, open [`http://localhost:8501`](http://localhost:8501) in your browser.

---

## 2. Main Live Demo Scenario: Redis Cache Outage (`inv_fault_cache_unavailable`)

### 2.1 Demo Configuration
On the dashboard tab **"Interactive Single-Run Investigator"**:

| Dashboard Parameter | Value to Select |
|---|---|
| **Execution Runtime (Sidebar)** | `local` (Default) |
| **Scenario** | `inv_fault_cache_unavailable` (Pre-selected) |
| **Evidence Condition** | `E0` (Full observability) |
| **Diagnostic Budget** | `8` (Cost units) |
| **Diagnostic Method** | `scored_adaptive_v2` (Pre-selected) |
| **Stopping Policy Mode** | `default` (or `first_supported_cause`) |

### 2.2 What to Click in the Dashboard
1. Click the primary blue button: **"Execute Scenario & Diagnose"**.
2. A spinner appears for ~2 seconds while NexTrace injects the fault, sends a live reservation probe, observes the HTTP 503 failure, gathers diagnostic evidence, evaluates candidate utility scores, and reaches a stopping decision.

---

## 3. What to Show & Explain to Judges

### 3.1 Top Metrics Row
Show the judges the six metric tiles rendered at the top:
- **Outcome:** `supported_diagnosis`
- **Failure Class:** `supported_diagnosis`
- **Predicted Causes:** `inventory-cache:cache_service_unavailable`
- **Current Health:** `degraded_or_failing`
- **Budget Used:** `2 / 8` (75% budget remaining — high diagnostic efficiency)
- **Set Precision / Recall:** `1.00 / 1.00` (Perfect root cause attribution)

### 3.2 Evidence Gate & Incident Summary
Highlight the summary banner:
- **Evidence Gate:** `True` — *"Confirmed inventory-cache is unreachable via direct probe and service state."*
- **Incident-Window Diagnosis:** `inventory-cache:cache_service_unavailable`
- **Monotonic Wall-Clock:** `~2.0s` (well within deadline)

### 3.3 Step-by-Step Decision Log (Interactive Table)
Explain the selector's reasoning:
1. **Step 1 — Service Triage:** NexTrace queries `get_service_health(service="inventory-service")`.
   - Result: `ready=False`, `database_connectivity="ok"`, `cache_connectivity="failed"`.
   - The selector immediately refutes database failure hypotheses while corroborating a cache failure hypothesis.
2. **Step 2 — Pinpoint Root Cause:** NexTrace evaluates candidate utility scores and picks `get_service_health(service="inventory-cache")`.
   - Result: `reachable=False`.
   - Directly proves `inventory-cache:cache_service_unavailable`.
3. **Step 3 — Centralized Stopping Policy:** The Evidence Gate certifies sufficient corroborated evidence and triggers `first_supported_cause` termination without wasting additional budget checks.

### 3.4 Candidate Check Utility Scores (Expandable Section)
Open the expander:
`Step 1 Candidate Scores` / `Step 2 Candidate Scores`
- Show judges that checks are prioritized by distinguishing utility:
  $$\text{Utility} = \frac{\text{Distinguishing Power} \times \text{Availability} \times \text{Reliability}}{\text{Cost}}$$
- Low-cost, high-information checks are scheduled before expensive or redundant probes.

### 3.5 Final Hypothesis States
Show the hypothesis tracking table:
- `IH2_INV_CACHE_UNAVAILABLE`: Stance = `SUPPORTED`, Confidence = `HIGH`, Supported by `ev-01, ev-02`.
- `IH1_INV_DB_UNAVAILABLE`: Plausibility reduced to 0; refuted by healthy DB connectivity.

---

## 4. 60-Second Presentation Pitch Script

> *"Judges, modern distributed architectures depend on multiple upstream and downstream services. Here, our Inventory Service relies on PostgreSQL for persistent state and Redis for fast stock reservation caching.*
>
> *We have injected a controlled outage into the Redis Cache (`inventory-cache`). As expected, user checkout requests immediately fail with HTTP 503.*
>
> *Rather than executing an expensive, blind checklist or guessing via ungrounded LLM prompts, NexTrace's `scored_adaptive_v2` selector evaluates candidate probes using information-theoretic distinguishing value normalized by cost.*
>
> *In just two steps consuming only 2 out of 8 budget units, NexTrace probes Inventory Service, verifies that PostgreSQL is healthy while cache connectivity failed, directly confirms that `inventory-cache` is unreachable, satisfies the Evidence Gate, and reaches a certified supported diagnosis of `inventory-cache:cache_service_unavailable` with 100% precision and zero overclaims.*
>
> *All investigations are governed by deterministic evidence gates, monotonic deadlines, and strict data preservation."*

---

## 5. Terminal Backup Commands (If Dashboard Browser is Unavailable)

If presenting from a terminal without a browser, run the exact same workflow via the CLI:

```powershell
cd "D:\Avishkar Nextrace\nextrace"
$env:PYTHONPATH="."

# 1. Start healthy Inventory app
python -m nextrace_lab start --runtime local --app inventory_app

# 2. Verify baseline persistence
python -m nextrace_lab verify-healthy --runtime local --app inventory_app

# 3. Inject Redis Cache Outage
python -m nextrace_lab inject-fault --runtime local inv_fault_cache_unavailable

# 4. Run E0 diagnosis with scored_adaptive_v2 (Budget 8)
python -m nextrace_lab diagnose --runtime local --app inventory_app --evidence E0 --budget 8 --method scored_adaptive_v2

# 5. Reset faults back to healthy state
python -m nextrace_lab reset-faults --runtime local --app inventory_app
```

---

## 6. Safe Reset & Teardown

To restore clean state after a presentation run:

```powershell
# Reset all fault overrides for inventory_app
python -m nextrace_lab reset-faults --runtime local --app inventory_app

# Or stop all local service processes cleanly
python -m nextrace_lab stop --runtime local --app all
```

> [!IMPORTANT]
> **Data Preservation & Safety Guarantee:**  
> NexTrace never runs destructive database operations, `docker compose down -v`, `docker rm`, or image/volume deletions. SQLite and PostgreSQL storage files and cache states are preserved.

---

## 7. Troubleshooting Guide

### Issue 1: "Python is not recognized as an internal or external command"
**Fix:**
- Ensure Python 3.14 is selected in VS Code:
  - Press `Ctrl + Shift + P`
  - Type `Python: Select Interpreter`
  - Select `Python 3.14.7 ('pythoncore-3.14-64')` (`C:\Users\dhiraj\AppData\Local\Python\pythoncore-3.14-64\python.exe`)
- Or use `py` instead of `python`:
  ```powershell
  py -m streamlit run nextrace_lab/dashboard.py --server.port 8501
  ```

### Issue 2: "Port 8501 is already in use"
**Fix:**
Run on an alternate port or terminate the orphan Streamlit process:
```powershell
# Option A: Launch on port 8502
python -m streamlit run nextrace_lab/dashboard.py --server.port 8502

# Option B: Find and stop the PID holding port 8501
netstat -ano | findstr :8501
# Replace <PID> with the process id from the last column:
taskkill /PID <PID> /F
```

### Issue 3: "LabExecutionLock Busy" Error in Dashboard
**Fix:**
If a previous diagnostic run was forcibly canceled mid-execution:
```powershell
# Check lock status
python -m nextrace_lab lock-status

# If lock is stale, manually remove the lock file:
Remove-Item "var/run/lab_execution.lock" -Force -ErrorAction SilentlyContinue
```

### Issue 4: Docker Desktop Unavailable
**Explanation:**
- Docker Desktop is completely optional for this demo.
- Local mode (`--runtime local`) uses SQLite over TCP and local FastAPI microservices, providing the exact same fault scenarios, evidence gates, and diagnostic algorithms with zero reliance on Docker.
- If Docker daemon is stopped, keep the runtime set to `local`.

---

## 8. Summary of Demo Artifacts

| Component | Port | Status | Verification Reference |
|---|---|---|---|
| **Inventory API** | `18010` | Healthy / Live | `GET /health/ready` |
| **Inventory Service** | `18011` | Healthy / Live | `GET /health/ready` |
| **Inventory DB (SQLite TCP)** | `15433` | Reachable | TCP probe |
| **Inventory Cache** | `16379` | Reachable | TCP probe |
| **Research Dashboard** | `8501` | Running (HTTP 200) | [`http://localhost:8501`](http://localhost:8501) |
