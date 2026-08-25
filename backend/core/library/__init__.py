"""
Resource Library — unified knowledge & asset hub for Project Lucy.

This package provides a facade layer over the existing specialized models
(Module, PocTemplate, Finding, Evidence, Playbook, etc.) plus native storage
for new resource types (Note, Snippet, Configuration, Documentation, CVE cache, ...).

Architecture: "Unified experience, specialized underlying models."
The library never modifies runtime tables (Agent, Task, Credential, Log, AuditTrail).
It indexes them via read-only providers and stores library metadata
(tags, status, version, relations) on the Resource table.
"""
from core.library.registry import LibraryRegistry, ResourceProvider, registry

__all__ = ["LibraryRegistry", "ResourceProvider", "registry"]
