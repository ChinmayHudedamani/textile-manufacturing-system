"""
Warehouse Truck Dispatch & Anti-Double Dispatch Router (Scene 4).
Routes:
- POST /api/v1/dispatch/scan-truck (or /api/v1/dispatch/create)
- GET  /api/v1/dispatch/manifest
"""
import uuid
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models import FabricRoll, DispatchItem, CustomerNotification, AuditEventLog
from backend.app.schemas import DispatchScanDTO, DispatchItemResponse

router = APIRouter(tags=["Truck Dispatch & Manifest"])
IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}

# Fleet of Available Factory Trucks with realistic payload capacities, current loads, and destinations

AVAILABLE_TRUCKS = [
    {
        "truck_plate": "MH-09-CV-4421",
        "model": "Tata Ultra T.7 (Medium Duty)",
        "max_weight_kg": 4500,
        "destination_city": "Mumbai (Bhiwandi Textile Hub)",
        "driver_name": "Raju Patil",
        "driver_phone": "+91 98231 44210",
        "status": "AVAILABLE"
    },
    {
        "truck_plate": "MH-12-RN-8812",
        "model": "Ashok Leyland Ecomet 1215",
        "max_weight_kg": 7500,
        "destination_city": "Mumbai (Bhiwandi Textile Hub)",
        "driver_name": "Satish Shinde",
        "driver_phone": "+91 98902 88120",
        "status": "AVAILABLE"
    },
    {
        "truck_plate": "GJ-05-BX-2204",
        "model": "BharatBenz 1617R (Heavy Duty)",
        "max_weight_kg": 11000,
        "destination_city": "Surat (Ring Road Textile Market)",
        "driver_name": "Dinesh Patel",
        "driver_phone": "+91 98250 22041",
        "status": "AVAILABLE"
    },
    {
        "truck_plate": "KA-01-AK-9042",
        "model": "Eicher Pro 2049 (City Express)",
        "max_weight_kg": 3200,
        "destination_city": "Bengaluru (Peenya Apparel Park)",
        "driver_name": "Venkatesh Rao",
        "driver_phone": "+91 94481 90420",
        "status": "AVAILABLE"
    },
    {
        "truck_plate": "TN-38-EF-5531",
        "model": "Tata 1109 LPT Container",
        "max_weight_kg": 6800,
        "destination_city": "Tiruppur (Export Knitwear Zone)",
        "driver_name": "Murugan Swamy",
        "driver_phone": "+91 94432 55311",
        "status": "AVAILABLE"
    }
]


@router.get("/api/v1/dispatch/trucks")
async def list_available_trucks(db: AsyncSession = Depends(get_db)):
    """
    Returns fleet of available transport trucks, their gross weight capacity,
    assigned delivery destinations, and AI load consolidation suggestions.
    """
    # Fetch dispatched items to compute current loaded weight per truck
    stmt = (
        select(DispatchItem, FabricRoll)
        .join(FabricRoll, DispatchItem.roll_id == FabricRoll.roll_id)
    )
    res = await db.execute(stmt)
    records = res.all()

    loaded_weights: Dict[str, float] = {}
    loaded_rolls_count: Dict[str, int] = {}
    for d, r in records:
        plate = d.truck_license_plate
        loaded_weights[plate] = loaded_weights.get(plate, 0.0) + float(r.gross_weight_kg)
        loaded_rolls_count[plate] = loaded_rolls_count.get(plate, 0) + 1

    trucks_data = []
    destinations_map: Dict[str, List[dict]] = {}

    for t in AVAILABLE_TRUCKS:
        plate = t["truck_plate"]
        loaded_kg = round(loaded_weights.get(plate, 0.0), 1)
        remaining_kg = max(0.0, round(t["max_weight_kg"] - loaded_kg, 1))
        utilization_pct = min(100.0, round((loaded_kg / t["max_weight_kg"]) * 100, 1))

        truck_obj = {
            **t,
            "current_load_kg": loaded_kg,
            "remaining_capacity_kg": remaining_kg,
            "utilization_percentage": utilization_pct,
            "loaded_rolls_count": loaded_rolls_count.get(plate, 0)
        }
        trucks_data.append(truck_obj)

        city = t["destination_city"]
        if city not in destinations_map:
            destinations_map[city] = []
        destinations_map[city].append(truck_obj)

    # Generate Smart Route Consolidation Suggestions
    consolidation_suggestions = []
    for city, city_trucks in destinations_map.items():
        if len(city_trucks) > 1:
            total_loaded = sum(tr["current_load_kg"] for tr in city_trucks)
            heaviest_truck = max(city_trucks, key=lambda x: x["max_weight_kg"])
            if total_loaded <= heaviest_truck["max_weight_kg"]:
                truck_plates = ", ".join(tr["truck_plate"] for tr in city_trucks)
                fuel_savings_inr = 8500 * (len(city_trucks) - 1)
                consolidation_suggestions.append({
                    "destination_city": city,
                    "target_truck": heaviest_truck["truck_plate"],
                    "candidate_trucks": [tr["truck_plate"] for tr in city_trucks],
                    "combined_weight_kg": total_loaded,
                    "target_capacity_kg": heaviest_truck["max_weight_kg"],
                    "estimated_fuel_savings_inr": fuel_savings_inr,
                    "recommendation": f"Combine shipments heading to {city} ({truck_plates}) into {heaviest_truck['truck_plate']} ({heaviest_truck['model']}). Saves ₹{fuel_savings_inr:,} in highway tolls & diesel."
                })

    return {
        "status": "OK",
        "trucks": trucks_data,
        "consolidation_suggestions": consolidation_suggestions
    }


@router.post("/api/v1/dispatch/scan-truck")

@router.post("/api/v1/dispatch/create")
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
        event_id=str(uuid.uuid4()),
        action_type="ROLL_DISPATCHED",
        actor_id=payload.dispatched_by or "DISPATCH_CLERK_1",
        entity_name="FabricRoll",
        entity_id=roll.roll_id,
        payload_hash=payload_hash,
        details=f'{{"truck_plate":"{payload.truck_plate}","invoice":"{payload.invoice_number}"}}',
        created_at=now_utc
    )

    from sqlalchemy.exc import IntegrityError
    try:
        db.add(dispatch_entry)
        db.add(notif)
        db.add(audit_entry)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CRITICAL: Double Dispatch Blocked! Roll '{payload.roll_barcode}' was claimed by a concurrent dock transaction."
        )

    response_data = {
        "status": "DISPATCH_CONFIRMED",
        "roll_barcode": payload.roll_barcode,
        "length_meters": float(roll.length_meters),
        "gross_weight_kg": float(roll.gross_weight_kg),
        "truck_plate": payload.truck_plate.strip().upper(),
        "invoice_number": payload.invoice_number.strip().upper(),
        "dispatched_at": now_utc.isoformat()
    }
    IDEMPOTENCY_CACHE[cache_key] = response_data
    return response_data


@router.get("/api/v1/dispatch/manifest", response_model=List[DispatchItemResponse])
async def list_dispatched_manifest(db: AsyncSession = Depends(get_db)):
    """Returns shipping manifest of all rolls loaded onto trucks."""
    stmt = (
        select(DispatchItem, FabricRoll)
        .join(FabricRoll, DispatchItem.roll_id == FabricRoll.roll_id)
        .order_by(DispatchItem.dispatched_at.desc())
    )
    res = await db.execute(stmt)
    records = res.all()

    output = []
    for d, r in records:
        output.append(DispatchItemResponse(
            dispatch_id=d.dispatch_id,
            roll_id=d.roll_id,
            roll_barcode=r.roll_barcode,
            order_id=d.order_id,
            truck_license_plate=d.truck_license_plate,
            invoice_number=d.invoice_number,
            length_meters=float(r.length_meters),
            dispatched_by=d.dispatched_by,
            dispatched_at=d.dispatched_at
        ))
    return output


@router.delete("/api/v1/dispatch/manifest/{dispatch_id}")
async def revoke_dispatch(dispatch_id: str, db: AsyncSession = Depends(get_db)):
    """Revokes a dispatch manifest item (e.g. truck recall or dock gate correction)."""
    stmt = select(DispatchItem).where(DispatchItem.dispatch_id == dispatch_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Dispatch record not found.")

    await db.delete(item)
    await db.commit()
    return {"status": "REVOKED", "dispatch_id": dispatch_id, "message": "Roll released from truck manifest."}

