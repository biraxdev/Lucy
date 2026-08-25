"""EvidenceProvider — wraps Evidence for the library (read-only)."""
from __future__ import annotations

from db.models import Evidence
from core.library.base import safe_iso
from core.library.providers.linked import LinkedProvider


class EvidenceProvider(LinkedProvider):
    resource_type = "evidence"
    source_model = Evidence
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Evidence) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: Evidence) -> dict:
        return {
            "name": entity.name,
            "type": entity.type,
            "mime_type": entity.mime_type,
            "size": entity.size,
            "sha256": entity.sha256,
            "encrypted": entity.encrypted,
            "description": entity.description,
            "collected_by": entity.collected_by,
            "agent_id": entity.agent_id,
            "task_id": entity.task_id,
            "finding_id": entity.finding_id,
        }

    def _entity_metadata(self, entity: Evidence) -> dict:
        return {
            "name": entity.name,
            "type": entity.type,
            "mime_type": entity.mime_type,
            "size": entity.size,
            "sha256": entity.sha256,
            "md5": entity.md5,
            "storage_path": entity.storage_path,
            "encrypted": entity.encrypted,
            "collected_by": entity.collected_by,
            "collected_at": safe_iso(entity.collected_at),
            "chain_hash": entity.chain_hash,
            "agent_id": entity.agent_id,
            "task_id": entity.task_id,
            "finding_id": entity.finding_id,
            "campaign_id": entity.campaign_id,
        }

    def _entity_relations(self, entity: Evidence) -> dict:
        return {
            "agent_id": entity.agent_id,
            "task_id": entity.task_id,
            "finding_id": entity.finding_id,
            "campaign_id": entity.campaign_id,
        }
