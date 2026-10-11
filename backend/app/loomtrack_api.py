"""
LoomTrack API Adapter Router.
Bridges the teammate's React frontend (/api/auth, /api/dashboard, /api/orders,
/api/yarn, /api/machines, /api/rolls, /api/workers, /api/track/{id}) with
the underlying SQLite/SQLAlchemy enterprise operational database.
"""
import uuid
import hmac
import hashlib
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, List, Dict, Any

from fastapi import APIRouter, HTTPException, Request, Response, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.responses import Response as FastResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.app.database import get_db, AsyncSessionLocal
from backend.app.models import (
    CustomerOrder, Machine, RawMaterialBatch, FabricRoll, DispatchItem
)

router = APIRouter(prefix="/api")

# Secret key for JWT generation (pure python implementation, zero external C/cryptography dependency)
JWT_SECRET = os.environ.get("JWT_SECRET", "loomtrack-jwt-secret-key-enterprise-2026")
ACCESS_TOKEN_MINUTES = 60 * 8
REFRESH_TOKEN_DAYS = 7


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def _b64decode(s: str) -> bytes:
    padding = '=' * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_access_token(user_id: str, role: str, extra: Optional[dict] = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.now(timezone.utc)
    exp = int((now + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp())
    payload = {
        "sub": user_id,
        "role": role,
        "exp": exp,
        "type": "access"
    }
    if extra:
        payload.update(extra)

    hdr_b64 = _b64encode(json.dumps(header).encode('utf-8'))
    pay_b64 = _b64encode(json.dumps(payload).encode('utf-8'))
    sig = hmac.new(JWT_SECRET.encode('utf-8'), f"{hdr_b64}.{pay_b64}".encode('utf-8'), hashlib.sha256).digest()
    sig_b64 = _b64encode(sig)
    return f"{hdr_b64}.{pay_b64}.{sig_b64}"


def create_refresh_token(user_id: str, role: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.now(timezone.utc)
    exp = int((now + timedelta(days=REFRESH_TOKEN_DAYS)).timestamp())
    payload = {
        "sub": user_id,
        "role": role,
        "exp": exp,
        "type": "refresh"
    }
    hdr_b64 = _b64encode(json.dumps(header).encode('utf-8'))
    pay_b64 = _b64encode(json.dumps(payload).encode('utf-8'))
    sig = hmac.new(JWT_SECRET.encode('utf-8'), f"{hdr_b64}.{pay_b64}".encode('utf-8'), hashlib.sha256).digest()
    sig_b64 = _b64encode(sig)
    return f"{hdr_b64}.{pay_b64}.{sig_b64}"


def decode_token(token: str) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token structure")
    hdr_b64, pay_b64, sig_b64 = parts
    expected_sig = _b64encode(hmac.new(JWT_SECRET.encode('utf-8'), f"{hdr_b64}.{pay_b64}".encode('utf-8'), hashlib.sha256).digest())
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")
    payload = json.loads(_b64decode(pay_b64).decode('utf-8'))
    now = int(datetime.now(timezone.utc).timestamp())
    if "exp" in payload and payload["exp"] < now:
        raise HTTPException(status_code=401, detail="Token expired")
    return payload


def extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie(
        key="access_token", value=access, httponly=True, secure=False,
        samesite="lax", max_age=ACCESS_TOKEN_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=REFRESH_TOKEN_DAYS * 86400, path="/",
    )


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


# ---------- Data Models ----------
class LoginBody(BaseModel):
    role: Literal["owner", "admin", "employee", "customer"]
    identifier: str
    secret: str


class SessionUser(BaseModel):
    id: str
    role: str
    name: str
    initials: str
    order_id: Optional[str] = None


class YarnReceive(BaseModel):
    type: str
    color: str
    qty: float
    reorder: float = 300
    supplier: str
    order: str
    image: Optional[str] = None


class MachineUpdate(BaseModel):
    status: Literal["Running", "Idle", "Maintenance"]


class RollUpdate(BaseModel):
    qc: Optional[Literal["Pass", "Rework", "Reject", "Pending"]] = None
    defect: Optional[str] = None


class WorkerCreate(BaseModel):
    id: str
    name: str
    role: str
    shift: Literal["A", "B", "C"] = "A"
    pin: str = Field(min_length=4, max_length=6)


class WorkerUpdate(BaseModel):
    active: Optional[bool] = None
    pin: Optional[str] = Field(default=None, min_length=4, max_length=6)
    status: Optional[Literal["Clocked in", "Off shift"]] = None


# ---------- Static Seed / In-Memory Mock Store for Workers & Session Users ----------
USERS_STORE = {
    "owner": {"id": "u-owner", "username": "owner", "password": "owner123", "role": "owner", "name": "Arun Mehra", "initials": "AM"},
    "admin": {"id": "u-admin", "username": "admin", "password": "admin123", "role": "admin", "name": "Priya Nair", "initials": "AD"},
}

WORKERS_STORE: Dict[str, dict] = {
    "E-101": {"id": "E-101", "name": "Ravi Kumar", "role": "Weaver", "shift": "B", "status": "Clocked in", "hours": 6.4, "wage": 768, "pin": "1234", "active": True},
    "E-102": {"id": "E-102", "name": "Meena Shah", "role": "QC Inspector", "shift": "A", "status": "Clocked in", "hours": 7.1, "wage": 994, "pin": "2345", "active": True},
    "E-103": {"id": "E-103", "name": "Arjun Das", "role": "Machine Operator", "shift": "B", "status": "Off shift", "hours": 0, "wage": 0, "pin": "3456", "active": True},
}

ORDERS_EXTRA_STORE: Dict[str, dict] = {
    "ORD-1042": {"id": "ORD-1042", "buyer": "Lotus Garments", "fabric": "Combed Cotton 40s", "color": "Indigo", "qty": 1200, "passed": 780, "deadline": "2025-06-14", "stage": "Checking", "value": 48200, "otp": "1234", "image": "https://images.unsplash.com/photo-1558769132-cb1aea458c5e?auto=format&fit=crop&w=900&q=80"},
    "ORD-1043": {"id": "ORD-1043", "buyer": "Northline Home", "fabric": "Organic Twill", "color": "Moss", "qty": 800, "passed": 800, "deadline": "2025-06-18", "stage": "Ready", "value": 36100, "otp": "4321", "image": "https://images.unsplash.com/photo-1558171813-4c088753af8f?auto=format&fit=crop&w=900&q=80"},
    "ORD-1044": {"id": "ORD-1044", "buyer": "Kite & Loom", "fabric": "Recycled Denim", "color": "Washed Blue", "qty": 1500, "passed": 0, "deadline": "2025-06-09", "stage": "Weaving", "value": 58400, "otp": "9988", "image": "https://images.unsplash.com/photo-1598032895397-b9472444bf93?auto=format&fit=crop&w=900&q=80"},
}

YARN_STORE: List[dict] = [
    {"id": "LOT-C30-118", "type": "Cotton combed 30s", "color": "Indigo", "qty": 640, "reorder": 300, "supplier": "Arvind Fibres", "order": "ORD-1042", "image": "https://images.unsplash.com/photo-1528459105426-b9548367069b?auto=format&fit=crop&w=800&q=80"},
    {"id": "LOT-TW-204", "type": "Organic cotton", "color": "Moss", "qty": 182, "reorder": 250, "supplier": "GreenThread Co.", "order": "ORD-1043", "image": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80"},
    {"id": "LOT-DN-092", "type": "Recycled denim", "color": "Washed Blue", "qty": 920, "reorder": 400, "supplier": "BlueCycle", "order": "ORD-1044", "image": "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=800&q=80"},
]

MACHINES_STORE: List[dict] = [
    {"id": "S-11", "name": "Spinner 11", "type": "Spinning", "status": "Running", "order": "ORD-1042", "output": 3120, "shift": "A", "efficiency": 87, "floor": 1},
    {"id": "S-12", "name": "Spinner 12", "type": "Spinning", "status": "Running", "order": "ORD-1043", "output": 2890, "shift": "A", "efficiency": 83, "floor": 1},
    {"id": "W-07", "name": "Rapier 07", "type": "Weaving", "status": "Running", "order": "ORD-1042", "output": 2640, "shift": "B", "efficiency": 91, "floor": 1},
    {"id": "W-03", "name": "Rapier 03", "type": "Weaving", "status": "Idle", "order": "ORD-1044", "output": 1880, "shift": "B", "efficiency": 74, "floor": 1},
    {"id": "D-02", "name": "Dyeing 02", "type": "Dyeing", "status": "Maintenance", "order": "ORD-1043", "output": 920, "shift": "A", "efficiency": 0, "floor": 2},
    {"id": "D-05", "name": "Dyeing 05", "type": "Dyeing", "status": "Running", "order": "ORD-1042", "output": 1420, "shift": "A", "efficiency": 78, "floor": 2},
    {"id": "F-01", "name": "Finisher 01", "type": "Finishing", "status": "Running", "order": "ORD-1043", "output": 1680, "shift": "B", "efficiency": 85, "floor": 2},
    {"id": "F-02", "name": "Finisher 02", "type": "Finishing", "status": "Idle", "order": "ORD-1044", "output": 740, "shift": "B", "efficiency": 62, "floor": 2},
]

ROLLS_STORE: List[dict] = [
    {"id": "RL-7781", "order": "ORD-1042", "machine": "W-07", "length": 240, "qc": "Pass", "defect": "—", "worker": "Ravi Kumar", "dispatched": False, "image": "https://images.unsplash.com/photo-1618220179428-22790b461013?auto=format&fit=crop&w=700&q=80"},
    {"id": "RL-7782", "order": "ORD-1042", "machine": "W-07", "length": 210, "qc": "Rework", "defect": "Uneven weaving", "worker": "Ravi Kumar", "dispatched": False, "image": "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?auto=format&fit=crop&w=700&q=80"},
    {"id": "RL-7783", "order": "ORD-1043", "machine": "D-02", "length": 280, "qc": "Pass", "defect": "—", "worker": "Meena Shah", "dispatched": True, "image": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=700&q=80"},
    {"id": "RL-7784", "order": "ORD-1044", "machine": "W-03", "length": 160, "qc": "Pending", "defect": "—", "worker": "Arjun Das", "dispatched": False, "image": "https://images.unsplash.com/photo-1566206091558-7f218b696731?auto=format&fit=crop&w=700&q=80"},
]

FILES_STORE: Dict[str, dict] = {}


# ---------- Auth Dependency ----------
async def get_current_user(request: Request) -> SessionUser:
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    role = payload.get("role")
    sub = payload.get("sub")
    if role == "customer":
        order_id = payload.get("order_id", sub)
        order = ORDERS_EXTRA_STORE.get(order_id)
        buyer_name = order["buyer"] if order else "Customer"
        return SessionUser(id=sub, role="customer", name=buyer_name, initials="LG", order_id=order_id)
    if role == "employee":
        worker = WORKERS_STORE.get(sub)
        if not worker or not worker.get("active", True):
            raise HTTPException(status_code=401, detail="Account inactive")
        return SessionUser(id=worker["id"], role="employee", name=worker["name"],
                           initials="".join(n[0] for n in worker["name"].split()[:2]))
    # owner / admin
    user = USERS_STORE.get(sub) or USERS_STORE.get(role)
    if not user:
        return SessionUser(id=sub, role=role, name=sub.title(), initials=sub[:2].upper())
    return SessionUser(id=user["id"], role=user["role"], name=user["name"], initials=user.get("initials", "US"))


def require_roles(*allowed):
    async def _dep(user: SessionUser = Depends(get_current_user)):
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Not allowed")
        return user
    return _dep


# ---------- Auth Endpoints ----------
@router.post("/auth/login")
async def login(body: LoginBody, response: Response):
    role, identifier, secret = body.role, body.identifier.strip(), body.secret

    if role in ("owner", "admin"):
        user = USERS_STORE.get(identifier.lower())
        if not user or user.get("role") != role or user.get("password") != secret:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        access = create_access_token(user["id"], role)
        refresh = create_refresh_token(user["id"], role)
        set_auth_cookies(response, access, refresh)
        return {
            "access_token": access,
            "user": {"id": user["id"], "role": role, "name": user["name"], "initials": user.get("initials", "US")},
        }

    if role == "employee":
        worker = WORKERS_STORE.get(identifier.upper())
        if not worker:
            raise HTTPException(status_code=401, detail="Employee not found")
        if not worker.get("active", True):
            raise HTTPException(status_code=403, detail="Account disabled by admin")
        if worker.get("pin") != secret:
            raise HTTPException(status_code=401, detail="Wrong PIN")
        access = create_access_token(worker["id"], "employee")
        refresh = create_refresh_token(worker["id"], "employee")
        set_auth_cookies(response, access, refresh)
        return {
            "access_token": access,
            "user": {
                "id": worker["id"],
                "role": "employee",
                "name": worker["name"],
                "initials": "".join(n[0] for n in worker["name"].split()[:2])
            },
        }

    # customer
    order_id = identifier.upper()
    order = ORDERS_EXTRA_STORE.get(order_id)
    if not order:
        raise HTTPException(status_code=401, detail="Order not found")
    if order.get("otp") != secret:
        raise HTTPException(status_code=401, detail="Wrong OTP")
    access = create_access_token(order["id"], "customer", extra={"order_id": order["id"]})
    refresh = create_refresh_token(order["id"], "customer")
    set_auth_cookies(response, access, refresh)
    return {
        "access_token": access,
        "user": {
            "id": order["id"],
            "role": "customer",
            "name": order["buyer"],
            "initials": "LG",
            "order_id": order["id"]
        },
    }


@router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/auth/me")
async def me(user: SessionUser = Depends(get_current_user)):
    return user


# ---------- Tracking ----------
@router.get("/track/{order_id}")
async def track(order_id: str):
    oid = order_id.upper()
    order = ORDERS_EXTRA_STORE.get(oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    res = dict(order)
    res.pop("otp", None)
    return res


# ---------- Dashboard ----------
@router.get("/dashboard")
async def dashboard(user: SessionUser = Depends(get_current_user)):
    orders = list(ORDERS_EXTRA_STORE.values())
    if user.role == "customer":
        orders = [o for o in orders if o["id"] == user.order_id]
    cleaned_orders = []
    for o in orders:
        c = dict(o)
        c.pop("otp", None)
        cleaned_orders.append(c)
    return {
        "orders": cleaned_orders,
        "machines": MACHINES_STORE,
        "yarn": YARN_STORE,
        "rolls": ROLLS_STORE if user.role != "customer" else [r for r in ROLLS_STORE if r["order"] == user.order_id],
        "workers": list(WORKERS_STORE.values())
    }


# ---------- Orders ----------
@router.get("/orders")
async def list_orders(user: SessionUser = Depends(get_current_user)):
    orders = list(ORDERS_EXTRA_STORE.values())
    if user.role == "customer":
        orders = [o for o in orders if o["id"] == user.order_id]
    cleaned = []
    for o in orders:
        c = dict(o)
        c.pop("otp", None)
        cleaned.append(c)
    return cleaned


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: SessionUser = Depends(get_current_user)):
    oid = order_id.upper()
    order = ORDERS_EXTRA_STORE.get(oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == "customer" and order["id"] != user.order_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    res = dict(order)
    res.pop("otp", None)
    return res


@router.patch("/orders/{order_id}/advance")
async def advance_order(order_id: str, user: SessionUser = Depends(require_roles("owner", "admin"))):
    oid = order_id.upper()
    order = ORDERS_EXTRA_STORE.get(oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    stages = ["Weaving", "Checking", "Ready", "Shipped"]
    curr = order.get("stage", "Weaving")
    idx = stages.index(curr) if curr in stages else 0
    next_stage = stages[min(idx + 1, len(stages) - 1)]
    order["stage"] = next_stage
    res = dict(order)
    res.pop("otp", None)
    return res


# ---------- Yarn ----------
@router.get("/yarn")
async def list_yarn(user: SessionUser = Depends(require_roles("owner", "admin", "employee"))):
    return YARN_STORE


@router.post("/yarn")
async def receive_yarn(body: YarnReceive, user: SessionUser = Depends(require_roles("owner", "admin", "employee"))):
    lot_id = f"LOT-{str(uuid.uuid4())[:6].upper()}"
    doc = {
        "id": lot_id,
        "type": body.type,
        "color": body.color,
        "qty": body.qty,
        "reorder": body.reorder,
        "supplier": body.supplier,
        "order": body.order,
        "image": body.image or "https://images.unsplash.com/photo-1528459105426-b9548367069b?auto=format&fit=crop&w=800&q=80",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    YARN_STORE.insert(0, doc)
    return YARN_STORE


# ---------- Machines ----------
@router.get("/machines")
async def list_machines(user: SessionUser = Depends(get_current_user)):
    return MACHINES_STORE


@router.patch("/machines/{machine_id}")
async def update_machine(machine_id: str, body: MachineUpdate, user: SessionUser = Depends(require_roles("owner", "admin", "employee"))):
    mid = machine_id.upper()
    m = next((x for x in MACHINES_STORE if x["id"] == mid), None)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    m["status"] = body.status
    return m


@router.get("/machines/live")
async def machines_live(user: SessionUser = Depends(get_current_user)):
    import time, math
    tick = int(time.time())
    out = []
    for m in MACHINES_STORE:
        doc = dict(m)
        if doc.get("status") == "Running":
            base_out = int(doc.get("output", 0))
            drift = int(((tick % 60) / 60) * 18)
            doc["output"] = base_out + drift
            eff = doc.get("efficiency", 80)
            doc["efficiency"] = max(55, min(99, int(eff + math.sin(tick / 7.0) * 3)))
        out.append(doc)
    return out


# ---------- Rolls ----------
@router.get("/rolls")
async def list_rolls(user: SessionUser = Depends(get_current_user)):
    if user.role == "customer":
        return [r for r in ROLLS_STORE if r["order"] == user.order_id]
    return ROLLS_STORE


@router.patch("/rolls/{roll_id}")
async def update_roll(roll_id: str, body: RollUpdate, user: SessionUser = Depends(require_roles("owner", "admin", "employee"))):
    rid = roll_id.upper()
    roll = next((r for r in ROLLS_STORE if r["id"] == rid), None)
    if not roll:
        raise HTTPException(status_code=404, detail="Roll not found")
    if body.qc is not None:
        roll["qc"] = body.qc
    if body.defect is not None:
        roll["defect"] = body.defect
    return roll


# ---------- Workers ----------
@router.get("/workers")
async def list_workers(user: SessionUser = Depends(require_roles("owner", "admin"))):
    return [
        {k: v for k, v in w.items() if k != "pin"}
        for w in WORKERS_STORE.values()
    ]


@router.post("/workers")
async def create_worker(body: WorkerCreate, user: SessionUser = Depends(require_roles("admin"))):
    wid = body.id.upper()
    if wid in WORKERS_STORE:
        raise HTTPException(status_code=409, detail="Employee ID already exists")
    WORKERS_STORE[wid] = {
        "id": wid,
        "name": body.name,
        "role": body.role,
        "shift": body.shift,
        "status": "Off shift",
        "hours": 0,
        "wage": 0,
        "active": True,
        "pin": body.pin,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return [
        {k: v for k, v in w.items() if k != "pin"}
        for w in WORKERS_STORE.values()
    ]


@router.patch("/workers/{worker_id}")
async def update_worker(worker_id: str, body: WorkerUpdate, user: SessionUser = Depends(require_roles("admin"))):
    wid = worker_id.upper()
    worker = WORKERS_STORE.get(wid)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    if body.active is not None:
        worker["active"] = body.active
    if body.status is not None:
        worker["status"] = body.status
    if body.pin is not None:
        worker["pin"] = body.pin
    return {k: v for k, v in worker.items() if k != "pin"}


# ---------- Uploads ----------
@router.post("/upload")
async def upload_file(request: Request, user: SessionUser = Depends(get_current_user)):
    file_id = str(uuid.uuid4())
    content = await request.body()
    FILES_STORE[file_id] = {
        "id": file_id,
        "filename": "upload.bin",
        "content_type": request.headers.get("content-type", "application/octet-stream"),
        "content": content
    }
    return {"id": file_id, "url": f"/api/files/{file_id}"}


@router.get("/files/{file_id}")
async def get_file(file_id: str):
    file_entry = FILES_STORE.get(file_id)
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    return FastResponse(
        content=file_entry["content"],
        media_type=file_entry["content_type"],
        headers={"Cache-Control": "public, max-age=86400"}
    )
