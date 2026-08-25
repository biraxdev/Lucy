"""
Migration 002 — Performance indexes for high-throughput paths.

Adds composite and single-column indexes used by the dashboard, websocket
handlers, and list endpoints. All statements are idempotent.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "002"
DESCRIPTION = "Performance indexes for agents, tasks, credentials, logs, and chat"

INDEX_SQL = """
-- Agent status / last_seen lookups (dashboard, orchestrator, dynamic groups)
CREATE INDEX IF NOT EXISTS idx_agents_status_last_seen ON agents(status, last_seen);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_status ON agents(tenant_id, status);

-- Task list filters (dashboard, task queue, per-agent history)
CREATE INDEX IF NOT EXISTS idx_tasks_agent_status_created ON tasks(agent_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at);
-- Note: idx_tasks_timeline is created in migration 003 after the column is added.

-- Credential source / time window queries
CREATE INDEX IF NOT EXISTS idx_credentials_agent_captured ON credentials(agent_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_credentials_severity ON credentials(confidence);

-- Log tailing / filtering
CREATE INDEX IF NOT EXISTS idx_logs_timestamp_level ON logs(timestamp, level);
CREATE INDEX IF NOT EXISTS idx_logs_module ON logs(module);

-- Chat event feed
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_agent ON chat_messages(agent_id);

-- Alert / finding status
CREATE INDEX IF NOT EXISTS idx_alert_events_read_timestamp ON alert_events(read, timestamp);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);

-- File event history
CREATE INDEX IF NOT EXISTS idx_file_events_agent_timestamp ON file_events(agent_id, timestamp);

-- Refresh token cleanup
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at, revoked);
"""


def up() -> None:
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        for statement in INDEX_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                database.execute_sql(stmt)
    logger.info("Migration %s applied.", SCHEMA_VERSION)


migrate = up


def down() -> None:
    from database import database

    indexes = [
        "idx_agents_status_last_seen",
        "idx_agents_tenant_status",
        "idx_tasks_agent_status_created",
        "idx_tasks_status_created",
        "idx_tasks_timeline",
        "idx_credentials_agent_captured",
        "idx_credentials_severity",
        "idx_logs_timestamp_level",
        "idx_logs_module",
        "idx_chat_messages_created",
        "idx_chat_messages_agent",
        "idx_alert_events_read_timestamp",
        "idx_findings_status",
        "idx_file_events_agent_timestamp",
        "idx_refresh_tokens_expires",
    ]
    with database:
        for name in indexes:
            database.execute_sql(f"DROP INDEX IF EXISTS {name}")
    logger.info("Migration %s rolled back.", SCHEMA_VERSION)


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
