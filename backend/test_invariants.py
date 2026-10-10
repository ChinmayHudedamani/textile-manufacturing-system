import pytest
import pytest_asyncio
import uuid
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.database import AsyncSessionLocal, engine, Base
from backend.app.models import FabricRoll, CustomerOrder, RawMaterialBatch, DispatchItem
from backend.app.seed_data import seed_initial_mill_data

@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_initial_mill_data(session)
    yield

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_rejection_of_uninspected_roll_dispatch(client: AsyncClient):
    """Verifies that uninspected or failed rolls cannot be dispatched to a truck."""
    roll_uuid = str(uuid.uuid4())
    barcode = f"ROLL-TEST-PENDING-{roll_uuid[:8]}"

    async with AsyncSessionLocal() as session:
        order = CustomerOrder(
            order_id=str(uuid.uuid4()),
            order_number=f"ORD-T1-{roll_uuid[:6]}",
            buyer_name="Test Buyer",
            fabric_specification="Cotton Poplin",
            color_hex="#000000",
            order_status="WEAVING_ACTIVE",
            target_meters=Decimal("5000.00"),
            delivery_deadline="2026-12-31"
        )
        session.add(order)
        await session.flush()

        roll = FabricRoll(
            roll_id=roll_uuid,
            roll_barcode=barcode,
            order_id=order.order_id,
            machine_id="WEAVE-LOOM-04",
            operator_id="OP-TEST",
            length_meters=Decimal("120.00"),
            gross_weight_kg=Decimal("25.00"),
            qc_status="PENDING",
            defect_type="NONE"
        )
        session.add(roll)
        await session.commit()

    # Attempt dispatch without QC pass
    response = await client.post("/api/v1/dispatch/scan-truck", json={
        "roll_barcode": barcode,
        "truck_plate": "KA-01-E-9002",
        "invoice_number": "INV-2026-001"
    })
    assert response.status_code == 400
    assert "Only PASSED rolls can be loaded" in response.json()["detail"]

@pytest.mark.asyncio
async def test_concurrency_lock_prevents_double_dispatch(client: AsyncClient):
    """Verifies that an already dispatched roll cannot be scanned onto a second manifest."""
    roll_uuid = str(uuid.uuid4())
    barcode = f"ROLL-TEST-PASS-{roll_uuid[:8]}"

    async with AsyncSessionLocal() as session:
        order = CustomerOrder(
            order_id=str(uuid.uuid4()),
            order_number=f"ORD-T2-{roll_uuid[:6]}",
            buyer_name="Test Buyer",
            fabric_specification="Cotton Poplin",
            color_hex="#000000",
            order_status="QC_STAGE",
            target_meters=Decimal("2000.00"),
            delivery_deadline="2026-12-31"
        )
        session.add(order)
        await session.flush()

        roll = FabricRoll(
            roll_id=roll_uuid,
            roll_barcode=barcode,
            order_id=order.order_id,
            machine_id="WEAVE-LOOM-04",
            operator_id="OP-TEST",
            length_meters=Decimal("150.00"),
            gross_weight_kg=Decimal("30.00"),
            qc_status="PASSED",
            defect_type="NONE"
        )
        session.add(roll)
        await session.commit()

    # First dispatch succeeds
    resp1 = await client.post("/api/v1/dispatch/scan-truck", json={
        "roll_barcode": barcode,
        "truck_plate": "KA-01-E-9002",
        "invoice_number": "INV-2026-001"
    })
    assert resp1.status_code == 200

    # Second duplicate dispatch must trigger HTTP 409 Conflict
    resp2 = await client.post("/api/v1/dispatch/scan-truck", json={
        "roll_barcode": barcode,
        "truck_plate": "MH-04-A-1100",
        "invoice_number": "INV-2026-002"
    })
    assert resp2.status_code == 409
    assert "Double Dispatch Blocked" in resp2.json()["detail"]

@pytest.mark.asyncio
async def test_safety_stock_threshold_alert(client: AsyncClient):
    """Verifies that yarn batch below safety stock threshold triggers alert."""
    lot = f"LOT-TEST-{uuid.uuid4().hex[:6]}"
    resp = await client.post("/api/v1/inventory/inward-yarn", json={
        "lot_number": lot,
        "supplier_name": "Test Fibers",
        "material_type": "COTTON_COMBED",
        "color_code": "#FFFFFF",
        "weight_kg": 150.0, # Below 250kg default threshold!
        "cost_per_kg": 4.50,
        "safety_stock_threshold_kg": 250.0
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["safety_alert"] is True

@pytest.mark.asyncio
async def test_customer_order_tracking_portal(client: AsyncClient):
    """Verifies customer self-service order tracking (Operational Gap 4)."""
    resp = await client.get("/api/v1/orders/track/ORD-2026-081")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_number"] == "ORD-2026-081"
    assert data["buyer_name"] == "Zara Sourcing / Inditex"
    assert "milestones" in data
    assert "notifications" in data
    assert len(data["milestones"]) > 0

@pytest.mark.asyncio
async def test_activity_based_costing_calculation(client: AsyncClient):
    """Verifies dynamic Activity-Based Costing engine."""
    resp = await client.get("/api/v1/costing/order/ord-zara-081")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_manufacturing_cost"] > 0
    assert data["final_cost_per_meter"] > 0
    assert len(data["cost_waterfall"]) > 0

@pytest.mark.asyncio
async def test_parallel_concurrency_race_condition(client: AsyncClient):
    """
    ACID Serializability & Concurrency Stress Test:
    Spawns 20 concurrent coroutines attempting to scan the same fabric roll
    simultaneously across different virtual docks/invoices.
    
    Mathematical Invariant:
    Sum(HTTP 200) == 1
    Sum(HTTP 409) == 19
    """
    import asyncio
    roll_uuid = str(uuid.uuid4())
    barcode = f"ROLL-RACE-{roll_uuid[:8]}"

    async with AsyncSessionLocal() as session:
        order = CustomerOrder(
            order_id=str(uuid.uuid4()),
            order_number=f"ORD-RACE-{roll_uuid[:6]}",
            buyer_name="Race Test Buyer",
            fabric_specification="Cotton Poplin",
            color_hex="#000000",
            order_status="QC_STAGE",
            target_meters=Decimal("1000.00"),
            delivery_deadline="2026-12-31"
        )
        session.add(order)
        await session.flush()

        roll = FabricRoll(
            roll_id=roll_uuid,
            roll_barcode=barcode,
            order_id=order.order_id,
            machine_id="WEAVE-LOOM-04",
            operator_id="OP-TEST",
            length_meters=Decimal("150.00"),
            gross_weight_kg=Decimal("30.00"),
            qc_status="PASSED",
            defect_type="NONE"
        )
        session.add(roll)
        await session.commit()

    async def attempt_dispatch(driver_idx: int):
        return await client.post("/api/v1/dispatch/scan-truck", json={
            "roll_barcode": barcode,
            "truck_plate": f"KA-01-TRUCK-{driver_idx}",
            "invoice_number": f"INV-RACE-{driver_idx}"
        })

    # Fire 20 parallel requests at the exact same millisecond
    responses = await asyncio.gather(*[attempt_dispatch(i) for i in range(20)])
    
    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(200)
    conflict_count = status_codes.count(409)

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert conflict_count == 19, f"Expected exactly 19 conflicts, got {conflict_count}"
