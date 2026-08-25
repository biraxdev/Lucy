"""
Configuration portability endpoints.

Export/import timelines, agent groups and modules as JSON.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config_port import export_config, import_config
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/config", tags=["config"])


class ImportBody(BaseModel):
    config: dict
    strategy: Literal["overwrite", "skip", "rename"] = "skip"


@router.get("/export")
async def export_configuration(
    types: str = "timelines,groups,modules",
    current_user: CurrentUser = None,
) -> dict:
    """Export configuration objects as JSON."""
    tenant_id = None
    if current_user and current_user.get("role") != "superadmin":
        tenant_id = current_user.get("tenant_id")

    type_list = [t.strip() for t in types.split(",") if t.strip()]
    return export_config(types=type_list, tenant_id=tenant_id)


@router.post("/import")
async def import_configuration(
    body: ImportBody,
    current_user: OperatorUser = None,
) -> dict:
    """Import configuration objects from JSON."""
    tenant_id = None
    if current_user and current_user.get("role") != "superadmin":
        tenant_id = current_user.get("tenant_id")

    if not isinstance(body.config, dict):
        raise HTTPException(status_code=400, detail="config must be a JSON object")

    return import_config(
        data=body.config,
        strategy=body.strategy,
        tenant_id=tenant_id,
    )
