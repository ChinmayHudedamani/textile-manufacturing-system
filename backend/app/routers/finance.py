"""
Finance & Activity-Based Costing (ABC) Router (Scene 6).
Routes:
- GET /api/v1/costing/order/{order_id} (or /api/v1/finance/pnl-summary)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models import CustomerOrder
from backend.app.schemas import OrderCostingResponse
from backend.app.costing import calculate_activity_based_costing

router = APIRouter(tags=["Finance & Costing"])


@router.get("/api/v1/costing/order/{order_id}", response_model=OrderCostingResponse)
async def compute_order_costing(order_id: str, db: AsyncSession = Depends(get_db)):
    """Dynamic Activity-Based Costing (ABC) calculation with margin and waterfall breakdown."""
    try:
        costing_result = await calculate_activity_based_costing(order_id, db)
        return costing_result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.get("/api/v1/finance/pnl-summary")
async def get_monthly_financial_pnl(db: AsyncSession = Depends(get_db)):
    """
    Consolidated PnL summary across all active orders:
    Computes total invoiced value, direct yarn absorption, machine energy, labor, and gross margins.
    """
    stmt = select(CustomerOrder)
    res = await db.execute(stmt)
    orders = res.scalars().all()

    breakdowns = []
    total_rev = 0.0
    total_cost = 0.0

    for o in orders:
        try:
            c = await calculate_activity_based_costing(o.order_id, db)
            breakdowns.append({
                "order_id": o.order_id,
                "order_number": o.order_number,
                "buyer_name": o.buyer_name,
                "target_meters": c["target_meters"],
                "passed_meters": c["total_passed_meters"],
                "revenue": c["revenue"],
                "total_cost": c["total_manufacturing_cost"],
                "yarn_cost": c["direct_material_cost"],
                "power_cost": c["machine_overhead_cost"],
                "labor_cost": c["direct_labor_cost"],
                "gross_margin_pct": c["gross_margin_percentage"],
                "cost_per_meter": c["final_cost_per_meter"]
            })
            total_rev += c["revenue"]
            total_cost += c["total_manufacturing_cost"]
        except Exception:
            continue

    overall_margin = round(((total_rev - total_cost) / total_rev * 100.0) if total_rev > 0 else 0.0, 2)
    return {
        "status": "OK",
        "currency": "INR",
        "currency_symbol": "₹",
        "total_revenue_inr": round(total_rev, 2),
        "total_absorbed_cost_inr": round(total_cost, 2),
        "net_operating_profit_inr": round(total_rev - total_cost, 2),
        "overall_gross_margin_pct": overall_margin,
        "orders_evaluated": len(breakdowns),
        "order_breakdowns": breakdowns
    }

