"""RedirectorProvider — wraps Redirector for the library (read-only reference)."""
from __future__ import annotations

from db.models import Redirector
from core.library.providers.linked import LinkedProvider


class RedirectorProvider(LinkedProvider):
    resource_type = "redirector"
    source_model = Redirector
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Redirector) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Redirector) -> dict:
        return {
            "name": getattr(entity, "name", None),
            "domain": getattr(entity, "domain", None),
            "status": getattr(entity, "status", None),
            "description": getattr(entity, "description", None),
        }

    def _entity_metadata(self, entity: Redirector) -> dict:
        return entity.to_dict()
