"""
Resource Relations — typed bidirectional relations between resources.

Provides CRUD for ResourceRelation plus auto-resolution of relations
from entity fields (e.g. Finding.agent_id -> Agent resource).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from database import database
from db.models import Resource, ResourceRelation

logger = logging.getLogger(__name__)

VALID_RELATION_TYPES = [
    "references",
    "depends_on",
    "related_to",
    "implements",
    "tests",
    "describes",
    "affects",
    "derived_from",
    "part_of",
    "replaces",
]


def create_relation(
    source_id: str,
    target_id: str,
    relation_type: str,
    user: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Create a typed relation between two resources.

    Raises ValueError if the relation already exists or resources don't exist.
    """
    if relation_type not in VALID_RELATION_TYPES:
        raise ValueError(f"Invalid relation_type: {relation_type}. Valid: {VALID_RELATION_TYPES}")

    source = Resource.get_or_none(Resource.id == source_id)
    target = Resource.get_or_none(Resource.id == target_id)
    if not source:
        raise ValueError(f"Source resource {source_id} not found")
    if not target:
        raise ValueError(f"Target resource {target_id} not found")

    # Check for existing relation (unique constraint on source, target, relation_type)
    existing = ResourceRelation.get_or_none(
        (ResourceRelation.source_id == source_id)
        & (ResourceRelation.target_id == target_id)
        & (ResourceRelation.relation_type == relation_type)
    )
    if existing:
        raise ValueError(f"Relation already exists: {source_id} -> {target_id} ({relation_type})")

    import json
    rel = ResourceRelation.create(
        id=str(uuid.uuid4()),
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        metadata=json.dumps(metadata, ensure_ascii=False) if metadata else None,
        created_by=user.get("username") if user else None,
    )
    return rel.to_dict()


def delete_relation(relation_id: str) -> bool:
    """Delete a relation by ID. Returns True if deleted."""
    rel = ResourceRelation.get_or_none(ResourceRelation.id == relation_id)
    if not rel:
        return False
    rel.delete_instance()
    return True


def get_relations(resource_id: str) -> dict:
    """Get all relations (outgoing + incoming) for a resource."""
    outgoing = []
    for rel in ResourceRelation.select().where(ResourceRelation.source_id == resource_id):
        target = Resource.get_or_none(Resource.id == rel.target_id)
        if target:
            outgoing.append({
                "relation_id": str(rel.id),
                "relation_type": rel.relation_type,
                "direction": "outgoing",
                "target": target.to_dict(include_content=False),
                "created_by": rel.created_by,
                "created_at": rel.created_at.isoformat() if hasattr(rel.created_at, "isoformat") else str(rel.created_at),
            })

    incoming = []
    for rel in ResourceRelation.select().where(ResourceRelation.target_id == resource_id):
        source = Resource.get_or_none(Resource.id == rel.source_id)
        if source:
            incoming.append({
                "relation_id": str(rel.id),
                "relation_type": rel.relation_type,
                "direction": "incoming",
                "source": source.to_dict(include_content=False),
                "created_by": rel.created_by,
                "created_at": rel.created_at.isoformat() if hasattr(rel.created_at, "isoformat") else str(rel.created_at),
            })

    return {"outgoing": outgoing, "incoming": incoming}


def auto_resolve_relations(resource_id: str) -> dict:
    """Auto-resolve relations from entity fields.

    For example, if a Finding resource has agent_id=X, find the Agent resource
    with source_id=X and suggest a relation.
    """
    r = Resource.get_or_none(Resource.id == resource_id)
    if not r:
        return {"suggested": []}

    suggestions = []
    meta = r.metadata_dict or {}

    # Common fields that reference other entities
    ref_fields = ["agent_id", "task_id", "finding_id", "campaign_id", "module", "technique_id", "tactic_id"]

    for field in ref_fields:
        value = meta.get(field)
        if not value:
            continue

        # Try to find a Resource with this source_id
        target = Resource.get_or_none(Resource.source_id == str(value))
        if target and str(target.id) != str(r.id):
            # Determine relation type based on field
            rel_type = "references"
            if field == "agent_id":
                rel_type = "affects"
            elif field == "task_id":
                rel_type = "references"
            elif field == "finding_id":
                rel_type = "references"
            elif field == "campaign_id":
                rel_type = "part_of"
            elif field == "module":
                rel_type = "depends_on"
            elif field == "technique_id":
                rel_type = "implements"
            elif field == "tactic_id":
                rel_type = "part_of"

            suggestions.append({
                "field": field,
                "value": str(value),
                "target_resource_id": str(target.id),
                "target_name": target.name,
                "target_type": target.resource_type,
                "suggested_relation_type": rel_type,
            })

    return {"suggested": suggestions}


def get_relation_graph(resource_id: str, depth: int = 2) -> dict:
    """Get a graph of relations starting from a resource (BFS up to depth)."""
    visited: set[str] = set()
    nodes: list[dict] = []
    edges: list[dict] = []

    def bfs(rid: str, current_depth: int):
        if current_depth > depth or rid in visited:
            return
        visited.add(rid)

        r = Resource.get_or_none(Resource.id == rid)
        if not r:
            return

        nodes.append({
            "id": str(r.id),
            "name": r.name,
            "resource_type": r.resource_type,
            "status": r.status,
        })

        # Outgoing
        for rel in ResourceRelation.select().where(ResourceRelation.source_id == rid):
            target_id = str(rel.target_id)
            edges.append({
                "source": str(rid),
                "target": target_id,
                "relation_type": rel.relation_type,
            })
            bfs(target_id, current_depth + 1)

        # Incoming
        for rel in ResourceRelation.select().where(ResourceRelation.target_id == rid):
            source_id = str(rel.source_id)
            edges.append({
                "source": source_id,
                "target": str(rid),
                "relation_type": rel.relation_type,
            })
            bfs(source_id, current_depth + 1)

    bfs(resource_id, 0)
    return {"nodes": nodes, "edges": edges}
