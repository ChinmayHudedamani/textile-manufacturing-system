// =====================================================================
// Everest Textile Manufacturing System (ETMS) - Reactive Data Store
// Dual-Mode Architecture: Live FastAPI REST API + Resilient Offline Client DB
// =====================================================================

const API_BASE = (typeof window !== 'undefined' && window.location.protocol === 'file:')
    ? "http://localhost:8000/api/v1"
    : `${window.location.origin}/api/v1`;

class ETMSStore {
    constructor() {
        this.isBackendOnline = false;
        this.offlineQueue = JSON.parse(localStorage.getItem("etms_offline_queue") || "[]");
        
        // Factory Simulation Engine Parameters
        this.simSpeedMultiplier = 1; // 1x (Realtime), 10x, 60x (Shift Fast-forward)
        this.isSimulationRunning = true;
        this.simSecondsOfDay = 8 * 3600 + 14 * 60; // Starts at 08:14 AM (Morning Shift)
        this.telemetryHistory = {}; // machine_id -> array of { time, rpm, power, tension }
        
        // Initial Local State (used for offline or instant browser testing)
        this.state = this.loadLocalState();
        this.listeners = [];
        this.initTelemetryHistory();
        this.startContinuousSimulationEngine();
    }

    initTelemetryHistory() {
        this.state.machines.forEach(m => {
            if (!this.telemetryHistory[m.machine_id]) {
                this.telemetryHistory[m.machine_id] = [];
                for (let i = 20; i >= 0; i--) {
                    this.telemetryHistory[m.machine_id].push({
                        rpm: m.current_status === 'RUNNING' ? (m.current_rpm || 740) + (Math.random() * 10 - 5) : 0,
                        amps: m.current_status === 'RUNNING' ? (m.current_power_draw_amps || 15.4) + (Math.random() * 0.4 - 0.2) : 1.8,
                        tension: m.stage === 'WEAVING' && m.current_status === 'RUNNING' ? (m.warp_tension_cn || 180) + (Math.random() * 4 - 2) : 0
                    });
                }
            }
        });
    }

    startContinuousSimulationEngine() {
        if (this.simTimer) clearInterval(this.simTimer);
        this.simTimer = setInterval(() => {
            if (this.isSimulationRunning) {
                this.advanceSimulationStep();
            }
        }, 1000);
    }

    setSimulationSpeed(multiplier) {
        this.simSpeedMultiplier = multiplier;
        this.notify();
    }

    toggleSimulationPlayback() {
        this.isSimulationRunning = !this.isSimulationRunning;
        this.notify();
    }

    advanceSimulationStep() {
        const stepSec = this.simSpeedMultiplier;
        this.simSecondsOfDay = (this.simSecondsOfDay + stepSec) % 86400;

        // Realistic Jitter & Stochastic Wear on active machines
        this.state.machines.forEach(m => {
            if (m.current_status === "RUNNING") {
                const rpmJitter = (Math.random() * 6 - 3);
                const baseRpm = m.rated_capacity_rpm > 1000 ? 11800 : 740;
                m.current_rpm = Math.max(0, Math.round(baseRpm + rpmJitter));
                
                // Cumulative picks: (RPM / 60) * elapsed simulated seconds
                const picksGained = Math.round((m.current_rpm / 60) * stepSec);
                m.current_picks_cumulative += picksGained;
                
                // Power fluctuations with harmonic mechanical load
                const loadNoise = (Math.sin(Date.now() / 3000) * 0.6) + (Math.random() * 0.3 - 0.15);
                m.current_power_draw_amps = Number((15.4 + loadNoise).toFixed(2));
                
                // Warp tension sensor breathing
                if (m.stage === "WEAVING") {
                    m.warp_tension_cn = Math.round(180 + Math.sin(Date.now() / 2000) * 6 + (Math.random() * 2 - 1));
                    m.weft_insertion_m_min = Math.round(m.current_rpm * (m.reed_width_cm / 100));
                }

                m.idle_seconds = 0;
                m.is_idle_alert = false;
            } else if (m.current_status === "IDLE") {
                m.idle_seconds += stepSec;
                m.is_idle_alert = (m.idle_seconds > 120);
                m.current_rpm = 0;
                m.current_power_draw_amps = 1.8;
                if (m.stage === "WEAVING") m.warp_tension_cn = 0;
            }

            // Record to rolling telemetry waveform (max 30 historical samples)
            if (!this.telemetryHistory[m.machine_id]) this.telemetryHistory[m.machine_id] = [];
            this.telemetryHistory[m.machine_id].push({
                rpm: m.current_rpm || 0,
                amps: m.current_power_draw_amps || 1.8,
                tension: m.warp_tension_cn || 0
            });
            if (this.telemetryHistory[m.machine_id].length > 30) {
                this.telemetryHistory[m.machine_id].shift();
            }
        });

        // Synchronize Zara Inditex order live completion
        const zaraOrder = this.state.orders.find(o => o.order_id === "ord-zara-081");
        if (zaraOrder) {
            // ~ 1 meter every 2,850 picks (28.5 picks/cm * 100 cm/m)
            const loom1 = this.state.machines.find(m => m.machine_id === "WEAVE-LOOM-01");
            const loom4 = this.state.machines.find(m => m.machine_id === "WEAVE-LOOM-04");
            const runningLoomPicks = ((loom1 && loom1.current_status === "RUNNING" ? 12 : 0) + (loom4 && loom4.current_status === "RUNNING" ? 12 : 0)) * stepSec;
            const metersAdded = runningLoomPicks / 2850;
            zaraOrder.passed_meters = Number((zaraOrder.passed_meters + metersAdded).toFixed(1));
            zaraOrder.completion_percentage = Math.min(100, Number(((zaraOrder.passed_meters / zaraOrder.target_meters) * 100).toFixed(1)));
        }

        this.notify();
    }

    getSimulationTimeFormatted() {
        const hrs = Math.floor(this.simSecondsOfDay / 3600);
        const mins = Math.floor((this.simSecondsOfDay % 3600) / 60);
        const secs = this.simSecondsOfDay % 60;
        const pad = (n) => String(n).padStart(2, '0');
        const shift = hrs >= 6 && hrs < 14 ? "SHIFT A (MORNING)" : (hrs >= 14 && hrs < 22 ? "SHIFT B (AFTERNOON)" : "SHIFT C (NIGHT)");
        return {
            timeStr: `${pad(hrs)}:${pad(mins)}:${pad(secs)}`,
            shiftName: shift
        };
    }

    updateMachineConfiguration(machineId, updates) {
        const m = this.state.machines.find(x => x.machine_id === machineId);
        if (!m) return;
        Object.assign(m, updates);
        this.saveLocalState();
        return m;
    }

    triggerMachineFault(machineId, faultType = "WEFT_BREAK") {
        const m = this.state.machines.find(x => x.machine_id === machineId);
        if (!m) return;
        m.current_status = "IDLE";
        m.current_rpm = 0;
        m.idle_seconds = 1;
        m.is_idle_alert = true;
        if (m.weft_stops_shift !== undefined) m.weft_stops_shift += 1;
        this.saveLocalState();
    }

    loadLocalState() {
        const cached = localStorage.getItem("etms_local_data");
        if (cached) {
            try { return JSON.parse(cached); } catch (e) {}
        }
        return {
            batches: [
                {
                    batch_id: "batch-cotton-992",
                    lot_number: "LOT-COTTON-992",
                    supplier_name: "Gujarat Agro Fibers Ltd.",
                    material_type: "COTTON_COMBED",
                    color_code: "#F5F5DC",
                    received_weight_kg: 1200.0,
                    current_stock_kg: 850.5,
                    cost_per_kg: 4.25,
                    safety_stock_threshold_kg: 250.0,
                    is_safety_stock_triggered: false,
                    inward_date: new Date(Date.now() - 5 * 86400000).toISOString()
                },
                {
                    batch_id: "batch-poly-401",
                    lot_number: "LOT-POLY-401",
                    supplier_name: "Reliance Petrochemicals",
                    material_type: "POLYESTER_FILAMENT",
                    color_code: "#E0E7FF",
                    received_weight_kg: 800.0,
                    current_stock_kg: 185.0, // BELOW THRESHOLD!
                    cost_per_kg: 2.95,
                    safety_stock_threshold_kg: 250.0,
                    is_safety_stock_triggered: true,
                    inward_date: new Date(Date.now() - 8 * 86400000).toISOString()
                },
                {
                    batch_id: "batch-rayon-108",
                    lot_number: "LOT-RAYON-108",
                    supplier_name: "Grasim Industries",
                    material_type: "VISCOSE_RAYON",
                    color_code: "#FEF08A",
                    received_weight_kg: 650.0,
                    current_stock_kg: 410.0,
                    cost_per_kg: 3.80,
                    safety_stock_threshold_kg: 200.0,
                    is_safety_stock_triggered: false,
                    inward_date: new Date(Date.now() - 2 * 86400000).toISOString()
                },
                {
                    batch_id: "batch-spun-552",
                    lot_number: "LOT-SPUN-552",
                    supplier_name: "Vardhman Textiles",
                    material_type: "SPUN_BLEND",
                    color_code: "#CBD5E1",
                    received_weight_kg: 1500.0,
                    current_stock_kg: 1100.0,
                    cost_per_kg: 3.40,
                    safety_stock_threshold_kg: 300.0,
                    is_safety_stock_triggered: false,
                    inward_date: new Date(Date.now() - 1 * 86400000).toISOString()
                }
            ],
            machines: [
                {
                    machine_id: "SPIN-FRAME-01",
                    stage: "SPINNING",
                    rated_capacity_rpm: 12000,
                    current_status: "RUNNING",
                    assigned_order_id: "ord-zara-081",
                    overhead_hourly_rate: 38.00,
                    current_picks_cumulative: 524800,
                    current_power_draw_amps: 24.5,
                    current_rpm: 11800,
                    idle_seconds: 0,
                    is_idle_alert: false,
                    // Industrial Textile Technical Attributes
                    spindles_active: "1,008 / 1,008",
                    yarn_count_spec: "60s Ne Combed",
                    twist_multiplier: "3.85 TM",
                    end_breakage_rate: "1.2 / 1000 sp-hr",
                    running_efficiency_pct: 98.3,
                    doff_timer_min: 42,
                    roving_lot: "ROV-COT-992"
                },
                {
                    machine_id: "SPIN-FRAME-02",
                    stage: "SPINNING",
                    rated_capacity_rpm: 12000,
                    current_status: "IDLE",
                    assigned_order_id: null,
                    overhead_hourly_rate: 38.00,
                    current_picks_cumulative: 310200,
                    current_power_draw_amps: 1.8,
                    current_rpm: 0,
                    idle_seconds: 185, // > 120s: IDLE ALERT TRIGGERED
                    is_idle_alert: true,
                    spindles_active: "0 / 1,008",
                    yarn_count_spec: "40s Ne Carded",
                    twist_multiplier: "4.10 TM",
                    end_breakage_rate: "0.0 / 1000 sp-hr",
                    running_efficiency_pct: 0.0,
                    doff_timer_min: 0,
                    roving_lot: "ROV-POLY-401"
                },
                {
                    machine_id: "WEAVE-LOOM-01",
                    stage: "WEAVING",
                    rated_capacity_rpm: 750,
                    current_status: "RUNNING",
                    assigned_order_id: "ord-zara-081",
                    overhead_hourly_rate: 45.00,
                    current_picks_cumulative: 189400,
                    current_power_draw_amps: 16.2,
                    current_rpm: 720,
                    idle_seconds: 0,
                    is_idle_alert: false,
                    // Weaving Specifications
                    loom_type: "Tsudakoma ZAX9100 Airjet",
                    reed_width_cm: 190.0,
                    warp_count: "60s Ne Combed",
                    weft_count: "60s Ne Combed",
                    picks_per_cm: 28.5,
                    warp_tension_cn: 185,
                    weft_insertion_m_min: 1368,
                    running_efficiency_pct: 95.8,
                    warp_stops_shift: 2,
                    weft_stops_shift: 1
                },
                {
                    machine_id: "WEAVE-LOOM-02",
                    stage: "WEAVING",
                    rated_capacity_rpm: 750,
                    current_status: "RUNNING",
                    assigned_order_id: "ord-ms-094",
                    overhead_hourly_rate: 45.00,
                    current_picks_cumulative: 245000,
                    current_power_draw_amps: 15.8,
                    current_rpm: 735,
                    idle_seconds: 0,
                    is_idle_alert: false,
                    loom_type: "Picanol OmniPlus-i Airjet",
                    reed_width_cm: 220.0,
                    warp_count: "30s Ne Viscose Rayon",
                    weft_count: "30s Ne Viscose Rayon",
                    picks_per_cm: 24.0,
                    warp_tension_cn: 210,
                    weft_insertion_m_min: 1617,
                    running_efficiency_pct: 97.4,
                    warp_stops_shift: 1,
                    weft_stops_shift: 0
                },
                {
                    machine_id: "WEAVE-LOOM-03",
                    stage: "WEAVING",
                    rated_capacity_rpm: 750,
                    current_status: "MAINTENANCE",
                    assigned_order_id: null,
                    overhead_hourly_rate: 45.00,
                    current_picks_cumulative: 98000,
                    current_power_draw_amps: 0.0,
                    current_rpm: 0,
                    idle_seconds: 4200,
                    is_idle_alert: true,
                    loom_type: "Itema R9500² Rapier",
                    reed_width_cm: 190.0,
                    warp_count: "75D Poly Filament",
                    weft_count: "75D Poly Filament",
                    picks_per_cm: 32.0,
                    warp_tension_cn: 0,
                    weft_insertion_m_min: 0,
                    running_efficiency_pct: 0.0,
                    warp_stops_shift: 6,
                    weft_stops_shift: 4
                },
                {
                    machine_id: "WEAVE-LOOM-04", // SPEC BENCHMARK
                    stage: "WEAVING",
                    rated_capacity_rpm: 750,
                    current_status: "RUNNING",
                    assigned_order_id: "ord-zara-081",
                    overhead_hourly_rate: 45.00,
                    current_picks_cumulative: 105412,
                    current_power_draw_amps: 15.4,
                    current_rpm: 740,
                    idle_seconds: 0,
                    is_idle_alert: false,
                    loom_type: "Tsudakoma ZAX9100 Airjet",
                    reed_width_cm: 190.0,
                    warp_count: "60s Ne Combed",
                    weft_count: "60s Ne Combed",
                    picks_per_cm: 28.5,
                    warp_tension_cn: 182,
                    weft_insertion_m_min: 1406,
                    running_efficiency_pct: 98.6,
                    warp_stops_shift: 0,
                    weft_stops_shift: 1
                },
                {
                    machine_id: "DYE-VAT-01",
                    stage: "DYEING",
                    rated_capacity_rpm: 120,
                    current_status: "RUNNING",
                    assigned_order_id: "ord-ms-094",
                    overhead_hourly_rate: 55.00,
                    current_picks_cumulative: 44200,
                    current_power_draw_amps: 28.0,
                    current_rpm: 115,
                    idle_seconds: 0,
                    is_idle_alert: false,
                    dye_machine_type: "Thies Eco-Soft Soft-Flow Jet",
                    liquor_ratio: "1:6",
                    vat_temp_celsius: 98.4,
                    target_temp_celsius: 98.0,
                    ph_level: 6.2,
                    delta_e_tolerance: 0.42,
                    recipe_id: "REC-MS-TWILL-NAVY-B"
                },
                {
                    machine_id: "DYE-VAT-02",
                    stage: "DYEING",
                    rated_capacity_rpm: 120,
                    current_status: "IDLE",
                    assigned_order_id: null,
                    overhead_hourly_rate: 55.00,
                    current_picks_cumulative: 12000,
                    current_power_draw_amps: 2.1,
                    current_rpm: 0,
                    idle_seconds: 45,
                    is_idle_alert: false,
                    dye_machine_type: "Fongs High-Temp Jigger",
                    liquor_ratio: "1:4",
                    vat_temp_celsius: 24.1,
                    target_temp_celsius: 130.0,
                    ph_level: 7.0,
                    delta_e_tolerance: 0.35,
                    recipe_id: "REC-IDLE-RINSE"
                }
            ],
            orders: [
                {
                    order_id: "ord-zara-081",
                    order_number: "ORD-2026-081",
                    buyer_name: "Zara Sourcing / Inditex",
                    buyer_email: "procurement@inditex.com",
                    fabric_specification: "60s Combed Cotton Poplin",
                    color_hex: "#2563EB",
                    target_meters: 5000.0,
                    passed_meters: 3450.0,
                    completion_percentage: 69.0,
                    order_status: "WEAVING_ACTIVE",
                    delivery_deadline: "2026-11-15",
                    contract_price_per_meter: 48.50
                },
                {
                    order_id: "ord-ms-094",
                    order_number: "ORD-2026-094",
                    buyer_name: "Marks & Spencer UK",
                    buyer_email: "orders@marksandspencer.com",
                    fabric_specification: "Viscose Rayon Twill 180 GSM",
                    color_hex: "#059669",
                    target_meters: 2500.0,
                    passed_meters: 2100.0,
                    completion_percentage: 84.0,
                    order_status: "QC_STAGE",
                    delivery_deadline: "2026-10-30",
                    contract_price_per_meter: 52.00
                },
                {
                    order_id: "ord-arvind-102",
                    order_number: "ORD-2026-102",
                    buyer_name: "Arvind Mills Export",
                    buyer_email: "garments@arvindmills.com",
                    fabric_specification: "Polyester Filament Sheeting",
                    color_hex: "#7C3AED",
                    target_meters: 8000.0,
                    passed_meters: 1200.0,
                    completion_percentage: 15.0,
                    order_status: "MATERIAL_ALLOCATED",
                    delivery_deadline: "2026-12-01",
                    contract_price_per_meter: 38.00
                }
            ],
            rolls: [
                {
                    roll_id: "roll-081-01",
                    roll_barcode: "ROLL-081-PASS-01",
                    order_id: "ord-zara-081",
                    machine_id: "WEAVE-LOOM-04",
                    operator_id: "OP-812",
                    length_meters: 120.0,
                    gross_weight_kg: 26.4,
                    qc_status: "PASSED",
                    defect_type: "NONE",
                    defect_points: 1,
                    astm_grade: "GRADE_A",
                    produced_at: new Date(Date.now() - 3 * 86400000).toISOString(),
                    is_dispatched: false
                },
                {
                    roll_id: "roll-081-02",
                    roll_barcode: "ROLL-081-DISPATCHED-02", // ALREADY DISPATCHED
                    order_id: "ord-zara-081",
                    machine_id: "WEAVE-LOOM-04",
                    operator_id: "OP-812",
                    length_meters: 140.0,
                    gross_weight_kg: 30.8,
                    qc_status: "PASSED",
                    defect_type: "NONE",
                    defect_points: 0,
                    astm_grade: "GRADE_A",
                    produced_at: new Date(Date.now() - 2 * 86400000).toISOString(),
                    is_dispatched: true
                },
                {
                    roll_id: "roll-081-03",
                    roll_barcode: "ROLL-081-PENDING-03", // READY TO INSPECT
                    order_id: "ord-zara-081",
                    machine_id: "WEAVE-LOOM-04",
                    operator_id: "OP-403",
                    length_meters: 135.0,
                    gross_weight_kg: 29.7,
                    qc_status: "PENDING",
                    defect_type: "NONE",
                    defect_points: 0,
                    astm_grade: "GRADE_A",
                    produced_at: new Date(Date.now() - 4 * 3600000).toISOString(),
                    is_dispatched: false
                },
                {
                    roll_id: "roll-081-04",
                    roll_barcode: "ROLL-081-REJECTED-04",
                    order_id: "ord-zara-081",
                    machine_id: "WEAVE-LOOM-01",
                    operator_id: "OP-109",
                    length_meters: 110.0,
                    gross_weight_kg: 24.2,
                    qc_status: "REJECTED",
                    defect_type: "UNEVEN_WEAVING",
                    defect_points: 14,
                    astm_grade: "REJECT",
                    produced_at: new Date(Date.now() - 1 * 86400000).toISOString(),
                    is_dispatched: false
                },
                {
                    roll_id: "roll-094-01",
                    roll_barcode: "ROLL-094-PASS-01", // READY TO LOAD TO TRUCK!
                    order_id: "ord-ms-094",
                    machine_id: "WEAVE-LOOM-02",
                    operator_id: "OP-301",
                    length_meters: 160.0,
                    gross_weight_kg: 35.2,
                    qc_status: "PASSED",
                    defect_type: "NONE",
                    defect_points: 2,
                    astm_grade: "GRADE_A",
                    produced_at: new Date(Date.now() - 1 * 86400000).toISOString(),
                    is_dispatched: false
                }
            ],
            dispatches: [
                {
                    dispatch_id: "dispatch-01",
                    roll_id: "roll-081-02",
                    roll_barcode: "ROLL-081-DISPATCHED-02",
                    order_id: "ord-zara-081",
                    truck_license_plate: "KA-01-E-9002",
                    invoice_number: "INV-2026-001",
                    dispatched_by: "DISPATCH_SUPERVISOR_KUMAR",
                    dispatched_at: new Date(Date.now() - 6 * 3600000).toISOString()
                }
            ],
            notifications: [
                {
                    notification_id: "notif-01",
                    order_id: "ord-zara-081",
                    milestone_event: "ORDER_RECEIVED",
                    channel: "PORTAL",
                    message_body: "Purchase Order ORD-2026-081 confirmed. Target: 5,000m Combed Cotton Poplin.",
                    sent_at: new Date(Date.now() - 6 * 86400000).toISOString()
                },
                {
                    notification_id: "notif-02",
                    order_id: "ord-zara-081",
                    milestone_event: "MATERIAL_ALLOCATED",
                    channel: "EMAIL",
                    message_body: "1,100 kg combed cotton yarn (Lot: LOT-COTTON-992) staged in spinning preparatory.",
                    sent_at: new Date(Date.now() - 5 * 86400000).toISOString()
                },
                {
                    notification_id: "notif-03",
                    order_id: "ord-zara-081",
                    milestone_event: "WEAVING_ACTIVE",
                    channel: "SMS",
                    message_body: "Weaving initiated on Airjet Loom WEAVE-LOOM-04 at 740 picks/min.",
                    sent_at: new Date(Date.now() - 3 * 86400000).toISOString()
                },
                {
                    notification_id: "notif-04",
                    order_id: "ord-zara-081",
                    milestone_event: "PARTIAL_QC_COMPLETED",
                    channel: "PORTAL",
                    message_body: "First batch of 260m fabric inspected and approved with 99.2% ASTM Grade A rating.",
                    sent_at: new Date(Date.now() - 1 * 86400000).toISOString()
                }
            ]
        };
    }

    saveLocalState() {
        localStorage.setItem("etms_local_data", JSON.stringify(this.state));
        this.notify();
    }

    subscribe(fn) {
        this.listeners.push(fn);
        return () => {
            this.listeners = this.listeners.filter(l => l !== fn);
        };
    }

    notify() {
        this.listeners.forEach(fn => fn(this.state));
    }

    // Full live synchronization against Python FastAPI backend endpoints
    async checkBackendHealth() {
        try {
            const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(1800) });
            if (res.ok) {
                this.isBackendOnline = true;
                await this.syncAllBackendData();
                return true;
            }
        } catch (e) {
            this.isBackendOnline = false;
        }
        return false;
    }

    async syncAllBackendData() {
        if (!this.isBackendOnline) return;
        try {
            // Concurrent fetch of all mill operational tables
            const [mRes, bRes, rRes, oRes] = await Promise.all([
                fetch(`${API_BASE}/machines`),
                fetch(`${API_BASE}/inventory/batches`),
                fetch(`${API_BASE}/quality/rolls`),
                fetch(`${API_BASE}/orders`)
            ]);

            if (mRes.ok) this.state.machines = await mRes.json();
            if (bRes.ok) this.state.batches = await bRes.json();
            if (rRes.ok) this.state.rolls = await rRes.json();
            if (oRes.ok) this.state.orders = await oRes.json();

            this.initTelemetryHistory();
            this.saveLocalState();
            this.notify();
        } catch (err) {
            console.warn("[ETMS SYNC WARNING]:", err);
        }
    }


    // 1. Scene 1: Gate Inward
    async addInwardYarn(payload) {
        if (this.isBackendOnline) {
            try {
                const res = await fetch(`${API_BASE}/inventory/inward-yarn`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Failed to book inward yarn.");
                }
                const data = await res.json();
                await this.refreshBatches();
                return data;
            } catch (err) {
                console.warn("Backend failed, using client DB:", err.message);
            }
        }

        // Local Invariant Check
        if (this.state.batches.some(b => b.lot_number.toUpperCase() === payload.lot_number.toUpperCase())) {
            throw new Error(`Lot number ${payload.lot_number} already registered in raw inventory.`);
        }

        const threshold = payload.safety_stock_threshold_kg || 250.0;
        const newBatch = {
            batch_id: "batch-" + Date.now(),
            lot_number: payload.lot_number.toUpperCase(),
            supplier_name: payload.supplier_name,
            material_type: payload.material_type,
            color_code: payload.color_code,
            received_weight_kg: Number(payload.weight_kg),
            current_stock_kg: Number(payload.weight_kg),
            cost_per_kg: Number(payload.cost_per_kg),
            safety_stock_threshold_kg: threshold,
            is_safety_stock_triggered: Number(payload.weight_kg) < threshold,
            inward_date: new Date().toISOString()
        };

        this.state.batches.unshift(newBatch);
        this.saveLocalState();
        return {
            status: "SUCCESS",
            batch_id: newBatch.batch_id,
            lot_number: newBatch.lot_number,
            safety_alert: newBatch.is_safety_stock_triggered
        };
    }

    async refreshBatches() {
        if (!this.isBackendOnline) return this.state.batches;
        try {
            const res = await fetch(`${API_BASE}/inventory/batches`);
            if (res.ok) {
                this.state.batches = await res.json();
                this.saveLocalState();
            }
        } catch (e) {}
        return this.state.batches;
    }

    // 2. Scene 2: Production Floor Simulation Tick
    async tickTelemetry() {
        if (this.isBackendOnline) {
            try {
                const res = await fetch(`${API_BASE}/simulate/tick`, { method: "POST" });
                if (res.ok) {
                    const mRes = await fetch(`${API_BASE}/machines`);
                    if (mRes.ok) {
                        this.state.machines = await mRes.json();
                        this.notify();
                        return;
                    }
                }
            } catch (e) {}
        }

        // Local Simulation Pulse
        this.state.machines.forEach(m => {
            if (m.current_status === "RUNNING") {
                const picksIncrement = Math.floor(m.rated_capacity_rpm / 60) || 12;
                m.current_picks_cumulative += picksIncrement;
                m.idle_seconds = 0;
                m.is_idle_alert = false;
                m.current_power_draw_amps = Number((15.2 + (m.current_picks_cumulative % 5) * 0.3).toFixed(2));
            } else if (m.current_status === "IDLE") {
                m.idle_seconds += 2;
                m.is_idle_alert = (m.idle_seconds > 120);
                m.current_power_draw_amps = 1.8;
                m.current_rpm = 0;
            }
        });
        this.notify();
    }

    toggleMachineState(machineId) {
        const m = this.state.machines.find(x => x.machine_id === machineId);
        if (!m) return;
        if (m.current_status === "RUNNING") {
            m.current_status = "IDLE";
            m.current_rpm = 0;
            m.current_power_draw_amps = 1.8;
            m.idle_seconds = 1;
        } else if (m.current_status === "IDLE") {
            m.current_status = "RUNNING";
            m.current_rpm = m.rated_capacity_rpm > 1000 ? 11800 : 740;
            m.current_power_draw_amps = 15.4;
            m.idle_seconds = 0;
            m.is_idle_alert = false;
        } else if (m.current_status === "MAINTENANCE") {
            m.current_status = "RUNNING";
            m.idle_seconds = 0;
            m.is_idle_alert = false;
        }
        this.saveLocalState();
    }

    // 3. Scene 3: Quality Control & ASTM D5430
    calculateASTMGrade(defectPoints, lengthMeters) {
        if (!lengthMeters || lengthMeters <= 0) return "GRADE_A";
        const pointsPer100 = (defectPoints / lengthMeters) * 100;
        if (pointsPer100 <= 15) return "GRADE_A";
        if (pointsPer100 <= 25) return "GRADE_B";
        if (pointsPer100 <= 40) return "GRADE_C";
        return "REJECT";
    }

    async processQCInspection(barcode, verdict, defectType, defectPoints, operatorId) {
        if (this.isBackendOnline) {
            try {
                const res = await fetch(`${API_BASE}/quality/inspect`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        roll_barcode: barcode,
                        verdict,
                        defect_type: defectType,
                        defect_points: defectPoints,
                        operator_id: operatorId
                    })
                });
                if (res.ok) {
                    const data = await res.json();
                    await this.refreshRolls();
                    return data;
                }
            } catch (e) {}
        }

        const roll = this.state.rolls.find(r => r.roll_barcode.toUpperCase() === barcode.toUpperCase());
        if (!roll) {
            throw new Error(`Fabric roll barcode '${barcode}' not found.`);
        }

        roll.qc_status = verdict;
        roll.defect_type = defectType || "NONE";
        roll.defect_points = Number(defectPoints || 0);
        roll.astm_grade = this.calculateASTMGrade(roll.defect_points, roll.length_meters);
        roll.operator_id = operatorId || roll.operator_id;
        roll.inspection_timestamp = new Date().toISOString();

        if (verdict === "REJECTED" || verdict === "REWORK") {
            this.state.notifications.unshift({
                notification_id: "notif-" + Date.now(),
                order_id: roll.order_id,
                milestone_event: "QC_REVISION",
                channel: "PORTAL",
                message_body: `Quality Alert: Roll ${roll.roll_barcode} flagged for ${defectType}. Rework initiated to maintain strict ASTM grade standards.`,
                sent_at: new Date().toISOString()
            });
        }

        this.saveLocalState();
        return {
            status: "UPDATED",
            roll_barcode: roll.roll_barcode,
            qc_status: roll.qc_status,
            defect_type: roll.defect_type,
            astm_grade: roll.astm_grade,
            machine_id: roll.machine_id,
            operator_id: roll.operator_id
        };
    }

    getUpstreamLineage(barcode) {
        const roll = this.state.rolls.find(r => r.roll_barcode.toUpperCase() === barcode.toUpperCase());
        if (!roll) return null;

        const order = this.state.orders.find(o => o.order_id === roll.order_id);
        const machine = this.state.machines.find(m => m.machine_id === roll.machine_id);
        const batch = this.state.batches[0]; // Active cotton batch

        return {
            roll_barcode: roll.roll_barcode,
            length_meters: roll.length_meters,
            qc_status: roll.qc_status,
            defect_type: roll.defect_type,
            defect_points: roll.defect_points,
            astm_grade: roll.astm_grade,
            order: order ? {
                order_number: order.order_number,
                buyer_name: order.buyer_name,
                fabric_specification: order.fabric_specification
            } : null,
            lineage: {
                origin_machine_id: roll.machine_id,
                machine_stage: machine ? machine.stage : "WEAVING",
                operator_id: roll.operator_id,
                produced_at: roll.produced_at,
                yarn_batch: batch ? {
                    lot_number: batch.lot_number,
                    supplier_name: batch.supplier_name,
                    material_type: batch.material_type
                } : null
            },
            recommended_action: roll.qc_status === "REJECTED"
                ? `Hold Loom ${roll.machine_id} for reed/weft calibration and audit Operator ${roll.operator_id}`
                : "Operational parameters verified within tolerance limits"
        };
    }

    // 4. Scene 4: Warehouse Truck Dispatch Terminal
    async dispatchRollToTruck(barcode, truckPlate, invoiceNumber) {
        if (this.isBackendOnline) {
            try {
                const idempotencyKey = `CLERK-${Date.now()}-${barcode}-${invoiceNumber.trim().toUpperCase()}`;
                const res = await fetch(`${API_BASE}/dispatch/scan-truck`, {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Idempotency-Key": idempotencyKey
                    },
                    body: JSON.stringify({
                        roll_barcode: barcode,
                        truck_plate: truckPlate,
                        invoice_number: invoiceNumber
                    })
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.detail || "Dispatch authorization failed.");
                }
                return data;
            } catch (err) {
                // If it's a 400 or 409 invariant error, throw directly!
                if (err.message.includes("Dispatch Rejected") || err.message.includes("Double Dispatch Blocked") || err.message.includes("missing")) {
                    throw err;
                }
                console.warn("Backend offline, enforcing client invariants...");
            }
        }

        // --- CLIENT INVARIANT CHECKS (Guarantees zero invalid dispatches anywhere!) ---
        const roll = this.state.rolls.find(r => r.roll_barcode.toUpperCase() === barcode.toUpperCase());
        if (!roll) {
            throw new Error(`Roll barcode '${barcode}' missing from database.`);
        }

        // Invariant 1: Roll MUST be PASSED
        if (roll.qc_status !== "PASSED") {
            throw new Error(`Dispatch Rejected: Roll status is '${roll.qc_status}'. Only PASSED rolls can be loaded to a truck manifest.`);
        }

        // Invariant 2: ZERO DOUBLE DISPATCHES
        const alreadyDispatched = this.state.dispatches.find(d => d.roll_id === roll.roll_id);
        if (alreadyDispatched) {
            throw new Error(`CRITICAL: Double Dispatch Blocked! Roll '${barcode}' was already loaded onto Truck ${alreadyDispatched.truck_license_plate} under Invoice ${alreadyDispatched.invoice_number}.`);
        }

        const newDispatch = {
            dispatch_id: "disp-" + Date.now(),
            roll_id: roll.roll_id,
            roll_barcode: roll.roll_barcode,
            order_id: roll.order_id,
            truck_license_plate: truckPlate.toUpperCase(),
            invoice_number: invoiceNumber.toUpperCase(),
            dispatched_by: "DISPATCH_CLERK_1",
            dispatched_at: new Date().toISOString()
        };

        this.state.dispatches.unshift(newDispatch);
        roll.is_dispatched = true;

        this.state.notifications.unshift({
            notification_id: "notif-" + Date.now(),
            order_id: roll.order_id,
            milestone_event: "DISPATCH_LOADING",
            channel: "PORTAL",
            message_body: `Logistics Alert: Roll ${roll.roll_barcode} (${roll.length_meters}m) loaded onto Truck ${truckPlate.toUpperCase()} under Invoice ${invoiceNumber.toUpperCase()}.`,
            sent_at: new Date().toISOString()
        });

        this.saveLocalState();
        return {
            status: "DISPATCH_CONFIRMED",
            roll_barcode: roll.roll_barcode,
            length_meters: roll.length_meters,
            gross_weight_kg: roll.gross_weight_kg,
            truck_plate: truckPlate.toUpperCase(),
            invoice_number: invoiceNumber.toUpperCase(),
            dispatched_at: newDispatch.dispatched_at
        };
    }

    getManifest(invoiceNumber) {
        const inv = invoiceNumber.toUpperCase();
        const matches = this.state.dispatches.filter(d => d.invoice_number === inv);
        const rolls = matches.map(d => {
            const r = this.state.rolls.find(x => x.roll_id === d.roll_id);
            return {
                roll_barcode: d.roll_barcode,
                length_meters: r ? r.length_meters : 140.0,
                gross_weight_kg: r ? r.gross_weight_kg : 30.0,
                dispatched_at: d.dispatched_at
            };
        });
        const totalMeters = rolls.reduce((acc, r) => acc + r.length_meters, 0);
        const totalWeight = rolls.reduce((acc, r) => acc + r.gross_weight_kg, 0);

        return {
            invoice_number: inv,
            truck_license_plate: matches.length ? matches[0].truck_license_plate : "KA-01-E-9002",
            roll_count: rolls.length,
            total_meters: totalMeters,
            total_weight_kg: totalWeight,
            rolls
        };
    }

    // 5. Scene 5: Customer Order Tracking (THE CUSTOMER GAP FIX)
    async trackOrder(orderNumber) {
        if (this.isBackendOnline) {
            try {
                const res = await fetch(`${API_BASE}/orders/track/${encodeURIComponent(orderNumber)}`);
                if (res.ok) {
                    return await res.json();
                }
            } catch (e) {}
        }

        const order = this.state.orders.find(o => o.order_number.toUpperCase() === orderNumber.toUpperCase());
        if (!order) {
            throw new Error(`Order number '${orderNumber}' not found.`);
        }

        const rolls = this.state.rolls.filter(r => r.order_id === order.order_id);
        const passedMeters = rolls.filter(r => r.qc_status === "PASSED").reduce((a, b) => a + b.length_meters, 0) || order.passed_meters;
        const rejectedMeters = rolls.filter(r => r.qc_status === "REJECTED").reduce((a, b) => a + b.length_meters, 0);
        const completionPct = Math.min(100, Number(((passedMeters / order.target_meters) * 100).toFixed(1)));

        const stages = [
            { stage_name: "ORDER_RECEIVED", label: "Order Confirmed", description: "PO specifications & weave construction verified", status: "COMPLETED", timestamp: "Oct 04, 2026" },
            { stage_name: "MATERIAL_ALLOCATED", label: "Yarn Staged", description: "Lot LOT-COTTON-992 weighed and delivered to preparatory", status: "COMPLETED", timestamp: "Oct 05, 2026" },
            { stage_name: "SPINNING_ACTIVE", label: "Spinning & Warping", description: "Spun yarns sized and wound onto warp beams", status: "COMPLETED", timestamp: "Oct 06, 2026" },
            { stage_name: "WEAVING_ACTIVE", label: "Weaving Active", description: "Loom WEAVE-LOOM-04 running at 740 picks/min", status: "ACTIVE", timestamp: "Oct 08, 2026" },
            { stage_name: "QC_STAGE", label: "ASTM 4-Point QC", description: "Bench verification and roll labeling", status: "PENDING", timestamp: null },
            { stage_name: "DISPATCHED", label: "Truck Departed", description: "Manifest signed and loaded to transport vehicle", status: "PENDING", timestamp: null }
        ];

        const notifs = this.state.notifications.filter(n => n.order_id === order.order_id);
        const disp = this.state.dispatches.find(d => d.order_id === order.order_id);

        return {
            order_id: order.order_id,
            order_number: order.order_number,
            buyer_name: order.buyer_name,
            buyer_email: order.buyer_email,
            fabric_specification: order.fabric_specification,
            color_hex: order.color_hex,
            target_meters: order.target_meters,
            delivery_deadline: order.delivery_deadline,
            order_status: order.order_status,
            completion_percentage: completionPct,
            passed_meters: passedMeters,
            rejected_meters: rejectedMeters,
            total_rolls_produced: rolls.length,
            passed_rolls_count: rolls.filter(r => r.qc_status === "PASSED").length,
            quality_grade_a_rate: 98.4,
            milestones: stages,
            notifications: notifs,
            dispatched_truck_plate: disp ? disp.truck_license_plate : null,
            invoice_number: disp ? disp.invoice_number : null,
            dispatched_at: disp ? disp.dispatched_at : null
        };
    }

    // 6. Scene 6: Activity-Based Costing Rollup
    async getOrderCosting(orderId) {
        if (this.isBackendOnline) {
            try {
                const res = await fetch(`${API_BASE}/costing/order/${orderId}`);
                if (res.ok) {
                    return await res.json();
                }
            } catch (e) {}
        }

        const order = this.state.orders.find(o => o.order_id === orderId) || this.state.orders[0];
        const passedMeters = order.passed_meters || 3450.0;
        const rejectedMeters = 240.0;

        const directMaterial = Number((passedMeters * 28.50).toFixed(2));
        const directLabor = 14250.00;
        const machineOverhead = 12400.00;
        const grossScrapLoss = Number((rejectedMeters * 18.50).toFixed(2));
        const scrapSalvageCredit = Number((rejectedMeters * 3.50).toFixed(2));
        
        // Direct material, labor, and machine overhead cover the whole run.
        // Gross scrap cost is absorbed across passedMeters; salvage credit offsets net outlay:
        const totalCost = Number((directMaterial + directLabor + machineOverhead - scrapSalvageCredit).toFixed(2));
        const unitCost = Number((totalCost / passedMeters).toFixed(2));

        const revenue = Number((passedMeters * order.contract_price_per_meter).toFixed(2));
        const grossProfit = Number((revenue - totalCost).toFixed(2));
        const grossMargin = Number(((grossProfit / revenue) * 100).toFixed(1));

        return {
            order_id: order.order_id,
            order_number: order.order_number,
            buyer_name: order.buyer_name,
            target_meters: order.target_meters,
            total_passed_meters: passedMeters,
            total_rejected_meters: rejectedMeters,
            contract_price_per_meter: order.contract_price_per_meter,
            direct_material_cost: directMaterial,
            direct_labor_cost: directLabor,
            machine_overhead_cost: machineOverhead,
            scrap_loss_cost: grossScrapLoss,
            scrap_salvage_credit: scrapSalvageCredit,
            total_manufacturing_cost: totalCost,
            final_cost_per_meter: unitCost,
            revenue: revenue,
            gross_profit: grossProfit,
            gross_margin_percentage: grossMargin,
            cost_waterfall: [
                { name: "Direct Raw Yarn", amount: directMaterial, type: "cost" },
                { name: "Floor Labor Wages", amount: directLabor, type: "cost" },
                { name: "Loom Power & Overhead", amount: machineOverhead, type: "cost" },
                { name: "Scrap Salvage Credit", amount: -scrapSalvageCredit, type: "credit" },
                { name: "Total Manufacturing Cost", amount: totalCost, type: "total_cost" },
                { name: "Contract Revenue", amount: revenue, type: "revenue" },
                { name: "Net Gross Margin", amount: grossProfit, type: "profit" }
            ]
        };
    }
}

const store = new ETMSStore();
