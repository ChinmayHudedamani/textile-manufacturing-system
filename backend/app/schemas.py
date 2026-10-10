from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class InwardYarnDTO(BaseModel):
    lot_number: str = Field(..., description="Unique supplier yarn lot identifier")
    supplier_name: str = Field(..., description="Yarn spinning mill or distributor")
    material_type: str = Field("COTTON_COMBED", description="Fiber blend type")
    color_code: str = Field("#FFFFFF", description="Yarn color hex code or shade reference")
    weight_kg: float = Field(..., gt=0, description="Gross pallet net yarn weight in kg")
    cost_per_kg: float = Field(..., gt=0, description="Invoiced cost per kg in USD/INR")
    safety_stock_threshold_kg: Optional[float] = Field(250.0, ge=0)

class RawMaterialBatchResponse(BaseModel):
    batch_id: str
    lot_number: str
    supplier_name: str
    material_type: str
    color_code: str
    received_weight_kg: float
    current_stock_kg: float
    cost_per_kg: float
    safety_stock_threshold_kg: float
    is_safety_stock_triggered: bool
    inward_date: datetime

class TelemetryUpdateDTO(BaseModel):
    machine_id: str
    state: str = Field("RUNNING", description="RUNNING, IDLE, MAINTENANCE, FAULT")
    picks_cumulative: int = Field(..., ge=0)
    current_draw_amps: float = Field(..., ge=0)
    rpm: Optional[int] = Field(650, ge=0)
    idle_seconds: Optional[int] = Field(0, ge=0)
    timestamp_epoch_ms: Optional[int] = None

class MachineResponse(BaseModel):
    machine_id: str
    stage: str
    rated_capacity_rpm: int
    current_status: str
    assigned_order_id: Optional[str]
    overhead_hourly_rate: float
    current_picks_cumulative: int
    current_power_draw_amps: float
    current_rpm: int
    idle_seconds: int
    is_idle_alert: bool
    last_heartbeat: Optional[datetime]

class QCVerdictDTO(BaseModel):
    roll_barcode: str
    verdict: str = Field(..., description="PASSED, REWORK, REJECTED")
    defect_type: Optional[str] = Field("NONE", description="NONE, HOLE, COLOR_MISMATCH, UNEVEN_WEAVING, CONTAMINATION, SLUB, OIL_STAIN")
    defect_points: Optional[int] = Field(0, ge=0, description="ASTM D5430 4-point penalty score")
    operator_id: Optional[str] = "OP-AUTO"

class FabricRollResponse(BaseModel):
    roll_id: str
    roll_barcode: str
    order_id: str
    machine_id: str
    operator_id: str
    length_meters: float
    gross_weight_kg: float
    qc_status: str
    defect_type: str
    defect_points: int
    astm_grade: str
    inspection_timestamp: Optional[datetime]
    produced_at: datetime
    is_dispatched: bool

class DispatchScanDTO(BaseModel):
    roll_barcode: str
    truck_plate: str
    invoice_number: str
    dispatched_by: Optional[str] = "DISPATCH_CLERK_1"

class DispatchItemResponse(BaseModel):
    dispatch_id: str
    roll_id: str
    roll_barcode: str
    order_id: str
    truck_license_plate: str
    invoice_number: str
    dispatched_by: str
    dispatched_at: datetime

class CustomerNotificationDTO(BaseModel):
    order_id: str
    milestone_event: str
    channel: str = "PORTAL"
    message_body: str

class CustomerNotificationResponse(BaseModel):
    notification_id: str
    order_id: str
    milestone_event: str
    channel: str
    message_body: str
    sent_at: datetime

class OrderProgressMilestone(BaseModel):
    stage_name: str
    status: str # COMPLETED, ACTIVE, PENDING
    label: str
    description: str
    timestamp: Optional[str]

class CustomerTrackingResponse(BaseModel):
    order_id: str
    order_number: str
    buyer_name: str
    buyer_email: Optional[str]
    fabric_specification: str
    color_hex: str
    target_meters: float
    delivery_deadline: str
    order_status: str
    completion_percentage: float
    passed_meters: float
    rejected_meters: float
    total_rolls_produced: int
    passed_rolls_count: int
    quality_grade_a_rate: float
    milestones: List[OrderProgressMilestone]
    notifications: List[CustomerNotificationResponse]
    dispatched_truck_plate: Optional[str]
    invoice_number: Optional[str]
    dispatched_at: Optional[datetime]

class OrderCostingResponse(BaseModel):
    order_id: str
    order_number: str
    buyer_name: str
    target_meters: float
    total_passed_meters: float
    total_rejected_meters: float
    contract_price_per_meter: float
    direct_material_cost: float
    direct_labor_cost: float
    machine_overhead_cost: float
    scrap_loss_cost: float
    scrap_salvage_credit: float = 0.0
    total_manufacturing_cost: float
    final_cost_per_meter: float
    revenue: float
    gross_profit: float
    gross_margin_percentage: float
    cost_waterfall: List[Dict[str, Any]]
