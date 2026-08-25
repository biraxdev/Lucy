"""PlaybookProvider — wraps Playbook for the library."""
from __future__ import annotations

from db.models import Playbook
from core.library.providers.linked import LinkedProvider


class PlaybookProvider(LinkedProvider):
    resource_type = "playbook"
    source_model = Playbook
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: Playbook) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Playbook) -> dict:
        return {
            "name": entity.name,
            "description": entity.description,
        }

    def _entity_metadata(self, entity: Playbook) -> dict:
        return entity.to_dict()

    def _update_entity(self, entity: Playbook, data: dict, user):
        if "name" in data:
            entity.name = data["name"]
        if "description" in data:
            entity.description = data["description"]
        entity.save()
        return entity

    def _delete_entity(self, entity: Playbook, user) -> None:
        entity.delete_instance()
