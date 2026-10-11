from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models import (
    RawMaterialBatch, CustomerOrder, Machine,
    FabricRoll, DispatchItem, LaborShiftLog, 
    CustomerNotification, MaterialAllocation
)

async def seed_initial_mill_data(db: AsyncSession):
    """Populates realistic textile mill operational data if tables are empty."""
    check = await db.execute(select(CustomerOrder).limit(1))
    if check.scalar_one_or_none() is not None:
        return # Data already present

    # 1. Raw Material Batches
    batches = [
        RawMaterialBatch(
            batch_id="batch-cotton-992",
            lot_number="LOT-COTTON-992",
            supplier_name="Gujarat Agro Fibers Ltd.",
            material_type="COTTON_COMBED",
            color_code="#F5F5DC",
            received_weight_kg=Decimal("1200.000"),
            current_stock_kg=Decimal("850.500"),
            cost_per_kg=Decimal("4.25"),
            safety_stock_threshold_kg=Decimal("250.000"),
            inward_date=datetime.utcnow() - timedelta(days=5)
        ),
        RawMaterialBatch(
            batch_id="batch-poly-401",
            lot_number="LOT-POLY-401",
            supplier_name="Reliance Petrochemicals",
            material_type="POLYESTER_FILAMENT",
            color_code="#E0E7FF",
            received_weight_kg=Decimal("800.000"),
            current_stock_kg=Decimal("185.000"), # BELOW SAFETY THRESHOLD!
            cost_per_kg=Decimal("2.95"),
            safety_stock_threshold_kg=Decimal("250.000"),
            inward_date=datetime.utcnow() - timedelta(days=8)
        ),
        RawMaterialBatch(
            batch_id="batch-rayon-108",
            lot_number="LOT-RAYON-108",
            supplier_name="Grasim Industries",
            material_type="VISCOSE_RAYON",
            color_code="#FEF08A",
            received_weight_kg=Decimal("650.000"),
            current_stock_kg=Decimal("410.000"),
            cost_per_kg=Decimal("3.80"),
            safety_stock_threshold_kg=Decimal("200.000"),
            inward_date=datetime.utcnow() - timedelta(days=2)
        ),
        RawMaterialBatch(
            batch_id="batch-spun-552",
            lot_number="LOT-SPUN-552",
            supplier_name="Vardhman Textiles",
            material_type="SPUN_BLEND",
            color_code="#CBD5E1",
            received_weight_kg=Decimal("1500.000"),
            current_stock_kg=Decimal("1100.000"),
            cost_per_kg=Decimal("3.40"),
            safety_stock_threshold_kg=Decimal("300.000"),
            inward_date=datetime.utcnow() - timedelta(days=1)
        )
    ]
    for b in batches:
        db.add(b)

    # 2. Customer Orders
    orders = [
        CustomerOrder(
            order_id="ord-zara-081",
            order_number="ORD-2026-081",
            buyer_name="Zara Sourcing / Inditex",
            buyer_email="procurement@inditex.com",
            fabric_specification="60s Combed Cotton Poplin",
            color_hex="#2563EB",
            target_meters=Decimal("5000.00"),
            delivery_deadline="2026-11-15",
            order_status="WEAVING_ACTIVE",
            contract_price_per_meter=Decimal("48.50"),
            created_at=datetime.utcnow() - timedelta(days=6)
        ),
        CustomerOrder(
            order_id="ord-ms-094",
            order_number="ORD-2026-094",
            buyer_name="Marks & Spencer UK",
            buyer_email="orders@marksandspencer.com",
            fabric_specification="Viscose Rayon Twill 180 GSM",
            color_hex="#059669",
            target_meters=Decimal("2500.00"),
            delivery_deadline="2026-10-30",
            order_status="QC_STAGE",
            contract_price_per_meter=Decimal("52.00"),
            created_at=datetime.utcnow() - timedelta(days=10)
        ),
        CustomerOrder(
            order_id="ord-arvind-102",
            order_number="ORD-2026-102",
            buyer_name="Arvind Mills Export",
            buyer_email="garments@arvindmills.com",
            fabric_specification="Polyester Filament Sheeting",
            color_hex="#7C3AED",
            target_meters=Decimal("8000.00"),
            delivery_deadline="2026-12-01",
            order_status="MATERIAL_ALLOCATED",
            contract_price_per_meter=Decimal("38.00"),
            created_at=datetime.utcnow() - timedelta(days=1)
        )
    ]
    for o in orders:
        db.add(o)

    # 3. Material Allocations
    allocations = [
        MaterialAllocation(
            allocation_id="alloc-1",
            order_id="ord-zara-081",
            batch_id="batch-cotton-992",
            allocated_weight_kg=Decimal("1100.000"),
            allocated_at=datetime.utcnow() - timedelta(days=5)
        ),
        MaterialAllocation(
            allocation_id="alloc-2",
            order_id="ord-ms-094",
            batch_id="batch-rayon-108",
            allocated_weight_kg=Decimal("520.000"),
            allocated_at=datetime.utcnow() - timedelta(days=9)
        )
    ]
    for a in allocations:
        db.add(a)

    # 4. Machines
    machines = [
        # Spinning Stage (4 Frames)
        Machine(
            machine_id="SPIN-FRAME-01",
            stage="SPINNING",
            rated_capacity_rpm=14800,
            current_status="RUNNING",
            assigned_order_id="ord-zara-081",
            overhead_hourly_rate=Decimal("38.00"),
            current_picks_cumulative=524800,
            current_power_draw_amps=Decimal("18.4"),
            current_rpm=14800,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="SPIN-FRAME-02",
            stage="SPINNING",
            rated_capacity_rpm=14800,
            current_status="RUNNING",
            assigned_order_id="ord-ms-094",
            overhead_hourly_rate=Decimal("38.00"),
            current_picks_cumulative=310200,
            current_power_draw_amps=Decimal("17.9"),
            current_rpm=14650,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="SPIN-FRAME-03",
            stage="SPINNING",
            rated_capacity_rpm=14800,
            current_status="RUNNING",
            assigned_order_id="ord-arvind-102",
            overhead_hourly_rate=Decimal("38.00"),
            current_picks_cumulative=412000,
            current_power_draw_amps=Decimal("18.2"),
            current_rpm=14720,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="SPIN-FRAME-04",
            stage="SPINNING",
            rated_capacity_rpm=14800,
            current_status="IDLE",
            assigned_order_id=None,
            overhead_hourly_rate=Decimal("38.00"),
            current_picks_cumulative=198400,
            current_power_draw_amps=Decimal("1.8"),
            current_rpm=0,
            idle_seconds=185, # > 120s: TRIGGERS AMBER WARNING
            last_heartbeat=datetime.utcnow() - timedelta(seconds=185)
        ),
        # Weaving Stage (6 Airjet Looms)
        Machine(
            machine_id="WEAVE-LOOM-01",
            stage="WEAVING",
            rated_capacity_rpm=750,
            current_status="RUNNING",
            assigned_order_id="ord-zara-081",
            overhead_hourly_rate=Decimal("45.00"),
            current_picks_cumulative=189400,
            current_power_draw_amps=Decimal("16.2"),
            current_rpm=720,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="WEAVE-LOOM-02",
            stage="WEAVING",
            rated_capacity_rpm=750,
            current_status="RUNNING",
            assigned_order_id="ord-ms-094",
            overhead_hourly_rate=Decimal("45.00"),
            current_picks_cumulative=245000,
            current_power_draw_amps=Decimal("15.8"),
            current_rpm=735,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="WEAVE-LOOM-03",
            stage="WEAVING",
            rated_capacity_rpm=750,
            current_status="RUNNING",
            assigned_order_id="ord-arvind-102",
            overhead_hourly_rate=Decimal("45.00"),
            current_picks_cumulative=172000,
            current_power_draw_amps=Decimal("15.5"),
            current_rpm=725,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="WEAVE-LOOM-04", # THE BENCHMARK SPEC MACHINE
            stage="WEAVING",
            rated_capacity_rpm=750,
            current_status="RUNNING",
            assigned_order_id="ord-zara-081",
            overhead_hourly_rate=Decimal("45.00"),
            current_picks_cumulative=105412,
            current_power_draw_amps=Decimal("14.8"),
            current_rpm=720,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="WEAVE-LOOM-05",
            stage="WEAVING",
            rated_capacity_rpm=750,
            current_status="RUNNING",
            assigned_order_id="ord-zara-081",
            overhead_hourly_rate=Decimal("45.00"),
            current_picks_cumulative=210500,
            current_power_draw_amps=Decimal("15.6"),
            current_rpm=730,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="WEAVE-LOOM-06",
            stage="WEAVING",
            rated_capacity_rpm=750,
            current_status="RUNNING",
            assigned_order_id="ord-ms-094",
            overhead_hourly_rate=Decimal("45.00"),
            current_picks_cumulative=195200,
            current_power_draw_amps=Decimal("16.0"),
            current_rpm=728,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        # Dyeing Vats (3 Vats)
        Machine(
            machine_id="DYE-VAT-01",
            stage="DYEING",
            rated_capacity_rpm=120,
            current_status="RUNNING",
            assigned_order_id="ord-ms-094",
            overhead_hourly_rate=Decimal("55.00"),
            current_picks_cumulative=44200,
            current_power_draw_amps=Decimal("28.0"),
            current_rpm=115,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="DYE-VAT-02",
            stage="DYEING",
            rated_capacity_rpm=120,
            current_status="RUNNING",
            assigned_order_id="ord-zara-081",
            overhead_hourly_rate=Decimal("55.00"),
            current_picks_cumulative=38100,
            current_power_draw_amps=Decimal("26.4"),
            current_rpm=110,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        ),
        Machine(
            machine_id="DYE-VAT-03",
            stage="DYEING",
            rated_capacity_rpm=120,
            current_status="RUNNING",
            assigned_order_id="ord-arvind-102",
            overhead_hourly_rate=Decimal("55.00"),
            current_picks_cumulative=29400,
            current_power_draw_amps=Decimal("14.2"),
            current_rpm=80,
            idle_seconds=0,
            last_heartbeat=datetime.utcnow()
        )
    ]
    for m in machines:
        db.add(m)

    # 5. Fabric Rolls
    rolls = [
        # Rolls for ORD-2026-081 (Zara)
        FabricRoll(
            roll_id="roll-081-01",
            roll_barcode="ROLL-081-PASS-01",
            order_id="ord-zara-081",
            machine_id="WEAVE-LOOM-04",
            operator_id="OP-812",
            length_meters=Decimal("120.00"),
            gross_weight_kg=Decimal("26.40"),
            qc_status="PASSED",
            defect_type="NONE",
            defect_points=1,
            inspection_timestamp=datetime.utcnow() - timedelta(days=2),
            produced_at=datetime.utcnow() - timedelta(days=3)
        ),
        FabricRoll(
            roll_id="roll-081-02",
            roll_barcode="ROLL-081-DISPATCHED-02",
            order_id="ord-zara-081",
            machine_id="WEAVE-LOOM-04",
            operator_id="OP-812",
            length_meters=Decimal("140.00"),
            gross_weight_kg=Decimal("30.80"),
            qc_status="PASSED",
            defect_type="NONE",
            defect_points=0,
            inspection_timestamp=datetime.utcnow() - timedelta(days=1),
            produced_at=datetime.utcnow() - timedelta(days=2)
        ),
        FabricRoll(
            roll_id="roll-081-03",
            roll_barcode="ROLL-081-PENDING-03",
            order_id="ord-zara-081",
            machine_id="WEAVE-LOOM-04",
            operator_id="OP-403",
            length_meters=Decimal("135.00"),
            gross_weight_kg=Decimal("29.70"),
            qc_status="PENDING", # READY TO INSPECT ON QC BENCH
            defect_type="NONE",
            defect_points=0,
            produced_at=datetime.utcnow() - timedelta(hours=4)
        ),
        FabricRoll(
            roll_id="roll-081-04",
            roll_barcode="ROLL-081-REJECTED-04",
            order_id="ord-zara-081",
            machine_id="WEAVE-LOOM-01",
            operator_id="OP-109",
            length_meters=Decimal("110.00"),
            gross_weight_kg=Decimal("24.20"),
            qc_status="REJECTED",
            defect_type="UNEVEN_WEAVING",
            defect_points=14,
            inspection_timestamp=datetime.utcnow() - timedelta(hours=12),
            produced_at=datetime.utcnow() - timedelta(days=1)
        ),
        # Rolls for ORD-2026-094 (Marks & Spencer)
        FabricRoll(
            roll_id="roll-094-01",
            roll_barcode="ROLL-094-PASS-01",
            order_id="ord-ms-094",
            machine_id="WEAVE-LOOM-02",
            operator_id="OP-301",
            length_meters=Decimal("160.00"),
            gross_weight_kg=Decimal("35.20"),
            qc_status="PASSED", # READY TO SCAN ON TRUCK MANIFEST!
            defect_type="NONE",
            defect_points=2,
            inspection_timestamp=datetime.utcnow() - timedelta(hours=18),
            produced_at=datetime.utcnow() - timedelta(days=1)
        ),
        FabricRoll(
            roll_id="roll-094-02",
            roll_barcode="ROLL-094-PENDING-02",
            order_id="ord-ms-094",
            machine_id="WEAVE-LOOM-02",
            operator_id="OP-301",
            length_meters=Decimal("155.00"),
            gross_weight_kg=Decimal("34.10"),
            qc_status="PENDING",
            defect_type="NONE",
            defect_points=0,
            produced_at=datetime.utcnow() - timedelta(hours=2)
        )
    ]
    for r in rolls:
        db.add(r)

    # 6. Dispatch Items (Existing dispatched roll to demonstrate anti-double dispatch)
    dispatch_items = [
        DispatchItem(
            dispatch_id="dispatch-01",
            roll_id="roll-081-02",
            order_id="ord-zara-081",
            truck_license_plate="KA-01-E-9002",
            invoice_number="INV-2026-001",
            dispatched_by="DISPATCH_SUPERVISOR_KUMAR",
            dispatched_at=datetime.utcnow() - timedelta(hours=6)
        )
    ]
    for d in dispatch_items:
        db.add(d)

    # 7. Labor Shift Logs
    labor_logs = [
        LaborShiftLog(
            log_id="log-01",
            worker_id="OP-812",
            shift_date="2026-10-08",
            hours_worked=Decimal("8.00"),
            hourly_rate=Decimal("14.50"),
            assigned_order_id="ord-zara-081",
            logged_at=datetime.utcnow() - timedelta(days=2)
        ),
        LaborShiftLog(
            log_id="log-02",
            worker_id="OP-403",
            shift_date="2026-10-09",
            hours_worked=Decimal("8.00"),
            hourly_rate=Decimal("14.50"),
            assigned_order_id="ord-zara-081",
            logged_at=datetime.utcnow() - timedelta(days=1)
        ),
        LaborShiftLog(
            log_id="log-03",
            worker_id="OP-301",
            shift_date="2026-10-09",
            hours_worked=Decimal("8.00"),
            hourly_rate=Decimal("15.00"),
            assigned_order_id="ord-ms-094",
            logged_at=datetime.utcnow() - timedelta(days=1)
        )
    ]
    for l in labor_logs:
        db.add(l)

    # 8. Customer Milestone Notifications (addresses Operational Gap 4!)
    notifications = [
        CustomerNotification(
            notification_id="notif-01",
            order_id="ord-zara-081",
            milestone_event="ORDER_RECEIVED",
            channel="PORTAL",
            message_body="Purchase Order ORD-2026-081 confirmed. Target: 5,000m Combed Cotton Poplin.",
            sent_at=datetime.utcnow() - timedelta(days=6)
        ),
        CustomerNotification(
            notification_id="notif-02",
            order_id="ord-zara-081",
            milestone_event="MATERIAL_ALLOCATED",
            channel="EMAIL",
            message_body="1,100 kg combed cotton yarn (Lot: LOT-COTTON-992) staged in spinning preparatory.",
            sent_at=datetime.utcnow() - timedelta(days=5)
        ),
        CustomerNotification(
            notification_id="notif-03",
            order_id="ord-zara-081",
            milestone_event="WEAVING_ACTIVE",
            channel="SMS",
            message_body="Weaving initiated on Airjet Loom WEAVE-LOOM-04 at 740 picks/min.",
            sent_at=datetime.utcnow() - timedelta(days=3)
        ),
        CustomerNotification(
            notification_id="notif-04",
            order_id="ord-zara-081",
            milestone_event="PARTIAL_QC_COMPLETED",
            channel="PORTAL",
            message_body="First batch of 260m fabric inspected and approved with 99.2% ASTM Grade A rating.",
            sent_at=datetime.utcnow() - timedelta(days=1)
        )
    ]
    for n in notifications:
        db.add(n)

    await db.commit()
