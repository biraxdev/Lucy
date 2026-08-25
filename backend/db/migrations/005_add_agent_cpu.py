"""
Migration 005 — Add cpu_percent column to agents table.

Agents report CPU usage in their heartbeats; this column stores the last
reported value so the dashboard can display per-agent CPU/RAM metrics.
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "005"
DESCRIPTION = "Add cpu_percent column to agents for live CPU monitoring"


def migrate() -> None:
    """Apply migration (idempotent)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        cursor = database.execute_sql("PRAGMA table_info(agents)")
        columns = [row[1] for row in cursor.fetchall()]
        if "cpu_percent" not in columns:
            database.execute_sql(
                "ALTER TABLE agents ADD COLUMN cpu_percent REAL"
            )
            logger.info("Added 'cpu_percent' column to agents.")
        else:
            logger.debug("'cpu_percent' column already exists on agents.")
    logger.info("Migration %s applied.", SCHEMA_VERSION)
