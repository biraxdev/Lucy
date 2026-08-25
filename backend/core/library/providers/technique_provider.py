"""TechniqueProvider — wraps Technique for the library (read-only)."""
from __future__ import annotations

from db.models import Technique, _json_loads
from core.library.providers.linked import LinkedProvider


class TechniqueProvider(LinkedProvider):
    resource_type = "technique"
    source_model = Technique
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Technique) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Technique) -> dict:
        return {
            "name": entity.name,
            "mitre_id": entity.mitre_id,
            "tactic_id": str(entity.tactic_id) if entity.tactic_id else None,
            "description": entity.description,
            "platform": entity.platform,
            "data_sources": _json_loads(entity.data_sources) if entity.data_sources else [],
        }

    def _entity_metadata(self, entity: Technique) -> dict:
        return {
            "name": entity.name,
            "mitre_id": entity.mitre_id,
            "tactic_id": str(entity.tactic_id) if entity.tactic_id else None,
            "platform": entity.platform,
            "data_sources": _json_loads(entity.data_sources) if entity.data_sources else [],
            "description": entity.description,
        }

    def _entity_relations(self, entity: Technique) -> dict:
        return {"tactic_id": str(entity.tactic_id) if entity.tactic_id else None}
