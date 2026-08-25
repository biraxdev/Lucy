"""
Unified full-text search across Lucy backend entities.

Searches Agent, Task, Credential, Log, Finding, AlertEvent, FileEvent, and
AuditTrail. Returns a flattened, scored result list sorted by relevance.
"""
from typing import Any, Optional

from database import database
from db.models import (
    Agent,
    AuditTrail,
    Credential,
    FileEvent,
    Finding,
    AlertEvent as AlertEventModel,
    Log,
    Task,
)


# Map resource type -> (model, list of searchable text fields)
SEARCHABLE_ENTITIES: dict[str, tuple[Any, list[str]]] = {
    "agent": (Agent, ["hostname", "os", "username", "ip_public", "ip_private", "status", "tags"]),
    "task": (Task, ["module", "action", "status", "params", "result", "error"]),
    "credential": (Credential, ["url", "hostname", "username", "source", "tags"]),
    "log": (Log, ["level", "module", "message"]),
    "finding": (Finding, ["title", "description", "severity", "status"]),
    "alert": (AlertEventModel, ["event", "title", "message", "severity"]),
    "file": (FileEvent, ["path", "action", "status"]),
    "audit": (AuditTrail, ["action", "actor", "resource_type", "resource_id", "details"]),
}


class SearchEngine:
    """Simple unified full-text search backed by Peewee LIKE queries."""

    def search(
        self,
        query: str,
        types: Optional[list[str]] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a unified search result payload.

        Args:
            query: free-text query (split on whitespace; each token must match)
            types: restrict to these resource types; None = all types
            tenant_id: optional tenant filter (not implemented on all models)
            limit: max total results
        """
        if not query or not query.strip():
            return {"query": "", "total": 0, "results": []}

        tokens = [t.lower() for t in query.strip().split() if t]
        if not tokens:
            return {"query": query, "total": 0, "results": []}

        requested = set(types or SEARCHABLE_ENTITIES.keys())
        requested &= set(SEARCHABLE_ENTITIES.keys())

        results: list[dict] = []
        for resource_type in requested:
            model, fields = SEARCHABLE_ENTITIES[resource_type]
            rows = self._query_model(model, fields, tokens, tenant_id, limit)
            for row in rows:
                score = self._score(row, fields, tokens)
                results.append(self._format_result(resource_type, row, score))

        results.sort(key=lambda r: r["score"], reverse=True)
        return {
            "query": query,
            "tokens": tokens,
            "total": len(results),
            "results": results[:limit],
        }

    def _query_model(
        self,
        model: Any,
        fields: list[str],
        tokens: list[str],
        tenant_id: Optional[str],
        limit: int,
    ) -> list[Any]:
        # Build a single LIKE clause requiring every token to appear somewhere
        # in the concatenated searchable fields.
        concat_fields = []
        for field_name in fields:
            if hasattr(model, field_name):
                concat_fields.append(getattr(model, field_name))

        if not concat_fields:
            return []

        # Peewee concatenation: use fn.CONCAT or fn.COALESCE workaround.
        # Simpler approach: chain OR clauses per token, then filter in Python.
        from peewee import fn

        concat_expr = fn.COALESCE(concat_fields[0], "")
        for expr in concat_fields[1:]:
            concat_expr = fn.CONCAT(concat_expr, " ", fn.COALESCE(expr, ""))

        q = model.select()
        for token in tokens:
            q = q.where(concat_expr.contains(token))

        if tenant_id and hasattr(model, "tenant_id"):
            q = q.where(model.tenant_id == tenant_id)

        return list(q.limit(limit))

    def _score(self, row: Any, fields: list[str], tokens: list[str]) -> int:
        """Simple scoring: +10 for token in title-ish field, +1 otherwise."""
        score = 0
        text_cache: dict[str, str] = {}

        # Heuristic: first field is usually the "title"
        title_field = fields[0]

        for token in tokens:
            for field_name in fields:
                text = text_cache.get(field_name)
                if text is None:
                    text = self._field_text(row, field_name)
                    text_cache[field_name] = text
                if token in text:
                    score += 10 if field_name == title_field else 1
        return score

    def _field_text(self, row: Any, field_name: str) -> str:
        value = getattr(row, field_name, None)
        if value is None:
            return ""
        return str(value).lower()

    def _format_result(self, resource_type: str, row: Any, score: int) -> dict:
        d = row.to_dict()
        return {
            "type": resource_type,
            "id": d.get("id"),
            "score": score,
            "title": self._result_title(resource_type, row),
            "snippet": self._result_snippet(resource_type, row),
            "data": d,
        }

    def _result_title(self, resource_type: str, row: Any) -> str:
        if resource_type == "agent":
            return f"{row.hostname} ({row.os})"
        if resource_type == "task":
            return f"{row.module} / {row.action}"
        if resource_type == "credential":
            return f"{row.username} @ {row.source}"
        if resource_type == "log":
            return f"[{row.level}] {row.module}"
        if resource_type == "finding":
            return row.title
        if resource_type == "alert":
            return row.title
        if resource_type == "file":
            return row.path
        if resource_type == "audit":
            return f"{row.action} by {row.actor}"
        return str(row.id)

    def _result_snippet(self, resource_type: str, row: Any) -> str:
        if resource_type == "agent":
            return f"{row.status} — {row.ip_public or row.ip_private or 'no IP'}"
        if resource_type == "task":
            return row.status
        if resource_type == "credential":
            return row.url or row.hostname or ""
        if resource_type == "log":
            return row.message or ""
        if resource_type == "finding":
            return row.description or ""
        if resource_type == "alert":
            return row.message or ""
        if resource_type == "file":
            return row.action or ""
        if resource_type == "audit":
            return row.resource_type or ""
        return ""


def search(
    query: str,
    types: Optional[list[str]] = None,
    tenant_id: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Convenience wrapper."""
    return SearchEngine().search(query, types=types, tenant_id=tenant_id, limit=limit)
