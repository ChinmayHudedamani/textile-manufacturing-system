"""
Quality Control & ASTM D5430 Inspection Router (Scene 3).
Routes:
- GET  /api/v1/quality/rolls
- POST /api/v1/quality/inspect (or /api/v1/qc/inspect-roll)
- GET  /api/v1/quality/trace/{roll_barcode}
"""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models import (
    FabricRoll, DispatchItem, CustomerOrder, Machine, MaterialAllocation, RawMaterialBatch, CustomerNotification
)
from backend.app.schemas import QCVerdictDTO, FabricRollResponse

router = APIRouter(tags=["Quality Control & ASTM D5430"])


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


@router.get("/api/v1/quality/rolls", response_model=List[FabricRollResponse])
async def list_fabric_rolls(db: AsyncSession = Depends(get_db)):
    """Returns fabric rolls across all orders with QC verdicts."""
    stmt = (
        select(FabricRoll, DispatchItem)
        .outerjoin(DispatchItem, FabricRoll.roll_id == DispatchItem.roll_id)
        .order_by(FabricRoll.produced_at.desc())
    )
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


@router.post("/api/v1/quality/inspect")
@router.post("/api/v1/qc/inspect-roll")
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


@router.get("/api/v1/quality/trace/{roll_barcode}")
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


class NewRollDTO(BaseModel):
    order_id: str
    machine_id: str
    length_meters: float
    gross_weight_kg: float
    operator_id: Optional[str] = "OP-WEAVER-01"


@router.post("/api/v1/quality/rolls")
async def create_fabric_roll(payload: NewRollDTO, db: AsyncSession = Depends(get_db)):
    """Logs production of a new physical fabric roll at the loom."""
    count_stmt = select(FabricRoll)
    existing_rolls = (await db.execute(count_stmt)).scalars().all()
    next_idx = len(existing_rolls) + 1
    barcode = f"ROLL-{payload.machine_id}-{next_idx:04d}"

    new_roll = FabricRoll(
        roll_id=str(uuid.uuid4()),
        roll_barcode=barcode,
        order_id=payload.order_id,
        machine_id=payload.machine_id,
        operator_id=payload.operator_id,
        length_meters=payload.length_meters,
        gross_weight_kg=payload.gross_weight_kg,
        qc_status="PASSED",
        defect_type="NONE",
        defect_points=0,
        produced_at=datetime.utcnow()
    )
    db.add(new_roll)
    await db.commit()
    return {
        "status": "CREATED",
        "roll_id": new_roll.roll_id,
        "roll_barcode": new_roll.roll_barcode,
        "length_meters": payload.length_meters
    }


@router.delete("/api/v1/quality/rolls/{roll_id}")
async def delete_fabric_roll(roll_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes a fabric roll record."""
    stmt = select(FabricRoll).where(
        (FabricRoll.roll_id == roll_id) | (FabricRoll.roll_barcode == roll_id)
    )
    res = await db.execute(stmt)
    roll = res.scalar_one_or_none()
    if not roll:
        raise HTTPException(status_code=404, detail="Roll not found.")
    await db.delete(roll)
    await db.commit()
    return {"status": "DELETED", "roll_id": roll_id}

