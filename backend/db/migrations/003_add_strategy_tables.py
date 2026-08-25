"""
Migration 003 — Add strategy / operational data tables.

Adds TTP tracking (tactics, techniques), campaign containers,
reusable playbooks, and operator agent notes.
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "003"
DESCRIPTION = "Add tactics, techniques, campaigns, playbooks, agent_notes tables"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tactics (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    mitre_id        TEXT,
    name            TEXT NOT NULL,
    phase           TEXT,
    description     TEXT,
    created_at      DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tactics_tenant_id ON tactics(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tactics_mitre_id  ON tactics(mitre_id);

CREATE TABLE IF NOT EXISTS techniques (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    mitre_id        TEXT,
    name            TEXT NOT NULL,
    tactic_id       TEXT REFERENCES tactics(id) ON DELETE SET NULL,
    description     TEXT,
    platform        TEXT,
    data_sources    TEXT,
    created_at      DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_techniques_tenant_id ON techniques(tenant_id);
CREATE INDEX IF NOT EXISTS idx_techniques_mitre_id  ON techniques(mitre_id);
CREATE INDEX IF NOT EXISTS idx_techniques_tactic_id ON techniques(tactic_id);

CREATE TABLE IF NOT EXISTS campaigns (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    objective       TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    start_date      DATETIME,
    end_date        DATETIME,
    metadata        TEXT,
    created_at      DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_campaigns_tenant_id ON campaigns(tenant_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status    ON campaigns(status);

CREATE TABLE IF NOT EXISTS playbooks (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    technique_ids   TEXT,
    steps           TEXT,
    tags            TEXT,
    created_at      DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_playbooks_tenant_id ON playbooks(tenant_id);

CREATE TABLE IF NOT EXISTS agent_notes (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id        TEXT REFERENCES agents(id) ON DELETE CASCADE,
    user_id         TEXT REFERENCES users(id) ON DELETE SET NULL,
    content         TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'observation',
    created_at      DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_notes_tenant_id ON agent_notes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_notes_agent_id  ON agent_notes(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_notes_category  ON agent_notes(category);
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
