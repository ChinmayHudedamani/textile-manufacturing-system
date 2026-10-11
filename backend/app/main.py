"""
Everest Textile Manufacturing System (ETMS) - Enterprise Core API Server.
Modular Architecture:
- routers.inventory:  Scene 1 (Raw Yarn Inward & Safety Buffer)
- routers.machines:   Scene 2 (Floor Telemetry, Kanban, Breakdowns, Simulation Tick)
- routers.quality:    Scene 3 (ASTM D5430 4-Point Inspection & Upstream Lineage)
- routers.dispatch:   Scene 4 (Truck Dock Manifest & Anti-Double Dispatch Guard)
- routers.orders:     Scene 5 (Order Milestones & Buyer Self-Service Transparency)
- routers.finance:    Scene 6 (Activity-Based Costing & Mill PnL Books)
- loomtrack_api:      LoomTrack React App Multi-Role Compatibility Layer
"""
import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.database import engine, Base, AsyncSessionLocal
from backend.app.seed_data import seed_initial_mill_data

# Import Domain Routers
from backend.app.routers.inventory import router as inventory_router
from backend.app.routers.machines import router as machines_router
from backend.app.routers.quality import router as quality_router
from backend.app.routers.dispatch import router as dispatch_router
from backend.app.routers.orders import router as orders_router
from backend.app.routers.finance import router as finance_router
from backend.app.routers.demands import router as demands_router
from backend.app.loomtrack_api import router as loomtrack_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Seed Initial Operational Mill Data
    async with AsyncSessionLocal() as session:
        await seed_initial_mill_data(session)
    
    yield


app = FastAPI(
    title="Everest Textile Manufacturing System (ETMS) - Enterprise Core API",
    description="Modular Clean-Architecture Operational Ledger Engine for Everest Textile Mills",
    version="2.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.auth import (
    RoleRegistry,
    UserProfileDTO,
    get_current_user_role,
    BaseRole,
    UserRoleEnum
)

# 0. Health Liveness Probe
@app.get("/api/v1/health", tags=["System Health"])
async def health_check():
    """System liveness probe reporting service status and timestamp."""
    return {
        "status": "HEALTHY",
        "service": "ETMS Enterprise Core",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.1.0",
        "architecture": "Clean Modular Router-Controller Engine"
    }


# 0b. Strict Role Authentication & Profile Verification Endpoint
@app.get("/api/v1/auth/profile", response_model=UserProfileDTO, tags=["Authentication & RBAC"])
async def get_user_profile(user_role: BaseRole = Depends(get_current_user_role)):
    """Validates X-User-Role header and returns strict RBAC permissions & routes using OOP encapsulation."""
    return UserProfileDTO(
        role=user_role.role_name.value,
        display_title=user_role.display_title,
        allowed_routes=user_role.get_allowed_routes(),
        permissions=[p.value for p in user_role._permissions]
    )


@app.get("/api/v1/auth/roles", tags=["Authentication & RBAC"])
async def list_available_system_roles():
    """Returns available enterprise roles with their polymorphic permissions."""
    return [
        {
            "role": role_key,
            "display_title": role_obj.display_title,
            "allowed_routes": role_obj.get_allowed_routes()
        }
        for role_key, role_obj in RoleRegistry._REGISTRY.items()
    ]

# 1-6. Register Domain Feature Routers
app.include_router(inventory_router)
app.include_router(machines_router)
app.include_router(quality_router)
app.include_router(dispatch_router)
app.include_router(orders_router)
app.include_router(finance_router)
app.include_router(demands_router)

# 7. LoomTrack React Compatibility Router
app.include_router(loomtrack_router)

# 8. Serve Frontend Static Assets
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
