"""
Migration 007 — Add case management fields to campaigns table.

Adds: case_number, priority, assigned_to, due_date, tags.
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "007"
DESCRIPTION = "Add case management fields to campaigns (case_number, priority, assigned_to, due_date, tags)"


def migrate() -> None:
    """Apply migration (idempotent)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)

    with database:
        cursor = database.execute_sql("PRAGMA table_info(campaigns)")
        existing_cols = [row[1] for row in cursor.fetchall()]

        new_cols = [
            ("case_number", "VARCHAR(32)"),
            ("priority", "VARCHAR(16) DEFAULT 'normal'"),
            ("assigned_to", "VARCHAR(64)"),
            ("due_date", "DATETIME"),
            ("tags", "TEXT"),
        ]

        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                database.execute_sql(
                    f"ALTER TABLE campaigns ADD COLUMN {col_name} {col_type}"
                )
                logger.info("  Added column campaigns.%s", col_name)
            else:
                logger.debug("  Column campaigns.%s already exists", col_name)

    logger.info("Migration %s complete.", SCHEMA_VERSION)
