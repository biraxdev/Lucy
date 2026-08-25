import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from core.auth import decode_access_token

logger = logging.getLogger(__name__)

UNPROTECTED_PATHS = {
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/mfa/login",
    "/api/v1/auth/refresh",
    "/api/v1/setup/status",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def is_public_path(path: str) -> bool:
    """Return True for health, docs, auth, WebSocket and frontend static routes."""
    if path in UNPROTECTED_PATHS:
        return True
    if path.startswith("/ws"):
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
