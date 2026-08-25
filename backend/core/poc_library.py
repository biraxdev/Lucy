"""
PoC Library — loader and seeder for documented proof-of-concept chains.

The library lives in backend/data/poc_library.json (list of templates).
Each template has id, name, description, category, trigger, agent_group,
phases, steps (with action_description), and optional MITRE techniques.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import database
from db.models import PocTemplate

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "poc_library.json"


def load_library(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the PoC library JSON file."""
    p = Path(path or DEFAULT_PATH)
    if not p.exists():
        logger.warning("PoC library not found at %s", p)
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("templates", []) if isinstance(data, dict) else data
    except Exception as exc:
        logger.error("Failed to load PoC library from %s: %s", p, exc)
        return []


def seed_poc_templates(path: Path | str | None = None) -> int:
    """Seed PocTemplate rows from the JSON library (idempotent by puid)."""
    templates = load_library(path)
    if not templates:
        return 0

    seeded = 0
    source = str(Path(path or DEFAULT_PATH).resolve())
    now = datetime.now(timezone.utc)

    with database:
        for tpl in templates:
            puid = tpl.get("id")
            if not puid:
                continue
            defaults = {
                "name": tpl.get("name", puid),
                "description": tpl.get("description", ""),
                "icon": tpl.get("icon", "🛡"),
                "category": tpl.get("category", "full"),
                "trigger": tpl.get("trigger", "manual"),
                "agent_group": json.dumps(tpl.get("agent_group", ["all"])),
                "mitre_techniques": json.dumps(tpl.get("mitre_techniques", [])),
                "tags": json.dumps(tpl.get("tags", [])),
                "phases": json.dumps(tpl.get("phases", [])),
                "steps": json.dumps(tpl.get("steps", [])),
                "source_file": source,
                "updated_at": now,
            }
            existing = PocTemplate.get_or_none(PocTemplate.puid == puid)
            if existing:
                PocTemplate.update(**defaults).where(PocTemplate.puid == puid).execute()
                logger.debug("PoC template '%s' refreshed.", puid)
            else:
                defaults["created_at"] = now
                PocTemplate.create(puid=puid, **defaults)
                logger.info("PoC template '%s' seeded.", puid)
            seeded += 1

    logger.info("Seeded %d PoC templates from %s.", seeded, source)
    return seeded


def get_template_by_puid(puid: str) -> PocTemplate | None:
    return PocTemplate.get_or_none(PocTemplate.puid == puid)
