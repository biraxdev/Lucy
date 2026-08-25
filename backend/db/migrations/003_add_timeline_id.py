"""
Migration 003 — Add missing timeline_id column to tasks table.

Older schemas created before this field was added to the Task model need the
column for task_queue.py and orchestrator.py to function correctly.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "003"
DESCRIPTION = "Add timeline_id column to tasks table"

MIGRATION_SQL = """
ALTER TABLE tasks ADD COLUMN timeline_id TEXT;
CREATE INDEX IF NOT EXISTS idx_tasks_timeline ON tasks(timeline_id);
"""


def up() -> None:
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        for statement in MIGRATION_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                try:
                    database.execute_sql(stmt)
                except Exception as exc:
                    if "duplicate column" in str(exc).lower():
                        logger.debug("Column timeline_id already exists, skipping.")
                    else:
                        raise
    logger.info("Migration %s applied.", SCHEMA_VERSION)


def down() -> None:
    from database import database

    logger.info("Rolling back migration %s", SCHEMA_VERSION)
    with database:
        # SQLite does not support DROP COLUMN directly until 3.35+.
        # Recreating the table is intentionally skipped here because it would lose data.
        database.execute_sql("DROP TABLE IF EXISTS tasks_new")
    logger.warning("Migration %s rollback requires manual table recreation.", SCHEMA_VERSION)


migrate = up


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    action = sys.argv[1] if len(sys.argv) > 1 else "up"
    if action == "up":
        up()
    elif action == "down":
        down()
    else:
        print(f"Unknown action: {action}. Use 'up' or 'down'.")
        sys.exit(1)
