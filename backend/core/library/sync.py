"""
Library Sync — indexes existing entities into the Resource table.

Called at startup (after seeders) to create/update Resource rows that link
to existing specialized models (Module, PocTemplate, Finding, etc.).
Idempotent by (source_type, source_id).
"""
from __future__ import annotations

import logging
from typing import Optional

from core.library.base import get_or_create_linked_resource
from database import database
from db.models import (
    Agent,
    AgentGroup,
    AgentNote,
    BuildPack,
    C2Profile,
    Campaign,
    Credential,
    DetectionRule,
    Evidence,
    Finding,
    Log,
    Module,
    Playbook,
    PocTemplate,
    Redirector,
    Tactic,
    Task,
    Technique,
    Tenant,
    Timeline,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def sync_existing_resources() -> dict[str, int]:
    """Sync all existing entities into the Resource table.

    Returns a dict mapping source_type -> count of resources synced.
    Safe to call multiple times (idempotent).
    """
    counts: dict[str, int] = {}

    with database:
        counts["module"] = _sync_modules()
        counts["poc"] = _sync_pocs()
        counts["finding"] = _sync_findings()
        counts["evidence"] = _sync_evidence()
        counts["playbook"] = _sync_playbooks()
        counts["detection_rule"] = _sync_detection_rules()
        counts["c2_profile"] = _sync_c2_profiles()
        counts["build_pack"] = _sync_build_packs()
        counts["campaign"] = _sync_campaigns()
        counts["note"] = _sync_agent_notes()
        counts["tactic"] = _sync_tactics()
        counts["technique"] = _sync_techniques()
        # Runtime (read-only references)
        counts["agent"] = _sync_agents()
        counts["task"] = _sync_tasks()
        counts["credential_reference"] = _sync_credentials()
        counts["log"] = _sync_logs()
        counts["timeline"] = _sync_timelines()
        counts["group"] = _sync_groups()
        counts["redirector"] = _sync_redirectors()

    total = sum(counts.values())
    logger.info("Library sync complete: %d resources indexed (%s)", total, counts)
    return counts


def _sync_batch(model_cls, resource_type: str, mapper, tenant_field: str = "tenant_id") -> int:
    """Sync a model in batches. Returns count of resources processed."""
    count = 0
    try:
        total = model_cls.select().count()
        for offset in range(0, total, BATCH_SIZE):
            rows = model_cls.select().offset(offset).limit(BATCH_SIZE)
            for row in rows:
                data = mapper(row)
                if data is None:
                    continue
                tenant_id = str(getattr(row, tenant_field, None)) if getattr(row, tenant_field, None) else None
                get_or_create_linked_resource(
                    resource_type=resource_type,
                    source_type=resource_type,
                    source_id=str(row.id),
                    name=data.get("name", "Untitled"),
                    description=data.get("description"),
                    tenant_id=tenant_id,
                    extra=data.get("metadata", {}),
                )
                count += 1
    except Exception as exc:
        logger.warning("Sync error for %s: %s", resource_type, exc)
    return count


def _sync_modules() -> int:
    def mapper(m):
        return {
            "name": m.name,
            "description": m.description,
            "metadata": {
                "category": getattr(m, "category", None),
                "version": getattr(m, "version", None),
                "os_compat": getattr(m, "os_compat", None),
                "enabled": getattr(m, "enabled", True),
            },
        }
    return _sync_batch(Module, "module", mapper)


def _sync_pocs() -> int:
    def mapper(p):
        return {
            "name": p.name,
            "description": getattr(p, "description", None),
            "metadata": {
                "puid": getattr(p, "puid", None),
                "category": getattr(p, "category", None),
                "mitre_techniques": getattr(p, "mitre_techniques", None),
            },
        }
    return _sync_batch(PocTemplate, "poc", mapper)


def _sync_findings() -> int:
    def mapper(f):
        return {
            "name": f.title,
            "description": getattr(f, "description", None),
            "metadata": {
                "severity": getattr(f, "severity", None),
                "status": getattr(f, "status", None),
                "cvss": getattr(f, "cvss", None),
            },
        }
    return _sync_batch(Finding, "finding", mapper)


def _sync_evidence() -> int:
    def mapper(e):
        return {
            "name": getattr(e, "title", None) or f"Evidence {e.id}",
            "description": getattr(e, "description", None),
            "metadata": {
                "evidence_type": getattr(e, "evidence_type", None),
                "file_hash": getattr(e, "file_hash", None),
            },
        }
    return _sync_batch(Evidence, "evidence", mapper)


def _sync_playbooks() -> int:
    def mapper(p):
        return {
            "name": getattr(p, "name", None) or f"Playbook {p.id}",
            "description": getattr(p, "description", None),
            "metadata": {},
        }
    return _sync_batch(Playbook, "playbook", mapper)


def _sync_detection_rules() -> int:
    def mapper(d):
        return {
            "name": getattr(d, "name", None) or f"Rule {d.id}",
            "description": getattr(d, "description", None),
            "metadata": {
                "rule_type": getattr(d, "rule_type", None),
                "severity": getattr(d, "severity", None),
            },
        }
    return _sync_batch(DetectionRule, "detection_rule", mapper)


def _sync_c2_profiles() -> int:
    def mapper(c):
        return {
            "name": getattr(c, "name", None) or f"C2 Profile {c.id}",
            "description": getattr(c, "description", None),
            "metadata": {},
        }
    return _sync_batch(C2Profile, "c2_profile", mapper)


def _sync_build_packs() -> int:
    def mapper(b):
        return {
            "name": getattr(b, "name", None) or f"Build Pack {b.id}",
            "description": getattr(b, "description", None),
            "metadata": {
                "os": getattr(b, "os", None),
                "arch": getattr(b, "arch", None),
            },
        }
    return _sync_batch(BuildPack, "build_pack", mapper)


def _sync_campaigns() -> int:
    def mapper(c):
        return {
            "name": getattr(c, "name", None) or f"Campaign {c.id}",
            "description": getattr(c, "description", None),
            "metadata": {
                "status": getattr(c, "status", None),
                "priority": getattr(c, "priority", None),
            },
        }
    return _sync_batch(Campaign, "campaign", mapper)


def _sync_agent_notes() -> int:
    def mapper(n):
        return {
            "name": getattr(n, "title", None) or f"Note {n.id}",
            "description": getattr(n, "content", None),
            "metadata": {
                "agent_id": str(getattr(n, "agent_id", None)) if getattr(n, "agent_id", None) else None,
            },
        }
    return _sync_batch(AgentNote, "note", mapper)


def _sync_tactics() -> int:
    def mapper(t):
        return {
            "name": getattr(t, "name", None) or f"Tactic {t.id}",
            "description": getattr(t, "description", None),
            "metadata": {
                "tactic_id": getattr(t, "tactic_id", None),
            },
        }
    return _sync_batch(Tactic, "tactic", mapper)


def _sync_techniques() -> int:
    def mapper(t):
        tactic_val = getattr(t, "tactic", None)
        # tactic may be a Tactic model instance or a string — convert safely
        tactic_name = None
        if tactic_val is not None:
            if hasattr(tactic_val, "name"):
                tactic_name = tactic_val.name
            else:
                tactic_name = str(tactic_val)
        return {
            "name": getattr(t, "name", None) or f"Technique {t.id}",
            "description": getattr(t, "description", None),
            "metadata": {
                "technique_id": getattr(t, "technique_id", None),
                "tactic": tactic_name,
            },
        }
    return _sync_batch(Technique, "technique", mapper)


def _sync_agents() -> int:
    def mapper(a):
        return {
            "name": getattr(a, "hostname", None) or f"Agent {a.id}",
            "description": None,
            "metadata": {
                "os": getattr(a, "os", None),
                "status": getattr(a, "status", None),
                "ip": getattr(a, "ip", None),
                "username": getattr(a, "username", None),
            },
        }
    return _sync_batch(Agent, "agent", mapper)


def _sync_tasks() -> int:
    def mapper(t):
        return {
            "name": f"{getattr(t, 'module', 'task')}:{getattr(t, 'action', 'run')}",
            "description": None,
            "metadata": {
                "status": getattr(t, "status", None),
                "agent_id": str(getattr(t, "agent_id", None)) if getattr(t, "agent_id", None) else None,
            },
        }
    return _sync_batch(Task, "task", mapper)


def _sync_credentials() -> int:
    def mapper(c):
        return {
            "name": getattr(c, "url", None) or getattr(c, "hostname", None) or f"Credential {c.id}",
            "description": None,
            "metadata": {
                "hostname": getattr(c, "hostname", None),
                "username": getattr(c, "username", None),
                "source": getattr(c, "source", None),
                # NEVER include password_encrypted or any secret
            },
        }
    return _sync_batch(Credential, "credential_reference", mapper)


def _sync_logs() -> int:
    def mapper(l):
        return {
            "name": f"Log {l.id}",
            "description": getattr(l, "message", None),
            "metadata": {
                "level": getattr(l, "level", None),
                "source": getattr(l, "source", None),
            },
        }
    return _sync_batch(Log, "log", mapper)


def _sync_timelines() -> int:
    def mapper(t):
        return {
            "name": getattr(t, "name", None) or f"Timeline {t.id}",
            "description": getattr(t, "description", None),
            "metadata": {
                "status": getattr(t, "status", None),
                "trigger": getattr(t, "trigger", None),
            },
        }
    return _sync_batch(Timeline, "timeline", mapper)


def _sync_groups() -> int:
    def mapper(g):
        return {
            "name": getattr(g, "name", None) or f"Group {g.id}",
            "description": getattr(g, "description", None),
            "metadata": {},
        }
    return _sync_batch(AgentGroup, "group", mapper)


def _sync_redirectors() -> int:
    def mapper(r):
        return {
            "name": getattr(r, "name", None) or f"Redirector {r.id}",
            "description": getattr(r, "description", None),
            "metadata": {
                "domain": getattr(r, "domain", None),
                "status": getattr(r, "status", None),
            },
        }
    return _sync_batch(Redirector, "redirector", mapper)
