"""
Blockchain-like audit trail logger.

Every entry references the previous entry's hash, making tampering detectable.
Entries are stored in the AuditTrail table and can be verified with verify_chain.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from db.models import AuditTrail, Tenant


def _compute_hash(
    previous_hash: str,
    timestamp: datetime,
    action: str,
    actor: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    details: Optional[dict],
) -> str:
    payload = {
        "previous_hash": previous_hash,
        "timestamp": timestamp.isoformat(),
        "action": action,
        "actor": actor,
        "resource_type": resource_type or "",
        "resource_id": resource_id or "",
        "details": details or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_latest_hash() -> str:
    try:
        latest = AuditTrail.select().order_by(AuditTrail.timestamp.desc()).first()
        return latest.current_hash if latest else "0" * 64
    except Exception:
        return "0" * 64


def log_event(
    action: str,
    actor: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    tenant: Optional[Tenant] = None,
) -> AuditTrail:
    """Append a tamper-evident audit entry."""
    previous_hash = _get_latest_hash()
    timestamp = datetime.now(timezone.utc)
    current_hash = _compute_hash(
        previous_hash, timestamp, action, actor, resource_type, resource_id, details
    )
    return AuditTrail.create(
        tenant=tenant,
        timestamp=timestamp,
        action=action,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details, sort_keys=True) if details else None,
        previous_hash=previous_hash,
        current_hash=current_hash,
    )


def verify_chain(limit: Optional[int] = None) -> dict:
    """Verify the integrity of the audit chain.

    Returns a dict with valid (bool), checked_count, first_invalid_id, and
    the expected vs actual hash for the first mismatch.
    """
    query = AuditTrail.select().order_by(AuditTrail.timestamp.asc())
    if limit:
        query = query.limit(limit)

    entries = list(query)
    if not entries:
        return {"valid": True, "checked_count": 0, "first_invalid_id": None}

    previous_hash = "0" * 64
    for entry in entries:
        timestamp = entry.timestamp
        if isinstance(timestamp, str):
            from datetime import datetime as _dt
            timestamp = _dt.fromisoformat(timestamp)
        expected = _compute_hash(
            previous_hash,
            timestamp,
            entry.action,
            entry.actor,
            entry.resource_type,
            entry.resource_id,
            json.loads(entry.details) if entry.details else None,
        )
        if entry.previous_hash != previous_hash or entry.current_hash != expected:
            return {
                "valid": False,
                "checked_count": len(entries),
                "first_invalid_id": str(entry.id),
                "expected_hash": expected,
                "actual_hash": entry.current_hash,
                "expected_previous": previous_hash,
                "actual_previous": entry.previous_hash,
            }
        previous_hash = entry.current_hash

    return {
        "valid": True,
        "checked_count": len(entries),
        "first_invalid_id": None,
        "latest_hash": previous_hash,
    }
