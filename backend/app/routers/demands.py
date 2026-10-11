"""
Customer Demands, Quotations & Order Placement Router.
Designed exclusively for the Customer / Buyer Persona (Inditex / Marks & Spencer / Arvind).
Applies Object-Oriented Clean Architecture:
- Encapsulated DemandsController
- Domain Model DTOs
- Automatic capacity feasibility assessment
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.database import get_db
from backend.app.models import CustomerOrder, FabricRoll, CustomerNotification
from backend.app.auth import RequirePermission, Permission


router = APIRouter(prefix="/api/v1/customer", tags=["Customer Demands & Procurement Portal"])


# =====================================================================
# DTO Schemas
# =====================================================================

class CreateOrderDemandDTO(BaseModel):
    buyer_name: str = Field(..., description="Buyer or Brand Name (e.g., Zara Sourcing / Inditex)")
    buyer_email: str = Field(..., description="Procurement Contact Email")
    fabric_specification: str = Field(..., description="Yarn count & weave type (e.g., 60s Combed Cotton Poplin)")
    color_hex: str = Field(default="#2563EB", description="Color swatch hex code")
    target_meters: float = Field(..., gt=0, description="Total meters demanded")
    delivery_deadline: str = Field(..., description="Target delivery date (e.g. 2026-11-20)")
    urgency_level: str = Field(default="STANDARD", description="STANDARD | EXPEDITED | URGENT")


class OrderDemandResponse(BaseModel):
    order_id: str
    order_number: str
    buyer_name: str
    fabric_specification: str
    target_meters: float
    delivery_deadline: str
    order_status: str
    contract_price_per_meter: float
    total_order_value_inr: float
    created_at: str
    estimated_lead_days: int
    feasibility_status: str


# =====================================================================
# Controller (Encapsulated Business Logic)
# =====================================================================

class DemandsController:
    """Encapsulated Controller managing Customer Orders, Deadlines & Demand Calculations."""

    @staticmethod
    def calculate_feasibility(target_meters: float, deadline_str: str) -> dict:
        """
        Feasibility Engine:
        Calculates daily loom output capacity (Everest runs ~6 looms @ 200m/day = 1,200m/day).
        Estimates lead time in days and determines if delivery deadline is achievable.
        """
        mill_daily_capacity = 1200.0  # meters per day across active looms
        lead_days = max(3, int(round(target_meters / mill_daily_capacity)) + 2)  # +2 days for preparatory & ASTM QC

        try:
            deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            days_available = (deadline_date - datetime.utcnow().date()).days
            if days_available < lead_days:
                feasibility = "TIGHT_SCHEDULE"
            elif days_available < lead_days // 2:
                feasibility = "OVERCAPACITY_RISK"
            else:
                feasibility = "ON_SCHEDULE"
        except Exception:
            feasibility = "FEASIBLE"
            days_available = lead_days + 5

        return {
            "estimated_lead_days": lead_days,
            "feasibility_status": feasibility
        }


# =====================================================================
# API Endpoints
# =====================================================================

@router.get("/demands", response_model=List[OrderDemandResponse])
async def list_customer_demands(
    buyer_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns incoming orders, deadlines, and volume demands.
    Filtered for the Customer portal view.
    """
    stmt = select(CustomerOrder).order_by(CustomerOrder.created_at.desc())
    if buyer_name:
        stmt = stmt.where(CustomerOrder.buyer_name.ilike(f"%{buyer_name}%"))

    result = await db.execute(stmt)
    orders = result.scalars().all()

    response = []
    for o in orders:
        meters = float(o.target_meters)
        rate = float(o.contract_price_per_meter or 225.0)
        feas = DemandsController.calculate_feasibility(meters, o.delivery_deadline)

        response.append(OrderDemandResponse(
            order_id=o.order_id,
            order_number=o.order_number,
            buyer_name=o.buyer_name,
            fabric_specification=o.fabric_specification,
            target_meters=meters,
            delivery_deadline=o.delivery_deadline,
            order_status=o.order_status,
            contract_price_per_meter=rate,
            total_order_value_inr=round(meters * rate, 2),
            created_at=o.created_at.strftime("%b %d, %Y"),
            estimated_lead_days=feas["estimated_lead_days"],
            feasibility_status=feas["feasibility_status"]
        ))
    return response


@router.post("/demands", response_model=OrderDemandResponse, status_code=201)
async def submit_new_order_demand(
    payload: CreateOrderDemandDTO,
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a new incoming order demand directly from the Customer portal.
    Generates unique Order PO number, sets initial stage, and notifies production team.
    """
    count_stmt = select(func.count(CustomerOrder.order_id))
    order_count = (await db.execute(count_stmt)).scalar() or 0
    generated_order_number = f"ORD-2026-{(order_count + 101):03d}"

    rate_per_meter = Decimal("225.00")  # Standard Everest INR rate per meter

    new_order = CustomerOrder(
        order_id=str(uuid.uuid4()),
        order_number=generated_order_number,
        buyer_name=payload.buyer_name,
        buyer_email=payload.buyer_email,
        fabric_specification=payload.fabric_specification,
        color_hex=payload.color_hex,
        target_meters=Decimal(str(payload.target_meters)),
        delivery_deadline=payload.delivery_deadline,
        order_status="ORDER_RECEIVED",
        contract_price_per_meter=rate_per_meter,
        version_id=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_order)

    # Automatic initial confirmation notification
    initial_notif = CustomerNotification(
        notification_id=str(uuid.uuid4()),
        order_id=new_order.order_id,
        milestone_event="ORDER_RECEIVED",
        channel="PORTAL",
        message_body=f"Demand Registered: PO {generated_order_number} confirmed for {payload.target_meters:,.0f}m ({payload.fabric_specification}). Staging yarn batches.",
        sent_at=datetime.utcnow()
    )
    db.add(initial_notif)

    await db.commit()
    await db.refresh(new_order)

    feas = DemandsController.calculate_feasibility(float(new_order.target_meters), new_order.delivery_deadline)

    return OrderDemandResponse(
        order_id=new_order.order_id,
        order_number=new_order.order_number,
        buyer_name=new_order.buyer_name,
        fabric_specification=new_order.fabric_specification,
        target_meters=float(new_order.target_meters),
        delivery_deadline=new_order.delivery_deadline,
        order_status=new_order.order_status,
        contract_price_per_meter=float(rate_per_meter),
        total_order_value_inr=float(new_order.target_meters) * float(rate_per_meter),
        created_at=new_order.created_at.strftime("%b %d, %Y"),
        estimated_lead_days=feas["estimated_lead_days"],
        feasibility_status=feas["feasibility_status"]
    )
