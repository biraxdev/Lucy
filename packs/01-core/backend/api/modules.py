import json

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from core.module_manager import ModuleManager
from dependencies import AdminUser, CurrentUser, OperatorUser

router = APIRouter(prefix="/modules", tags=["modules"])
manager = ModuleManager()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ModuleUploadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    description: str = ""
    author: str = ""
    dependencies: list[str] = []
    os_compat: list[str] = ["windows", "linux", "darwin"]
    code: str = Field(..., min_length=1)


class ModuleUpdateRequest(BaseModel):
    version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    description: str | None = None
    enabled: bool | None = None
    code: str | None = None


# ---------------------------------------------------------------------------
# GET /api/v1/modules
# ---------------------------------------------------------------------------


@router.get("")
async def list_modules(
    current_user: CurrentUser,
    os: str | None = None,
    enabled_only: bool = True,
) -> list[dict]:
    """List available modules."""
    mods = manager.list_all(enabled_only=enabled_only, os_filter=os)
    return [m.to_dict(include_code=False) for m in mods]


# ---------------------------------------------------------------------------
# POST /api/v1/modules
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def upload_module(body: ModuleUploadRequest, current_user: OperatorUser) -> dict:
    """Upload and register a new module (or update existing)."""
    mod = manager.register(
        name=body.name,
        version=body.version,
        code=body.code,
        description=body.description,
        author=body.author,
        dependencies=body.dependencies,
        os_compat=body.os_compat,
    )
    return mod.to_dict(include_code=False)


# ---------------------------------------------------------------------------
# GET /api/v1/modules/{module_id}
# ---------------------------------------------------------------------------


@router.get("/{module_id}")
async def get_module(module_id: str, current_user: CurrentUser) -> dict:
    """Get module metadata (no code)."""
    mod = manager.get_by_id(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    return mod.to_dict(include_code=False)


# ---------------------------------------------------------------------------
# GET /api/v1/modules/{name}/download  — used by agent
# ---------------------------------------------------------------------------


@router.get("/{name}/download")
async def download_module(name: str, current_user: CurrentUser) -> dict:
    """
    Download module source code (HMAC signed).
    Used by agents to fetch plugins at runtime.
    """
    payload = manager.get_for_agent(name)
    if not payload:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found or disabled")

    manager.increment_install_count(name)
    return payload


# ---------------------------------------------------------------------------
# PATCH /api/v1/modules/{module_id}
# ---------------------------------------------------------------------------


@router.patch("/{module_id}")
async def update_module(
    module_id: str, body: ModuleUpdateRequest, current_user: OperatorUser
) -> dict:
    """Update module metadata or code."""
    mod = manager.get_by_id(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    if body.enabled is not None:
        manager.set_enabled(mod.name, body.enabled)

    if body.code is not None or body.version is not None:
        manager.register(
            name=mod.name,
            version=body.version or mod.version,
            code=body.code or mod.code,
            description=body.description or mod.description or "",
            author=mod.author or "",
            dependencies=mod.dependencies_list,
            os_compat=mod.os_compat_list,
        )

    refreshed = manager.get_by_id(module_id)
    return refreshed.to_dict(include_code=False)


# ---------------------------------------------------------------------------
# DELETE /api/v1/modules/{module_id}  — admin only
# ---------------------------------------------------------------------------


@router.delete("/{module_id}", status_code=204)
async def delete_module(module_id: str, admin: AdminUser) -> None:
    """Remove a module permanently (admin only)."""
    mod = manager.get_by_id(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    manager.delete(mod.name)
