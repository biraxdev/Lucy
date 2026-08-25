"""C2ProfileProvider — wraps C2Profile for the library."""
from __future__ import annotations

from db.models import C2Profile
from core.library.providers.linked import LinkedProvider


class C2ProfileProvider(LinkedProvider):
    resource_type = "c2_profile"
    source_model = C2Profile
    editable = True
    deletable = True

    def _entity_to_resource_dict(self, entity: C2Profile) -> dict:
        return entity.to_dict()

    def _entity_preview(self, entity: C2Profile) -> dict:
        return {
            "name": entity.name,
            "http_get_uri": entity.http_get_uri,
            "http_post_uri": entity.http_post_uri,
            "user_agent": entity.user_agent,
            "jitter_seconds": entity.jitter_seconds,
            "max_retries": entity.max_retries,
        }

    def _entity_metadata(self, entity: C2Profile) -> dict:
        return entity.to_dict()

    def _update_entity(self, entity: C2Profile, data: dict, user):
        if "name" in data:
            entity.name = data["name"]
        if "user_agent" in data:
            entity.user_agent = data["user_agent"]
        entity.save()
        return entity

    def _delete_entity(self, entity: C2Profile, user) -> None:
        entity.delete_instance()
