"""
Library Registry — central registry of resource providers.

Each provider implements the ResourceProvider protocol and handles one
resource_type. The registry routes search/get/preview/relations/create/
update/delete calls to the appropriate provider.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ResourceProvider(Protocol):
    """Interface every library provider must implement."""

    resource_type: str

    def search(
        self,
        query: str,
        filters: dict[str, Any],
        tenant_id: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        """Return (results, total_count) matching query + filters."""
        ...

    def get(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        """Return a single resource dict or None."""
        ...

    def preview(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        """Return a type-adapted preview dict or None."""
        ...

    def metadata(self, resource_id: str, tenant_id: Optional[str]) -> Optional[dict]:
        """Return type-specific metadata dict or None."""
        ...

    def relations(self, resource_id: str, tenant_id: Optional[str]) -> dict:
        """Return related resources (auto-resolved + explicit relations)."""
        ...

    # --- Optional write operations (override in editable providers) ---

    def create(self, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        """Create a new resource. Only for native/editable types."""
        raise NotImplementedError(f"{self.resource_type} does not support create")

    def update(self, resource_id: str, data: dict[str, Any], tenant_id: Optional[str], user: dict) -> dict:
        """Update a resource. Only for editable types."""
        raise NotImplementedError(f"{self.resource_type} does not support update")

    def delete(self, resource_id: str, tenant_id: Optional[str], user: dict) -> None:
        """Delete a resource. Only for deletable types."""
        raise NotImplementedError(f"{self.resource_type} does not support delete")


class LibraryRegistry:
    """Singleton registry mapping resource_type -> ResourceProvider."""

    _instance: Optional["LibraryRegistry"] = None

    def __new__(cls) -> "LibraryRegistry":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._providers: dict[str, ResourceProvider] = {}
            inst._loaded = False
            cls._instance = inst
        return cls._instance

    # --- Registration ---

    def register(self, provider: ResourceProvider) -> None:
        rtype = provider.resource_type
        if rtype in self._providers:
            logger.debug("Provider for '%s' already registered — replacing.", rtype)
        self._providers[rtype] = provider
        logger.debug("Registered library provider: %s", rtype)

    def unregister(self, resource_type: str) -> None:
        self._providers.pop(resource_type, None)

    # --- Lookup ---

    def get(self, resource_type: str) -> Optional[ResourceProvider]:
        return self._providers.get(resource_type)

    def all_types(self) -> list[str]:
        return sorted(self._providers.keys())

    def all_providers(self) -> dict[str, ResourceProvider]:
        return dict(self._providers)

    def is_registered(self, resource_type: str) -> bool:
        return resource_type in self._providers

    # --- Bulk loading ---

    def load_all_providers(self) -> None:
        """Import and register all built-in providers (idempotent)."""
        if self._loaded:
            return
        self._loaded = True

        # Native provider (handles ~25 native types)
        from core.library.providers.native import NativeProvider

        native = NativeProvider()
        for rtype in native.supported_types:
            self.register(_NativeTypeWrapper(native, rtype))

        # Knowledge providers
        self._try_register("core.library.providers.module_provider", "ModuleProvider")
        self._try_register("core.library.providers.poc_provider", "PocProvider")
        self._try_register("core.library.providers.finding_provider", "FindingProvider")
        self._try_register("core.library.providers.evidence_provider", "EvidenceProvider")
        self._try_register("core.library.providers.playbook_provider", "PlaybookProvider")
        self._try_register("core.library.providers.detection_rule_provider", "DetectionRuleProvider")
        self._try_register("core.library.providers.c2_profile_provider", "C2ProfileProvider")
        self._try_register("core.library.providers.build_pack_provider", "BuildPackProvider")
        self._try_register("core.library.providers.campaign_provider", "CampaignProvider")
        self._try_register("core.library.providers.note_provider", "NoteProvider")
        self._try_register("core.library.providers.tactic_provider", "TacticProvider")
        self._try_register("core.library.providers.technique_provider", "TechniqueProvider")

        # Runtime providers (read-only references)
        self._try_register("core.library.providers.agent_provider", "AgentProvider")
        self._try_register("core.library.providers.task_provider", "TaskProvider")
        self._try_register("core.library.providers.credential_provider", "CredentialProvider")
        self._try_register("core.library.providers.log_provider", "LogProvider")
        self._try_register("core.library.providers.timeline_provider", "TimelineProvider")
        self._try_register("core.library.providers.group_provider", "GroupProvider")
        self._try_register("core.library.providers.redirector_provider", "RedirectorProvider")

        # External providers
        self._try_register("core.library.providers.cve_provider", "CVEProvider")

        logger.info("Library registry loaded %d providers.", len(self._providers))

    def _try_register(self, module_path: str, class_name: str) -> None:
        """Import a provider class and register it. Skip silently on ImportError."""
        import importlib

        try:
            mod = importlib.import_module(module_path)
            provider_cls = getattr(mod, class_name)
            provider = provider_cls()
            self.register(provider)
        except ImportError as exc:
            logger.debug("Provider %s not available: %s", class_name, exc)
        except Exception as exc:
            logger.warning("Failed to load provider %s: %s", class_name, exc)


class _NativeTypeWrapper:
    """Wraps the NativeProvider for a single resource_type.

    The NativeProvider handles many types; this wrapper exposes one type
    through the standard provider interface so the registry treats it
    uniformly.
    """

    def __init__(self, native: "NativeProvider", rtype: str):
        self._native = native
        self.resource_type = rtype

    def search(self, query, filters, tenant_id, limit, offset):
        return self._native.search(self.resource_type, query, filters, tenant_id, limit, offset)

    def get(self, resource_id, tenant_id):
        return self._native.get(self.resource_type, resource_id, tenant_id)

    def preview(self, resource_id, tenant_id):
        return self._native.preview(self.resource_type, resource_id, tenant_id)

    def metadata(self, resource_id, tenant_id):
        return self._native.metadata(self.resource_type, resource_id, tenant_id)

    def relations(self, resource_id, tenant_id):
        return self._native.relations(self.resource_type, resource_id, tenant_id)

    def create(self, data, tenant_id, user):
        return self._native.create(self.resource_type, data, tenant_id, user)

    def update(self, resource_id, data, tenant_id, user):
        return self._native.update(self.resource_type, resource_id, data, tenant_id, user)

    def delete(self, resource_id, tenant_id, user):
        return self._native.delete(self.resource_type, resource_id, tenant_id, user)


# Singleton
registry = LibraryRegistry()
