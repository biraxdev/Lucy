"""
Migration 004 — Add channel column to chat_messages.

Supports the dynamic chat feature: messages are tagged with a channel
('global' for the continuous feed, 'group:{id}' for contextual group chats).
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "004"
DESCRIPTION = "Add channel column to chat_messages for multi-channel chat"


def migrate() -> None:
    """Apply migration (idempotent)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        # SQLite doesn't support ADD COLUMN IF NOT EXISTS directly, so we check.
        cursor = database.execute_sql("PRAGMA table_info(chat_messages)")
        columns = [row[1] for row in cursor.fetchall()]
        if "channel" not in columns:
            database.execute_sql(
                "ALTER TABLE chat_messages ADD COLUMN channel TEXT NOT NULL DEFAULT 'global'"
            )
            logger.info("Added 'channel' column to chat_messages.")
        else:
            logger.debug("'channel' column already exists on chat_messages.")

        # Index for fast channel-filtered queries.
        cursor = database.execute_sql(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_chat_messages_channel'"
        )
        if not cursor.fetchone():
            database.execute_sql(
                "CREATE INDEX idx_chat_messages_channel ON chat_messages(channel)"
            )
            logger.info("Created index idx_chat_messages_channel.")
    logger.info("Migration %s applied.", SCHEMA_VERSION)
