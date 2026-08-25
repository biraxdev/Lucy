"""CredentialProvider — wraps Credential for the library (read-only, NO secrets).

CRITICAL: This provider NEVER exposes password_encrypted or any decrypted secret.
Only metadata (url, hostname, username, source, confidence, tags) is returned.
The actual secret reveal stays on the dedicated /credentials/{id}/reveal endpoint.
"""
from __future__ import annotations

from db.models import Credential
from core.library.base import safe_iso
from core.library.providers.linked import LinkedProvider


class CredentialProvider(LinkedProvider):
    resource_type = "credential_reference"
    source_model = Credential
    editable = False
    deletable = False

    def _entity_to_resource_dict(self, entity: Credential) -> dict:
        # NEVER include password_encrypted
        return {
            "id": str(entity.id),
            "tenant_id": str(entity.tenant_id) if entity.tenant_id else None,
            "agent_id": str(entity.agent_id) if entity.agent_id else None,
            "url": entity.url,
            "hostname": entity.hostname,
            "username": entity.username,
            "source": entity.source,
            "confidence": entity.confidence,
            "tags": entity.tags_list,
            "metadata": entity.metadata_dict,
            "captured_at": safe_iso(entity.captured_at),
            "version": entity.version,
            # password_encrypted is INTENTIONALLY EXCLUDED
        }

    def _entity_preview(self, entity: Credential) -> dict:
        return {
            "url": entity.url,
            "hostname": entity.hostname,
            "username": entity.username,
            "source": entity.source,
            "confidence": entity.confidence,
            "tags": entity.tags_list,
            "captured_at": safe_iso(entity.captured_at),
            # NO password, NO password_encrypted
        }

    def _entity_metadata(self, entity: Credential) -> dict:
        return {
            "url": entity.url,
            "hostname": entity.hostname,
            "username": entity.username,
            "source": entity.source,
            "confidence": entity.confidence,
            "tags": entity.tags_list,
            "metadata": entity.metadata_dict,
            "agent_id": str(entity.agent_id) if entity.agent_id else None,
            "captured_at": safe_iso(entity.captured_at),
            "version": entity.version,
            "dedup_hash": entity.dedup_hash,
            # NO password_encrypted, NO decrypted password
        }

    def _entity_relations(self, entity: Credential) -> dict:
        return {
            "agent_id": str(entity.agent_id) if entity.agent_id else None,
        }
