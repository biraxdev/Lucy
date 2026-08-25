"""Pack Manager — business logic for BuildPack operations."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from database import database
from db.models import BuildPack

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")[:60]
    return f"{base}_{uuid.uuid4().hex[:8]}"


def list_packs(query: str | None = None) -> list[dict[str, Any]]:
    """Return all packs, optionally filtered by query."""
    q = BuildPack.select().order_by(BuildPack.name)
    if query:
        term = f"%{query}%"
        q = q.where(
            (BuildPack.name.contains(term))
            | (BuildPack.description.contains(term))
            | (BuildPack.tags.contains(query))
            | (BuildPack.bpid.contains(query))
        )
    return [p.to_dict() for p in q]


def get_pack(bpid: str) -> dict[str, Any] | None:
    pack = BuildPack.get_or_none(BuildPack.bpid == bpid)
    return pack.to_dict() if pack else None


def _pack_payload(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": body.get("name", "New pack"),
        "description": body.get("description", ""),
        "icon": body.get("icon", "📦"),
        "tags": json.dumps(body.get("tags", [])),
        "modules": json.dumps(body.get("modules", [])),
        "build_options": json.dumps(body.get("build_options", {})),
        "updated_at": _now(),
    }


def create_pack(bpid: str, body: dict[str, Any]) -> dict[str, Any]:
    if BuildPack.get_or_none(BuildPack.bpid == bpid):
        raise ValueError(f"Build pack '{bpid}' already exists")
    data = _pack_payload(body)
    data["created_at"] = _now()
    with database:
        pack = BuildPack.create(bpid=bpid, **data)
    return pack.to_dict()


def update_pack(bpid: str, body: dict[str, Any]) -> dict[str, Any]:
    pack = BuildPack.get_or_none(BuildPack.bpid == bpid)
    if not pack:
        raise ValueError(f"Build pack '{bpid}' not found")
    if pack.source_file:
        raise ValueError("Cannot edit a built-in pack")
    data = _pack_payload(body)
    with database:
        BuildPack.update(**data).where(BuildPack.bpid == bpid).execute()
        pack = BuildPack.get(BuildPack.bpid == bpid)
    return pack.to_dict()


def delete_pack(bpid: str) -> None:
    pack = BuildPack.get_or_none(BuildPack.bpid == bpid)
    if not pack:
        raise ValueError(f"Build pack '{bpid}' not found")
    if pack.source_file:
        raise ValueError("Cannot delete a built-in pack")
    with database:
        pack.delete_instance()


def duplicate_pack(bpid: str, new_id: str | None = None) -> dict[str, Any]:
    pack = BuildPack.get_or_none(BuildPack.bpid == bpid)
    if not pack:
        raise ValueError(f"Build pack '{bpid}' not found")
    target = new_id or _slugify(pack.name)
    if BuildPack.get_or_none(BuildPack.bpid == target):
        target = _slugify(pack.name)
    data = _pack_payload(pack.to_dict())
    data["created_at"] = _now()
    with database:
        new_pack = BuildPack.create(bpid=target, **data)
    return new_pack.to_dict()


def combine_pack(bpid_a: str, bpid_b: str, new_id: str, name: str) -> dict[str, Any]:
    a = BuildPack.get_or_none(BuildPack.bpid == bpid_a)
    b = BuildPack.get_or_none(BuildPack.bpid == bpid_b)
    if not a or not b:
        raise ValueError("One or both packs not found")
    if BuildPack.get_or_none(BuildPack.bpid == new_id):
        raise ValueError(f"Build pack '{new_id}' already exists")
    modules_a = set(a.modules_list)
    modules_b = set(b.modules_list)
    tags = list(set(a.tags_list) | set(b.tags_list))
    opts = {**a.build_options_dict, **b.build_options_dict}
    body = {
        "name": name,
        "description": f"Combined {a.name} + {b.name}",
        "icon": a.icon,
        "tags": tags,
        "modules": sorted(modules_a | modules_b),
        "build_options": opts,
    }
    return create_pack(new_id, body)


def export_pack(bpid: str) -> dict[str, Any]:
    pack = BuildPack.get_or_none(BuildPack.bpid == bpid)
    if not pack:
        raise ValueError(f"Build pack '{bpid}' not found")
    return {
        "id": pack.bpid,
        "name": pack.name,
        "description": pack.description,
        "icon": pack.icon,
        "tags": pack.tags_list,
        "modules": pack.modules_list,
        "build_options": pack.build_options_dict,
    }


def import_pack(body: dict[str, Any]) -> dict[str, Any]:
    bpid = body.get("id") or _slugify(body.get("name", "imported"))
    if BuildPack.get_or_none(BuildPack.bpid == bpid):
        bpid = _slugify(body.get("name", "imported"))
    return create_pack(bpid, body)


def apply_pack(bpid: str) -> dict[str, Any]:
    pack = BuildPack.get_or_none(BuildPack.bpid == bpid)
    if not pack:
        raise ValueError(f"Build pack '{bpid}' not found")
    return {
        "bpid": pack.bpid,
        "name": pack.name,
        "modules": pack.modules_list,
        "build_options": pack.build_options_dict,
    }
