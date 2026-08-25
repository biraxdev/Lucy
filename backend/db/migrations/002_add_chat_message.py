"""
Migration 002 — Add chat_messages table.

Stores the conversational view of Lucy: operator messages, persona-translated
events, and optional raw technical payloads for advanced users.
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "002"
DESCRIPTION = "Add chat_messages table for the conversational UI"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         TEXT REFERENCES users(id) ON DELETE SET NULL,
    role            TEXT NOT NULL DEFAULT 'assistant',
    content         TEXT NOT NULL,
    raw_payload     TEXT,
    source_event_type TEXT,
    agent_id        TEXT,
    task_id         TEXT,
    metadata        TEXT,
    created_at      DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_id ON chat_messages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_agent_id  ON chat_messages(agent_id);
"""


def migrate() -> None:
    """Apply migration (idempotent)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        for statement in SCHEMA_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                database.execute_sql(stmt)
    logger.info("Migration %s applied.", SCHEMA_VERSION)
