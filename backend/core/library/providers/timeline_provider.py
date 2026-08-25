"""TimelineProvider — wraps Timeline for the library (read-only reference)."""
from __future__ import annotations

from db.models import Timeline
from core.library.providers.linked import LinkedProvider


class TimelineProvider(LinkedProvider):
    resource_type = "timeline"
    source_model = Timeline
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Timeline) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Timeline) -> dict:
        return {
            "name": getattr(entity, "name", None),
            "description": getattr(entity, "description", None),
            "status": getattr(entity, "status", None),
            "trigger": getattr(entity, "trigger", None),
        }

    def _entity_metadata(self, entity: Timeline) -> dict:
        return entity.to_dict()
