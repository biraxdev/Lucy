"""AgentProvider — wraps Agent for the library (read-only reference).

NEVER exposes aes_key or public_key. Only metadata for the library view.
"""
from __future__ import annotations

from db.models import Agent
from core.library.providers.linked import LinkedProvider


def _iso(val):
    """Safely convert a datetime or string to ISO format string."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


class AgentProvider(LinkedProvider):
    resource_type = "agent"
    source_model = Agent
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Agent) -> dict:
        d = entity.to_dict()
        # Strip sensitive fields
        d.pop("aes_key", None)
        d.pop("public_key", None)
        return d

    def _entity_preview(self, entity: Agent) -> dict:
        return {
            "hostname": entity.hostname,
            "os": entity.os,
            "username": entity.username,
            "ip_public": entity.ip_public,
            "ip_private": entity.ip_private,
            "status": entity.status,
            "architecture": entity.architecture,
            "last_seen": _iso(entity.last_seen),
            "first_seen": _iso(entity.first_seen),
            "tags": entity.tags_list,
            "group_id": str(entity.group_id) if entity.group_id else None,
        }

    def _entity_metadata(self, entity: Agent) -> dict:
        return {
            "hostname": entity.hostname,
            "os": entity.os,
            "username": entity.username,
            "ip_public": entity.ip_public,
            "ip_private": entity.ip_private,
            "architecture": entity.architecture,
            "processor": entity.processor,
            "ram_total": entity.ram_total,
            "ram_available": entity.ram_available,
            "cpu_percent": entity.cpu_percent,
            "status": entity.status,
            "last_seen": _iso(entity.last_seen),
            "first_seen": _iso(entity.first_seen),
            "tags": entity.tags_list,
            "metadata": entity.metadata_dict,
            "group_id": str(entity.group_id) if entity.group_id else None,
            # NEVER include aes_key or public_key
        }

    def _entity_relations(self, entity: Agent) -> dict:
        return {
            "group_id": str(entity.group_id) if entity.group_id else None,
            "tags": entity.tags_list,
        }
