"""TacticProvider — wraps Tactic for the library (read-only)."""
from __future__ import annotations

from db.models import Tactic
from core.library.providers.linked import LinkedProvider


class TacticProvider(LinkedProvider):
    resource_type = "tactic"
    source_model = Tactic
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Tactic) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Tactic) -> dict:
        return {
            "name": entity.name,
            "mitre_id": entity.mitre_id,
            "phase": entity.phase,
            "description": entity.description,
        }

    def _entity_metadata(self, entity: Tactic) -> dict:
        return {
            "name": entity.name,
            "mitre_id": entity.mitre_id,
            "phase": entity.phase,
            "description": entity.description,
        }
