import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from core.auth import decode_access_token

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {
    # --- Public endpoints (login, register, health, metrics) ---
    "/health",
    "/metrics",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/mfa/login",
    "/api/v1/auth/refresh",
    "/api/v1/setup/status",
    "/api/v1/agents/register",
    # --- Docs / OpenAPI ---
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Legacy alias for any code still referencing the old name
UNPROTECTED_PATHS = PUBLIC_PATHS


def is_public_path(path: str) -> bool:
    """Return True for health, docs, auth, WebSocket, agent self-service and frontend static routes."""
    if path in UNPROTECTED_PATHS:
        return True
    if path.startswith("/ws"):
        return True
    # Agent self-service endpoints (heartbeat, result submission, module download)
    # These use agent_id-based auth or API key, not JWT.
    if path.startswith("/api/v1/agents/") and path.endswith("/heartbeat"):
        return True
    if path.startswith("/api/v1/tasks/") and path.endswith("/result"):
        return True
    # Module download — agents fetch plugins at runtime without JWT
    if path.startswith("/api/v1/modules/") and path.endswith("/download"):
        return True
    if path.startswith("/api/") or path == "/graphql":
        return False
    # Non-API routes are served by the frontend in portable mode and don't require auth.
    return True


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured request/response logging with request ID injection."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "%s %s %s | %dms | req_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and latency for Prometheus."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            status = 500
            raise exc
        else:
            return response
        finally:
            duration = time.perf_counter() - start
            from core.metrics import observe_request

            observe_request(request.method, request.url.path, status, duration)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Extracts Bearer token or API key, injects request.state.user."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if is_public_path(path):
            return await call_next(request)

        user = None

        api_key = request.headers.get("X-API-Key")
        if api_key:
            user = await self._resolve_api_key(api_key)

        if user is None:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    payload = decode_access_token(token)
                    user = {
                        "id": payload["sub"],
                        "role": payload.get("role", "viewer"),
                        "scope": payload.get("scope", "full"),
                        "auth_method": "jwt",
                    }
                except ValueError:
                    pass

        if user is None and not self._is_public(path):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        request.state.user = user
        return await call_next(request)

    @staticmethod
    async def _resolve_api_key(api_key: str) -> dict | None:
        try:
            from db.models import User

            user = User.get_or_none(User.api_key == api_key)
            if user:
                return {
                    "id": str(user.id),
                    "role": user.role,
                    "scope": "full",
                    "auth_method": "api_key",
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _is_public(path: str) -> bool:
        return is_public_path(path)


class RBACMiddleware(BaseHTTPMiddleware):
    """Default-deny role enforcement.

    Runs after JWTAuthMiddleware. Public paths are allowed. For protected
    paths, the endpoint may declare ``__required_roles__`` as a list of
    allowed roles. If omitted, the route is treated as authenticated-only
    (any role). ``superadmin`` implicitly passes any role check.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if is_public_path(request.url.path):
            return await call_next(request)

        user = getattr(request.state, "user", None)
        if not user:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        endpoint = request.scope.get("endpoint") if request.scope else None
        required = getattr(endpoint, "__required_roles__", None)
        if required:
            role = user.get("role", "viewer")
            if role == "superadmin" or role in required:
                return await call_next(request)
            return JSONResponse(
                status_code=403,
                content={"detail": f"Required role: {required}, got: {role}"},
            )

        return await call_next(request)
