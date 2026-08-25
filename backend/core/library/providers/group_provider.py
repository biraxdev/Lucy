"""GroupProvider — wraps AgentGroup for the library (read-only reference)."""
from __future__ import annotations

from db.models import AgentGroup
from core.library.providers.linked import LinkedProvider


class GroupProvider(LinkedProvider):
    resource_type = "group"
    source_model = AgentGroup
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: AgentGroup) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: AgentGroup) -> dict:
        return {
            "name": entity.name,
            "description": getattr(entity, "description", None),
            "color": getattr(entity, "color", None),
            "members": entity.members_list,
            "tags": entity.tags_list,
        }

    def _entity_metadata(self, entity: AgentGroup) -> dict:
        return {
            "name": entity.name,
            "description": getattr(entity, "description", None),
            "color": getattr(entity, "color", None),
            "members": entity.members_list,
            "tags": entity.tags_list,
        }
