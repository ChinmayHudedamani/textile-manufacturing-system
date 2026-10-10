-- =====================================================================
-- Everest Textile Manufacturing System (ETMS) - Enterprise DDL
-- Database: PostgreSQL 16
-- Enforces strict relational boundaries, check constraints, & row locks
-- =====================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------
-- 1. ENUM DEFINITIONS
-- ---------------------------------------------------------------------
CREATE TYPE material_type_enum AS ENUM (
    'COTTON_COMBED', 
    'POLYESTER_FILAMENT', 
    'VISCOSE_RAYON', 
    'SPUN_BLEND'
);

CREATE TYPE order_status_enum AS ENUM (
    'ORDER_RECEIVED', 
    'MATERIAL_ALLOCATED', 
    'SPINNING_ACTIVE', 
    'WEAVING_ACTIVE', 
    'DYEING_ACTIVE', 
    'QC_STAGE', 
    'COMPLETED', 
    'DISPATCHED'
);

CREATE TYPE machine_stage_enum AS ENUM (
    'SPINNING', 
    'WEAVING', 
    'DYEING'
);

CREATE TYPE machine_state_enum AS ENUM (
    'IDLE', 
    'RUNNING', 
    'MAINTENANCE', 
    'OFFLINE'
);

CREATE TYPE qc_verdict_enum AS ENUM (
    'PENDING', 
    'PASSED', 
    'REWORK', 
    'REJECTED'
);

CREATE TYPE defect_type_enum AS ENUM (
    'NONE', 
    'HOLE', 
    'COLOR_MISMATCH', 
    'UNEVEN_WEAVING', 
    'CONTAMINATION',
    'SLUB',
    'OIL_STAIN'
);

CREATE TYPE notification_channel_enum AS ENUM (
    'PORTAL',
    'SMS',
    'EMAIL',
    'WEBHOOK'
);

-- ---------------------------------------------------------------------
-- 2. RAW MATERIALS & INWARD LEDGER
-- ---------------------------------------------------------------------
CREATE TABLE raw_material_batches (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_number VARCHAR(64) NOT NULL UNIQUE,
    supplier_name VARCHAR(255) NOT NULL,
    material_type material_type_enum NOT NULL,
    color_code VARCHAR(32) NOT NULL,
    received_weight_kg NUMERIC(12, 3) NOT NULL CHECK (received_weight_kg > 0),
    current_stock_kg NUMERIC(12, 3) NOT NULL CHECK (current_stock_kg >= 0),
    cost_per_kg NUMERIC(10, 2) NOT NULL CHECK (cost_per_kg > 0),
    safety_stock_threshold_kg NUMERIC(12, 3) NOT NULL DEFAULT 250.000,
    inward_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 3. CUSTOMER ORDERS & ALLOCATIONS
-- ---------------------------------------------------------------------
CREATE TABLE customer_orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number VARCHAR(32) NOT NULL UNIQUE,
    buyer_name VARCHAR(255) NOT NULL,
    buyer_email VARCHAR(255),
    fabric_specification VARCHAR(128) NOT NULL,
    color_hex VARCHAR(7) NOT NULL,
    target_meters NUMERIC(10, 2) NOT NULL CHECK (target_meters > 0),
    delivery_deadline DATE NOT NULL,
    order_status order_status_enum NOT NULL DEFAULT 'ORDER_RECEIVED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE material_allocations (
    allocation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES customer_orders(order_id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES raw_material_batches(batch_id) ON DELETE RESTRICT,
    allocated_weight_kg NUMERIC(12, 3) NOT NULL CHECK (allocated_weight_kg > 0),
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 4. MACHINES & OPERATIONAL FLOOR REGISTRY
-- ---------------------------------------------------------------------
CREATE TABLE machines (
    machine_id VARCHAR(32) PRIMARY KEY,
    stage machine_stage_enum NOT NULL,
    rated_capacity_rpm INT NOT NULL,
    current_status machine_state_enum NOT NULL DEFAULT 'IDLE',
    assigned_order_id UUID REFERENCES customer_orders(order_id) ON DELETE SET NULL,
    overhead_hourly_rate NUMERIC(8, 2) NOT NULL DEFAULT 45.00,
    current_picks_cumulative BIGINT NOT NULL DEFAULT 0,
    current_power_draw_amps NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    last_heartbeat TIMESTAMPTZ
);

-- ---------------------------------------------------------------------
-- 5. FABRIC ROLLS & QUALITY ASSURANCE (ASTM D5430)
-- ---------------------------------------------------------------------
CREATE TABLE fabric_rolls (
    roll_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    roll_barcode VARCHAR(64) NOT NULL UNIQUE,
    order_id UUID NOT NULL REFERENCES customer_orders(order_id) ON DELETE RESTRICT,
    machine_id VARCHAR(32) NOT NULL REFERENCES machines(machine_id) ON DELETE RESTRICT,
    operator_id VARCHAR(64) NOT NULL,
    length_meters NUMERIC(10, 2) NOT NULL CHECK (length_meters > 0),
    gross_weight_kg NUMERIC(10, 2) NOT NULL CHECK (gross_weight_kg > 0),
    qc_status qc_verdict_enum NOT NULL DEFAULT 'PENDING',
    defect_type defect_type_enum NOT NULL DEFAULT 'NONE',
    defect_points INT NOT NULL DEFAULT 0 CHECK (defect_points >= 0),
    inspection_timestamp TIMESTAMPTZ,
    produced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 6. OUTBOUND DISPATCH MANIFEST (ANTI-DOUBLE DISPATCH)
-- ---------------------------------------------------------------------
CREATE TABLE dispatch_items (
    dispatch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    roll_id UUID NOT NULL UNIQUE REFERENCES fabric_rolls(roll_id) ON DELETE RESTRICT,
    order_id UUID NOT NULL REFERENCES customer_orders(order_id) ON DELETE RESTRICT,
    truck_license_plate VARCHAR(32) NOT NULL,
    invoice_number VARCHAR(64) NOT NULL,
    dispatched_by VARCHAR(64) NOT NULL,
    dispatched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 7. LABOR SHIFT COSTING LOGS
-- ---------------------------------------------------------------------
CREATE TABLE labor_shift_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    worker_id VARCHAR(64) NOT NULL,
    shift_date DATE NOT NULL,
    hours_worked NUMERIC(5, 2) NOT NULL CHECK (hours_worked > 0),
    hourly_rate NUMERIC(8, 2) NOT NULL CHECK (hourly_rate > 0),
    assigned_order_id UUID NOT NULL REFERENCES customer_orders(order_id) ON DELETE RESTRICT,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 8. CUSTOMER MILESTONE NOTIFICATION LOGS (NEW: GAP 4 FIX)
-- ---------------------------------------------------------------------
CREATE TABLE customer_notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES customer_orders(order_id) ON DELETE CASCADE,
    milestone_event VARCHAR(64) NOT NULL,
    channel notification_channel_enum NOT NULL DEFAULT 'PORTAL',
    message_body TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 9. HIGH-VELOCITY QUERY INDEXES
-- ---------------------------------------------------------------------
CREATE INDEX idx_rolls_order_id ON fabric_rolls(order_id);
CREATE INDEX idx_rolls_qc_status ON fabric_rolls(qc_status);
CREATE INDEX idx_orders_status ON customer_orders(order_status);
CREATE INDEX idx_raw_materials_stock ON raw_material_batches(current_stock_kg);
CREATE INDEX idx_dispatch_invoice ON dispatch_items(invoice_number);
CREATE INDEX idx_dispatch_truck ON dispatch_items(truck_license_plate);
CREATE INDEX idx_notifications_order_id ON customer_notifications(order_id);

-- ---------------------------------------------------------------------
-- 10. REAL-TIME REPORTING VIEWS
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW view_order_progress AS
SELECT 
    co.order_id,
    co.order_number,
    co.buyer_name,
    co.target_meters,
    co.order_status,
    COALESCE(SUM(CASE WHEN fr.qc_status = 'PASSED' THEN fr.length_meters ELSE 0 END), 0) AS passed_meters,
    COALESCE(SUM(CASE WHEN fr.qc_status = 'REJECTED' THEN fr.length_meters ELSE 0 END), 0) AS rejected_meters,
    COUNT(fr.roll_id) AS total_rolls_produced,
    ROUND(
        (COALESCE(SUM(CASE WHEN fr.qc_status = 'PASSED' THEN fr.length_meters ELSE 0 END), 0) / co.target_meters) * 100, 
        2
    ) AS completion_percentage
FROM customer_orders co
LEFT JOIN fabric_rolls fr ON co.order_id = fr.order_id
GROUP BY co.order_id, co.order_number, co.buyer_name, co.target_meters, co.order_status;
