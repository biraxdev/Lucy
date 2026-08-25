"""
Unified full-text search API.

GET /api/v1/search?q=...&types=...&limit=...
"""
from fastapi import APIRouter, Query
from typing import Optional

from core.search_engine import search, SEARCHABLE_ENTITIES
from dependencies import CurrentUser, get_tenant_id

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def unified_search(
    q: str = Query(..., min_length=1, description="Search query"),
    types: Optional[list[str]] = Query(None, description="Resource types to search"),
    limit: int = Query(50, ge=1, le=500),
    current_user: CurrentUser = None,
) -> dict:
    """Search across agents, tasks, credentials, logs, findings, alerts, files, and audit trail."""
    tenant_id = None
    if current_user and current_user.get("role") != "superadmin":
        tenant_id = current_user.get("tenant_id")

    result = search(query=q, types=types, tenant_id=tenant_id, limit=limit)
    return result
