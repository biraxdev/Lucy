"""PocProvider — wraps PocTemplate for the library."""
from __future__ import annotations

from db.models import PocTemplate
from core.library.providers.linked import LinkedProvider


class PocProvider(LinkedProvider):
    resource_type = "poc"
    source_model = PocTemplate
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: PocTemplate) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: PocTemplate) -> dict:
        return {
            "name": entity.name,
            "description": entity.description,
            "icon": entity.icon,
            "category": entity.category,
            "trigger": entity.trigger,
            "agent_group": entity.agent_group_list,
            "mitre_techniques": entity.mitre_list,
            "tags": entity.tags_list,
            "phases": entity.phases_list,
            "steps_count": len(entity.steps_list),
        }

    def _entity_metadata(self, entity: PocTemplate) -> dict:
        return {
            "puid": entity.puid,
            "name": entity.name,
            "category": entity.category,
            "trigger": entity.trigger,
            "agent_group": entity.agent_group_list,
            "mitre_techniques": entity.mitre_list,
            "tags": entity.tags_list,
            "phases": entity.phases_list,
            "steps": entity.steps_list,
            "source_file": entity.source_file,
        }

    def _entity_relations(self, entity: PocTemplate) -> dict:
        return {"mitre_techniques": entity.mitre_list, "modules": [s.get("module") for s in entity.steps_list if s.get("module")]}

    def _update_entity(self, entity: PocTemplate, data: dict, user):
        if "description" in data:
            entity.description = data["description"]
        if "category" in data:
            entity.category = data["category"]
        if "tags" in data:
            import json
            entity.tags = json.dumps(data["tags"], ensure_ascii=False)
        entity.save()
        return entity

    def _delete_entity(self, entity: PocTemplate, user) -> None:
        entity.delete_instance()
