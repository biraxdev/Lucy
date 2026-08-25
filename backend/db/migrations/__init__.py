"""
Migration runner for Project Lucy.

Imports all numbered migration modules and exposes a `run_migrations()` helper
that executes each one in order. Migrations are expected to be idempotent
(`IF NOT EXISTS` or `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
"""
import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _discover_migrations() -> list[str]:
    """Return sorted migration module names (e.g. 001_initial)."""
    here = Path(__file__).resolve().parent
    modules = []
    for path in here.glob("*.py"):
        name = path.stem
        if name.startswith("_"):
            continue
        # Sort by the leading numeric prefix
        prefix = name.split("_", 1)[0]
        try:
            int(prefix)
        except ValueError:
            continue
        modules.append(name)
    return sorted(modules)


def run_migrations() -> None:
    """Execute all discovered migrations in order."""
    for name in _discover_migrations():
        try:
            module = importlib.import_module(f"db.migrations.{name}")
            migrate = getattr(module, "migrate", None)
            if migrate is None:
                logger.warning("Migration %s has no migrate() function; skipped.", name)
                continue
            migrate()
            logger.info("Migration %s applied.", name)
        except Exception:
            logger.exception("Migration %s failed.", name)
            raise
