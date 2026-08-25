"""
Base helpers for library providers.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from database import database
from db.models import Resource, ResourceRelation, ResourceVersion

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_content_hash(content: Optional[str]) -> Optional[str]:
    """SHA-256 of content for duplicate detection."""
    if not content:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def safe_iso(val) -> Optional[str]:
    """Safely convert a datetime or string to ISO format string."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def visibility_filter(user: Optional[dict]) -> tuple[Optional[str], list[str]]:
    """Return (tenant_id, allowed_visibility_levels) for a user."""
    if user is None:
        return None, ["public"]

    role = user.get("role", "viewer")
    tenant_id = user.get("tenant_id")

    if role == "superadmin":
        return None, ["public", "internal", "restricted", "private"]
    if role in ("admin", "operator"):
        return tenant_id, ["public", "internal", "restricted", "private"]
    # viewer
    return tenant_id, ["public", "internal"]


def apply_visibility(query, user: Optional[dict]):
    """Apply tenant + visibility filtering to a Peewee query on Resource."""
    tenant_id, allowed = visibility_filter(user)
    query = query.where(Resource.visibility.in_(allowed))
    if tenant_id is not None:
        # public resources from any tenant + internal/restricted/private from own tenant
        from peewee import Expression
        query = query.where(
            (Resource.tenant_id.is_null() & (Resource.visibility == "public"))
            | (Resource.tenant_id == tenant_id)
        )
    else:
        # superadmin or no user — see everything allowed by visibility
        pass
    return query


def get_or_create_linked_resource(
    resource_type: str,
    source_type: str,
    source_id: str,
    name: str,
    description: Optional[str],
    tenant_id: Optional[str],
    extra: Optional[dict] = None,
) -> Resource:
    """Get or create a Resource row that links to an existing entity.

    Idempotent by (source_type, source_id). Updates name/description/extra
    if the entity has changed.
    """
    extra = extra or {}
    now = _utcnow()

    existing = Resource.get_or_none(
        (Resource.source_type == source_type) & (Resource.source_id == str(source_id))
    )

    if existing:
        changed = False
        if existing.name != name:
            existing.name = name
            changed = True
        if existing.description != description and description is not None:
            existing.description = description
            changed = True
        # Merge extra metadata
        if extra:
            current_meta = existing.metadata_dict
            if current_meta != extra:
                current_meta.update(extra)
                existing.metadata_dict = current_meta
                changed = True
        if changed:
            existing.updated_at = now
            existing.save()
        return existing

    resource = Resource.create(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        resource_type=resource_type,
        name=name,
        description=description,
        source_type=source_type,
        source_id=str(source_id),
        metadata=json.dumps(extra, ensure_ascii=False) if extra else None,
        created_at=now,
        updated_at=now,
    )
    logger.debug("Created linked resource %s (%s:%s)", resource.id, source_type, source_id)
    return resource


def create_version_snapshot(resource: Resource, change_note: Optional[str] = None, user: Optional[dict] = None) -> ResourceVersion:
    """Create a version snapshot of a resource (for versioning)."""
    snapshot = {
        "name": resource.name,
        "description": resource.description,
        "status": resource.status,
        "version": resource.version,
        "tags": resource.tags_list,
        "metadata": resource.metadata_dict,
        "content": resource.content,
        "language": resource.language,
        "references": resource.references_list,
        "dependencies": resource.dependencies_list,
    }
    return ResourceVersion.create(
        id=str(uuid.uuid4()),
        resource_id=resource.id,
        version=resource.version,
        snapshot=json.dumps(snapshot, ensure_ascii=False),
        content=resource.content,
        change_note=change_note,
        created_by=user.get("username") if user else None,
        created_at=_utcnow(),
    )
