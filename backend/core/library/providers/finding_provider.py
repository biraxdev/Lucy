"""FindingProvider — wraps Finding for the library."""
from __future__ import annotations

from db.models import Finding
from core.library.providers.linked import LinkedProvider


class FindingProvider(LinkedProvider):
    resource_type = "finding"
    source_model = Finding
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: Finding) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Finding) -> dict:
        return {
            "title": entity.title,
            "severity": entity.severity,
            "status": entity.status,
            "description": entity.description,
            "recommendation": entity.recommendation,
            "cvss": float(entity.cvss) if entity.cvss else None,
            "agent_id": entity.agent_id,
        }

    def _entity_metadata(self, entity: Finding) -> dict:
        return {
            "title": entity.title,
            "severity": entity.severity,
            "status": entity.status,
            "cvss": float(entity.cvss) if entity.cvss else None,
            "agent_id": entity.agent_id,
            "evidence": entity.evidence,
            "recommendation": entity.recommendation,
        }

    def _entity_relations(self, entity: Finding) -> dict:
        return {"agent_id": entity.agent_id}

    def _update_entity(self, entity: Finding, data: dict, user):
        if "title" in data:
            entity.title = data["title"]
        if "severity" in data:
            entity.severity = data["severity"]
        if "status" in data:
            entity.status = data["status"]
        if "description" in data:
            entity.description = data["description"]
        if "recommendation" in data:
            entity.recommendation = data["recommendation"]
        if "cvss" in data:
            entity.cvss = str(data["cvss"]) if data["cvss"] else None
        entity.save()
        return entity

    def _delete_entity(self, entity: Finding, user) -> None:
        entity.delete_instance()
