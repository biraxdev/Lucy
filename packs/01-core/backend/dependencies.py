from typing import Annotated

from fastapi import Depends, HTTPException, Request, status


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


def require_role(*roles: str):
    """Role-based access control dependency factory."""

    def _check(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {list(roles)}, got: {user['role']}",
            )
        return user

    return _check


def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_operator(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user["role"] not in ("admin", "operator", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or Admin access required",
        )
    return user


def require_superadmin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user["role"] != "superadmin":
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


CurrentUser = Annotated[dict, Depends(get_current_user)]
AdminUser = Annotated[dict, Depends(require_admin)]
OperatorUser = Annotated[dict, Depends(require_operator)]
SuperAdminUser = Annotated[dict, Depends(require_superadmin)]
TenantId = Annotated[str | None, Depends(get_tenant_id)]
