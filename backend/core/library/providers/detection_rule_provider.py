"""DetectionRuleProvider — wraps DetectionRule for the library."""
from __future__ import annotations

from db.models import DetectionRule, _json_loads
from core.library.providers.linked import LinkedProvider


class DetectionRuleProvider(LinkedProvider):
    resource_type = "detection_rule"
    source_model = DetectionRule
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: DetectionRule) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: DetectionRule) -> dict:
        return {
            "title": entity.title,
            "description": entity.description,
            "rule_type": entity.rule_type,
            "severity": entity.severity,
            "status": entity.status,
            "mitre_technique": entity.mitre_technique,
            "rule_content": entity.rule_content,
            "tags": _json_loads(entity.tags) if entity.tags else [],
        }

    def _entity_metadata(self, entity: DetectionRule) -> dict:
        return {
            "title": entity.title,
            "rule_type": entity.rule_type,
            "severity": entity.severity,
            "status": entity.status,
            "mitre_technique": entity.mitre_technique,
            "finding_id": entity.finding_id,
            "rule_content": entity.rule_content,
            "tags": _json_loads(entity.tags) if entity.tags else [],
            "created_by": entity.created_by,
        }

    def _entity_relations(self, entity: DetectionRule) -> dict:
        return {"mitre_technique": entity.mitre_technique, "finding_id": entity.finding_id}

    def _update_entity(self, entity: DetectionRule, data: dict, user):
        if "title" in data:
            entity.title = data["title"]
        if "description" in data:
            entity.description = data["description"]
        if "severity" in data:
            entity.severity = data["severity"]
        if "status" in data:
            entity.status = data["status"]
        if "rule_content" in data:
            entity.rule_content = data["rule_content"]
        if "tags" in data:
            import json
            entity.tags = json.dumps(data["tags"], ensure_ascii=False)
        entity.save()
        return entity

    def _delete_entity(self, entity: DetectionRule, user) -> None:
        entity.delete_instance()
