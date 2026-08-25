"""
Build Packs — loader and seeder for reusable agent build presets.

The packs live in backend/data/build_packs.json. Each pack defines a set of
modules and default build options (stealth, transport, TTL, etc.).
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import database
from db.models import BuildPack

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "build_packs.json"


def load_packs(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the build packs JSON file."""
    p = Path(path or DEFAULT_PATH)
    if not p.exists():
        logger.warning("Build packs file not found at %s", p)
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("packs", []) if isinstance(data, dict) else data
    except Exception as exc:
        logger.error("Failed to load build packs from %s: %s", p, exc)
        return []


def seed_build_packs(path: Path | str | None = None) -> int:
    """Seed BuildPack rows from the JSON file (idempotent by bpid)."""
    packs = load_packs(path)
    if not packs:
        return 0

    seeded = 0
    source = str(Path(path or DEFAULT_PATH).resolve())
    now = datetime.now(timezone.utc)

    with database:
        for pack in packs:
            bpid = pack.get("id")
            if not bpid:
                continue
            defaults = {
                "name": pack.get("name", bpid),
                "description": pack.get("description", ""),
                "icon": pack.get("icon", "📦"),
                "tags": json.dumps(pack.get("tags", [])),
                "modules": json.dumps(pack.get("modules", [])),
                "build_options": json.dumps(pack.get("build_options", {})),
                "source_file": source,
                "updated_at": now,
            }
            existing = BuildPack.get_or_none(BuildPack.bpid == bpid)
            if existing:
                BuildPack.update(**defaults).where(BuildPack.bpid == bpid).execute()
                logger.debug("Build pack '%s' refreshed.", bpid)
            else:
                defaults["created_at"] = now
                BuildPack.create(bpid=bpid, **defaults)
                logger.info("Build pack '%s' seeded.", bpid)
            seeded += 1

    logger.info("Seeded %d build packs from %s.", seeded, source)
    return seeded


def get_pack_by_bpid(bpid: str) -> BuildPack | None:
    return BuildPack.get_or_none(BuildPack.bpid == bpid)
