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
    # ---- Plug-and-play descriptor fields ----
    actions: list[str] | None = None
    params_schema: dict | None = None
    category: str | None = None
    mitre_techniques: list[str] | None = None
    tags: list[str] | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None
    expected_duration: int | None = None


class ModuleUpdateRequest(BaseModel):
    version: str | None = Field(None, pattern=r"^\d+\.\d+\.\d+$")
    description: str | None = None
    enabled: bool | None = None
    code: str | None = None
    actions: list[str] | None = None
    params_schema: dict | None = None
    category: str | None = None
    mitre_techniques: list[str] | None = None
    tags: list[str] | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None
    expected_duration: int | None = None


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
        actions=body.actions,
        params_schema=body.params_schema,
        category=body.category,
        mitre_techniques=body.mitre_techniques,
        tags=body.tags,
        inputs=body.inputs,
        outputs=body.outputs,
        expected_duration=body.expected_duration,
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
# GET /api/v1/modules/{module_id}/descriptor
# ---------------------------------------------------------------------------


@router.get("/{module_id}/descriptor")
async def get_module_descriptor(module_id: str, current_user: CurrentUser) -> dict:
    """Return the plug-and-play descriptor for a module (actions, params_schema, etc.)."""
    mod = manager.get_by_id(module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    return {
        "name": mod.name,
        "version": mod.version,
        "description": mod.description,
        "author": mod.author,
        "dependencies": mod.dependencies_list,
        "os_compat": mod.os_compat_list,
        "actions": mod.actions_list,
        "params_schema": mod.params_schema_dict,
        "category": mod.category,
        "mitre_techniques": mod.mitre_list,
        "tags": mod.tags_list,
        "inputs": mod.inputs_list,
        "outputs": mod.outputs_list,
        "expected_duration": mod.expected_duration,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/modules/upload-manifest  — JSON/YAML manifest upload
# ---------------------------------------------------------------------------


@router.post("/upload-manifest", status_code=201)
async def upload_module_manifest(
    file: UploadFile,
    current_user: OperatorUser,
) -> dict:
    """Upload a module manifest (JSON or YAML) and register the module.

    The manifest must contain: name, version, code.
    Optional descriptor fields: actions, params_schema, category, mitre_techniques,
    tags, inputs, outputs, expected_duration, description, author, dependencies, os_compat.
    """
    import logging

    logger = logging.getLogger(__name__)

    content = await file.read()
    text = content.decode("utf-8")

    try:
        if file.filename and file.filename.lower().endswith((".yaml", ".yml")):
            try:
                import yaml
                manifest = yaml.safe_load(text) or {}
            except ImportError:
                raise HTTPException(status_code=400, detail="PyYAML not installed; cannot parse YAML manifests")
        else:
            manifest = json.loads(text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid manifest file: {exc}")

    name = manifest.get("name")
    version = manifest.get("version", "1.0.0")
    code = manifest.get("code")
    if not name or not code:
        raise HTTPException(status_code=400, detail="Manifest must contain 'name' and 'code' fields")

    # Validate OS compatibility
    os_compat = manifest.get("os_compat", ["windows", "linux", "darwin"])
    valid_os = {"windows", "linux", "darwin"}
    invalid = [o for o in os_compat if o not in valid_os]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid os_compat values: {invalid}")

    mod = manager.register(
        name=name,
        version=version,
        code=code,
        description=manifest.get("description", ""),
        author=manifest.get("author", "lucy"),
        dependencies=manifest.get("dependencies", []),
        os_compat=os_compat,
        actions=manifest.get("actions"),
        params_schema=manifest.get("params_schema"),
        category=manifest.get("category"),
        mitre_techniques=manifest.get("mitre_techniques"),
        tags=manifest.get("tags"),
        inputs=manifest.get("inputs"),
        outputs=manifest.get("outputs"),
        expected_duration=manifest.get("expected_duration"),
    )
    logger.info("Module '%s' registered from manifest upload by %s.", name, current_user.get("username") if isinstance(current_user, dict) else current_user)
    return mod.to_dict(include_code=False)


# ---------------------------------------------------------------------------
# GET /api/v1/modules/{name}/download  — used by agent
# ---------------------------------------------------------------------------


@router.get("/{name}/download")
async def download_module(name: str) -> dict:
    """
    Download module source code (HMAC signed).
    Used by agents to fetch plugins at runtime. No JWT required — agents
    authenticate via X-API-Key header (resolved by middleware) or are
    allowed through for module fetching.
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

    if body.code is not None or body.version is not None or any(
        v is not None for v in [
            body.description, body.actions, body.params_schema,
            body.category, body.mitre_techniques, body.tags,
            body.inputs, body.outputs, body.expected_duration,
        ]
    ):
        manager.register(
            name=mod.name,
            version=body.version or mod.version,
            code=body.code or mod.code,
            description=body.description if body.description is not None else mod.description or "",
            author=mod.author or "",
            dependencies=mod.dependencies_list,
            os_compat=mod.os_compat_list,
            actions=body.actions if body.actions is not None else mod.actions_list,
            params_schema=body.params_schema if body.params_schema is not None else mod.params_schema_dict,
            category=body.category if body.category is not None else mod.category,
            mitre_techniques=body.mitre_techniques if body.mitre_techniques is not None else mod.mitre_list,
            tags=body.tags if body.tags is not None else mod.tags_list,
            inputs=body.inputs if body.inputs is not None else mod.inputs_list,
            outputs=body.outputs if body.outputs is not None else mod.outputs_list,
            expected_duration=body.expected_duration if body.expected_duration is not None else mod.expected_duration,
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
