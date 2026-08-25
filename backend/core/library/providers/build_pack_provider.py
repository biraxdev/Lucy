"""BuildPackProvider — wraps BuildPack for the library."""
from __future__ import annotations

from db.models import BuildPack
from core.library.providers.linked import LinkedProvider


class BuildPackProvider(LinkedProvider):
    resource_type = "build_pack"
    source_model = BuildPack
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: BuildPack) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: BuildPack) -> dict:
        return {
            "name": entity.name,
            "description": entity.description,
            "icon": entity.icon,
            "modules": entity.modules_list,
            "tags": entity.tags_list,
        }

    def _entity_metadata(self, entity: BuildPack) -> dict:
        return {
            "bpid": entity.bpid,
            "name": entity.name,
            "modules": entity.modules_list,
            "build_options": entity.build_options_dict,
            "tags": entity.tags_list,
            "source_file": entity.source_file,
        }

    def _entity_relations(self, entity: BuildPack) -> dict:
        return {"modules": entity.modules_list}

    def _update_entity(self, entity: BuildPack, data: dict, user):
        if "name" in data:
            entity.name = data["name"]
        if "description" in data:
            entity.description = data["description"]
        entity.save()
        return entity

    def _delete_entity(self, entity: BuildPack, user) -> None:
        entity.delete_instance()
