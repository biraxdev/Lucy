"""
NativeProvider — handles all native resource types (no underlying entity).

Native types store their content directly in the Resource.content field.
This provider supports full CRUD: search, get, preview, metadata, relations,
create, update, delete, versioning.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from peewee import fn

from core.library.base import (
    apply_visibility,
    compute_content_hash,
    create_version_snapshot,
)
from database import database
from db.models import Resource, ResourceRelation

logger = logging.getLogger(__name__)

# All native resource types (no existing model — stored directly in Resource)
SUPPORTED_NATIVE_TYPES = [
    "snippet",
    "script",
    "template",
    "configuration",
    "documentation",
    "note",
    "research",
    "command",
    "workflow",
    "test",
    "dataset",
    "asset",
    "api_reference",
    "integration",
    "architecture_doc",
    "decision",
    "idea",
    "todo",
    "experiment",
    "report",
    "tool",
    "payload",
    "exploit_research",
    "proof",
]


class NativeProvider:
    """Provider for native resource types — CRUD directly on Resource table."""

    def __init__(self):
        self.supported_types = SUPPORTED_NATIVE_TYPES

    # --- Search ---

    def search(
        self,
        resource_type: str,
        query: str,
        filters: dict[str, Any],
        tenant_id: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        q = Resource.select().where(Resource.resource_type == resource_type)

        # Tenant + visibility
        user = filters.get("_user")
        q = apply_visibility(q, user)

        # Text search
        if query and query.strip():
            tokens = [t.lower() for t in query.strip().split() if t]
            for token in tokens:
                q = q.where(
                    (fn.LOWER(Resource.name).contains(token))
                    | (fn.LOWER(Resource.description).contains(token))
                    | (fn.LOWER(Resource.content).contains(token))
                )

        # Filters
        q = self._apply_filters(q, filters)

        total = q.count()
        rows = q.order_by(Resource.updated_at.desc()).limit(limit).offset(offset)
        return [r.to_dict(include_content=False) for r in rows], total

    def _apply_filters(self, q, filters: dict[str, Any]):
        if filters.get("tag"):
            tags = filters["tag"] if isinstance(filters["tag"], list) else [filters["tag"]]
            for tag in tags:
                q = q.where(Resource.tags.contains(tag))
        if filters.get("status"):
            statuses = filters["status"] if isinstance(filters["status"], list) else [filters["status"]]
            q = q.where(Resource.status.in_(statuses))
        if filters.get("language"):
            q = q.where(Resource.language == filters["language"])
        if filters.get("project"):
            q = q.where(Resource.project == filters["project"])
        if filters.get("favorite"):
            q = q.where(Resource.favorite == True)
        if filters.get("pinned"):
            q = q.where(Resource.pinned == True)
        return q

    # --- Get ---

    def get(self, resource_type: str, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != resource_type:
            return None
        return r.to_dict()

    # --- Preview (type-adapted) ---

    def preview(self, resource_type: str, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != resource_type:
            return None
        d = r.to_dict()
        # Type-adapted preview fields
        d["preview_type"] = resource_type
        if resource_type in ("script", "snippet", "command", "payload"):
            d["preview_fields"] = ["name", "language", "content", "dependencies", "tags"]
        elif resource_type in ("configuration", "template"):
            d["preview_fields"] = ["name", "language", "content", "tags"]
        elif resource_type in ("documentation", "note", "research", "report", "architecture_doc", "decision", "idea", "todo", "experiment"):
            d["preview_fields"] = ["name", "content", "tags", "owner", "created_at"]
        elif resource_type == "asset":
            d["preview_fields"] = ["name", "storage_path", "content_hash", "tags"]
        else:
            d["preview_fields"] = ["name", "description", "content", "tags"]
        return d

    # --- Metadata ---

    def metadata(self, resource_type: str, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != resource_type:
            return None
        return {
            "id": str(r.id),
            "resource_type": r.resource_type,
            "name": r.name,
            "description": r.description,
            "status": r.status,
            "version": r.version,
            "tags": r.tags_list,
            "project": r.project,
            "owner": r.owner,
            "source": r.source,
            "license": r.license,
            "references": r.references_list,
            "dependencies": r.dependencies_list,
            "metadata": r.metadata_dict,
            "language": r.language,
            "visibility": r.visibility,
            "content_hash": r.content_hash,
            "favorite": r.favorite,
            "pinned": r.pinned,
            "use_count": r.use_count,
            "created_by": r.created_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    # --- Relations ---

    def relations(self, resource_type: str, resource_id: str, tenant_id: Optional[str]) -> dict:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r:
            return {"outgoing": [], "incoming": []}

        outgoing = []
        for rel in ResourceRelation.select().where(ResourceRelation.source_id == r.id):
            target = Resource.get_or_none(Resource.id == rel.target_id)
            if target:
                outgoing.append({
                    "relation_id": str(rel.id),
                    "relation_type": rel.relation_type,
                    "target": target.to_dict(include_content=False),
                })

        incoming = []
        for rel in ResourceRelation.select().where(ResourceRelation.target_id == r.id):
            source = Resource.get_or_none(Resource.id == rel.source_id)
            if source:
                incoming.append({
                    "relation_id": str(rel.id),
                    "relation_type": rel.relation_type,
                    "source": source.to_dict(include_content=False),
                })

        return {"outgoing": outgoing, "incoming": incoming}

    # --- Create ---

    def create(self, resource_type: str, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        now = datetime.now(timezone.utc)
        content = data.get("content")
        content_hash = compute_content_hash(content)

        r = Resource.create(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            resource_type=resource_type,
            name=data.get("name", "Untitled"),
            description=data.get("description"),
            status=data.get("status", "draft"),
            version=data.get("version", "1.0.0"),
            tags=json.dumps(data["tags"], ensure_ascii=False) if data.get("tags") else None,
            project=data.get("project"),
            owner=data.get("owner") or (user.get("username") if user else None),
            source=data.get("source"),
            license=data.get("license"),
            references=None,
            dependencies=None,
            metadata=None,
            content=content,
            language=data.get("language"),
            visibility=data.get("visibility", "internal"),
            storage_path=data.get("storage_path"),
            content_hash=content_hash,
            favorite=False,
            pinned=False,
            use_count=0,
            source_type="native",
            source_id=None,
            created_by=user.get("username") if user else None,
            created_at=now,
            updated_at=now,
        )
        # Set JSON fields via property setters
        if data.get("tags"):
            r.tags_list = data["tags"]
        if data.get("references"):
            r.references_list = data["references"]
        if data.get("dependencies"):
            r.dependencies_list = data["dependencies"]
        if data.get("metadata"):
            r.metadata_dict = data["metadata"]
        r.save()
        return r.to_dict()

    # --- Update ---

    def update(self, resource_type: str, resource_id: str, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != resource_type:
            raise ValueError("Resource not found")

        # Create version snapshot before update (if content changed)
        content_changed = data.get("content") is not None and data["content"] != r.content
        if content_changed:
            create_version_snapshot(r, change_note=data.get("change_note"), user=user)

        now = datetime.now(timezone.utc)
        if "name" in data:
            r.name = data["name"]
        if "description" in data:
            r.description = data["description"]
        if "status" in data:
            r.status = data["status"]
        if "version" in data:
            r.version = data["version"]
        if "project" in data:
            r.project = data["project"]
        if "owner" in data:
            r.owner = data["owner"]
        if "source" in data:
            r.source = data["source"]
        if "license" in data:
            r.license = data["license"]
        if "language" in data:
            r.language = data["language"]
        if "visibility" in data:
            r.visibility = data["visibility"]
        if "storage_path" in data:
            r.storage_path = data["storage_path"]
        if "favorite" in data:
            r.favorite = data["favorite"]
        if "pinned" in data:
            r.pinned = data["pinned"]
        if "tags" in data:
            r.tags_list = data["tags"]
        if "references" in data:
            r.references_list = data["references"]
        if "dependencies" in data:
            r.dependencies_list = data["dependencies"]
        if "metadata" in data:
            r.metadata_dict = data["metadata"]
        if content_changed:
            r.content = data["content"]
            r.content_hash = compute_content_hash(data["content"])

        r.updated_at = now
        r.save()
        return r.to_dict()

    # --- Delete ---

    def delete(self, resource_type: str, resource_id: str, tenant_id: Optional[str], user: dict) -> None:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != resource_type:
            raise ValueError("Resource not found")
        with database:
            # Delete relations first (cascade should handle, but be explicit)
            ResourceRelation.delete().where(
                (ResourceRelation.source_id == r.id) | (ResourceRelation.target_id == r.id)
            ).execute()
            r.delete_instance()
