"""
Tenant management API for Project Lucy — multi-tenant isolation.
Only superadmin (role='superadmin') can create/delete tenants and assign users.
"""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from database import database
from db.models import Tenant, User
from dependencies import CurrentUser, SuperAdminUser

router = APIRouter(prefix="/tenants", tags=["tenants"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TenantCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    color: str = "#6366f1"

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9\-]{1,30}[a-z0-9]$", v):
            raise ValueError("slug must be lowercase letters, numbers, hyphens (3-32 chars)")
        return v


class TenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    active: bool | None = None


class UserAssign(BaseModel):
    user_id: str
    role: str = "operator"  # admin | operator | viewer


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_tenants(current_user: CurrentUser) -> list[dict]:
    """All users can see the list; non-superadmin only sees their own tenant."""
    if current_user.get("role") == "superadmin":
        return [t.to_dict() for t in Tenant.select().order_by(Tenant.name)]
    tid = current_user.get("tenant_id")
    if tid:
        t = Tenant.get_or_none(Tenant.id == tid)
        return [t.to_dict()] if t else []
    return []


@router.post("", status_code=201)
async def create_tenant(body: TenantCreate, current_user: SuperAdminUser) -> dict:
    if Tenant.get_or_none(Tenant.slug == body.slug):
        raise HTTPException(409, f"Slug '{body.slug}' already exists")
    with database:
        tenant = Tenant.create(
            name=body.name,
            slug=body.slug,
            description=body.description,
            color=body.color,
        )
    return tenant.to_dict()


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, current_user: CurrentUser) -> dict:
    tenant = Tenant.get_or_none(Tenant.id == tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if current_user.get("role") != "superadmin" and str(current_user.get("tenant_id")) != tenant_id:
        raise HTTPException(403, "Access denied")
    return tenant.to_dict()


@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, body: TenantUpdate, current_user: SuperAdminUser) -> dict:
    tenant = Tenant.get_or_none(Tenant.id == tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        with database:
            Tenant.update(**updates).where(Tenant.id == tenant_id).execute()
    return Tenant.get_by_id(tenant_id).to_dict()


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, current_user: SuperAdminUser) -> None:
    with database:
        n = Tenant.delete().where(Tenant.id == tenant_id).execute()
    if not n:
        raise HTTPException(404, "Tenant not found")


@router.get("/{tenant_id}/members")
async def list_tenant_members(tenant_id: str, current_user: SuperAdminUser) -> list[dict]:
    return [u.to_dict() for u in User.select().where(User.tenant == tenant_id)]


@router.post("/{tenant_id}/members")
async def assign_user(tenant_id: str, body: UserAssign, current_user: SuperAdminUser) -> dict:
    tenant = Tenant.get_or_none(Tenant.id == tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    user = User.get_or_none(User.id == body.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    with database:
        User.update(tenant=tenant_id, role=body.role).where(User.id == body.user_id).execute()
    return User.get_by_id(body.user_id).to_dict()


@router.delete("/{tenant_id}/members/{user_id}", status_code=204)
async def remove_user(tenant_id: str, user_id: str, current_user: SuperAdminUser) -> None:
    with database:
        User.update(tenant=None, role="viewer").where(User.id == user_id).execute()


@router.get("/{tenant_id}/stats")
async def tenant_stats(tenant_id: str, current_user: CurrentUser) -> dict:
    if current_user.get("role") != "superadmin" and str(current_user.get("tenant_id")) != tenant_id:
        raise HTTPException(403, "Access denied")
    from db.models import Agent, Task, Credential, Finding
    return {
        "tenant_id": tenant_id,
        "agents":      Agent.select().where(Agent.tenant == tenant_id).count(),
        "tasks":       Task.select().where(Task.tenant == tenant_id).count(),
        "credentials": Credential.select().where(Credential.tenant == tenant_id).count(),
        "findings":    Finding.select().where(Finding.tenant == tenant_id).count(),
        "members":     User.select().where(User.tenant == tenant_id).count(),
    }
