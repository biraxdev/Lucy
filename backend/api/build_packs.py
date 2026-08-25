"""Build Pack API — reusable agent build presets with full pack management."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from core.pack_manager import (
    apply_pack,
    combine_pack,
    create_pack,
    delete_pack,
    duplicate_pack,
    export_pack,
    get_pack,
    import_pack,
    list_packs,
    update_pack,
)
from db.models import BuildPack
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/build-packs", tags=["build-packs"])


class BuildPackCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    icon: str = "📦"
    tags: list[str] = []
    modules: list[str] = []
    build_options: dict = {}


class BuildPackUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    tags: list[str] | None = None
    modules: list[str] | None = None
    build_options: dict | None = None


class BuildPackCombine(BaseModel):
    bpid_b: str
    new_id: str
    name: str


class BuildPackBuild(BaseModel):
    pass


class BuildPackImport(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    icon: str = "📦"
    tags: list[str] = []
    modules: list[str] = []
    build_options: dict = {}


@router.get("")
async def list_build_packs(q: str | None = Query(None), current_user: CurrentUser = None) -> list[dict]:
    _ = current_user
    """Return all reusable build packs, optionally filtered by query."""
    return list_packs(q)


@router.get("/{bpid}")
async def get_build_pack(bpid: str, current_user: CurrentUser) -> dict:
    """Return a specific build pack by its stable id."""
    pack = get_pack(bpid)
    if not pack:
        raise HTTPException(404, "Build pack not found")
    return pack


@router.post("", status_code=201)
async def create_build_pack(body: BuildPackCreate, current_user: OperatorUser) -> dict:
    """Create a new custom build pack."""
    try:
        return create_pack(body.id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{bpid}")
async def update_build_pack(bpid: str, body: BuildPackUpdate, current_user: OperatorUser) -> dict:
    """Update a custom build pack."""
    try:
        update = body.model_dump(exclude_unset=True)
        existing = get_pack(bpid)
        if not existing:
            raise HTTPException(404, "Build pack not found")
        # merge fields
        for key in ["name", "description", "icon", "tags", "modules", "build_options"]:
            if key not in update or update[key] is None:
                update[key] = existing.get(key)
        return update_pack(bpid, update)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{bpid}")
async def delete_build_pack(bpid: str, current_user: OperatorUser) -> dict:
    """Delete a custom build pack."""
    try:
        delete_pack(bpid)
        return {"deleted": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{bpid}/duplicate", status_code=201)
async def duplicate_build_pack(bpid: str, current_user: OperatorUser) -> dict:
    """Duplicate a build pack."""
    try:
        return duplicate_pack(bpid)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{bpid}/combine", status_code=201)
async def combine_build_pack(bpid: str, body: BuildPackCombine, current_user: OperatorUser) -> dict:
    """Combine two build packs into a new one."""
    try:
        return combine_pack(bpid, body.bpid_b, body.new_id, body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{bpid}/export")
async def export_build_pack(bpid: str, current_user: CurrentUser) -> dict:
    """Export a build pack as JSON."""
    try:
        return export_pack(bpid)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/import", status_code=201)
async def import_build_pack(body: BuildPackImport, current_user: OperatorUser) -> dict:
    """Import a build pack from JSON."""
    try:
        return import_pack(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{bpid}/apply")
async def apply_build_pack(bpid: str, current_user: CurrentUser) -> dict:
    """Return build options ready to be used by the AgentBuilder."""
    try:
        return apply_pack(bpid)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{bpid}/build", status_code=201)
async def build_from_pack(bpid: str, request: Request, current_user: OperatorUser) -> dict:
    """Build an agent directly from a pack."""
    pack = get_pack(bpid)
    if not pack:
        raise HTTPException(404, "Build pack not found")

    from api.build import BuildRequest, schedule_build
    from db.models import User

    user = User.get_by_id(current_user.get("id"))
    build_options = pack.get("build_options", {})
    # Limit options to BuildRequest known fields to avoid Pydantic extra-field errors
    known = set(BuildRequest.model_fields.keys())
    build_options = {k: v for k, v in build_options.items() if k in known}

    body = BuildRequest(
        os="windows",
        arch="x64",
        modules=pack.get("modules", []),
        server_url=str(request.base_url).rstrip("/"),
        api_key=user.api_key if user else "",
        **build_options,
    )
    build_id = schedule_build(body, str(current_user.get("id")))
    return {"build_id": build_id, "status": "queued"}
