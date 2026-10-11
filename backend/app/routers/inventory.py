"""
Inventory & Raw Yarn Store Router (Scene 1).
Routes:
- POST /api/v1/inventory/inward-yarn (or /api/v1/yarn/inward)
- GET  /api/v1/inventory/batches (or /api/v1/yarn/stock)
"""
import uuid
from decimal import Decimal
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models import RawMaterialBatch
from backend.app.schemas import InwardYarnDTO, RawMaterialBatchResponse

router = APIRouter(tags=["Inventory & Raw Yarn"])


@router.post("/api/v1/inventory/inward-yarn", status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/yarn/inward", status_code=status.HTTP_201_CREATED)
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


@router.get("/api/v1/inventory/batches", response_model=List[RawMaterialBatchResponse])
@router.get("/api/v1/yarn/stock", response_model=List[RawMaterialBatchResponse])
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


@router.delete("/api/v1/inventory/batches/{batch_id}")
@router.delete("/api/v1/yarn/stock/{batch_id}")
async def delete_raw_material_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes a raw material batch from inventory (for floor manager corrections)."""
    stmt = select(RawMaterialBatch).where(
        (RawMaterialBatch.batch_id == batch_id) | (RawMaterialBatch.lot_number == batch_id)
    )
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch or lot '{batch_id}' not found.")

    await db.delete(batch)
    await db.commit()
    return {"status": "DELETED", "batch_id": batch_id, "message": "Batch removed successfully."}

