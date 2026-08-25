"""NoteProvider — wraps AgentNote for the library."""
from __future__ import annotations

from db.models import AgentNote
from core.library.base import safe_iso
from core.library.providers.linked import LinkedProvider


class NoteProvider(LinkedProvider):
    resource_type = "note"
    source_model = AgentNote
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: AgentNote) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: AgentNote) -> dict:
        return {
            "content": entity.content,
            "category": entity.category,
            "agent_id": str(entity.agent_id) if entity.agent_id else None,
            "created_at": safe_iso(entity.created_at),
        }

    def _entity_metadata(self, entity: AgentNote) -> dict:
        return {
            "content": entity.content,
            "category": entity.category,
            "agent_id": str(entity.agent_id) if entity.agent_id else None,
            "user_id": str(entity.user_id) if entity.user_id else None,
        }

    def _entity_relations(self, entity: AgentNote) -> dict:
        return {"agent_id": str(entity.agent_id) if entity.agent_id else None}

    def _update_entity(self, entity: AgentNote, data: dict, user):
        if "content" in data:
            entity.content = data["content"]
        if "category" in data:
            entity.category = data["category"]
        entity.save()
        return entity

    def _delete_entity(self, entity: AgentNote, user) -> None:
        entity.delete_instance()
