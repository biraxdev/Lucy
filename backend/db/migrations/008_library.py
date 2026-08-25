"""
Migration 008 — Resource Library tables.

Creates: resources, resource_versions, resource_relations.
These tables form the unified library index layer on top of existing
specialized models. Idempotent (CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS).
"""
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "008"
DESCRIPTION = "Resource Library — resources, resource_versions, resource_relations"

SCHEMA_SQL = """
-- ============================================================
-- Resource Library — unified index layer
-- ============================================================

CREATE TABLE IF NOT EXISTS resources (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT REFERENCES tenants(id) ON DELETE SET NULL,
    resource_type TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    version       TEXT NOT NULL DEFAULT '1.0.0',
    tags          TEXT,
    project       TEXT,
    owner         TEXT,
    source        TEXT,
    license       TEXT,
    references    TEXT,
    dependencies  TEXT,
    metadata      TEXT,
    content       TEXT,
    language      TEXT,
    visibility    TEXT NOT NULL DEFAULT 'internal',
    storage_path  TEXT,
    content_hash  TEXT,
    favorite      INTEGER NOT NULL DEFAULT 0,
    pinned        INTEGER NOT NULL DEFAULT 0,
    use_count     INTEGER NOT NULL DEFAULT 0,
    source_type   TEXT,
    source_id     TEXT,
    created_by    TEXT,
    created_at    DATETIME NOT NULL,
    updated_at    DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resources_type             ON resources(resource_type);
CREATE INDEX IF NOT EXISTS idx_resources_name             ON resources(name);
CREATE INDEX IF NOT EXISTS idx_resources_project          ON resources(project);
CREATE INDEX IF NOT EXISTS idx_resources_content_hash     ON resources(content_hash);
CREATE INDEX IF NOT EXISTS idx_resources_source_type      ON resources(source_type);
CREATE INDEX IF NOT EXISTS idx_resources_source_id        ON resources(source_id);
CREATE INDEX IF NOT EXISTS idx_resources_tenant_type_status ON resources(tenant_id, resource_type, status);
CREATE INDEX IF NOT EXISTS idx_resources_source_link      ON resources(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_resources_updated          ON resources(updated_at);

CREATE TABLE IF NOT EXISTS resource_versions (
    id          TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    version     TEXT NOT NULL,
    snapshot    TEXT NOT NULL,
    content     TEXT,
    change_note TEXT,
    created_by  TEXT,
    created_at  DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resource_versions_resource ON resource_versions(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_versions_res_ver  ON resource_versions(resource_id, version);

CREATE TABLE IF NOT EXISTS resource_relations (
    id            TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    target_id     TEXT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    metadata      TEXT,
    created_by    TEXT,
    created_at    DATETIME NOT NULL,
    UNIQUE(source_id, target_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_resource_relations_source ON resource_relations(source_id);
CREATE INDEX IF NOT EXISTS idx_resource_relations_target ON resource_relations(target_id);
CREATE INDEX IF NOT EXISTS idx_resource_relations_reverse ON resource_relations(target_id, source_id);
"""


def migrate() -> None:
    """Apply migration (idempotent — uses CREATE TABLE/INDEX IF NOT EXISTS)."""
    from database import database

    logger.info("Running migration %s: %s", SCHEMA_VERSION, DESCRIPTION)
    with database:
        for statement in SCHEMA_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                database.execute_sql(stmt)
    logger.info("Migration %s complete.", SCHEMA_VERSION)
