"""
Migration 006 — Add plug-and-play module descriptors, PoC templates, and build packs.

- Adds descriptor columns to the `modules` table (actions, params_schema, category, ...).
- Creates `poc_templates` table for documented proof-of-concept chains.
- Creates `build_packs` table for reusable agent build presets.
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "006"
DESCRIPTION = "Add module descriptors, poc_templates, and build_packs tables"


def migrate() -> None:
    """Apply migration (idempotent)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)

    with database:
        # ------------------------------------------------------------------
        # Module descriptor columns
        # ------------------------------------------------------------------
        cursor = database.execute_sql("PRAGMA table_info(modules)")
        module_cols = [row[1] for row in cursor.fetchall()]

        new_module_cols = [
            ("actions", "TEXT"),
            ("params_schema", "TEXT"),
            ("category", "TEXT"),
            ("mitre_techniques", "TEXT"),
            ("tags", "TEXT"),
            ("inputs", "TEXT"),
            ("outputs", "TEXT"),
            ("expected_duration", "INTEGER"),
        ]
        for col, dtype in new_module_cols:
            if col not in module_cols:
                database.execute_sql(f"ALTER TABLE modules ADD COLUMN {col} {dtype}")
                logger.info("Added column '%s' to modules table.", col)
            else:
                logger.debug("Column '%s' already exists on modules.", col)

        # ------------------------------------------------------------------
        # PoC templates table
        # ------------------------------------------------------------------
        database.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS poc_templates (
                id                 TEXT PRIMARY KEY,
                puid               TEXT NOT NULL UNIQUE,
                name               TEXT NOT NULL,
                description        TEXT,
                icon               TEXT DEFAULT '🛡',
                category           TEXT DEFAULT 'full',
                trigger            TEXT DEFAULT 'manual',
                agent_group        TEXT,
                mitre_techniques   TEXT,
                tags               TEXT,
                phases             TEXT,
                steps              TEXT,
                source_file        TEXT,
                created_at         DATETIME NOT NULL,
                updated_at         DATETIME NOT NULL
            )
            """
        )
        database.execute_sql(
            "CREATE INDEX IF NOT EXISTS idx_poc_templates_category ON poc_templates(category)"
        )
        database.execute_sql(
            "CREATE INDEX IF NOT EXISTS idx_poc_templates_puid ON poc_templates(puid)"
        )

        # ------------------------------------------------------------------
        # Build packs table
        # ------------------------------------------------------------------
        database.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS build_packs (
                id                 TEXT PRIMARY KEY,
                bpid               TEXT NOT NULL UNIQUE,
                name               TEXT NOT NULL,
                description        TEXT,
                icon               TEXT DEFAULT '📦',
                tags               TEXT,
                modules            TEXT,
                build_options      TEXT,
                source_file        TEXT,
                created_at         DATETIME NOT NULL,
                updated_at         DATETIME NOT NULL
            )
            """
        )
        database.execute_sql(
            "CREATE INDEX IF NOT EXISTS idx_build_packs_bpid ON build_packs(bpid)"
        )

    logger.info("Migration %s applied.", SCHEMA_VERSION)


if __name__ == "__main__":
    migrate()
