"""
Library API — exposes the Resource Library through a REST interface.

This router is designed to match the frontend's expected URL scheme:
    GET    /api/v1/library
    GET    /api/v1/library/search
    GET    /api/v1/library/types
    GET    /api/v1/library/tags
    POST   /api/v1/library
    GET    /api/v1/library/:id
    PATCH  /api/v1/library/:id
    DELETE /api/v1/library/:id
    GET    /api/v1/library/:id/preview
    GET    /api/v1/library/:id/versions
    POST   /api/v1/library/:id/versions
    POST   /api/v1/library/:id/versions/:version_id/restore
    GET    /api/v1/library/:id/relations
    POST   /api/v1/library/:id/relations
    DELETE /api/v1/library/:id/relations/:relation_id
    GET    /api/v1/library/:id/graph
    POST   /api/v1/library/:id/favorite
    POST   /api/v1/library/:id/pin
    POST   /api/v1/library/:id/duplicate
    GET    /api/v1/library/duplicates
    GET    /api/v1/library/suggestions/:id
    POST   /api/v1/library/import
    GET    /api/v1/library/:id/export
    POST   /api/v1/library/cve/import
    GET    /api/v1/library/stats
"""
from __future__ import annotations

import json
from typing import Any, Optional

import asyncio

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from core.library.base import compute_content_hash
from core.library.registry import registry
from core.library.relations import (
    VALID_RELATION_TYPES,
    auto_resolve_relations,
    create_relation as _create_relation,
    delete_relation as _delete_relation,
    get_relation_graph,
    get_relations as _get_relations,
)
from core.library.search import get_all_tags, get_type_counts, search_resources
from database import database
from db.models import Resource, ResourceVersion
from dependencies import AdminUser, CurrentUser, OperatorUser

router = APIRouter(prefix="/library", tags=["library"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _ResourceCreate(BaseModel):
    resource_type: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    content: str = ""
    language: str = ""
    status: str = "draft"
    visibility: str = "internal"
    tags: list[str] = []
    references: list[str] = []
    dependencies: list[str] = []
    metadata: dict = {}


class _ResourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None
    content: str | None = None
    language: str | None = None
    status: str | None = None
    version: str | None = None
    visibility: str | None = None
    tags: list[str] | None = None
    references: list[str] | None = None
    dependencies: list[str] | None = None
    metadata: dict | None = None
    favorite: bool | None = None
    pinned: bool | None = None
    change_note: str | None = None


class _RelationCreate(BaseModel):
    target_id: str = Field(..., min_length=1)
    relation_type: str = Field(..., pattern="^(references|depends_on|related_to|implements|tests|describes|affects|derived_from|part_of|replaces)$")
    metadata: dict = {}


class _CVEImport(BaseModel):
    cve_id: str = Field(..., pattern=r"^CVE-\d{4}-\d+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_tenant(user: dict | None) -> Optional[str]:
    return user.get("tenant_id") if user else None


def _provider_or_404(resource_type: str) -> Any:
    registry.load_all_providers()
    provider = registry.get(resource_type)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown resource type: {resource_type}",
        )
    return provider


def _resource_or_404(resource_id: str) -> Resource:
    resource = Resource.get_or_none(Resource.id == resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


# ---------------------------------------------------------------------------
# List / Search
# ---------------------------------------------------------------------------


@router.get("")
async def list_resources(
    current_user: CurrentUser,
    q: str = "",
    type: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    language: str | None = None,
    visibility: str | None = None,
    favorite: bool | None = None,
    pinned: bool | None = None,
    sort: str = "updated_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Search resources with filtering and pagination."""
    filters: dict[str, Any] = {"sort": sort}
    if type:
        filters["type"] = type
    if tag:
        filters["tag"] = tag
    if status:
        filters["status"] = status
    if language:
        filters["language"] = language
    if visibility:
        filters["visibility"] = visibility
    if favorite is not None:
        filters["favorite"] = favorite
    if pinned is not None:
        filters["pinned"] = pinned

    results, total = search_resources(q, filters, current_user, limit, offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/search")
async def search_library(
    current_user: CurrentUser,
    q: str = "",
    type: list[str] = Query(default=[]),
    tag: list[str] = Query(default=[]),
    status: list[str] = Query(default=[]),
    language: str | None = None,
    visibility: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Dedicated search endpoint."""
    filters: dict[str, Any] = {}
    if type:
        filters["type"] = type
    if tag:
        filters["tag"] = tag
    if status:
        filters["status"] = status
    if language:
        filters["language"] = language
    if visibility:
        filters["visibility"] = visibility

    results, total = search_resources(q, filters, current_user, limit, offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Types, tags, stats
# ---------------------------------------------------------------------------


@router.get("/types")
async def list_types(current_user: CurrentUser) -> dict:
    """List all resource types with counts."""
    counts = get_type_counts(current_user)
    registry.load_all_providers()
    return {
        "types": [
            {"type": rtype, "count": counts.get(rtype, 0)}
            for rtype in registry.all_types()
        ],
    }


@router.get("/tags")
async def list_tags(current_user: CurrentUser) -> dict:
    """List all unique tags across resources."""
    return {"tags": get_all_tags(current_user)}


@router.get("/stats")
async def get_stats(current_user: CurrentUser) -> dict:
    """High-level library statistics."""
    counts = get_type_counts(current_user)
    return {
        "total_resources": sum(counts.values()),
        "by_type": counts,
        "providers_loaded": len(registry.all_providers()),
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resource(body: _ResourceCreate, current_user: OperatorUser) -> dict:
    """Create a new native resource."""
    provider = _provider_or_404(body.resource_type)
    tenant_id = _extract_tenant(current_user)
    data = body.model_dump()
    data["created_by"] = current_user.get("username")
    return provider.create(data, tenant_id, current_user)


@router.get("/{resource_id}")
async def get_resource(resource_id: str, current_user: CurrentUser) -> dict:
    """Get a single resource."""
    return _resource_or_404(resource_id).to_dict(include_content=True)


@router.patch("/{resource_id}")
async def update_resource(
    resource_id: str,
    body: _ResourceUpdate,
    current_user: OperatorUser,
) -> dict:
    """Update an existing resource."""
    resource = _resource_or_404(resource_id)
    provider = _provider_or_404(resource.resource_type)
    tenant_id = _extract_tenant(current_user)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["updated_by"] = current_user.get("username")
    return provider.update(resource_id, data, tenant_id, current_user)


@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: str,
    current_user: AdminUser,
) -> dict:
    """Delete a resource."""
    resource = _resource_or_404(resource_id)
    provider = _provider_or_404(resource.resource_type)
    tenant_id = _extract_tenant(current_user)
    provider.delete(resource_id, tenant_id, current_user)
    return {"deleted": True, "id": resource_id}


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


@router.get("/{resource_id}/preview")
async def preview_resource(
    resource_id: str,
    current_user: CurrentUser,
) -> dict:
    """Get a type-adapted preview."""
    resource = _resource_or_404(resource_id)
    provider = _provider_or_404(resource.resource_type)
    tenant_id = _extract_tenant(current_user)
    preview = provider.preview(resource_id, tenant_id)
    if preview is None:
        return resource.to_dict(include_content=False)
    return preview


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get("/{resource_id}/versions")
async def get_resource_versions(
    resource_id: str,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Get version history for a resource."""
    _resource_or_404(resource_id)
    query = ResourceVersion.select().where(ResourceVersion.resource == resource_id)
    query = query.order_by(ResourceVersion.created_at.desc())
    total = query.count()
    versions = [v.to_dict() for v in query.limit(limit).offset(offset)]
    return {"versions": versions, "total": total, "limit": limit, "offset": offset}


@router.post("/{resource_id}/versions")
async def create_version_snapshot(
    resource_id: str,
    current_user: CurrentUser,
    change_note: str = Form(""),
) -> dict:
    """Create a manual version snapshot."""
    resource = _resource_or_404(resource_id)
    from core.library.base import create_version_snapshot
    return create_version_snapshot(resource, change_note, current_user).to_dict()


@router.post("/{resource_id}/versions/{version_id}/restore")
async def restore_version(
    resource_id: str,
    version_id: str,
    current_user: OperatorUser,
) -> dict:
    """Restore a resource to a previous version."""
    resource = _resource_or_404(resource_id)
    version = ResourceVersion.get_or_none(ResourceVersion.id == version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = json.loads(version.snapshot) if version.snapshot else {}
    for field in ["name", "description", "content", "language", "status", "version", "visibility"]:
        if field in snapshot:
            setattr(resource, field, snapshot[field])

    # Restore JSON fields
    if "tags" in snapshot:
        resource.tags_list = snapshot["tags"]
    if "references" in snapshot:
        resource.references_list = snapshot["references"]
    if "dependencies" in snapshot:
        resource.dependencies_list = snapshot["dependencies"]
    if "metadata" in snapshot:
        resource.metadata_dict = snapshot["metadata"]

    resource.content_hash = compute_content_hash(resource.content)
    resource.save()
    return resource.to_dict(include_content=True)


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


@router.get("/{resource_id}/relations")
async def get_resource_relations(
    resource_id: str,
    current_user: CurrentUser,
) -> dict:
    """Get all relations + auto-suggestions."""
    _resource_or_404(resource_id)
    rels = _get_relations(resource_id)
    rels["auto"] = auto_resolve_relations(resource_id).get("suggested", [])
    return rels


@router.post("/{resource_id}/relations")
async def add_resource_relation(
    resource_id: str,
    body: _RelationCreate,
    current_user: CurrentUser,
) -> dict:
    """Create a typed relation from this resource to another."""
    _resource_or_404(resource_id)
    try:
        return _create_relation(
            source_id=resource_id,
            target_id=body.target_id,
            relation_type=body.relation_type,
            user=current_user,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{resource_id}/relations/{relation_id}")
async def remove_relation(
    resource_id: str,
    relation_id: str,
    current_user: CurrentUser,
) -> dict:
    """Delete a relation."""
    deleted = _delete_relation(relation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relation not found")
    return {"deleted": True, "id": relation_id}


@router.get("/{resource_id}/graph")
async def get_graph(
    resource_id: str,
    current_user: CurrentUser,
    depth: int = Query(2, ge=1, le=5),
) -> dict:
    """Get a graph of related resources."""
    _resource_or_404(resource_id)
    return get_relation_graph(resource_id, depth)


# ---------------------------------------------------------------------------
# Favorites / pins
# ---------------------------------------------------------------------------


@router.post("/{resource_id}/favorite")
async def toggle_favorite(resource_id: str, current_user: CurrentUser) -> dict:
    """Toggle favorite flag."""
    resource = _resource_or_404(resource_id)
    resource.favorite = not resource.favorite
    resource.save()
    return {"id": str(resource.id), "favorite": resource.favorite}


@router.post("/{resource_id}/pin")
async def toggle_pin(resource_id: str, current_user: CurrentUser) -> dict:
    """Toggle pinned flag."""
    resource = _resource_or_404(resource_id)
    resource.pinned = not resource.pinned
    resource.save()
    return {"id": str(resource.id), "pinned": resource.pinned}


# ---------------------------------------------------------------------------
# Duplicate
# ---------------------------------------------------------------------------


@router.post("/{resource_id}/duplicate")
async def duplicate_resource(
    resource_id: str,
    current_user: CurrentUser,
) -> dict:
    """Duplicate a native resource."""
    resource = _resource_or_404(resource_id)
    import uuid
    new = Resource.create(
        id=str(uuid.uuid4()),
        tenant_id=resource.tenant_id,
        resource_type=resource.resource_type,
        name=f"{resource.name} (copy)",
        description=resource.description,
        status=resource.status,
        version="1.0.0",
        tags=resource.tags,
        project=resource.project,
        owner=resource.owner,
        source=resource.source,
        license=resource.license,
        references=resource.references,
        dependencies=resource.dependencies,
        metadata=resource.metadata,
        content=resource.content,
        language=resource.language,
        visibility=resource.visibility,
        storage_path=resource.storage_path,
        content_hash=resource.content_hash,
        favorite=False,
        pinned=False,
        use_count=0,
        source_type="native",
        source_id=None,
        created_by=current_user.get("username"),
    )
    return new.to_dict(include_content=True)


@router.get("/duplicates")
async def get_duplicates(current_user: CurrentUser) -> dict:
    """Find resources with identical content hashes."""
    from peewee import fn
    q = (
        Resource.select(Resource.content_hash, fn.COUNT(Resource.id).alias("cnt"))
        .where(Resource.content_hash.is_null(False) & (Resource.content_hash != ""))
        .group_by(Resource.content_hash)
        .having(fn.COUNT(Resource.id) > 1)
    )
    duplicates = []
    for row in q:
        resources = [r.to_dict(include_content=False) for r in Resource.select().where(Resource.content_hash == row.content_hash)]
        duplicates.append({"content_hash": row.content_hash, "resources": resources})
    return {"duplicates": duplicates, "count": len(duplicates)}


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


@router.get("/suggestions/{resource_id}")
async def get_suggestions(
    resource_id: str,
    current_user: CurrentUser,
) -> dict:
    """Get AI-style suggestions for a resource (simplified)."""
    resource = _resource_or_404(resource_id)
    suggestions = []

    # Suggest tags from similar resources
    if resource.name:
        similar = (
            Resource.select()
            .where((Resource.id != resource_id) & (Resource.resource_type == resource.resource_type))
            .limit(5)
        )
        if similar.count():
            suggestions.append({
                "type": "metadata",
                "description": f"Compare with {similar.count()} other {resource.resource_type} resources",
            })

    # Suggest duplicates if any
    if resource.content_hash:
        dupes = Resource.select().where(
            (Resource.content_hash == resource.content_hash) & (Resource.id != resource_id)
        )
        if dupes.count():
            suggestions.append({
                "type": "duplicate",
                "description": f"Found {dupes.count()} resource(s) with identical content",
            })

    return {"suggestions": suggestions}


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------


@router.post("/import")
async def import_resource(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    resource_type: str = Form(""),
    name: str = Form(""),
    language: str = Form(""),
    tags: str = Form(""),
) -> dict:
    """Import a file as a native resource."""
    content = (await file.read()).decode("utf-8", errors="replace")
    rtype = resource_type or "snippet"
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    provider = _provider_or_404(rtype)
    data = {
        "name": name or file.filename or "imported",
        "content": content,
        "language": language or (file.filename.split(".")[-1] if file.filename else ""),
        "tags": tags_list,
    }
    return await run_in_threadpool(provider.create, data, _extract_tenant(current_user), current_user)


@router.get("/{resource_id}/export")
async def export_resource(
    resource_id: str,
    current_user: CurrentUser,
    format: str = Query("json"),
) -> dict:
    """Export a resource in the requested format (json, yaml, md, raw)."""
    resource = _resource_or_404(resource_id)
    if format == "json":
        content = json.dumps(resource.to_dict(include_content=True), indent=2, default=str)
    elif format == "yaml":
        try:
            import yaml
            content = yaml.safe_dump(resource.to_dict(include_content=True), default_flow_style=False, sort_keys=False)
        except ImportError:
            content = json.dumps(resource.to_dict(include_content=True), indent=2, default=str)
    elif format == "md":
        content = f"# {resource.name}\n\n{resource.description or ''}\n\n```{resource.language or ''}\n{resource.content or ''}\n```"
    else:  # raw
        content = resource.content or ""

    return {
        "content": content,
        "name": f"{resource.name}.{format}",
        "content_type": "application/json" if format == "json" else "text/plain",
    }


# ---------------------------------------------------------------------------
# CVE import
# ---------------------------------------------------------------------------


@router.post("/cve/import")
async def import_cve(
    body: _CVEImport,
    current_user: CurrentUser,
) -> dict:
    """Import a CVE from NVD and cache it as a resource."""
    from core.threat_intel import search_cve_by_keyword
    cves = await run_in_threadpool(search_cve_by_keyword, body.cve_id, 5)
    data = next((c for c in cves if c.get("cve_id") == body.cve_id), None)
    if not data:
        raise HTTPException(status_code=404, detail=f"CVE {body.cve_id} not found")

    import uuid
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    with database:
        r = Resource.create(
            id=str(uuid.uuid4()),
            tenant_id=_extract_tenant(current_user),
            resource_type="cve",
            name=body.cve_id,
            description=data.get("description", ""),
            status="active",
            version="1.0.0",
            tags=json.dumps(["cve", data.get("severity", "")], ensure_ascii=False),
            content=json.dumps(data, ensure_ascii=False, indent=2),
            content_hash=compute_content_hash(json.dumps(data, ensure_ascii=False, indent=2)),
            language="json",
            visibility="internal",
            source_type="cve",
            source_id=body.cve_id,
            created_by=current_user.get("username"),
            created_at=now,
            updated_at=now,
        )
        r.metadata_dict = data
        r.save()
    return r.to_dict(include_content=False)
