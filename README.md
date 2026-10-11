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

## 3. Security, Authentication & Role-Based Access Control (RBAC)

ETMS enforces a zero-trust, role-governed operational model. When the application launches or when switching personas, users enter the **Full-Screen Industrial Security & Access Terminal**:

* **Ambient Video Transition Backdrop:** Plays `frontend/public/videos/login-transition.mp4` with a dark-glass radial gradient overlay.
* **OOP Role-Based Permissions (Zero `if-else` sprawl):** Encapsulated in `backend/app/auth.py` via polymorphic classes (`AdminRole`, `OwnerRole`, `FloorSupervisorRole`, `CustomerRole`).
* **Strict Feature Isolation:** Selecting a persona automatically unlocks only authorized modules and locks down restricted pages.
* **Demo Credentials & Evaluator 1-Click Badges:**
  | Operational Persona | Username | Default Password | Primary Authorized Focus |
  | :--- | :--- | :--- | :--- |
  | **🛡️ System Admin** | `admin` | `admin123` | Full Mill Orchestration (Yarn, Machines, ASTM QC, Fleet, Orders, Demands, P&L) |
  | **👑 Mill Owner / CFO** | `owner` | `everest2026` | ₹ Activity-Based Unit Economics, Gross Margin Speedometer, Electricity Burn |
  | **⚡ Floor Supervisor** | `supervisor` | `floor2026` | RPM & Picks IoT Telemetry, Idle Alarms, ASTM 4-Point QC Bench |
  | **🛍️ Customer / Buyer** | `buyer` | `buyer2026` | Commercial Demands, Feasibility Engine, Live Lifecycle Stepper (Zero Phone Calls) |

---

## 4. The 6 Operational Scenes (SOPs)

### Scene 1: Production Floor HUD & Loom Telemetry (`/floor/live-map`)
* **Actor:** Floor Supervisor
* **Background Layer:** Ambient full-width loom video loop (`machine-scene-background.mp4`) with calibrated contrast and low-opacity dark-glass lighting.
* **Capabilities:**
  * Real-time telemetry monitoring for spinning frames (`SPIN-FRAME-01..02`), airjet looms (`WEAVE-LOOM-01..04`), and dyeing vats (`DYE-VAT-01..02`).
  * Live metrics: RPM, Picks Cumulative, Active Current Draw (Amps), and Idle Seconds.
  * **Automatic 120-Second Idle Warning:** Workstations idling over 120s flash an amber alert border (`@keyframes idle-amber-flash`).
  * **Integrated Edge Telemetry Simulator:** Single-click buttons to inject telemetry pulses (+12 picks/s) or toggle looms between `RUNNING` and `IDLE`.
  * Overall Equipment Effectiveness (OEE) score calculation (Availability × Performance × Quality = 88.4%).

### Scene 2: Gate Inward Intake & Safety Stock Ledger (`/gate/inward`)
* **Actor:** Inward Store Incharge
* **Background Layer:** Amber-gold radial thread luster glow.
* **Capabilities:**
  * Digital platform floor scale weigh-in simulation.
  * Books incoming yarn pallets (Cotton, Polyester, Viscose, Spun Blends) into raw material inventory.
  * **Safety Stock Alert Banner:** Automatically flags yarn lots when `current_stock_kg < safety_stock_threshold_kg` (e.g. `LOT-POLY-401` at 185 kg vs 250 kg minimum threshold).

### Scene 3: Quality Control & ASTM D5430 4-Point Roll Grading (`/qc/inspect`)
* **Actor:** Quality Inspector
* **Background Layer:** High-resolution fabric texture (`qc-fabric-texture.jpg`).
* **Capabilities:**
  * Barcode scanning of fabric rolls (e.g. `ROLL-081-PENDING-03`).
  * **ASTM D5430 4-Point Defect Grader:** Penalizes defects (Holes, Uneven Weaving, Color Mismatch, Slubs, Oil Stains) and automatically computes Grade A, Grade B, Grade C, or Reject.
  * **Upstream Root-Cause Lineage Trace:** Inspecting any failed roll reveals the source Loom (`WEAVE-LOOM-04`), Shift Operator (`OP-812`), and Raw Yarn Batch (`LOT-COTTON-992`).
  * **1-Click Loom Hold:** Dispatches an emergency calibration maintenance order to the offending machine.

### Scene 4: Fleet Trucks & Heavy Commercial Transport (`/warehouse/dispatch`)
* **Actor:** Dispatch Clerk
* **Background Layer:** Heavy Commercial Fleet yard banner with authentic multi-axle Eicher, Tata 1613, and Ashok Leyland trucks (`fleet-trucks.png`).
* **Capabilities:**
  * Displays transport vehicles with unique registered license plates, tare weights, and payload capacities (3.5T to 16.0T).
  * **Smart AI Route Consolidation:** Analyzes active dispatch orders; automatically recommends combining shipments bound for the same hub (e.g. Mumbai Port / Surat Hub) to eliminate redundant fuel burn and tolls.
  * **Anti-Double Dispatch Lock:** If a roll is already dispatched (e.g. `ROLL-081-DISPATCHED-02`), triggers a **harsh klaxon sound effect** and an urgent **"CRITICAL: DOUBLE DISPATCH BLOCKED!"** security modal.
  * **QC Verification Invariant:** Uninspected (`PENDING`) or `REJECTED` rolls are strictly blocked from loading.

### Scene 5: Customer Demands, Deadlines & Order Transparency Portal (`/customer/demands` & `/customer/track`)
* **Actor:** Buyer / Customer (e.g. Zara Sourcing / Inditex, Marks & Spencer, Arvind Mills)
* **Design System & Visual Spec (Fraunces Luxury Textile Cards):**
  * **Card 1 (Order & Buyer):** Interactive woven fabric swatch box (`repeating-linear-gradient` that rotates on hover) and fabric chips.
  * **Card 2 (Target Quantity):** Real-time tape measure visualizer with sliding pin indicator calibrated to passed meters.
  * **Card 3 (Passed QC Rolls):** 16-segment inspection status bar lighting up green as rolls pass ASTM inspection.
  * **Card 4 (Completion ETA):** Circular progress ring showing deadline dates and automated lead-time calculation.
* **Commercial Demand & Quotation Intake:**
  * Direct intake form calculating capacity feasibility against mill daily loom rate ($1,200\text{ m/day}$ baseline).
  * Evaluates delivery deadlines: `ON_SCHEDULE`, `TIGHT_SCHEDULE`, or `OVERCAPACITY_RISK`.
  * Multi-stage pipeline stepper: Order Confirmed ➔ Yarn Staged ➔ Spinning ➔ Weaving Active ➔ ASTM QC ➔ Dispatched.

### Scene 6: Activity-Based Costing (ABC) & Financial Closing (`/owner/financial-rollup`)
* **Actor:** Mill Owner / CFO
* **Capabilities:**
  * True dynamic formula in Indian Rupees (₹ INR):
    $$\text{Actual Unit Cost} = \frac{\text{Direct Raw Yarn Consumed} + \text{Floor Wages} + \text{Loom Energy \& Depreciation} + \text{Scrap Loss}}{\text{Passed Production Meters}}$$
  * Contract Gross Profit Margin speedometer (e.g. 22.7% margin on ₹225/m selling price).
  * **Visual Waterfall Chart:** Displays exact monetary rollup across materials, wages, machine overhead, defect waste, and final net profit.

---

## 5. Media Pipeline & Asset Architecture
* **`frontend/public/videos/login-transition.mp4`**: Factory floor transition clip powering the login security terminal.
* **`frontend/public/videos/machine-scene-background.mp4`**: Ambient real-time loom operation loop behind floor machines.
* **`frontend/public/fleet-trucks.png`**: High-resolution Indian commercial truck fleet staged in the dispatch yard.
* **`frontend/public/qc-fabric-texture.jpg`**: High-resolution woven fabric texture behind ASTM inspection benches.
* **`frontend/public/login-textile-pattern.jpg`**: Industrial woven textile weave header inside the login dialog.

---

## 6. Verification & Invariant Matrix

| Invariant Rule | Verification Mechanism | Test Function (`test_invariants.py`) |
| :--- | :--- | :--- |
| **Inventory Non-Negativity** | DB Check constraint `current_stock_kg >= 0` | `test_safety_stock_threshold_alert` |
| **Roll Traceability Lineage** | Enforced Foreign Key on `machine_id` & `order_id` | `test_astm_qc_grading_and_lineage_trace` |
| **No Dispatch of Uninspected Fabric** | HTTP 400 rejection unless `qc_status == 'PASSED'` | `test_rejection_of_uninspected_roll_dispatch` |
| **Zero Double-Dispatches** | Unique row lock & constraint on `roll_id` in `dispatch_items` | `test_concurrency_lock_prevents_double_dispatch` |
| **Customer Transparency Access** | Self-service tracking & demands endpoint | `test_customer_order_tracking_portal` |
| **Activity-Based Costing Accuracy** | True multi-variable cost rollup in ₹ INR | `test_activity_based_costing_calculation` |

---

## 7. How to Run the System

### Option A: Next.js Modern Industrial Frontend (Port 3000)
```bash
# In frontend/ directory
npm run dev -- -p 3000
```
Runs the full responsive Next.js application with Turbopack, live role switching modal, IoT telemetry, Fraunces KPI cards, and embedded video streaming.

### Option B: Full-Stack Python FastAPI Backend (Port 8000)
```bash
# 1. Activate Virtual Environment
.venv/Scripts/activate

# 2. Start Core API Server
uvicorn backend.app.main:app --port 8000
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
