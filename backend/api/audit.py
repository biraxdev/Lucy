"""
Audit trail REST API — blockchain-like immutable event log.
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from core.audit_logger import log_event, verify_chain
from db.models import AuditTrail, Tenant
from dependencies import CurrentUser, OperatorUser, SuperAdminUser

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditCreate(BaseModel):
    action: str = Field(..., max_length=64)
    actor: str = Field(..., max_length=128)
    resource_type: Optional[str] = Field(None, max_length=64)
    resource_id: Optional[str] = Field(None, max_length=128)
    details: Optional[dict] = None
    tenant_id: Optional[str] = None


class AuditVerifyResponse(BaseModel):
    valid: bool
    checked_count: int
    first_invalid_id: Optional[str] = None
    latest_hash: Optional[str] = None


@router.get("")
async def list_audit_entries(
    current_user: CurrentUser,
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    q = AuditTrail.select().order_by(AuditTrail.timestamp.desc())
    if action:
        q = q.where(AuditTrail.action == action)
    if resource_type:
        q = q.where(AuditTrail.resource_type == resource_type)
    if resource_id:
        q = q.where(AuditTrail.resource_id == resource_id)
    if actor:
        q = q.where(AuditTrail.actor == actor)

    tenant = getattr(current_user, "tenant", None)
    if tenant:
        q = q.where(AuditTrail.tenant == tenant)

    return [entry.to_dict() for entry in q.offset(offset).limit(limit)]


@router.get("/verify", response_model=AuditVerifyResponse)
async def verify_audit_chain(
    current_user: CurrentUser,
    limit: int = Query(1000, ge=1, le=10000),
) -> dict:
    return verify_chain(limit=limit)


@router.post("", status_code=201)
async def create_audit_entry(
    body: AuditCreate,
    current_user: OperatorUser,
) -> dict:
    tenant = None
    if body.tenant_id:
        tenant = Tenant.get_or_none(Tenant.id == body.tenant_id)

    entry = log_event(
        action=body.action,
        actor=body.actor,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        details=body.details,
        tenant=tenant,
    )
    return entry.to_dict()


@router.delete("", status_code=204)
async def delete_all_audit_entries(current_user: SuperAdminUser) -> None:
    """Emergency only — superadmin can wipe the audit trail."""
    AuditTrail.delete().execute()
