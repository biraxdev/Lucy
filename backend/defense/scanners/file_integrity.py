import hashlib
import json
import os
from datetime import datetime
from pathlib import Path


def _hash_file(path: str) -> str | None:
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        return f"error:{exc}"


def run(action: str = "check", **params) -> dict:
    """File integrity monitor for critical system files on owned hosts."""
    paths = params.get("paths", [])
    if isinstance(paths, str):
        paths = [paths]

    baseline = params.get("baseline", {})
    if isinstance(baseline, str):
        try:
            baseline = json.loads(baseline)
        except Exception:
            baseline = {}

    results = []
    changed = []
    missing = []

    for path in paths:
        current = _hash_file(path)
        expected = baseline.get(path)
        status = "unchanged" if expected is None else ("unchanged" if current == expected else "modified")
        if current is None:
            status = "missing"
            missing.append(path)
        elif expected is not None and current != expected:
            changed.append(path)

        results.append({
            "path": path,
            "current_hash": current,
            "expected_hash": expected,
            "status": status,
        })

    return {
        "status": "completed",
        "action": action,
        "checked": len(paths),
        "changed": changed,
        "missing": missing,
        "results": results,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
