# Everest Textile Mills: Software Architecture Guide & Evaluator Defense Playbook

---

## 1. Ground-Up Fundamentals: How Modern Web Software is Built

When an evaluator asks about routes, controllers, and authentication, they are testing your understanding of the **Separation of Concerns**—how data moves across the application layers:

```
[ FRONTEND (UI Client) ]
       │  HTTP Request (Method + URL + Headers with JWT + JSON Body)
       ▼
[ ROUTER ] ───────────► Matches endpoint path (/api/v1/yarn/inward)
       │
       ▼
[ MIDDLEWARE (Auth & RBAC) ] ──► Validates JWT token & checks role permissions
       │
       ▼
[ CONTROLLER ] ────────► Validates input schema, extracts parameters
       │
       ▼
[ SERVICE / DOMAIN LOGIC ] ────► Runs business rules & calculations
       │
       ▼
[ DATABASE (SQL / ORM) ] ──────► ACID transaction (INSERT / UPDATE)
       │
       ▲  HTTP Response (Status 200/201/400/409 + JSON payload)
[ FRONTEND STATE ] ────► Re-renders UI reactively without page reload
```

### Core Concepts Demystified

* **Frontend:** The client interface (browser application). It manages visual components, form validations, optimistic UI updates, and makes asynchronous network calls (`fetch` or `axios`).
* **Routes:** The server's traffic address book. It pairs an HTTP verb with a URL path (e.g., `POST /api/v1/yarn/inward`, `GET /api/v1/machines/floor-map`). A route contains no business logic; it merely directs incoming requests to the designated controller.
* **Controllers:** The orchestrators. A controller takes the incoming request (`req`), extracts parameters (`req.body`, `req.params`), validates data types against schemas (Pydantic / Zod / DTOs), calls the business logic/service layer, and returns an HTTP response with a status code (e.g., `201 Created` or `400 Bad Request`).
* **Authentication vs. Authorization (RBAC):**
  * *Authentication (Who are you?):* Verifies identity using credentials, returning a signed JSON Web Token (JWT) or session cookie.
  * *Authorization / Role-Based Access Control (What can you do?):* Checks if the user's role permits the requested action (e.g., a *Store Manager* can inward yarn, while an *External Buyer* has read-only access to order tracking).
* **Middleware:** Functions that sit in the request pipeline before the controller. Middleware checks CORS policies, parses JSON bodies, validates JWT tokens, and enforces rate limits.
* **Models / Database:** The persistence layer. Relational tables connected by foreign keys to ensure data consistency and prevent orphaned records.

---

## 2. Mapping the Everest Textile Mills Problem Statement to Architecture

Each scene from the challenge maps directly to RESTful endpoints, controller functions, and real-world edge cases:

| Mill Workflow Scene | HTTP Verb & Route | Controller Handler | Authorized Role | Key Edge Cases Handled |
| :--- | :--- | :--- | :--- | :--- |
| **1. Yarn Arrives at the Gate** | `POST /api/v1/yarn/inward` | `YarnController.inwardDelivery` | `store_manager`, `admin` | Validates gatepass, enforces unique vehicle/lot constraints to prevent double-inwarding, auto-clears low-stock alert. |
| **1b. Stock & Low-Stock Alerts** | `GET /api/v1/yarn/stock` | `YarnController.getStockStatus` | `all_roles` | Compares current stock against the 250 kg safety buffer; flags immediate replenishment warning. |
| **2. Production Floor Mid-Shift** | `GET /api/v1/machines/floor-map` | `MachineController.getFloorMap` | `all_roles` | Computes live machine status across Spinning, Weaving, and Dyeing without walking the floor. |
| **2b. Machine Breakdown** | `PATCH /api/v1/machines/:id/breakdown` | `MachineController.logBreakdown` | `floor_supervisor` | Pauses order timers, prevents scheduling jobs on halted machines, logs downtime for MTTR tracking. |
| **3. Fabric QC Before Dispatch** | `POST /api/v1/qc/inspect-roll` | `QualityController.recordInspection` | `qc_inspector` | 4-Point inspection logging; maintains complete traceability back to loom and yarn lot; flags scrap/rework. |
| **4. Buyer Inquiries** | `GET /api/v1/orders/:id/track` | `OrderController.trackMilestones` | `buyer`, `sales` | Real-time production milestone stepper (Spinning → Weaving → Dyeing → QC → Dispatch) with live ETA. |
| **5. Truck Loading & Dispatch** | `POST /api/v1/dispatch/create` | `DispatchController.dispatchTruck` | `store_manager` | **Atomic Guard:** Prevents duplicate roll dispatch across trucks; matches invoice against buyer PO. |
| **6. Owner Closing the Books** | `GET /api/v1/finance/pnl-summary` | `FinanceController.getMonthlyBook` | `owner` | Unifies raw material costs, machine energy, and shift labor wages against invoiced revenue for unit margins. |

---

## 3. Interactive Evaluator Feature: Live Architecture Inspector

In the running web application (`http://localhost:8000/`), there is an interactive tool: **"INSPECT ROUTE & ARCHITECTURE"** in the top navigation bar.

When clicked, an **Architecture Inspector Drawer** slides out displaying:
1. **Active HTTP Endpoint Contract** (Verb + URI)
2. **Controller Handler Signature** & Schema Validation specification
3. **Middleware & Role-Based Access Control (RBAC)** state
4. **Exact SQL / ACID Transaction Query**
5. **Key Invariants and Edge Cases Handled** (Double-dispatch locks, safety buffers, ASTM grading)

As you navigate between scenes (Yarn Gate, Floor Telemetry, Quality QC, Dispatch, Buyer Portal, Finance), the Architecture Drawer dynamically updates its context!

---

## 4. Evaluator Presentation & Defense Playbook

When presenting to the evaluator, use this structured flow:

### Step 1: Address the Problem Directly
> *"Sir, we focused on building a clean, decoupled architecture solving the six core operational bottlenecks of Everest Textile Mills. Instead of isolated screens, every view is backed by strict RESTful route contracts, role-based access control, and transactional integrity."*

### Step 2: Open the Live Application and Show the Inspector
1. Open `http://localhost:8000/`.
2. Click **"INSPECT ROUTE & ARCHITECTURE"** in the top bar.
3. Switch between tabs (Gate Inward, Floor Machines, QC Inspection, Dispatch Dock, Buyer Portal, Finance Costing).
4. Point out the live route (`POST /api/v1/yarn/inward`), the controller logic (`YarnController.inwardDelivery`), and the database transaction.

### Step 3: Demonstrate Critical Invariants
1. **Anti-Double Dispatch Guard**:
   * Navigate to Scene 4 (Truck Dispatch).
   * Attempt to dispatch an already-loaded or rejected roll.
   * Point out the database transaction lock (`SELECT ... FOR UPDATE`) that returns `HTTP 409 Conflict`.
2. **ASTM D5430 Fabric Inspection**:
   * Show that grading is mathematically calculated using points per 100 meters, not subjective guesses.
3. **Activity-Based Costing**:
   * In Scene 6, explain how machine overhead and kWh power draw are absorbed into unit cost per meter.
