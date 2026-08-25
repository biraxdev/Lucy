"""
Dashboard API for live operational views.

GET /api/v1/dashboard/heatmap?by=time|agent&hours=24
"""
from fastapi import APIRouter, Query
from typing import Literal

from core.heatmap_engine import HeatmapEngine
from dependencies import CurrentUser, get_tenant_id

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/heatmap")
async def activity_heatmap(
    by: Literal["time", "agent"] = Query("time", description="Heatmap aggregation mode"),
    hours: int = Query(24, ge=1, le=168, description="Hours window for agent mode"),
    current_user: CurrentUser = None,
) -> dict:
    """Return a live activity heatmap for agents."""
    tenant_id = None
    if current_user and current_user.get("role") != "superadmin":
        tenant_id = current_user.get("tenant_id")

    return HeatmapEngine().heatmap(by=by, hours_window=hours, tenant_id=tenant_id)
