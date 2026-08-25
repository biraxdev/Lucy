"""ModuleProvider — wraps the Module model for the library."""
from __future__ import annotations

from db.models import Module
from core.library.providers.linked import LinkedProvider


class ModuleProvider(LinkedProvider):
    resource_type = "module"
    source_model = Module
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: Module) -> dict:
        return entity.to_dict(include_code=False)

    def _entity_preview(self, entity: Module) -> dict:
        return {
            "name": entity.name,
            "version": entity.version,
            "description": entity.description,
            "category": entity.category,
            "os_compat": entity.os_compat_list,
            "actions": entity.actions_list,
            "dependencies": entity.dependencies_list,
            "mitre_techniques": entity.mitre_list,
            "tags": entity.tags_list,
            "enabled": entity.enabled,
            "expected_duration": entity.expected_duration,
            "author": entity.author,
            "install_count": entity.install_count,
        }

    def _entity_metadata(self, entity: Module) -> dict:
        return {
            "name": entity.name,
            "version": entity.version,
            "category": entity.category,
            "os_compat": entity.os_compat_list,
            "actions": entity.actions_list,
            "params_schema": entity.params_schema_dict,
            "dependencies": entity.dependencies_list,
            "inputs": entity.inputs_list,
            "outputs": entity.outputs_list,
            "mitre_techniques": entity.mitre_list,
            "tags": entity.tags_list,
            "enabled": entity.enabled,
            "expected_duration": entity.expected_duration,
            "author": entity.author,
            "install_count": entity.install_count,
            "signature": entity.signature,
        }

    def _entity_relations(self, entity: Module) -> dict:
        from db.models import Resource
        rels = {"mitre_techniques": entity.mitre_list, "dependencies": entity.dependencies_list}
        return rels

    def _update_entity(self, entity: Module, data: dict, user):
        if "description" in data:
            entity.description = data["description"]
        if "category" in data:
            entity.category = data["category"]
        if "enabled" in data:
            entity.enabled = data["enabled"]
        if "tags" in data and hasattr(entity, "tags"):
            import json
            entity.tags = json.dumps(data["tags"], ensure_ascii=False)
        entity.save()
        return entity

    def _delete_entity(self, entity: Module, user) -> None:
        entity.delete_instance()
