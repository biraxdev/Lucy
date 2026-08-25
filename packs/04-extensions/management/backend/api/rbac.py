"""
RBAC management API for Lucy C2.
Manage operator roles and permissions.
GET  /rbac/roles       — list all roles
GET  /rbac/permissions — list all permissions
GET  /rbac/users       — list users with their roles
PUT  /rbac/users/{id}  — update a user's role (admin only)
GET  /rbac/matrix      — role-permission matrix
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from database import database
from db.models import User
from dependencies import CurrentUser, AdminUser

router = APIRouter(prefix="/rbac", tags=["rbac"])

# ---------------------------------------------------------------------------
# Role & permission definitions
# ---------------------------------------------------------------------------

ROLES = {
    "superadmin": {
        "description": "Full access — all tenants, all operations",
        "permissions": ["*"],
    },
    "admin": {
        "description": "Tenant admin — manage users, agents, all operations",
        "permissions": [
            "agents:read", "agents:write", "agents:delete",
            "tasks:read", "tasks:write", "tasks:delete",
            "credentials:read", "credentials:write", "credentials:delete",
            "findings:read", "findings:write", "findings:delete",
            "alerts:read", "alerts:write",
            "reports:read", "reports:write",
            "build:read", "build:write",
            "timelines:read", "timelines:write",
            "operators:read", "operators:manage",
            "rbac:read",
        ],
    },
    "operator": {
        "description": "Red team operator — execute operations, manage agents",
        "permissions": [
            "agents:read", "agents:write",
            "tasks:read", "tasks:write",
            "credentials:read", "credentials:write",
            "findings:read", "findings:write",
            "alerts:read", "alerts:write",
            "reports:read", "reports:write",
            "build:read", "build:write",
            "timelines:read", "timelines:write",
            "operators:read",
        ],
    },
    "viewer": {
        "description": "Read-only access — observe operations, view data",
        "permissions": [
            "agents:read",
            "tasks:read",
            "credentials:read",
            "findings:read",
            "alerts:read",
            "reports:read",
            "build:read",
            "timelines:read",
            "operators:read",
        ],
    },
}

ALL_PERMISSIONS = [
    "agents:read", "agents:write", "agents:delete",
    "tasks:read", "tasks:write", "tasks:delete",
    "credentials:read", "credentials:write", "credentials:delete",
    "findings:read", "findings:write", "findings:delete",
    "alerts:read", "alerts:write",
    "reports:read", "reports:write",
    "build:read", "build:write",
    "timelines:read", "timelines:write",
    "operators:read", "operators:manage",
    "rbac:read",
]


class UpdateRoleBody(BaseModel):
    role: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/roles")
async def list_roles(current_user: CurrentUser = None) -> dict:
    """List all available roles with their permissions."""
    return ROLES


@router.get("/permissions")
async def list_permissions(current_user: CurrentUser = None) -> list[str]:
    """List all possible permissions."""
    return ALL_PERMISSIONS


@router.get("/users")
async def list_users(current_user: AdminUser = None) -> list[dict]:
    """List all users with their roles (admin only)."""
    with database:
        users = User.select(User.id, User.username, User.role, User.created_at)
        return [
            {
                "id": str(u.id),
                "username": u.username,
                "role": u.role,
                "created_at": str(u.created_at) if hasattr(u, "created_at") else None,
            }
            for u in users
        ]


@router.put("/users/{user_id}")
async def update_user_role(
    user_id: str,
    body: UpdateRoleBody,
    current_user: AdminUser = None,
) -> dict:
    """Update a user's role (admin only)."""
    if body.role not in ROLES:
        raise HTTPException(400, f"Invalid role. Valid roles: {list(ROLES.keys())}")

    with database:
        updated = User.update(
            role=body.role,
            updated_at=datetime.now(timezone.utc),
        ).where(User.id == user_id).execute()
        if not updated:
            raise HTTPException(404, "User not found")

    return {"ok": True, "user_id": user_id, "role": body.role}


@router.get("/matrix")
async def permission_matrix(current_user: CurrentUser = None) -> dict:
    """Return the role-permission matrix for UI rendering."""
    matrix = {}
    for role, info in ROLES.items():
        perms = info["permissions"]
        if "*" in perms:
            matrix[role] = {p: True for p in ALL_PERMISSIONS}
        else:
            matrix[role] = {p: p in perms for p in ALL_PERMISSIONS}
    return {
        "roles": list(ROLES.keys()),
        "permissions": ALL_PERMISSIONS,
        "matrix": matrix,
    }


@router.get("/me")
async def my_permissions(current_user: CurrentUser = None) -> dict:
    """Return the current user's role and permissions."""
    role = current_user.get("role", "viewer") if isinstance(current_user, dict) else "viewer"
    role_info = ROLES.get(role, ROLES["viewer"])
    perms = role_info["permissions"]
    return {
        "user_id": current_user.get("id") if isinstance(current_user, dict) else None,
        "username": current_user.get("username") if isinstance(current_user, dict) else None,
        "role": role,
        "permissions": perms,
        "is_admin": role in ("admin", "superadmin"),
        "is_operator": role in ("admin", "operator", "superadmin"),
    }
