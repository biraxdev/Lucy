"""
Unified library search — searches across all resource types via the Resource table.

Delegates to the CVEProvider for live NVD search when resource_type=cve and
the query is not found in the local cache.
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

from peewee import fn

from core.library.base import apply_visibility
from db.models import Resource

logger = logging.getLogger(__name__)

# --- LRU cache for search results ---
_SEARCH_CACHE: OrderedDict[str, tuple[Any, float]] = OrderedDict()
_SEARCH_CACHE_MAX = 128
_SEARCH_CACHE_TTL = 30.0  # seconds


def _cache_key(query: str, filters: dict, user: Optional[dict], limit: int, offset: int) -> str:
    """Build a stable cache key from search parameters."""
    user_key = user.get("username") if user else "anon"
    filter_key = str(sorted(filters.items()))
    raw = f"{query}|{filter_key}|{user_key}|{limit}|{offset}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> Optional[tuple]:
    """Get a cached result if not expired."""
    if key in _SEARCH_CACHE:
        results, ts = _SEARCH_CACHE[key]
        if time.time() - ts < _SEARCH_CACHE_TTL:
            _SEARCH_CACHE.move_to_end(key)
            return results
        del _SEARCH_CACHE[key]
    return None


def _cache_set(key: str, results: tuple) -> None:
    """Store a result in the cache."""
    _SEARCH_CACHE[key] = (results, time.time())
    while len(_SEARCH_CACHE) > _SEARCH_CACHE_MAX:
        _SEARCH_CACHE.popitem(last=False)


def search_resources(
    query: str,
    filters: dict[str, Any],
    user: Optional[dict],
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Search across all resource types in the Resource table.

    Args:
        query: Text search query (whitespace-tokenized, AND logic).
        filters: Dict with optional keys: type (str|list), tag (str|list),
                 status (str|list), language (str), project (str),
                 visibility (str), favorite (bool), pinned (bool).
        user: Current user dict for visibility filtering.
        limit: Max results.
        offset: Pagination offset.

    Returns:
        (results, total_count)
    """
    # Check cache
    cache_key = _cache_key(query, filters, user, limit, offset)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    q = Resource.select()

    # Visibility + tenant filtering
    q = apply_visibility(q, user)

    # Type filter
    if filters.get("type"):
        types = filters["type"] if isinstance(filters["type"], list) else [filters["type"]]
        q = q.where(Resource.resource_type.in_(types))

    # Text search (AND logic on tokens)
    if query and query.strip():
        tokens = [t.lower() for t in query.strip().split() if t]
        for token in tokens:
            q = q.where(
                (fn.LOWER(Resource.name).contains(token))
                | (fn.LOWER(Resource.description).contains(token))
                | (fn.LOWER(Resource.content).contains(token))
            )

    # Tag filter
    if filters.get("tag"):
        tags = filters["tag"] if isinstance(filters["tag"], list) else [filters["tag"]]
        for tag in tags:
            q = q.where(Resource.tags.contains(tag))

    # Status filter
    if filters.get("status"):
        statuses = filters["status"] if isinstance(filters["status"], list) else [filters["status"]]
        q = q.where(Resource.status.in_(statuses))

    # Language filter
    if filters.get("language"):
        q = q.where(Resource.language == filters["language"])

    # Project filter
    if filters.get("project"):
        q = q.where(Resource.project == filters["project"])

    # Visibility filter (explicit override)
    if filters.get("visibility"):
        q = q.where(Resource.visibility == filters["visibility"])

    # Favorite / pinned
    if filters.get("favorite"):
        q = q.where(Resource.favorite == True)
    if filters.get("pinned"):
        q = q.where(Resource.pinned == True)

    # Sorting
    sort = filters.get("sort", "updated_at")
    if sort == "name":
        q = q.order_by(Resource.name.asc())
    elif sort == "use_count":
        q = q.order_by(Resource.use_count.desc())
    elif sort == "created_at":
        q = q.order_by(Resource.created_at.desc())
    else:
        q = q.order_by(Resource.updated_at.desc())

    total = q.count()
    rows = q.limit(limit).offset(offset)
    result = ([r.to_dict(include_content=False) for r in rows], total)
    _cache_set(cache_key, result)
    return result


def get_type_counts(user: Optional[dict]) -> dict[str, int]:
    """Return a dict mapping resource_type -> count, respecting visibility."""
    q = Resource.select(Resource.resource_type, fn.COUNT(Resource.id).alias("cnt"))
    q = apply_visibility(q, user)
    q = q.group_by(Resource.resource_type)
    return {r.resource_type: r.cnt for r in q}


def get_all_tags(user: Optional[dict]) -> list[str]:
    """Return all unique tags across resources, respecting visibility."""
    import json
    q = Resource.select(Resource.tags)
    q = apply_visibility(q, user)
    q = q.where(Resource.tags.is_null(False))
    tags_set: set[str] = set()
    for r in q:
        if r.tags:
            try:
                tags = json.loads(r.tags)
                if isinstance(tags, list):
                    tags_set.update(tags)
            except (json.JSONDecodeError, TypeError):
                pass
    return sorted(tags_set)
