import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class RawMaterialBatch(Base):
    __tablename__ = "raw_material_batches"

    batch_id = Column(String(36), primary_key=True, default=generate_uuid)
    lot_number = Column(String(64), nullable=False, unique=True, index=True)
    supplier_name = Column(String(255), nullable=False)
    material_type = Column(String(32), nullable=False) # COTTON_COMBED, POLYESTER_FILAMENT, etc.
    color_code = Column(String(32), nullable=False)
    received_weight_kg = Column(Numeric(12, 3), nullable=False)
    current_stock_kg = Column(Numeric(12, 3), nullable=False, index=True)
    cost_per_kg = Column(Numeric(10, 2), nullable=False)
    safety_stock_threshold_kg = Column(Numeric(12, 3), nullable=False, default=Decimal("250.000"))
    inward_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    allocations = relationship("MaterialAllocation", back_populates="batch")

class CustomerOrder(Base):
    __tablename__ = "customer_orders"

    order_id = Column(String(36), primary_key=True, default=generate_uuid)
    order_number = Column(String(32), nullable=False, unique=True, index=True)
    buyer_name = Column(String(255), nullable=False)
    buyer_email = Column(String(255), nullable=True)
    fabric_specification = Column(String(128), nullable=False)
    color_hex = Column(String(7), nullable=False, default="#2563EB")
    target_meters = Column(Numeric(10, 2), nullable=False)
    delivery_deadline = Column(String(32), nullable=False)
    order_status = Column(String(32), nullable=False, default="ORDER_RECEIVED", index=True)
    contract_price_per_meter = Column(Numeric(10, 2), nullable=False, default=Decimal("45.00"))
    version_id = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    rolls = relationship("FabricRoll", back_populates="order")
    allocations = relationship("MaterialAllocation", back_populates="order")
    notifications = relationship("CustomerNotification", back_populates="order", cascade="all, delete-orphan")

class MaterialAllocation(Base):
    __tablename__ = "material_allocations"

    allocation_id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("customer_orders.order_id"), nullable=False)
    batch_id = Column(String(36), ForeignKey("raw_material_batches.batch_id"), nullable=False)
    allocated_weight_kg = Column(Numeric(12, 3), nullable=False)
    allocated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    order = relationship("CustomerOrder", back_populates="allocations")
    batch = relationship("RawMaterialBatch", back_populates="allocations")

class Machine(Base):
    __tablename__ = "machines"

    machine_id = Column(String(32), primary_key=True)
    stage = Column(String(32), nullable=False) # SPINNING, WEAVING, DYEING
    rated_capacity_rpm = Column(Integer, nullable=False, default=650)
    current_status = Column(String(32), nullable=False, default="IDLE") # IDLE, RUNNING, MAINTENANCE, OFFLINE
    assigned_order_id = Column(String(36), ForeignKey("customer_orders.order_id"), nullable=True)
    overhead_hourly_rate = Column(Numeric(8, 2), nullable=False, default=Decimal("45.00"))
    current_picks_cumulative = Column(Integer, nullable=False, default=0)
    current_power_draw_amps = Column(Numeric(6, 2), nullable=False, default=Decimal("0.00"))
    current_rpm = Column(Integer, nullable=False, default=0)
    idle_seconds = Column(Integer, nullable=False, default=0)
    last_heartbeat = Column(DateTime, default=datetime.utcnow, nullable=True)

class FabricRoll(Base):
    __tablename__ = "fabric_rolls"

    roll_id = Column(String(36), primary_key=True, default=generate_uuid)
    roll_barcode = Column(String(64), nullable=False, unique=True, index=True)
    order_id = Column(String(36), ForeignKey("customer_orders.order_id"), nullable=False, index=True)
    machine_id = Column(String(32), ForeignKey("machines.machine_id"), nullable=False)
    operator_id = Column(String(64), nullable=False)
    length_meters = Column(Numeric(10, 2), nullable=False)
    gross_weight_kg = Column(Numeric(10, 2), nullable=False)
    qc_status = Column(String(32), nullable=False, default="PENDING", index=True) # PENDING, PASSED, REWORK, REJECTED
    defect_type = Column(String(32), nullable=False, default="NONE") # NONE, HOLE, COLOR_MISMATCH, etc.
    defect_points = Column(Integer, nullable=False, default=0) # ASTM D5430 points
    version_id = Column(Integer, nullable=False, default=1)
    inspection_timestamp = Column(DateTime, nullable=True)
    produced_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    order = relationship("CustomerOrder", back_populates="rolls")
    machine = relationship("Machine")
    dispatch = relationship("DispatchItem", uselist=False, back_populates="roll")

class DispatchItem(Base):
    __tablename__ = "dispatch_items"

    dispatch_id = Column(String(36), primary_key=True, default=generate_uuid)
    roll_id = Column(String(36), ForeignKey("fabric_rolls.roll_id"), nullable=False, unique=True)
    order_id = Column(String(36), ForeignKey("customer_orders.order_id"), nullable=False)
    truck_license_plate = Column(String(32), nullable=False, index=True)
    invoice_number = Column(String(64), nullable=False, index=True)
    dispatched_by = Column(String(64), nullable=False)
    dispatched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    roll = relationship("FabricRoll", back_populates="dispatch")

class LaborShiftLog(Base):
    __tablename__ = "labor_shift_logs"

    log_id = Column(String(36), primary_key=True, default=generate_uuid)
    worker_id = Column(String(64), nullable=False)
    shift_date = Column(String(32), nullable=False)
    hours_worked = Column(Numeric(5, 2), nullable=False)
    hourly_rate = Column(Numeric(8, 2), nullable=False)
    assigned_order_id = Column(String(36), ForeignKey("customer_orders.order_id"), nullable=False)
    logged_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class CustomerNotification(Base):
    __tablename__ = "customer_notifications"

    notification_id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("customer_orders.order_id"), nullable=False, index=True)
    milestone_event = Column(String(64), nullable=False)
    channel = Column(String(32), nullable=False, default="PORTAL") # PORTAL, SMS, EMAIL, WEBHOOK
    message_body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    order = relationship("CustomerOrder", back_populates="notifications")

class AuditEventLog(Base):
    __tablename__ = "audit_event_log"

    event_id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_name = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    action_type = Column(String(32), nullable=False)
    actor_id = Column(String(64), nullable=False)
    payload_hash = Column(String(64), nullable=False) # SHA-256
    details = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
