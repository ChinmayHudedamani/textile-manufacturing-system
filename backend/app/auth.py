"""
Authentication & Authorization Module for Everest Textile Manufacturing System.
Applies Object-Oriented Principles:
- Polymorphism & Inheritance (BaseRole -> OwnerRole, FloorSupervisorRole, CustomerRole, AdminRole)
- Encapsulation (RoleManager hides internal permission mappings)
- Strict RBAC validation via FastAPI Dependency Injection
"""
from enum import Enum
from typing import List, Set, Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, status, Depends


class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"
    FLOOR_SUPERVISOR = "floor_supervisor"
    CUSTOMER = "customer"


class Permission(str, Enum):
    # Inventory
    VIEW_INVENTORY = "view_inventory"
    INWARD_YARN = "inward_yarn"
    DELETE_YARN = "delete_yarn"

    # Floor & Machines
    VIEW_MACHINES = "view_machines"
    CONTROL_MACHINES = "control_machines"
    FLAG_BREAKDOWN = "flag_breakdown"
    REPAIR_MACHINE = "repair_machine"

    # Quality Control
    VIEW_QUALITY = "view_quality"
    PRODUCE_ROLL = "produce_roll"
    INSPECT_ROLL = "inspect_roll"

    # Dispatch & Fleet
    VIEW_DISPATCH = "view_dispatch"
    SCAN_DISPATCH = "scan_dispatch"
    REVOKE_DISPATCH = "revoke_dispatch"

    # Orders & Tracking
    VIEW_ORDERS = "view_orders"
    TRACK_OWN_ORDER = "track_own_order"

    # Financial Books
    VIEW_FINANCE = "view_finance"
    EXPORT_COSTING = "export_costing"


# =====================================================================
# Object-Oriented Hierarchy: Role Base & Concrete Subclasses
# =====================================================================

class BaseRole:
    """Abstract Base Class for Enterprise Roles demonstrating Encapsulation & Inheritance."""
    def __init__(self, role_name: UserRoleEnum, display_title: str, permissions: Set[Permission]):
        self._role_name = role_name
        self._display_title = display_title
        self._permissions = permissions

    @property
    def role_name(self) -> UserRoleEnum:
        return self._role_name

    @property
    def display_title(self) -> str:
        return self._display_title

    def has_permission(self, permission: Permission) -> bool:
        """Encapsulated permission checking."""
        return permission in self._permissions

    def get_allowed_routes(self) -> List[str]:
        """Polymorphic route access definitions."""
        raise NotImplementedError("Subclasses must implement get_allowed_routes")


class AdminRole(BaseRole):
    """System Administrator: Full unconstrained system privileges."""
    def __init__(self):
        super().__init__(
            role_name=UserRoleEnum.ADMIN,
            display_title="System Administrator",
            permissions=set(Permission)
        )

    def get_allowed_routes(self) -> List[str]:
        return ["yarn", "machines", "quality", "dispatch", "orders", "finance"]


class OwnerRole(BaseRole):
    """Mill Owner: Executive Financial and Commercial Books."""
    def __init__(self):
        super().__init__(
            role_name=UserRoleEnum.OWNER,
            display_title="Mill Owner / Executive",
            permissions={
                Permission.VIEW_FINANCE,
                Permission.EXPORT_COSTING,
                Permission.VIEW_ORDERS,
                Permission.VIEW_MACHINES,
            }
        )

    def get_allowed_routes(self) -> List[str]:
        return ["finance", "orders"]


class FloorSupervisorRole(BaseRole):
    """Floor Supervisor: Shopfloor telemetry, looms, QC bench, dispatch dock."""
    def __init__(self):
        super().__init__(
            role_name=UserRoleEnum.FLOOR_SUPERVISOR,
            display_title="Shopfloor Supervisor",
            permissions={
                Permission.VIEW_INVENTORY,
                Permission.INWARD_YARN,
                Permission.DELETE_YARN,
                Permission.VIEW_MACHINES,
                Permission.CONTROL_MACHINES,
                Permission.FLAG_BREAKDOWN,
                Permission.REPAIR_MACHINE,
                Permission.VIEW_QUALITY,
                Permission.PRODUCE_ROLL,
                Permission.INSPECT_ROLL,
                Permission.VIEW_DISPATCH,
                Permission.SCAN_DISPATCH,
                Permission.REVOKE_DISPATCH,
                Permission.VIEW_ORDERS,
            }
        )

    def get_allowed_routes(self) -> List[str]:
        return ["yarn", "machines", "quality", "dispatch"]


class CustomerRole(BaseRole):
    """Customer / Buyer: Order progress, demands, and dispatch manifest."""
    def __init__(self):
        super().__init__(
            role_name=UserRoleEnum.CUSTOMER,
            display_title="Customer / Inditex / M&S Procurement",
            permissions={
                Permission.VIEW_ORDERS,
                Permission.TRACK_OWN_ORDER,
            }
        )

    def get_allowed_routes(self) -> List[str]:
        return ["demands", "orders"]


# =====================================================================
# Role Registry & Manager (Encapsulation)
# =====================================================================

class RoleRegistry:
    """Encapsulated Registry Factory mapping role keys to OOP Role instances."""
    _REGISTRY = {
        UserRoleEnum.ADMIN.value: AdminRole(),
        UserRoleEnum.OWNER.value: OwnerRole(),
        UserRoleEnum.FLOOR_SUPERVISOR.value: FloorSupervisorRole(),
        UserRoleEnum.CUSTOMER.value: CustomerRole(),
    }

    @classmethod
    def get_role(cls, role_key: Optional[str]) -> BaseRole:
        """Retrieves role object with safe default fallback to Admin."""
        clean_key = (role_key or "").strip().lower()
        return cls._REGISTRY.get(clean_key, cls._REGISTRY[UserRoleEnum.ADMIN.value])


class UserProfileDTO(BaseModel):
    role: str
    display_title: str
    allowed_routes: List[str]
    permissions: List[str]


# =====================================================================
# FastAPI Dependency Injection Guard
# =====================================================================

def get_current_user_role(
    x_user_role: Optional[str] = Header(default="admin", alias="X-User-Role")
) -> BaseRole:
    """Extracts and validates user role from HTTP Header."""
    return RoleRegistry.get_role(x_user_role)


class RequirePermission:
    """Dependency callable class validating fine-grained permissions."""
    def __init__(self, required_permission: Permission):
        self.required_permission = required_permission

    def __call__(self, user_role: BaseRole = Depends(get_current_user_role)) -> BaseRole:
        if not user_role.has_permission(self.required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Role '{user_role.display_title}' lacks required permission '{self.required_permission.value}'."
            )
        return user_role
