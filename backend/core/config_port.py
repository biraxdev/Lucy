"""
Configuration portability: export/import timelines, agent groups and modules.

Exports are JSON serialisable and human-readable. Imports support overwrite
and skip strategies for name collisions.
"""
import json
from datetime import datetime, timezone
from typing import Any, Literal

from database import database
from db.models import AgentGroup, Module, Timeline


def export_config(types: list[str] | None = None, tenant_id: str | None = None) -> dict[str, Any]:
    """Export configuration objects as a dict."""
    if types is None:
        types = ["timelines", "groups", "modules"]
    allowed = {"timelines", "groups", "modules"}
    selected = [t for t in types if t in allowed]

    result: dict[str, Any] = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "types": selected,
    }

    with database:
        if "timelines" in selected:
            result["timelines"] = [
                _timeline_to_export(t) for t in Timeline.select()
                if tenant_id is None or str(t.tenant_id) == tenant_id
            ]
        if "groups" in selected:
            result["groups"] = [
                _group_to_export(g) for g in AgentGroup.select()
                if tenant_id is None or str(g.tenant_id) == tenant_id
            ]
        if "modules" in selected:
            result["modules"] = [
                _module_to_export(m) for m in Module.select()
                if tenant_id is None or str(m.tenant_id) == tenant_id
            ]

    return result


def import_config(
    data: dict[str, Any],
    strategy: Literal["overwrite", "skip", "rename"] = "skip",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Import configuration objects into the database."""
    imported: dict[str, list[str]] = {"timelines": [], "groups": [], "modules": []}
    skipped: dict[str, list[str]] = {"timelines": [], "groups": [], "modules": []}

    with database:
        # Timelines
        for item in data.get("timelines", []):
            name = item.get("name")
            existing = Timeline.get_or_none(Timeline.name == name)
            if existing and strategy == "skip":
                skipped["timelines"].append(name)
                continue
            fields = {
                "name": name,
                "description": item.get("description", ""),
                "agent_group": _json_dumps(item.get("agent_group", ["all"])),
                "steps": _json_dumps(item.get("steps", [])),
                "trigger": item.get("trigger", "manual"),
                "loop": item.get("loop", False),
                "status": item.get("status", "draft"),
            }
            if tenant_id:
                fields["tenant_id"] = tenant_id
            if existing and strategy == "overwrite":
                Timeline.update(**fields).where(Timeline.id == existing.id).execute()
                imported["timelines"].append(name)
            else:
                Timeline.create(**fields)
                imported["timelines"].append(name)

        # Agent groups
        for item in data.get("groups", []):
            name = item.get("name")
            existing = AgentGroup.get_or_none(AgentGroup.name == name)
            if existing and strategy == "skip":
                skipped["groups"].append(name)
                continue
            fields = {
                "name": name,
                "description": item.get("description", ""),
                "type": item.get("type", "static"),
                "members": _json_dumps(item.get("members", [])),
                "dynamic_query": item.get("dynamic_query", ""),
                "color": item.get("color", "#22c55e"),
                "tags": _json_dumps(item.get("tags", [])),
            }
            if tenant_id:
                fields["tenant_id"] = tenant_id
            if existing and strategy == "overwrite":
                AgentGroup.update(**fields).where(AgentGroup.id == existing.id).execute()
                imported["groups"].append(name)
            else:
                AgentGroup.create(**fields)
                imported["groups"].append(name)

        # Modules
        for item in data.get("modules", []):
            name = item.get("name")
            existing = Module.get_or_none(Module.name == name)
            if existing and strategy == "skip":
                skipped["modules"].append(name)
                continue
            if strategy == "rename" and existing:
                name = f"{name}_imported_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            fields = {
                "name": name,
                "version": item.get("version", "1.0.0"),
                "code": item.get("code", ""),
                "description": item.get("description", ""),
                "author": item.get("author", ""),
                "dependencies": _json_dumps(item.get("dependencies", [])),
                "os_compat": _json_dumps(item.get("os_compat", ["windows", "linux", "darwin"])),
                "signature": item.get("signature", ""),
                "enabled": item.get("enabled", True),
            }
            if tenant_id:
                fields["tenant_id"] = tenant_id
            if existing and strategy == "overwrite":
                Module.update(**fields).where(Module.id == existing.id).execute()
                imported["modules"].append(name)
            else:
                Module.create(**fields)
                imported["modules"].append(name)

    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
    }


def _json_dumps(value: Any) -> str:
    return json.dumps(value) if value is not None else ""


def _timeline_to_export(t: Timeline) -> dict[str, Any]:
    from db.models import _json_loads
    return {
        "name": t.name,
        "description": t.description,
        "agent_group": _json_loads(t.agent_group) or ["all"],
        "steps": _json_loads(t.steps) or [],
        "trigger": t.trigger,
        "loop": t.loop,
        "status": t.status,
    }


def _group_to_export(g: AgentGroup) -> dict[str, Any]:
    from db.models import _json_loads
    return {
        "name": g.name,
        "description": g.description,
        "type": g.type,
        "members": g.members_list,
        "dynamic_query": g.dynamic_query,
        "color": g.color,
        "tags": g.tags_list,
    }


def _module_to_export(m: Module) -> dict[str, Any]:
    return {
        "name": m.name,
        "version": m.version,
        "code": m.code,
        "description": m.description,
        "author": m.author,
        "dependencies": m.dependencies_list,
        "os_compat": m.os_compat_list,
        "signature": m.signature,
        "enabled": m.enabled,
    }
