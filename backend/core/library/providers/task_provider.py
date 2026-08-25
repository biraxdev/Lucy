"""TaskProvider — wraps Task for the library (read-only reference)."""
from __future__ import annotations

from db.models import Task
from core.library.base import safe_iso
from core.library.providers.linked import LinkedProvider


class TaskProvider(LinkedProvider):
    resource_type = "task"
    source_model = Task
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Task) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Task) -> dict:
        return {
            "module": getattr(entity, "module", None),
            "action": getattr(entity, "action", None),
            "status": getattr(entity, "status", None),
            "agent_id": str(entity.agent_id) if getattr(entity, "agent_id", None) else None,
            "priority": getattr(entity, "priority", None),
            "created_at": safe_iso(entity.created_at),
        }

    def _entity_metadata(self, entity: Task) -> dict:
        d = entity.to_dict()
        d.pop("result", None)  # result can be large
        return d

    def _entity_relations(self, entity: Task) -> dict:
        return {
            "agent_id": str(entity.agent_id) if getattr(entity, "agent_id", None) else None,
            "module": getattr(entity, "module", None),
        }
