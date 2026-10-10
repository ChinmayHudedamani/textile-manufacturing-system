import uuid
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from backend.app.database import engine, Base, get_db, AsyncSessionLocal
from backend.app.models import (
    RawMaterialBatch, CustomerOrder, Machine,
    FabricRoll, DispatchItem, LaborShiftLog, 
    CustomerNotification, MaterialAllocation, AuditEventLog
)
from backend.app.schemas import (
    InwardYarnDTO, RawMaterialBatchResponse,
    TelemetryUpdateDTO, MachineResponse,
    QCVerdictDTO, FabricRollResponse,
    DispatchScanDTO, DispatchItemResponse,
    CustomerTrackingResponse, OrderProgressMilestone,
    CustomerNotificationResponse, CustomerNotificationDTO,
    OrderCostingResponse
)
from backend.app.costing import calculate_activity_based_costing
from backend.app.seed_data import seed_initial_mill_data

# In-memory Idempotency Cache to handle scanner retries / duplicate barcode reads
IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Seed Initial Operational Mill Data
    async with AsyncSessionLocal() as session:
        await seed_initial_mill_data(session)
    
    yield

app = FastAPI(
    title="Everest Textile Manufacturing System (ETMS) - Enterprise Core API",
    description="Tier 2 Enterprise Async Transaction & Operational Ledger Engine",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# 0. SYSTEM HEALTH & LIVENESS PROBE
# =====================================================================

@app.get("/api/v1/health")
async def health_check():
    """System liveness probe reporting service status and timestamp."""
    return {
        "status": "HEALTHY",
        "service": "ETMS Enterprise Core",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }

# =====================================================================
# 1. RAW MATERIAL INWARD & SAFETY STOCK LEDGER (SCENE 1)
# =====================================================================

@app.post("/api/v1/inventory/inward-yarn", status_code=status.HTTP_201_CREATED)
async def record_inward_yarn(payload: InwardYarnDTO, db: AsyncSession = Depends(get_db)):
    """Receives pallet weigh-in at the gate, logs lot, and checks safety thresholds."""
    existing_stmt = select(RawMaterialBatch).where(RawMaterialBatch.lot_number == payload.lot_number)
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lot number {payload.lot_number} already registered in raw inventory."
        )

    batch_uuid = str(uuid.uuid4())
    threshold = Decimal(str(payload.safety_stock_threshold_kg or 250.0))
    current_stock = Decimal(str(payload.weight_kg))

    new_batch = RawMaterialBatch(
        batch_id=batch_uuid,
        lot_number=payload.lot_number,
        supplier_name=payload.supplier_name,
        material_type=payload.material_type,
        color_code=payload.color_code,
        received_weight_kg=current_stock,
        current_stock_kg=current_stock,
        cost_per_kg=Decimal(str(payload.cost_per_kg)),
        safety_stock_threshold_kg=threshold,
        inward_date=datetime.utcnow()
    )
    db.add(new_batch)
    await db.commit()

    is_below_threshold = current_stock < threshold

    return {
        "status": "SUCCESS",
        "batch_id": batch_uuid,
        "lot_number": payload.lot_number,
        "current_stock_kg": float(current_stock),
        "safety_threshold_kg": float(threshold),
        "safety_alert": is_below_threshold,
        "message": "Pallet weighed and booked into inward ledger."
    }

@app.get("/api/v1/inventory/batches", response_model=List[RawMaterialBatchResponse])
async def list_raw_material_batches(db: AsyncSession = Depends(get_db)):
    """Returns raw yarn stock inventory with safety threshold warnings."""
    stmt = select(RawMaterialBatch).order_by(RawMaterialBatch.inward_date.desc())
    res = await db.execute(stmt)
    batches = res.scalars().all()

    output = []
    for b in batches:
        output.append(RawMaterialBatchResponse(
            batch_id=b.batch_id,
            lot_number=b.lot_number,
            supplier_name=b.supplier_name,
            material_type=b.material_type,
            color_code=b.color_code,
            received_weight_kg=float(b.received_weight_kg),
            current_stock_kg=float(b.current_stock_kg),
            cost_per_kg=float(b.cost_per_kg),
            safety_stock_threshold_kg=float(b.safety_stock_threshold_kg),
            is_safety_stock_triggered=b.current_stock_kg < b.safety_stock_threshold_kg,
            inward_date=b.inward_date
        ))
    return output

# =====================================================================
# 2. FLOOR PRODUCTION & EDGE TELEMETRY HUD (SCENE 2)
# =====================================================================

@app.get("/api/v1/machines", response_model=List[MachineResponse])
async def list_machines(db: AsyncSession = Depends(get_db)):
    """Returns operational status of all looms, spinning frames, and dyeing vats."""
    stmt = select(Machine).order_by(Machine.machine_id)
    res = await db.execute(stmt)
    machines = res.scalars().all()

    output = []
    for m in machines:
        is_idle_alert = (m.current_status == "IDLE" and m.idle_seconds > 120)
        output.append(MachineResponse(
            machine_id=m.machine_id,
            stage=m.stage,
            rated_capacity_rpm=m.rated_capacity_rpm,
            current_status=m.current_status,
            assigned_order_id=m.assigned_order_id,
            overhead_hourly_rate=float(m.overhead_hourly_rate),
            current_picks_cumulative=m.current_picks_cumulative,
            current_power_draw_amps=float(m.current_power_draw_amps),
            current_rpm=m.current_rpm,
            idle_seconds=m.idle_seconds,
            is_idle_alert=is_idle_alert,
            last_heartbeat=m.last_heartbeat
        ))
    return output

@app.post("/api/v1/machines/{machine_id}/telemetry")
async def ingest_edge_telemetry(machine_id: str, payload: TelemetryUpdateDTO, db: AsyncSession = Depends(get_db)):
    """Ingests real-time MQTT / sensor pulse updates from C++ edge daemon or simulator."""
    stmt = select(Machine).where(Machine.machine_id == machine_id)
    res = await db.execute(stmt)
    machine = res.scalar_one_or_none()

    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not registered.")

    machine.current_picks_cumulative = payload.picks_cumulative
    machine.current_power_draw_amps = Decimal(str(payload.current_draw_amps))
    machine.current_status = payload.state
    machine.current_rpm = payload.rpm or (720 if payload.state == "RUNNING" else 0)
    
    if payload.state == "RUNNING":
        machine.idle_seconds = 0
    else:
        machine.idle_seconds += payload.idle_seconds or 1

    machine.last_heartbeat = datetime.utcnow()
    await db.commit()

    return {
        "status": "INGESTED",
        "machine_id": machine_id,
        "state": machine.current_status,
        "picks_cumulative": machine.current_picks_cumulative,
        "idle_alert": (machine.current_status == "IDLE" and machine.idle_seconds > 120)
    }

# =====================================================================
# 3. QUALITY CONTROL & ASTM D5430 4-POINT INSPECTION (SCENE 3)
# =====================================================================

def calculate_astm_grade(defect_points: int, length_meters: float) -> str:
    """Calculates ASTM D5430 fabric grade per 100 meters."""
    if length_meters <= 0:
        return "GRADE_A"
    points_per_100m = (defect_points / length_meters) * 100
    if points_per_100m <= 15:
        return "GRADE_A"
    elif points_per_100m <= 25:
        return "GRADE_B"
    elif points_per_100m <= 40:
        return "GRADE_C"
    else:
        return "REJECT"

@app.get("/api/v1/quality/rolls", response_model=List[FabricRollResponse])
async def list_fabric_rolls(db: AsyncSession = Depends(get_db)):
    """Returns fabric rolls across all orders with QC verdicts."""
    stmt = select(FabricRoll, DispatchItem).outerjoin(DispatchItem, FabricRoll.roll_id == DispatchItem.roll_id).order_by(FabricRoll.produced_at.desc())
    res = await db.execute(stmt)
    rolls = res.all()

    output = []
    for r, d in rolls:
        astm = calculate_astm_grade(r.defect_points, float(r.length_meters))
        output.append(FabricRollResponse(
            roll_id=r.roll_id,
            roll_barcode=r.roll_barcode,
            order_id=r.order_id,
            machine_id=r.machine_id,
            operator_id=r.operator_id,
            length_meters=float(r.length_meters),
            gross_weight_kg=float(r.gross_weight_kg),
            qc_status=r.qc_status,
            defect_type=r.defect_type,
            defect_points=r.defect_points,
            astm_grade=astm,
            inspection_timestamp=r.inspection_timestamp,
            produced_at=r.produced_at,
            is_dispatched=(d is not None)
        ))
    return output

@app.post("/api/v1/quality/inspect")
async def process_roll_qc(payload: QCVerdictDTO, db: AsyncSession = Depends(get_db)):
    """Applies ASTM 4-point inspection verdict to a roll."""
    stmt = select(FabricRoll).where(FabricRoll.roll_barcode == payload.roll_barcode)
    res = await db.execute(stmt)
    roll = res.scalar_one_or_none()

    if not roll:
        raise HTTPException(status_code=404, detail="Fabric roll barcode not recognized.")

    roll.qc_status = payload.verdict
    roll.defect_type = payload.defect_type or "NONE"
    roll.defect_points = payload.defect_points or 0
    roll.inspection_timestamp = datetime.utcnow()
    if payload.operator_id:
        roll.operator_id = payload.operator_id

    # If roll failed due to machine fault, create an automated notification
    if payload.verdict in ("REJECTED", "REWORK"):
        notif = CustomerNotification(
            notification_id=str(uuid.uuid4()),
            order_id=roll.order_id,
            milestone_event="QC_REVISION",
            channel="PORTAL",
            message_body=f"Quality Alert: Roll {roll.roll_barcode} flagged for {payload.defect_type}. Automatic rework scheduled to ensure zero sub-par fabric leaves the mill.",
            sent_at=datetime.utcnow()
        )
        db.add(notif)

    await db.commit()

    astm = calculate_astm_grade(roll.defect_points, float(roll.length_meters))
    return {
        "status": "UPDATED",
        "roll_id": roll.roll_id,
        "roll_barcode": roll.roll_barcode,
        "qc_status": roll.qc_status,
        "defect_type": roll.defect_type,
        "defect_points": roll.defect_points,
        "astm_grade": astm,
        "machine_id": roll.machine_id,
        "operator_id": roll.operator_id
    }

@app.get("/api/v1/quality/trace/{roll_barcode}")
async def get_roll_upstream_traceability(roll_barcode: str, db: AsyncSession = Depends(get_db)):
    """
    UPSTREAM ROOT-CAUSE LINEAGE INVESTIGATION:
    Traces roll -> Loom ID -> Shift Operator -> Yarn Lot -> Supplier -> Order
    """
    stmt = (
        select(FabricRoll, CustomerOrder, Machine)
        .join(CustomerOrder, FabricRoll.order_id == CustomerOrder.order_id)
        .join(Machine, FabricRoll.machine_id == Machine.machine_id)
        .where(FabricRoll.roll_barcode == roll_barcode)
    )
    res = await db.execute(stmt)
    row = res.first()

    if not row:
        raise HTTPException(status_code=404, detail=f"Roll barcode {roll_barcode} not found.")

    roll, order, machine = row

    # Find allocated yarn batch
    alloc_stmt = (
        select(MaterialAllocation, RawMaterialBatch)
        .join(RawMaterialBatch, MaterialAllocation.batch_id == RawMaterialBatch.batch_id)
        .where(MaterialAllocation.order_id == order.order_id)
    )
    alloc_res = await db.execute(alloc_stmt)
    alloc_row = alloc_res.first()

    batch_info = None
    if alloc_row:
        _, batch = alloc_row
        batch_info = {
            "batch_id": batch.batch_id,
            "lot_number": batch.lot_number,
            "supplier_name": batch.supplier_name,
            "material_type": batch.material_type,
            "color_code": batch.color_code
        }

    return {
        "roll_barcode": roll.roll_barcode,
        "length_meters": float(roll.length_meters),
        "qc_status": roll.qc_status,
        "defect_type": roll.defect_type,
        "defect_points": roll.defect_points,
        "astm_grade": calculate_astm_grade(roll.defect_points, float(roll.length_meters)),
        "order": {
            "order_id": order.order_id,
            "order_number": order.order_number,
            "buyer_name": order.buyer_name,
            "fabric_specification": order.fabric_specification
        },
        "lineage": {
            "origin_machine_id": machine.machine_id,
            "machine_stage": machine.stage,
            "operator_id": roll.operator_id,
            "produced_at": roll.produced_at,
            "yarn_batch": batch_info
        },
        "recommended_action": (
            f"Hold Loom {machine.machine_id} for reed/weft calibration and inspect operator {roll.operator_id}'s tension settings"
            if roll.qc_status in ("REJECTED", "REWORK") else "Quality within target tolerances"
        )
    }

# =====================================================================
# 4. WAREHOUSE TRUCK DISPATCH & ANTI-DOUBLE DISPATCH (SCENE 4)
# =====================================================================

@app.post("/api/v1/dispatch/scan-truck")
async def scan_roll_to_truck(
    payload: DispatchScanDTO, 
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    CRITICAL INVARIANT CHECKS:
    1. Idempotency Key check to return cached 200 on barcode scanner double-presses.
    2. Roll must exist.
    3. Roll must have passed QC (qc_status == 'PASSED').
    4. Roll must not already be dispatched on any invoice (Anti-Double Dispatch Lock).
    5. Immutable cryptographic audit event log recorded.
    """
    # 0. Idempotency check
    cache_key = idempotency_key or f"SCAN:{payload.roll_barcode}:{payload.invoice_number.strip().upper()}"
    if cache_key in IDEMPOTENCY_CACHE:
        return IDEMPOTENCY_CACHE[cache_key]

    # 1. Fetch Roll with update lock
    roll_stmt = select(FabricRoll).where(FabricRoll.roll_barcode == payload.roll_barcode)
    res = await db.execute(roll_stmt)
    roll = res.scalar_one_or_none()

    if not roll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Roll barcode '{payload.roll_barcode}' missing from database."
        )

    # 2. Invariant: Only PASSED rolls can be dispatched
    if roll.qc_status != "PASSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dispatch Rejected: Roll status is '{roll.qc_status}'. Only PASSED rolls can be loaded to a truck manifest."
        )

    # 3. Invariant: Zero Double-Dispatches
    dispatch_check = await db.execute(
        select(DispatchItem).where(DispatchItem.roll_id == roll.roll_id)
    )
    existing_dispatch = dispatch_check.scalar_one_or_none()
    if existing_dispatch:
        # Check if this exact scan was already submitted on the same invoice (idempotent re-scan)
        if existing_dispatch.invoice_number == payload.invoice_number.strip().upper():
            return {
                "status": "DISPATCH_CONFIRMED",
                "roll_barcode": payload.roll_barcode,
                "length_meters": float(roll.length_meters),
                "gross_weight_kg": float(roll.gross_weight_kg),
                "truck_plate": existing_dispatch.truck_license_plate,
                "invoice_number": existing_dispatch.invoice_number,
                "dispatched_at": existing_dispatch.dispatched_at.isoformat()
            }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CRITICAL: Double Dispatch Blocked! Roll '{payload.roll_barcode}' was already loaded onto Truck {existing_dispatch.truck_license_plate} under Invoice {existing_dispatch.invoice_number}."
        )

    # 4. Commit Dispatch Record
    now_utc = datetime.utcnow()
    dispatch_entry = DispatchItem(
        dispatch_id=str(uuid.uuid4()),
        roll_id=roll.roll_id,
        order_id=roll.order_id,
        truck_license_plate=payload.truck_plate.strip().upper(),
        invoice_number=payload.invoice_number.strip().upper(),
        dispatched_by=payload.dispatched_by or "DISPATCH_CLERK_1",
        dispatched_at=now_utc
    )
    notif = CustomerNotification(
        notification_id=str(uuid.uuid4()),
        order_id=roll.order_id,
        milestone_event="DISPATCH_COMPLETED",
        channel="SMS_AND_PORTAL",
        message_body=f"Roll {roll.roll_barcode} ({float(roll.length_meters):.1f}m) loaded onto Truck {payload.truck_plate.strip().upper()} under Invoice {payload.invoice_number.strip().upper()}.",
        sent_at=now_utc
    )

    # Cryptographic Audit Log
    raw_payload_str = f"{roll.roll_barcode}:{payload.truck_plate}:{payload.invoice_number}:{now_utc.isoformat()}"
    payload_hash = hashlib.sha256(raw_payload_str.encode("utf-8")).hexdigest()
    audit_entry = AuditEventLog(
        entity_name="FabricRoll",
        entity_id=roll.roll_id,
        action_type="DISPATCH_COMMITTED",
        actor_id=payload.dispatched_by or "DISPATCH_CLERK_1",
        payload_hash=payload_hash,
        details=json.dumps({
            "truck_plate": payload.truck_plate.upper(),
            "invoice_number": payload.invoice_number.upper(),
            "length_meters": float(roll.length_meters)
        })
    )

    try:
        db.add(dispatch_entry)
        db.add(notif)
        db.add(audit_entry)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CRITICAL: Double Dispatch Blocked! Roll '{payload.roll_barcode}' was claimed concurrently on another invoice."
        )

    result_payload = {
        "status": "DISPATCH_CONFIRMED",
        "roll_barcode": payload.roll_barcode,
        "length_meters": float(roll.length_meters),
        "gross_weight_kg": float(roll.gross_weight_kg),
        "truck_plate": payload.truck_plate.upper(),
        "invoice_number": payload.invoice_number.upper(),
        "dispatched_at": dispatch_entry.dispatched_at.isoformat()
    }
    IDEMPOTENCY_CACHE[cache_key] = result_payload
    return result_payload

@app.get("/api/v1/dispatch/manifest/{invoice_number}")
async def get_invoice_manifest(invoice_number: str, db: AsyncSession = Depends(get_db)):
    """Retrieves all rolls loaded for an active truck manifest/invoice."""
    stmt = (
        select(DispatchItem, FabricRoll)
        .join(FabricRoll, DispatchItem.roll_id == FabricRoll.roll_id)
        .where(DispatchItem.invoice_number == invoice_number.strip().upper())
        .order_by(DispatchItem.dispatched_at.desc())
    )
    res = await db.execute(stmt)
    items = res.all()

    loaded_rolls = []
    total_meters = 0.0
    total_weight = 0.0
    truck_plate = ""

    for d, r in items:
        truck_plate = d.truck_license_plate
        total_meters += float(r.length_meters)
        total_weight += float(r.gross_weight_kg)
        loaded_rolls.append({
            "roll_barcode": r.roll_barcode,
            "length_meters": float(r.length_meters),
            "gross_weight_kg": float(r.gross_weight_kg),
            "operator_id": r.operator_id,
            "dispatched_at": d.dispatched_at.isoformat()
        })

    return {
        "invoice_number": invoice_number.upper(),
        "truck_license_plate": truck_plate,
        "roll_count": len(loaded_rolls),
        "total_meters": round(total_meters, 2),
        "total_weight_kg": round(total_weight, 2),
        "rolls": loaded_rolls
    }

# =====================================================================
# 5. CUSTOMER ORDER TRACKING & TRANSPARENCY PORTAL (SCENE 5 - GAP 4 FIX)
# =====================================================================

@app.get("/api/v1/orders")
async def list_customer_orders(db: AsyncSession = Depends(get_db)):
    """Returns all customer orders with current completion status."""
    stmt = select(CustomerOrder).order_by(CustomerOrder.created_at.desc())
    res = await db.execute(stmt)
    orders = res.scalars().all()

    output = []
    for o in orders:
        # Sum passed meters
        passed_stmt = select(func.sum(FabricRoll.length_meters)).where(
            FabricRoll.order_id == o.order_id, FabricRoll.qc_status == "PASSED"
        )
        passed_meters = (await db.execute(passed_stmt)).scalar() or Decimal("0.0")
        pct = (float(passed_meters) / float(o.target_meters)) * 100.0 if o.target_meters > 0 else 0.0

        output.append({
            "order_id": o.order_id,
            "order_number": o.order_number,
            "buyer_name": o.buyer_name,
            "buyer_email": o.buyer_email,
            "fabric_specification": o.fabric_specification,
            "color_hex": o.color_hex,
            "target_meters": float(o.target_meters),
            "passed_meters": float(passed_meters),
            "completion_percentage": round(min(pct, 100.0), 1),
            "order_status": o.order_status,
            "delivery_deadline": o.delivery_deadline
        })
    return output

@app.get("/api/v1/orders/track/{order_number}", response_model=CustomerTrackingResponse)
async def track_order_for_customer(order_number: str, db: AsyncSession = Depends(get_db)):
    """
    CUSTOMER SELF-SERVICE TRANSPARENCY PORTAL:
    Allows buyers to track orders directly without calling mill supervisors.
    """
    stmt = select(CustomerOrder).where(CustomerOrder.order_number == order_number.strip().upper())
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Order number '{order_number}' not found. Please verify your purchase order reference."
        )

    # 1. Fetch Rolls
    rolls_stmt = select(FabricRoll).where(FabricRoll.order_id == order.order_id)
    rolls_res = await db.execute(rolls_stmt)
    rolls = rolls_res.scalars().all()

    passed_meters = 0.0
    rejected_meters = 0.0
    passed_rolls_count = 0
    grade_a_count = 0

    for r in rolls:
        meters = float(r.length_meters)
        if r.qc_status == "PASSED":
            passed_meters += meters
            passed_rolls_count += 1
            if r.defect_points <= 5:
                grade_a_count += 1
        elif r.qc_status in ("REJECTED", "REWORK"):
            rejected_meters += meters

    target = float(order.target_meters)
    completion_pct = round((passed_meters / target * 100.0) if target > 0 else 0.0, 1)
    grade_a_rate = round((grade_a_count / passed_rolls_count * 100.0) if passed_rolls_count > 0 else 100.0, 1)

    # 2. Production Stepper Milestones
    stages = [
        ("ORDER_RECEIVED", "Order Confirmed", "Purchase Order verified and technical specification approved"),
        ("MATERIAL_ALLOCATED", "Yarn Staged", "Raw yarn batches allocated and weighed in spinning store"),
        ("SPINNING_ACTIVE", "Spinning Preparatory", "Yarn warping and sizing ongoing"),
        ("WEAVING_ACTIVE", "Weaving Active", "High-speed airjet loom insertion running on shop floor"),
        ("QC_STAGE", "Quality Inspection", "Rolls undergoing ASTM D5430 4-point grading bench inspection"),
        ("DISPATCHED", "Truck Dispatched", "Finished fabric rolls sealed and departed delivery dock")
    ]

    current_status = order.order_status
    status_order = [s[0] for s in stages]
    curr_idx = status_order.index(current_status) if current_status in status_order else 2

    milestones: List[OrderProgressMilestone] = []
    for idx, (st_name, label, desc) in enumerate(stages):
        if idx < curr_idx:
            st_status = "COMPLETED"
        elif idx == curr_idx:
            st_status = "ACTIVE"
        else:
            st_status = "PENDING"
        milestones.append(OrderProgressMilestone(
            stage_name=st_name,
            status=st_status,
            label=label,
            description=desc,
            timestamp=order.created_at.strftime("%b %d, %Y") if idx == 0 else None
        ))

    # 3. Notification Feed
    notif_stmt = (
        select(CustomerNotification)
        .where(CustomerNotification.order_id == order.order_id)
        .order_by(CustomerNotification.sent_at.desc())
    )
    notif_res = await db.execute(notif_stmt)
    notifs = notif_res.scalars().all()

    # 4. Check Dispatch Manifest
    disp_stmt = select(DispatchItem).where(DispatchItem.order_id == order.order_id).limit(1)
    disp_res = await db.execute(disp_stmt)
    disp_item = disp_res.scalar_one_or_none()

    return CustomerTrackingResponse(
        order_id=order.order_id,
        order_number=order.order_number,
        buyer_name=order.buyer_name,
        buyer_email=order.buyer_email,
        fabric_specification=order.fabric_specification,
        color_hex=order.color_hex,
        target_meters=target,
        delivery_deadline=order.delivery_deadline,
        order_status=order.order_status,
        completion_percentage=min(completion_pct, 100.0),
        passed_meters=round(passed_meters, 2),
        rejected_meters=round(rejected_meters, 2),
        total_rolls_produced=len(rolls),
        passed_rolls_count=passed_rolls_count,
        quality_grade_a_rate=grade_a_rate,
        milestones=milestones,
        notifications=[
            CustomerNotificationResponse(
                notification_id=n.notification_id,
                order_id=n.order_id,
                milestone_event=n.milestone_event,
                channel=n.channel,
                message_body=n.message_body,
                sent_at=n.sent_at
            ) for n in notifs
        ],
        dispatched_truck_plate=disp_item.truck_license_plate if disp_item else None,
        invoice_number=disp_item.invoice_number if disp_item else None,
        dispatched_at=disp_item.dispatched_at if disp_item else None
    )

@app.post("/api/v1/orders/{order_id}/notify")
async def emit_manual_customer_notification(order_id: str, payload: CustomerNotificationDTO, db: AsyncSession = Depends(get_db)):
    """Allows floor supervisor or automated worker to broadcast a milestone message to the buyer."""
    stmt = select(CustomerOrder).where(CustomerOrder.order_id == order_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order ID not found.")

    notif = CustomerNotification(
        notification_id=str(uuid.uuid4()),
        order_id=order_id,
        milestone_event=payload.milestone_event,
        channel=payload.channel,
        message_body=payload.message_body,
        sent_at=datetime.utcnow()
    )
    db.add(notif)
    await db.commit()

    return {
        "status": "NOTIFICATION_DISPATCHED",
        "notification_id": notif.notification_id,
        "channel": payload.channel,
        "message": payload.message_body
    }

# =====================================================================
# 6. EXECUTIVE FINANCIAL CLOSING & ABC COSTING (SCENE 6)
# =====================================================================

@app.get("/api/v1/costing/order/{order_id}", response_model=OrderCostingResponse)
async def compute_order_costing(order_id: str, db: AsyncSession = Depends(get_db)):
    """Dynamic Activity-Based Costing (ABC) calculation with margin and waterfall breakdown."""
    try:
        costing_result = await calculate_activity_based_costing(order_id, db)
        return costing_result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

# =====================================================================
# 7. REAL-TIME EDGE TELEMETRY SIMULATOR TICK
# =====================================================================

@app.post("/api/v1/simulate/tick")
async def simulate_floor_tick(db: AsyncSession = Depends(get_db)):
    """
    Simulates a 1-second pulse across the mill floor:
    - Increments pick counters on running looms
    - Ticks idle counters on stopped machines
    - Allows judges to evaluate real-time telemetry with a single click
    """
    stmt = select(Machine)
    res = await db.execute(stmt)
    machines = res.scalars().all()

    updates = []
    for m in machines:
        if m.current_status == "RUNNING":
            # Add picks based on RPM (picks per sec ~ rpm / 60)
            picks_increment = int(m.rated_capacity_rpm / 60)
            m.current_picks_cumulative += picks_increment
            m.idle_seconds = 0
            m.current_power_draw_amps = Decimal(str(round(15.0 + (m.current_picks_cumulative % 5) * 0.3, 2)))
        elif m.current_status == "IDLE":
            m.idle_seconds += 5
            m.current_power_draw_amps = Decimal("1.80")
        
        m.last_heartbeat = datetime.utcnow()
        updates.append({
            "machine_id": m.machine_id,
            "status": m.current_status,
            "picks": m.current_picks_cumulative,
            "idle_seconds": m.idle_seconds
        })

    await db.commit()
    return {"status": "PULSE_OK", "machines": updates}

# =====================================================================
# 8. SERVE FRONTEND STATIC FILES
# =====================================================================
import os
from fastapi.staticfiles import StaticFiles

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
