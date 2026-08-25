"""
Migration 002 — Add metadata columns to agents and credentials tables.

Run manually:
    python -m db.migrations.002_add_metadata_columns
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from database import database

logger = logging.getLogger(__name__)


def _column_exists(table: str, column: str) -> bool:
    cursor = database.execute_sql(
        "SELECT 1 FROM pragma_table_info(?) WHERE name=?;", (table, column)
    )
    return cursor.fetchone() is not None


def migrate() -> None:
    with database:
        if not _column_exists("agents", "metadata"):
            database.execute_sql("ALTER TABLE agents ADD COLUMN metadata TEXT;")
        if not _column_exists("credentials", "metadata"):
            database.execute_sql("ALTER TABLE credentials ADD COLUMN metadata TEXT;")
    logger.info("Migration 002 applied: metadata columns added to agents and credentials")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate()
