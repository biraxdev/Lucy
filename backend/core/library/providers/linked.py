"""
LinkedProvider — base class for providers that wrap an existing entity.

A LinkedProvider reads from a specialized model (Module, PocTemplate, Finding, ...)
and projects it to the unified Resource format. The Resource row is created by
the sync module and linked via (source_type, source_id).

Subclasses must override:
  - resource_type (str)
  - source_model (Peewee model class)
  - _entity_to_resource_dict(entity) -> dict (the projection)
  - _entity_preview(entity) -> dict (type-adapted preview)
  - _entity_metadata(entity) -> dict (type-specific metadata)
  - _entity_relations(entity) -> dict (auto-resolved relations, optional)

Optionally override for editable types:
  - _update_entity(entity, data, user) -> entity
  - _delete_entity(entity, user) -> None
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from peewee import fn

from core.library.base import apply_visibility
from database import database
from db.models import Resource, ResourceRelation

logger = logging.getLogger(__name__)


class LinkedProvider:
    """Base class for providers wrapping an existing specialized model."""

    resource_type: str = ""
    source_model: Any = None  # Peewee model class
    editable: bool = False
    deletable: bool = False

    # --- Search ---

    def search(
        self,
        query: str,
        filters: dict[str, Any],
        tenant_id: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        q = Resource.select().where(
            (Resource.resource_type == self.resource_type)
            & (Resource.source_type == self.resource_type)
        )
        user = filters.get("_user")
        q = apply_visibility(q, user)

        if query and query.strip():
            tokens = [t.lower() for t in query.strip().split() if t]
            for token in tokens:
                q = q.where(
                    (fn.LOWER(Resource.name).contains(token))
                    | (fn.LOWER(Resource.description).contains(token))
                )

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
        if filters.get("project"):
            q = q.where(Resource.project == filters["project"])
        if filters.get("favorite"):
            q = q.where(Resource.favorite == True)
        if filters.get("pinned"):
            q = q.where(Resource.pinned == True)
        return q

    # --- Get ---

    def get(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != self.resource_type:
            return None
        d = r.to_dict()
        # Enrich with entity-specific data
        entity = self._get_entity(r)
        if entity:
            d["entity"] = self._entity_to_resource_dict(entity)
        return d

    def _get_entity(self, resource: Resource):
        """Fetch the underlying entity for a Resource."""
        if not self.source_model or not resource.source_id:
            return None
        return self.source_model.get_or_none(self.source_model.id == resource.source_id)

    # --- Preview ---

    def preview(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != self.resource_type:
            return None
        entity = self._get_entity(r)
        d = r.to_dict(include_content=False)
        d["preview_type"] = self.resource_type
        if entity:
            d["preview"] = self._entity_preview(entity)
        return d

    # --- Metadata ---

    def metadata(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != self.resource_type:
            return None
        d = {
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
            "visibility": r.visibility,
            "favorite": r.favorite,
            "pinned": r.pinned,
            "use_count": r.use_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        entity = self._get_entity(r)
        if entity:
            d["entity_metadata"] = self._entity_metadata(entity)
        return d

    # --- Relations ---

    def relations(self, resource_id: str, tenant_id: Optional[str]) -> dict:
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

        # Add auto-resolved relations from entity
        entity = self._get_entity(r)
        auto = {}
        if entity:
            auto = self._entity_relations(entity)

        return {"outgoing": outgoing, "incoming": incoming, "auto": auto}

    # --- Write operations (override in subclasses) ---

    def create(self, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        raise NotImplementedError(f"{self.resource_type} does not support create via library")

    def update(self, resource_id: str, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        if not self.editable:
            raise NotImplementedError(f"{self.resource_type} does not support update")
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != self.resource_type:
            raise ValueError("Resource not found")

        entity = self._get_entity(r)
        if entity:
            entity = self._update_entity(entity, data, user)

        # Update library metadata on Resource
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if "tags" in data:
            r.tags_list = data["tags"]
        if "status" in data:
            r.status = data["status"]
        if "project" in data:
            r.project = data["project"]
        if "favorite" in data:
            r.favorite = data["favorite"]
        if "pinned" in data:
            r.pinned = data["pinned"]
        if "visibility" in data:
            r.visibility = data["visibility"]
        r.updated_at = now
        r.save()
        return r.to_dict()

    def delete(self, resource_id: str, tenant_id: Optional[str], user: dict) -> None:
        if not self.deletable:
            raise NotImplementedError(f"{self.resource_type} does not support delete")
        r = Resource.get_or_none(Resource.id == resource_id)
        if not r or r.resource_type != self.resource_type:
            raise ValueError("Resource not found")

        entity = self._get_entity(r)
        if entity:
            self._delete_entity(entity, user)

        with database:
            ResourceRelation.delete().where(
                (ResourceRelation.source_id == r.id) | (ResourceRelation.target_id == r.id)
            ).execute()
            r.delete_instance()

    # --- Methods to override ---

    def _entity_to_resource_dict(self, entity) -> dict:
        """Project entity to a dict for the 'entity' field."""
        return entity.to_dict()

    def _entity_preview(self, entity) -> dict:
        """Type-adapted preview of the entity."""
        return {}

    def _entity_metadata(self, entity) -> dict:
        """Type-specific metadata from the entity."""
        return {}

    def _entity_relations(self, entity) -> dict:
        """Auto-resolved relations from entity fields."""
        return {}

    def _update_entity(self, entity, data: dict, user: dict):
        """Update the underlying entity. Override for editable types."""
        return entity

    def _delete_entity(self, entity, user: dict) -> None:
        """Delete the underlying entity. Override for deletable types."""
        entity.delete_instance()
