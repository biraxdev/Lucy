"""CampaignProvider — wraps Campaign for the library."""
from __future__ import annotations

from db.models import Campaign
from core.library.base import safe_iso
from core.library.providers.linked import LinkedProvider


class CampaignProvider(LinkedProvider):
    resource_type = "campaign"
    source_model = Campaign
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: Campaign) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Campaign) -> dict:
        return {
            "name": entity.name,
            "description": entity.description,
            "objective": entity.objective,
            "status": entity.status,
            "priority": entity.priority,
            "assigned_to": entity.assigned_to,
            "case_number": entity.case_number,
            "tags": entity.tags_list,
        }

    def _entity_metadata(self, entity: Campaign) -> dict:
        return {
            "name": entity.name,
            "objective": entity.objective,
            "status": entity.status,
            "priority": entity.priority,
            "assigned_to": entity.assigned_to,
            "case_number": entity.case_number,
            "due_date": safe_iso(entity.due_date),
            "start_date": safe_iso(entity.start_date),
            "end_date": safe_iso(entity.end_date),
            "metadata": entity.metadata_dict,
            "tags": entity.tags_list,
        }

    def _update_entity(self, entity: Campaign, data: dict, user):
        if "name" in data:
            entity.name = data["name"]
        if "description" in data:
            entity.description = data["description"]
        if "status" in data:
            entity.status = data["status"]
        if "priority" in data:
            entity.priority = data["priority"]
        if "assigned_to" in data:
            entity.assigned_to = data["assigned_to"]
        if "tags" in data:
            entity.tags_list = data["tags"]
        entity.save()
        return entity

    def _delete_entity(self, entity: Campaign, user) -> None:
        entity.delete_instance()
