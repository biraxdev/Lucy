"""
Tag and metadata management service for Project Lucy.

Provides centralized operations for adding, removing, replacing tags and
metadata on agents and credentials, including filtering by tag/metadata.
"""
import json
from typing import Any, Optional

from peewee import Model

from database import database
from db.models import Agent, Credential, Resource


class TagManager:
    """Central service for tags and metadata on agents, credentials, and resources."""

    # Mapping resource name -> model class
    RESOURCE_MODELS: dict[str, type[Model]] = {
        "agent": Agent,
        "credential": Credential,
        "resource": Resource,
    }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_tags(tags: list[str] | str | None) -> list[str]:
        """Return a sorted, deduplicated, lower-cased list of tag strings."""
        if tags is None:
            return []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        result = []
        for tag in tags:
            if not isinstance(tag, str):
                continue
            tag = tag.strip().lower()
            if tag and tag not in result:
                result.append(tag)
        return sorted(result)

    @staticmethod
    def _serialize_json(value: Any) -> str | None:
        """Serialize a JSON value or return None if empty."""
        if value is None or value == {} or value == []:
            return None
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    # ------------------------------------------------------------------
    # Tag operations
    # ------------------------------------------------------------------

    def add_tags(self, resource: str, resource_id: str, tags: list[str]) -> dict:
        """Add tags to a single resource without duplicating existing ones."""
        model = self._get_model(resource)
        record = model.get_or_none(model.id == resource_id)
        if not record:
            raise ValueError(f"{resource} not found")

        new_tags = self._normalize_tags(tags)
        current = record.tags_list
        merged = current.copy()
        for tag in new_tags:
            if tag not in merged:
                merged.append(tag)
        merged = self._normalize_tags(merged)
        if merged != current:
            with database:
                record.tags_list = merged
                record.save()
        return record.to_dict()

    def remove_tags(self, resource: str, resource_id: str, tags: list[str]) -> dict:
        """Remove tags from a single resource."""
        model = self._get_model(resource)
        record = model.get_or_none(model.id == resource_id)
        if not record:
            raise ValueError(f"{resource} not found")

        to_remove = set(self._normalize_tags(tags))
        current = record.tags_list
        updated = [t for t in current if t not in to_remove]
        if updated != current:
            with database:
                record.tags_list = updated
                record.save()
        return record.to_dict()

    def set_tags(self, resource: str, resource_id: str, tags: list[str]) -> dict:
        """Replace tags on a single resource."""
        model = self._get_model(resource)
        record = model.get_or_none(model.id == resource_id)
        if not record:
            raise ValueError(f"{resource} not found")

        normalized = self._normalize_tags(tags)
        with database:
            record.tags_list = normalized
            record.save()
        return record.to_dict()

    def bulk_add_tags(self, resource: str, ids: list[str], tags: list[str]) -> dict:
        """Add tags to multiple resources."""
        model = self._get_model(resource)
        new_tags = self._normalize_tags(tags)
        updated = 0
        with database:
            for record in model.select().where(model.id.in_(ids)):
                current = record.tags_list
                merged = current.copy()
                for tag in new_tags:
                    if tag not in merged:
                        merged.append(tag)
                if merged != current:
                    record.tags_list = merged
                    record.save()
                    updated += 1
        return {"updated": updated}

    def bulk_remove_tags(self, resource: str, ids: list[str], tags: list[str]) -> dict:
        """Remove tags from multiple resources."""
        model = self._get_model(resource)
        to_remove = set(self._normalize_tags(tags))
        updated = 0
        with database:
            for record in model.select().where(model.id.in_(ids)):
                current = record.tags_list
                updated_tags = [t for t in current if t not in to_remove]
                if updated_tags != current:
                    record.tags_list = updated_tags
                    record.save()
                    updated += 1
        return {"updated": updated}

    def bulk_set_tags(self, resource: str, ids: list[str], tags: list[str]) -> dict:
        """Replace tags on multiple resources."""
        model = self._get_model(resource)
        normalized = self._normalize_tags(tags)
        updated = 0
        with database:
            for record in model.select().where(model.id.in_(ids)):
                if record.tags_list != normalized:
                    record.tags_list = normalized
                    record.save()
                    updated += 1
        return {"updated": updated}

    def get_unique_tags(self, resource: str) -> list[str]:
        """Return a sorted list of all unique tags for a resource type."""
        model = self._get_model(resource)
        unique_tags: set[str] = set()
        for record in model.select(model.tags):
            unique_tags.update(record.tags_list)
        return sorted(unique_tags)

    # ------------------------------------------------------------------
    # Metadata operations
    # ------------------------------------------------------------------

    def set_metadata(self, resource: str, resource_id: str, metadata: dict) -> dict:
        """Replace metadata on a single resource."""
        model = self._get_model(resource)
        record = model.get_or_none(model.id == resource_id)
        if not record:
            raise ValueError(f"{resource} not found")

        metadata = metadata or {}
        with database:
            record.metadata_dict = metadata
            record.save()
        return record.to_dict()

    def update_metadata(self, resource: str, resource_id: str, metadata: dict) -> dict:
        """Merge metadata into a single resource."""
        model = self._get_model(resource)
        record = model.get_or_none(model.id == resource_id)
        if not record:
            raise ValueError(f"{resource} not found")

        current = record.metadata_dict
        current.update(metadata)
        with database:
            record.metadata_dict = current
            record.save()
        return record.to_dict()

    def delete_metadata_keys(self, resource: str, resource_id: str, keys: list[str]) -> dict:
        """Delete metadata keys from a single resource."""
        model = self._get_model(resource)
        record = model.get_or_none(model.id == resource_id)
        if not record:
            raise ValueError(f"{resource} not found")

        current = record.metadata_dict
        changed = False
        for key in keys:
            if key in current:
                del current[key]
                changed = True
        if changed:
            with database:
                record.metadata_dict = current
                record.save()
        return record.to_dict()

    def bulk_set_metadata(self, resource: str, ids: list[str], metadata: dict) -> dict:
        """Replace metadata on multiple resources."""
        model = self._get_model(resource)
        metadata = metadata or {}
        updated = 0
        with database:
            for record in model.select().where(model.id.in_(ids)):
                if record.metadata_dict != metadata:
                    record.metadata_dict = metadata
                    record.save()
                    updated += 1
        return {"updated": updated}

    def bulk_update_metadata(self, resource: str, ids: list[str], metadata: dict) -> dict:
        """Merge metadata into multiple resources."""
        model = self._get_model(resource)
        updated = 0
        with database:
            for record in model.select().where(model.id.in_(ids)):
                current = record.metadata_dict
                current.update(metadata)
                if record.metadata_dict != current:
                    record.metadata_dict = current
                    record.save()
                    updated += 1
        return {"updated": updated}

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_by_tags(
        self, resource: str, tags: list[str], match_all: bool = True
    ) -> list[dict]:
        """Return resources matching the given tags.

        If match_all is True, resources must contain all tags.
        Otherwise, resources containing any of the tags are returned.
        """
        model = self._get_model(resource)
        target_tags = set(self._normalize_tags(tags))
        if not target_tags:
            return []

        results = []
        for record in model.select():
            record_tags = set(record.tags_list)
            if match_all and target_tags.issubset(record_tags):
                results.append(record.to_dict())
            elif not match_all and target_tags.intersection(record_tags):
                results.append(record.to_dict())
        return results

    def filter_by_metadata(
        self, resource: str, metadata_query: dict
    ) -> list[dict]:
        """Return resources whose metadata contains all key/value pairs in the query."""
        model = self._get_model(resource)
        if not metadata_query:
            return []

        results = []
        for record in model.select():
            record_meta = record.metadata_dict
            if all(record_meta.get(k) == v for k, v in metadata_query.items()):
                results.append(record.to_dict())
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_model(self, resource: str) -> type[Model]:
        resource = resource.lower()
        if resource not in self.RESOURCE_MODELS:
            raise ValueError(f"Unsupported resource: {resource}")
        return self.RESOURCE_MODELS[resource]


# Singleton instance
tag_manager = TagManager()
