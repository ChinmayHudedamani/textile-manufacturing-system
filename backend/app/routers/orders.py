"""
Customer Orders & Buyer Portal Tracking Router (Scene 5).
Routes:
- GET  /api/v1/orders
- GET  /api/v1/orders/track/{order_number} (or /api/v1/orders/{order_number}/track)
- POST /api/v1/orders/{order_id}/notify
"""
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models import CustomerOrder, FabricRoll, CustomerNotification, DispatchItem
from backend.app.schemas import (
    CustomerTrackingResponse, OrderProgressMilestone, CustomerNotificationResponse, CustomerNotificationDTO
)

router = APIRouter(tags=["Orders & Buyer Tracking"])


@router.get("/api/v1/orders")
async def list_orders_summary(db: AsyncSession = Depends(get_db)):
    """Provides milestone overview of all open manufacturing contracts."""
    stmt = select(CustomerOrder).order_by(CustomerOrder.created_at.desc())
    res = await db.execute(stmt)
    orders = res.scalars().all()

    output = []
    for o in orders:
        passed_stmt = select(FabricRoll).where(
            (FabricRoll.order_id == o.order_id) & (FabricRoll.qc_status == "PASSED")
        )
        passed_rolls = (await db.execute(passed_stmt)).scalars().all()
        passed_meters = sum(float(r.length_meters) for r in passed_rolls)
        pct = (passed_meters / float(o.target_meters) * 100.0) if float(o.target_meters) > 0 else 0.0

        output.append({
            "order_id": o.order_id,
            "order_number": o.order_number,
            "buyer_name": o.buyer_name,
            "fabric_specification": o.fabric_specification,
            "color_hex": o.color_hex,
            "target_meters": float(o.target_meters),
            "passed_meters": float(passed_meters),
            "completion_percentage": round(min(pct, 100.0), 1),
            "order_status": o.order_status,
            "delivery_deadline": o.delivery_deadline
        })
    return output


@router.get("/api/v1/orders/track/{order_number}", response_model=CustomerTrackingResponse)
@router.get("/api/v1/orders/{order_number}/track", response_model=CustomerTrackingResponse)
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


@router.post("/api/v1/orders/{order_id}/notify")
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
