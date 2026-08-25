from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from middleware import is_public_path


def get_current_user(request: Request) -> dict:
    """Inject the authenticated user from request state (set by JWTAuthMiddleware)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _has_role(user: dict, *roles: str) -> bool:
    """Role check. ``superadmin`` is always authorized."""
    role = user.get("role", "viewer")
    if role == "superadmin":
        return True
    return role in roles


def require_role(*roles: str):
    """Role-based access control dependency factory."""

    def _check(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if not _has_role(user, *roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {list(roles)}, got: {user['role']}",
            )
        return user

    return _check


def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if not _has_role(user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_operator(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if not _has_role(user, "admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or Admin access required",
        )
    return user


def require_superadmin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if not _has_role(user, "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return user


def get_tenant_id(request: Request) -> str | None:
    """
    Returns the effective tenant_id for this request.
    - Superadmins can pass ?tenant_id=xxx or X-Tenant-ID header to scope queries.
    - Regular users always use their own tenant_id from the JWT.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    if user.get("role") == "superadmin":
        # Allow explicit scoping via header or query param
        tid = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
        return tid or None
    return user.get("tenant_id")


def rbac_guard(request: Request) -> None:
    """
    Default-deny RBAC gate.

    - Public paths are explicitly allowed.
    - All other routes require an authenticated user.
    - If the endpoint has ``__required_roles__`` metadata, those roles are enforced.
    """
    if is_public_path(request.url.path):
        return

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    endpoint = request.scope.get("endpoint") if request.scope else None
    required = getattr(endpoint, "__required_roles__", None)
    if required and not _has_role(user, *required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role: {required}",
        )


CurrentUser = Annotated[dict, Depends(get_current_user)]
AdminUser = Annotated[dict, Depends(require_admin)]
OperatorUser = Annotated[dict, Depends(require_operator)]
SuperAdminUser = Annotated[dict, Depends(require_superadmin)]
TenantId = Annotated[str | None, Depends(get_tenant_id)]

# Rate limiter: 100/minute by IP for all endpoints unless overridden
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
