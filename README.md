# Everest Textile Manufacturing System (ETMS)

> *One unified software platform to replace notebooks and phone calls across the factory floor.*

[![Live Next.js App](https://img.shields.io/badge/Live%20App-http%3A%2F%2Flocalhost%3A3000-6366f1.svg)](http://localhost:3000)
[![API Server](https://img.shields.io/badge/FastAPI%20Core-http%3A%2F%2Flocalhost%3A8000-0d9488.svg)](http://localhost:8000/docs)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Frontend-Next.js%2016%20%2B%20Turbopack-000000.svg)](https://nextjs.org/)
[![C++20 Edge](https://img.shields.io/badge/Edge%20Daemon-C%2B%2B20%20%2B%20MQTT-00599C.svg)](https://isocpp.org/)
[![IEEE Std 830](https://img.shields.io/badge/Standard-IEEE%20830-green.svg)](https://standards.ieee.org/)
[![IEEE Std 1016](https://img.shields.io/badge/Standard-IEEE%201016-green.svg)](https://standards.ieee.org/)
[![ASTM D5430](https://img.shields.io/badge/Standard-ASTM%20D5430%20QC-orange.svg)](https://www.astm.org/)

---

## 🚀 Evaluator & Judge Quick Access Controls (1-Click Instant Persona Switcher)

Evaluators and judges can test every department across the mill floor seamlessly using the pre-configured credentials or the **1-click quick-select badges** inside the **Industrial Security & Access Terminal**:

| Role | Access Credentials | Permissions & Access Scope |
| :--- | :--- | :--- |
| **🛡️ System Admin** | **Username:** `admin`<br/>**Password:** `admin123` | **Full Mill Orchestration Scope:** Unlocks all 7 factory modules (Raw Yarn Inward, Loom Telemetry, ASTM D5430 Quality Bench, Fleet Logistics Dock, Instant Order Stepper, Commercial Demands Intake, Mill Owner P&L Costing). |
| **👑 Mill Owner / CFO** | **Username:** `owner`<br/>**Password:** `everest2026` | **Executive Financial Scope:** Focus on Activity-Based Costing (ABC) in **₹ INR**, Gross Profit Margin Speedometer, Electricity burn tracking, and high-level order progression. |
| **⚡ Floor Supervisor** | **Username:** `supervisor`<br/>**Password:** `floor2026` | **Shop Floor Execution Scope:** Live Rieter Ring Frames & Picanol Airjet Loom RPM/Picks telemetry, 120-second idle warnings, mid-shift handovers, and ASTM 4-point defect grading. |
| **🛍️ Customer / Buyer** | **Username:** `buyer`<br/>**Password:** `buyer2026` | **Commercial Transparency Scope (Zero Phone Calls):** Direct commercial demand intake with automated loom capacity feasibility (1,200m/day), live order lifecycle stepper, and certified QC roll certificate. |

---

## ⚡ Executive Overview & Problem Domain

Everest Textile Mills manufactures fabric across multi-stage production lines comprising **spinning, weaving, dyeing, and finishing** machines. The legacy operational environment relied on paper registers, floor walks, and phone calls, creating systemic operational gaps:

```
[ Gate Inward ] ──► [ Material Store ] ──► [ Production Floor ] ──► [ QC Station ] ──► [ FG Warehouse ] ──► [ Dispatch ]
 (Notebook Log)       (Stock Outs)         (Unmonitored Downtime)     (Paper Slips)      (Manual Binning)     (Wrong Loads)
```

### Critical Operational Gaps Solved by ETMS
1. **Raw Material Visibility:** Yarn intake was logged in notebooks without reconciliation against active weaving demand, causing stockouts. ETMS enforces **automated safety stock threshold alerts**.
2. **Shop Floor Transparency:** Machine runtime required floor walks, leaving idle capacity hidden. ETMS streams **real-time RPM, picks, and current draw (Amps) telemetry** with ambient loom video backdrops.
3. **Quality & Traceability:** Quality checks recorded on paper slips prevented tracing failed fabric rolls back to their machine or lot. ETMS implements **ASTM D5430 4-point penalty score grading** with full upstream lineage.
4. **Customer Communication (The Critical Fix):** Order tracking was handled over phone calls. ETMS introduces a **Customer Demands & Order Transparency Portal** with live feasibility engines.
5. **Dispatch Integrity:** Finished rolls risked double dispatch. ETMS enforces **hardware-grade row locks, truck payload capacity verification, and AI route consolidation**.
6. **Activity-Based Job Costing:** Invoices, wages, and electrical kWh were logged in separate books. ETMS computes true **Activity-Based Costing (ABC) in Indian Rupees (₹)**.

---

## 🏗️ Polyglot Architecture & Zero `if-else` Design

ETMS separates physical edge acquisition, business core, and user interfaces into a 3-tier polyglot architecture:

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
│ • Object-Oriented RBAC: Class Polymorphism (BaseRole -> AdminRole, etc.)    │
│ • Concurrency: Row-Level Locks (with_for_update) & Optimistic Concurrency   │
│ • Event Engine: Python Asyncio Worker Pool, Pydantic v2 Schema Validation   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTPS / REST APIs (Port 8000)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 3: MODERN INDUSTRIAL PWA (Next.js 16 + Turbopack + Vanilla Glass CSS)  │
│ • Authentic Textile Typography: Fraunces Serif + Manrope Font Suite         │
│ • Media Asset Pipeline: Ambient Loom Loops, Transition Video, Fleet Yard    │
│ • Interactive Visualizers: Woven Swatches, Tape Measurer, 16-Segment Bars   │
│ • Evaluator Drawer: Real-time SQL inspector & edge telemetry injector       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎬 The 6 Operational Scenes & Specialized Modules

### Scene 1: Production Floor HUD & Loom Telemetry (`/floor/live-map`)
* **Actor:** Floor Supervisor
* **Background:** Real-time ambient loom video loop (`machine-scene-background.mp4`) with calibrated contrast and dark-glass radial overlay.
* **Capabilities:**
  * Real-time telemetry monitoring for spinning frames (`SPIN-FRAME-01..04`), airjet looms (`WEAVE-LOOM-01..06`), and dyeing vats (`DYE-VAT-01..03`).
  * Live metrics: RPM, Picks Cumulative, Active Current Draw (Amps), and Idle Seconds.
  * **Automatic 120-Second Idle Warning:** Workstations idling over 120s trigger amber alert borders.
  * **Integrated Edge Telemetry Pulse:** Single-click evaluator button to inject telemetry pulses (+Picks) or test mid-shift handover.

### Scene 2: Gate Inward Intake & Safety Stock Ledger (`/gate/inward`)
* **Actor:** Inward Store Incharge
* **Background:** Amber-gold radial thread luster glow.
* **Capabilities:**
  * Digital platform floor scale weigh-in simulation.
  * Books incoming yarn pallets (Cotton, Polyester, Viscose, Spun Blends) into raw material inventory.
  * **Safety Stock Alert Banner:** Automatically flags yarn lots when `current_stock_kg < safety_stock_threshold_kg`.

### Scene 3: Quality Control & ASTM D5430 4-Point Roll Grading (`/qc/inspect`)
* **Actor:** Quality Inspector
* **Background:** High-resolution fabric texture (`qc-fabric-texture.jpg`).
* **Capabilities:**
  * Barcode scanning of fabric rolls (e.g. `ROLL-081-PENDING-03`).
  * **ASTM D5430 4-Point Defect Grader:** Penalizes defects (Holes, Uneven Weaving, Color Mismatch, Slubs, Oil Stains) and automatically computes Grade A, Grade B, Grade C, or Reject.
  * **Upstream Lineage Trace:** Inspecting any failed roll reveals the source Loom (`WEAVE-LOOM-04`), Shift Operator (`OP-812`), and Raw Yarn Batch (`LOT-COTTON-992`).

### Scene 4: Fleet Trucks & Heavy Commercial Transport (`/warehouse/dispatch`)
* **Actor:** Dispatch Clerk
* **Background:** Real heavy commercial fleet yard banner (`fleet-trucks.png`).
* **Capabilities:**
  * Displays transport vehicles with unique registered license plates, tare weights, and payload capacities (3.5T to 16.0T).
  * **Smart AI Route Consolidation:** Automatically analyzes active dispatch orders and recommends combining shipments bound for the same hub to save fuel and highway tolls.
  * **Anti-Double Dispatch Lock:** If a roll is already dispatched, triggers a harsh klaxon sound effect and an urgent security alert.

### Scene 5: Customer Demands, Deadlines & Order Transparency Portal (`/customer/demands` & `/customer/track`)
* **Actor:** Buyer / Customer (e.g. Zara Sourcing, Marks & Spencer, Arvind Mills)
* **Luxury Textile Design Suite (Fraunces Serif + Manrope):**
  * **Card 1 (Order & Buyer):** Features an interactive woven fabric swatch box (`repeating-linear-gradient` that rotates on hover) and fabric chips.
  * **Card 2 (Target Quantity):** Real-time tape measure visualizer with sliding pin indicator calibrated to passed meters.
  * **Card 3 (Passed QC Rolls):** 16-segment inspection status bar lighting up green as rolls pass ASTM inspection.
  * **Card 4 (Completion ETA):** Circular progress ring showing deadline dates and automated lead-time calculation.
* **Commercial Demand & Feasibility Engine:**
  * Direct intake form evaluating delivery deadlines against mill capacity (1,200 m/day baseline): `ON_SCHEDULE`, `TIGHT_SCHEDULE`, or `OVERCAPACITY_RISK`.
  * Multi-stage pipeline stepper: Order Confirmed ➔ Yarn Staged ➔ Spinning ➔ Weaving Active ➔ ASTM QC ➔ Dispatched.

### Scene 6: Activity-Based Costing (ABC) & Financial Closing (`/owner/financial-rollup`)
* **Actor:** Mill Owner / CFO
* **Capabilities:**
  * Dynamic formula in Indian Rupees (₹ INR):
    $$\text{Actual Unit Cost} = \frac{\text{Direct Raw Yarn Consumed} + \text{Floor Wages} + \text{Loom Energy \& Depreciation} + \text{Scrap Loss}}{\text{Passed Production Meters}}$$
  * Contract Gross Profit Margin speedometer (e.g. 22.7% margin on ₹225/m selling price).
  * **Visual Waterfall Breakdown:** Displays exact monetary rollup across materials, wages, machine overhead, defect waste, and final net profit.

---

## 🎨 Media Pipeline & Visual Assets

| Asset Path | Scene / Target | Visual Role |
| :--- | :--- | :--- |
| `frontend/public/videos/login-transition.mp4` | Access Terminal | Full-screen ambient transition video inside the login security modal. |
| `frontend/public/videos/machine-scene-background.mp4` | Tab 2: Machines | Real-time ambient loom operation video loop with dark-glass contrast filter. |
| `frontend/public/fleet-trucks.png` | Tab 4: Dispatch | High-res commercial Indian transport fleet banner. |
| `frontend/public/qc-fabric-texture.jpg` | Tab 3: QC Bench | Textured fabric weave backdrop behind ASTM D5430 inspection benches. |
| `frontend/public/login-textile-pattern.jpg` | Access Terminal Header | Industrial woven textile header motif inside the authentication dialog. |

---

## 🧪 Verification & Invariant Matrix

| Invariant Rule | Verification Mechanism | Test Function (`test_invariants.py`) |
| :--- | :--- | :--- |
| **Inventory Non-Negativity** | DB Check constraint `current_stock_kg >= 0` | `test_safety_stock_threshold_alert` |
| **Roll Traceability Lineage** | Enforced Foreign Key on `machine_id` & `order_id` | `test_astm_qc_grading_and_lineage_trace` |
| **No Dispatch of Uninspected Fabric** | HTTP 400 rejection unless `qc_status == 'PASSED'` | `test_rejection_of_uninspected_roll_dispatch` |
| **Zero Double-Dispatches** | Unique row lock & constraint on `roll_id` in `dispatch_items` | `test_concurrency_lock_prevents_double_dispatch` |
| **Customer Transparency Access** | Self-service tracking & demands endpoint | `test_customer_order_tracking_portal` |
| **Activity-Based Costing Accuracy** | True multi-variable cost rollup in ₹ INR | `test_activity_based_costing_calculation` |

---

## 💻 Local Development & Quick Start

### 1. Next.js Modern Industrial Frontend (Port 3000)
```bash
cd frontend
npm install
npm run dev -- -p 3000
# Open http://localhost:3000 in any browser
```

### 2. Full-Stack Python FastAPI Backend (Port 8000)
```bash
# In workspace root
.venv/Scripts/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --port 8000
# Interactive Swagger OpenAPI at http://localhost:8000/docs
```

### 3. Run Automated Invariant Tests
```bash
pytest backend/test_invariants.py -v
```

### 4. Full Enterprise Docker Compose Stack
```bash
docker-compose up --build
```

---

## 🛡️ License

Confidential & Proprietary — Hackathon Edition. All rights reserved.
