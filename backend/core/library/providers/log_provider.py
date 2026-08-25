"""LogProvider — wraps Log for the library (read-only reference)."""
from __future__ import annotations

from db.models import Log
from core.library.base import safe_iso
from core.library.providers.linked import LinkedProvider


class LogProvider(LinkedProvider):
    resource_type = "log"
    source_model = Log
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Log) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Log) -> dict:
        return {
            "level": getattr(entity, "level", None),
            "source": getattr(entity, "source", None),
            "message": getattr(entity, "message", None),
            "agent_id": str(getattr(entity, "agent_id", None)) if getattr(entity, "agent_id", None) else None,
            "timestamp": safe_iso(entity.created_at),
        }

    def _entity_metadata(self, entity: Log) -> dict:
        return entity.to_dict()

    def _entity_relations(self, entity: Log) -> dict:
        return {"agent_id": str(getattr(entity, "agent_id", None)) if getattr(entity, "agent_id", None) else None}
