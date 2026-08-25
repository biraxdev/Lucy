"""
Setup / onboarding API for Project Lucy.
Tracks whether the first-run wizard has been completed.
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import AdminUser, CurrentUser

router = APIRouter(prefix="/setup", tags=["setup"])
logger = logging.getLogger(__name__)

_SETUP_FLAG = Path("./data/.setup_complete")


def _is_setup_done() -> bool:
    return _SETUP_FLAG.exists()


def _mark_setup_done() -> None:
    _SETUP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    _SETUP_FLAG.write_text(datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Status — public (needed before login to decide if wizard shows)
# ---------------------------------------------------------------------------

@router.get("/status")
async def setup_status() -> dict:
    """Returns whether first-run setup has been completed."""
    done = _is_setup_done()
    health = await _check_health()
    return {
        "setup_complete": done,
        "completed_at": _SETUP_FLAG.read_text() if done else None,
        "health": health,
    }


# ---------------------------------------------------------------------------
# Complete — called by wizard on finish
# ---------------------------------------------------------------------------

class SetupCompleteBody(BaseModel):
    c2_url: str
    admin_password_changed: bool = False


@router.post("/complete")
async def complete_setup(body: SetupCompleteBody, current_user: AdminUser) -> dict:
    if _is_setup_done():
        return {"setup_complete": True, "message": "Already completed."}
    _mark_setup_done()
    logger.info("First-run setup completed by %s", current_user.get("username"))
    return {"setup_complete": True, "c2_url": body.c2_url}


# ---------------------------------------------------------------------------
# Reset — admin only
# ---------------------------------------------------------------------------

@router.post("/reset")
async def reset_setup(current_user: AdminUser) -> dict:
    if _SETUP_FLAG.exists():
        _SETUP_FLAG.unlink()
    return {"setup_complete": False}


# ---------------------------------------------------------------------------
# Health sub-check
# ---------------------------------------------------------------------------

async def _check_health() -> dict:
    checks: dict = {}

    # Database
    try:
        from database import database
        database.connect(reuse_if_open=True)
        database.execute_sql("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis
    try:
        import redis as redis_lib
        from config import settings
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Backend itself is obviously running
    checks["backend"] = "ok"

    return checks
