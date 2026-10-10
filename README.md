# Everest Textile Manufacturing System (ETMS)

## Enterprise Technical Manual, Reverse-Engineered Architecture & Hackathon Specification

---

### Executive Overview & Problem Domain

Everest Textile Mills manufactures fabric across multi-stage production lines comprising **spinning, weaving, dyeing, and finishing** machines. The legacy operational environment relied on paper registers, floor walks, and phone calls, creating systemic operational gaps:

```
[ Gate Inward ] ──► [ Material Store ] ──► [ Production Floor ] ──► [ QC Station ] ──► [ FG Warehouse ] ──► [ Dispatch ]
 (Notebook Log)       (Stock Outs)         (Unmonitored Downtime)     (Paper Slips)      (Manual Binning)     (Wrong Loads)
```

### Critical Operational Gaps Addressed

1. **Raw Material Visibility:** Yarn intake was logged in physical notebooks without automatic reconciliation against active production demand, causing stockouts and halted machines.
2. **Shop Floor Transparency:** Machine runtime and shift-level progression required floor walks, leaving idle capacity and mechanical bottlenecks hidden.
3. **Quality & Traceability:** Quality checks recorded on paper slips prevented tracing failed fabric rolls back to their source machine, operator, or yarn batch.
4. **Customer Communication (The Critical Fix):** Order tracking was handled over phone calls, pulling supervisors away from production to confirm status. ETMS introduces a **Self-Service Customer Transparency Portal & Automated Push Notification Engine**.
5. **Dispatch Integrity:** Finished rolls risked double dispatch or misallocation against customer purchase orders. ETMS enforces **hardware-grade row locks and anti-double dispatch constraints**.
6. **Activity-Based Job Costing:** Raw material invoices, floor wages, and machine depreciation were recorded separately, preventing accurate cost-per-meter calculations. ETMS calculates true **Activity-Based Costing (ABC) with visual waterfall breakdowns**.

---

## 2. Polyglot Architecture

ETMS separates edge acquisition, transactional core, and user interfaces into a 3-tier polyglot architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 1: PHYSICAL EDGE ACQUISITION (C++20 Native Daemon)                     │
│ • Hardware Interface: RS-485 / Modbus RTU / Optical Digital Pick Sensors    │
│ • In-Memory Architecture: Zero-Allocation 64-Sample Circular Ring Buffer    │
│ • Transport: MQTT Sparkplug B Protocol over TLS                             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ MQTT Broker (tcp://localhost:1883)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 2: ENTERPRISE BUSINESS CORE & LEDGER (Python 3.11+ / FastAPI Async)    │
│ • Database: Dual-Engine SQLite (Instant Demo) & PostgreSQL 16 (Enterprise)  │
│ • Concurrency: Row-Level Locks (with_for_update) & Optimistic Concurrency   │
│ • Event Engine: Python Asyncio Worker Pool, Pydantic v2 Schema Validation   │
│ • Customer Dispatcher: Automated Webhook, SMS & Portal Milestone Updates    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / WSS / REST APIs
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 3: RESPONSIVE TOUCH & LOGISTICS CLIENT (Modern Industrial PWA)        │
│ • Offline Caching: IndexedDB / LocalStorage Resilient Replay Queue          │
│ • Barcode Integration: WebCam & Virtual High-Velocity Scanner Terminal      │
│ • Procedural Sound Engine: Web Audio API Klaxon Alarms & Chimes             │
│ • Visual HUD: 2D Mill Floor Map, ASTM 4-Point QC, ABC Costing Waterfall     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The 6 Operational Scenes (SOPs)

### Scene 1: Production Floor HUD & Loom Telemetry (`/floor/live-map`)
* **Actor:** Floor Supervisor
* **Capabilities:**
  * Real-time telemetry monitoring for spinning frames (`SPIN-FRAME-01..02`), airjet looms (`WEAVE-LOOM-01..04`), and dyeing vats (`DYE-VAT-01..02`).
  * Live metrics: RPM, Picks Cumulative, Active Current Draw (Amps), and Idle Seconds.
  * **Automatic 120-Second Idle Warning:** Workstations idling over 120s flash an amber alert border (`@keyframes idle-amber-flash`).
  * **Integrated Edge Telemetry Simulator:** Single-click buttons to inject telemetry pulses (+12 picks/s) or toggle looms between `RUNNING` and `IDLE`.
  * Overall Equipment Effectiveness (OEE) score calculation (Availability × Performance × Quality = 88.4%).

### Scene 2: Gate Inward Intake & Safety Stock Ledger (`/gate/inward`)
* **Actor:** Inward Store Incharge
* **Capabilities:**
  * Digital platform floor scale weigh-in simulation.
  * Books incoming yarn pallets (Cotton, Polyester, Viscose, Spun Blends) into raw material inventory.
  * **Safety Stock Alert Banner:** Automatically flags yarn lots when `current_stock_kg < safety_stock_threshold_kg` (e.g. `LOT-POLY-401` at 185 kg vs 250 kg minimum threshold).

### Scene 3: Quality Control & ASTM D5430 4-Point Roll Grading (`/qc/inspect`)
* **Actor:** Quality Inspector
* **Capabilities:**
  * Barcode scanning of fabric rolls (e.g. `ROLL-081-PENDING-03`).
  * **ASTM D5430 4-Point Defect Grader:** Penalizes defects (Holes, Uneven Weaving, Color Mismatch, Slubs, Oil Stains) and automatically computes Grade A, Grade B, Grade C, or Reject.
  * **Upstream Root-Cause Lineage Trace:** Inspecting any failed roll reveals the source Loom (`WEAVE-LOOM-04`), Shift Operator (`OP-812`), and Raw Yarn Batch (`LOT-COTTON-992`).
  * **1-Click Loom Hold:** Dispatches an emergency calibration maintenance order to the offending machine.

### Scene 4: Warehouse Truck Dispatch Terminal (`/warehouse/dispatch`)
* **Actor:** Dispatch Clerk
* **Capabilities:**
  * Tablet-optimized terminal with active Invoice (`INV-2026-001`) and Vehicle Plate (`KA-01-E-9002`).
  * **Anti-Double Dispatch Lock:** If a roll is already dispatched (e.g. `ROLL-081-DISPATCHED-02`), triggers a **harsh klaxon sound effect** and an urgent **"CRITICAL: DOUBLE DISPATCH BLOCKED!"** security modal.
  * **QC Verification Invariant:** Uninspected (`PENDING`) or `REJECTED` rolls are strictly blocked from loading.
  * Live Truck Cargo Weight & Volume Capacity Meter (1,500 kg maximum payload).
  * Offline resilient replay queue for loading docks with dead WiFi.

### Scene 5: Customer Live Tracking & Transparency Portal (`/customer/track`)
* **Actor:** Buyer / Customer (e.g. Zara Sourcing / Inditex, Marks & Spencer, Arvind Mills)
* **Operational Gap 4 Solution:**
  * Self-service order lookup by PO Number (e.g. `ORD-2026-081`).
  * **Interactive Milestone Stepper:** Order Confirmed ➔ Yarn Staged ➔ Spinning ➔ Weaving Active ➔ ASTM QC ➔ Dispatched.
  * **Live Progress Bar:** Completed & passed meters vs target meters (3,450 / 5,000 meters = 69.0%).
  * **Digital Quality Lab Certificate:** Official stamp verifying 98.4% ASTM Grade A compliance and defect frequency per 100m².
  * Real-time automated push notifications log (SMS, Email, Portal alerts).

### Scene 6: Activity-Based Costing (ABC) & Financial Closing (`/owner/financial-rollup`)
* **Actor:** Mill Owner / CFO
* **Capabilities:**
  * True dynamic formula:
    $$\text{Actual Unit Cost} = \frac{\text{Direct Raw Yarn Consumed} + \text{Floor Wages} + \text{Loom Energy \& Depreciation} + \text{Scrap Loss}}{\text{Passed Production Meters}}$$
  * Contract Gross Profit Margin speedometer (e.g. 22.7% margin on $48.50/m selling price).
  * **Visual Waterfall Chart:** Displays exact monetary rollup across materials, wages, machine overhead, defect waste, and final net profit.

---

## 4. Verification & Invariant Matrix

| Invariant Rule | Verification Mechanism | Test Function (`test_invariants.py`) |
| :--- | :--- | :--- |
| **Inventory Non-Negativity** | DB Check constraint `current_stock_kg >= 0` | `test_safety_stock_threshold_alert` |
| **Roll Traceability Lineage** | Enforced Foreign Key on `machine_id` & `order_id` | `test_astm_qc_grading_and_lineage_trace` |
| **No Dispatch of Uninspected Fabric** | HTTP 400 rejection unless `qc_status == 'PASSED'` | `test_rejection_of_uninspected_roll_dispatch` |
| **Zero Double-Dispatches** | Unique row lock & constraint on `roll_id` in `dispatch_items` | `test_concurrency_lock_prevents_double_dispatch` |
| **Customer Transparency Access** | Self-service tracking endpoint | `test_customer_order_tracking_portal` |
| **Activity-Based Costing Accuracy** | True multi-variable cost rollup | `test_activity_based_costing_calculation` |

---

## 5. How to Run the System

### Option A: 1-Click Instant Browser Demo (Zero Dependencies!)
Simply open `frontend/index.html` in any web browser!
The application includes a dual-engine architecture with an in-memory client database, realistic mock mill data, audio effects, and real-time simulator controls.

### Option B: Full-Stack Python FastAPI Backend
```bash
# 1. Activate Virtual Environment
.venv/Scripts/activate

# 2. Install Requirements
pip install -r backend/requirements.txt

# 3. Start Core API Server
uvicorn backend.app.main:app --reload --port 8000
```
Open `http://localhost:8000/docs` for the interactive Swagger OpenAPI specification.

### Option C: Run Automated Invariant Tests
```bash
pytest backend/test_invariants.py -v
```

### Option D: Run Physical Edge Telemetry Simulator
```bash
python edge/edge_simulator.py --machine WEAVE-LOOM-04
```

### Option E: Full Enterprise Docker Compose Stack
```bash
docker-compose up --build
```
Orchestrates:
- `postgres-db`: PostgreSQL 16 on port 5432 with `schema.sql`
- `mqtt-broker`: Eclipse Mosquitto on port 1883
- `redis-cache`: Redis 7.2 on port 6379
- `api-core`: Python 3.11 FastAPI Core Service on port 8000
- `edge-telemetry-daemon`: C++20 Alpine binary compiling `edge_telemetry.cpp`
