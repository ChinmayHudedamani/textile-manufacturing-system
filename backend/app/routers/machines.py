"""
Production Floor & Machine Telemetry Router (Scene 2).
Routes:
- GET   /api/v1/machines (or /api/v1/machines/floor-map)
- POST  /api/v1/machines/{machine_id}/telemetry
- PATCH /api/v1/machines/{machine_id}/breakdown
- POST  /api/v1/simulate/tick
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models import Machine
from backend.app.schemas import TelemetryUpdateDTO, MachineResponse

router = APIRouter(tags=["Production Floor & Machines"])


class BreakdownDTO(BaseModel):
    reason: Optional[str] = Field("Mechanical Breakdown / Operator Alarm", description="Reason for halt")


@router.get("/api/v1/machines", response_model=List[MachineResponse])
@router.get("/api/v1/machines/floor-map", response_model=List[MachineResponse])
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


@router.post("/api/v1/machines/{machine_id}/telemetry")
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


@router.patch("/api/v1/machines/{machine_id}/breakdown")
async def log_machine_breakdown(machine_id: str, payload: Optional[BreakdownDTO] = None, db: AsyncSession = Depends(get_db)):
    """Halts machine, flags downtime, pauses timers, and switches power to idle."""
    stmt = select(Machine).where(Machine.machine_id == machine_id.upper())
    res = await db.execute(stmt)
    machine = res.scalar_one_or_none()

    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found.")

    machine.current_status = "IDLE"
    machine.current_rpm = 0
    machine.current_power_draw_amps = Decimal("1.80")
    machine.idle_seconds = 125
    machine.last_heartbeat = datetime.utcnow()
    await db.commit()

    return {
        "status": "BREAKDOWN_LOGGED",
        "machine_id": machine.machine_id,
        "current_status": "IDLE",
        "reason": payload.reason if payload else "Mechanical Breakdown",
        "idle_alert": True
    }


@router.patch("/api/v1/machines/{machine_id}/status")
async def update_machine_status(machine_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Toggles or sets machine status (RUNNING, IDLE, MAINTENANCE, FAULT)."""
    stmt = select(Machine).where(Machine.machine_id == machine_id.upper())
    res = await db.execute(stmt)
    machine = res.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found.")

    new_status = payload.get("status", "RUNNING").upper()
    machine.current_status = new_status
    if new_status == "RUNNING":
        machine.current_rpm = machine.rated_capacity_rpm
        machine.idle_seconds = 0
        machine.current_power_draw_amps = Decimal("16.5")
    elif new_status == "MAINTENANCE":
        machine.current_rpm = 0
        machine.current_power_draw_amps = Decimal("0.8")
    else: # IDLE or HALTED
        machine.current_rpm = 0
        machine.current_power_draw_amps = Decimal("1.8")

    machine.last_heartbeat = datetime.utcnow()
    await db.commit()
    return {
        "status": "STATUS_UPDATED",
        "machine_id": machine.machine_id,
        "current_status": machine.current_status,
        "current_rpm": machine.current_rpm,
        "current_power_draw_amps": float(machine.current_power_draw_amps)
    }


@router.delete("/api/v1/machines/{machine_id}")
async def delete_machine(machine_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes/decommissions a machine."""
    stmt = select(Machine).where(Machine.machine_id == machine_id.upper())
    res = await db.execute(stmt)
    machine = res.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found.")
    await db.delete(machine)
    await db.commit()
    return {"status": "DELETED", "machine_id": machine_id}


@router.post("/api/v1/simulate/tick")
async def simulate_floor_tick(db: AsyncSession = Depends(get_db)):
    """
    Simulates real-time telemetry dynamic pulse across mill equipment:
    - Increments pick counters on running machines
    - Varies live speed RPM slightly (natural micro-fluctuations)
    - Computes live dynamic power amp draws
    """
    import random
    stmt = select(Machine)
    res = await db.execute(stmt)
    machines = res.scalars().all()

    updates = []
    for m in machines:
        if m.current_status == "RUNNING":
            picks_increment = max(1, int(m.rated_capacity_rpm / 60))
            m.current_picks_cumulative += picks_increment
            m.idle_seconds = 0
            # realistic dynamic jitter around rated capacity
            jitter = random.randint(-15, 15)
            m.current_rpm = max(100, m.rated_capacity_rpm + jitter)
            # power draw fluctuation based on workload
            amps = round(14.0 + (m.current_rpm / 100) + random.uniform(-0.4, 0.4), 2)
            m.current_power_draw_amps = Decimal(str(amps))
        elif m.current_status == "IDLE":
            m.idle_seconds += 5
            m.current_rpm = 0
            m.current_power_draw_amps = Decimal("1.80")
        elif m.current_status == "MAINTENANCE":
            m.current_rpm = 0
            m.current_power_draw_amps = Decimal("0.50")

        m.last_heartbeat = datetime.utcnow()
        updates.append({
            "machine_id": m.machine_id,
            "status": m.current_status,
            "rpm": m.current_rpm,
            "power_amps": float(m.current_power_draw_amps),
            "picks": m.current_picks_cumulative,
            "idle_seconds": m.idle_seconds
        })

    await db.commit()
    return {"status": "PULSE_OK", "machines": updates}

