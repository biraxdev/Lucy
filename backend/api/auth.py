import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from config import settings
from core.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_api_key,
    verify_password,
)
from core.audit_logger import log_event
from core.totp import generate_code, generate_secret, get_provisioning_uri, verify as verify_totp
from database import database
from db.models import RefreshToken, User
from dependencies import AdminUser, CurrentUser, limiter

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


class ApiKeyResponse(BaseModel):
    api_key: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=1)


class MfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MfaLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=6)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_user_or_401(username: str) -> User:
    user = User.get_or_none(User.username == username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return user


def _store_refresh_token(user_id: str, raw_token: str) -> None:
    token_hash = RefreshToken.hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    with database:
        RefreshToken.create(
            user=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )


def _revoke_refresh_token(raw_token: str) -> None:
    token_hash = RefreshToken.hash_token(raw_token)
    with database:
        RefreshToken.update(revoked=True).where(
            RefreshToken.token_hash == token_hash
        ).execute()


def _validate_refresh_token(raw_token: str) -> RefreshToken:
    token_hash = RefreshToken.hash_token(raw_token)
    record = RefreshToken.get_or_none(RefreshToken.token_hash == token_hash)
    if not record or not record.is_valid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        )
    return record


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def login(body: LoginRequest, request: Request) -> dict:
    """Authenticate with username/password → returns JWT access + refresh tokens."""
    user = _get_user_or_401(body.username)

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # MFA enabled — require TOTP code in a second step
    if user.totp_enabled:
        return {
            "mfa_required": True,
            "user_id": str(user.id),
            "message": "MFA code required",
        }

    tenant_id = str(user.tenant_id) if user.tenant_id else None
    access_token = create_access_token(str(user.id), user.role, tenant_id=tenant_id)
    refresh_token = create_refresh_token(str(user.id))

    _store_refresh_token(str(user.id), refresh_token)

    with database:
        User.update(last_login=datetime.now(timezone.utc)).where(
            User.id == user.id
        ).execute()

    try:
        log_event(
            action="login",
            actor=user.username,
            resource_type="user",
            resource_id=str(user.id),
            details={"ip": request.client.host if request.client else None},
            tenant=user.tenant,
        )
    except Exception:
        pass

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_dict(),
    }


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/setup
# ---------------------------------------------------------------------------


@router.post("/mfa/setup")
async def mfa_setup(current_user: CurrentUser) -> dict:
    """Generate a TOTP secret and provisioning URI for the current user."""
    user = User.get_or_none(User.id == current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    secret = generate_secret()
    with database:
        User.update(totp_secret=secret).where(User.id == user.id).execute()

    return {
        "secret": secret,
        "provisioning_uri": get_provisioning_uri(secret, user.username),
    }


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/verify
# ---------------------------------------------------------------------------


@router.post("/mfa/verify")
async def mfa_verify(body: MfaVerifyRequest, current_user: CurrentUser) -> dict:
    """Verify a TOTP code and enable MFA for the current user."""
    user = User.get_or_none(User.id == current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="MFA setup not started")

    if not verify_totp(user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")

    with database:
        User.update(totp_enabled=True).where(User.id == user.id).execute()

    return {"ok": True, "message": "MFA enabled"}


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/login
# ---------------------------------------------------------------------------


@router.post("/mfa/login")
async def mfa_login(body: MfaLoginRequest, request: Request) -> dict:
    """Complete login with username, password and TOTP code."""
    user = _get_user_or_401(body.username)

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA not enabled for this user",
        )

    if not verify_totp(user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )

    tenant_id = str(user.tenant_id) if user.tenant_id else None
    access_token = create_access_token(str(user.id), user.role, tenant_id=tenant_id)
    refresh_token = create_refresh_token(str(user.id))

    _store_refresh_token(str(user.id), refresh_token)

    with database:
        User.update(last_login=datetime.now(timezone.utc)).where(
            User.id == user.id
        ).execute()

    try:
        log_event(
            action="login_mfa",
            actor=user.username,
            resource_type="user",
            resource_id=str(user.id),
            details={"ip": request.client.host if request.client else None},
            tenant=user.tenant,
        )
    except Exception:
        pass

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_dict(),
    }


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(body: RefreshRequest, request: Request) -> TokenResponse:
    """Exchange a valid refresh token for a new access token (rotation)."""
    try:
        payload = decode_refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    record = _validate_refresh_token(body.refresh_token)

    user_id = payload["sub"]
    user = User.get_or_none(User.id == user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    _revoke_refresh_token(body.refresh_token)

    tenant_id = str(user.tenant_id) if user.tenant_id else None
    new_access = create_access_token(str(user.id), user.role, tenant_id=tenant_id)

    return TokenResponse(access_token=new_access)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


@router.get("/me")
async def me(current_user: CurrentUser) -> dict:
    """Return current authenticated user info."""
    user = User.get_or_none(User.id == current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user.to_dict()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, current_user: CurrentUser) -> None:
    """Revoke the provided refresh token."""
    _revoke_refresh_token(body.refresh_token)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/rotate-key  (API key rotation)
# ---------------------------------------------------------------------------


@router.post("/rotate-key", response_model=ApiKeyResponse)
async def rotate_api_key(current_user: CurrentUser) -> ApiKeyResponse:
    """Generate a new API key for the current user, invalidating the old one."""
    new_key = generate_api_key()
    with database:
        User.update(api_key=new_key).where(User.id == current_user["id"]).execute()
    return ApiKeyResponse(api_key=new_key)


@router.get("/api-key", response_model=ApiKeyResponse)
async def get_api_key(current_user: CurrentUser) -> ApiKeyResponse:
    """Return the current operator API key without rotating it."""
    user = User.get_or_none(User.id == current_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return ApiKeyResponse(api_key=user.api_key)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/change-password
# ---------------------------------------------------------------------------


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
) -> None:
    """Change password for the current user."""
    from core.auth import hash_password

    user = User.get_or_none(User.id == current_user["id"])
    if not user or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    with database:
        User.update(password_hash=hash_password(body.new_password)).where(
            User.id == current_user["id"]
        ).execute()


class ChangeUsernameRequest(BaseModel):
    password: str
    new_username: str = Field(..., min_length=1, max_length=64)


@router.post("/change-username", status_code=status.HTTP_204_NO_CONTENT)
async def change_username(
    body: ChangeUsernameRequest,
    current_user: CurrentUser,
) -> None:
    """Change username for the current user."""
    user = User.get_or_none(User.id == current_user["id"])
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect",
        )
    if User.get_or_none(User.username == body.new_username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    with database:
        User.update(username=body.new_username).where(
            User.id == current_user["id"]
        ).execute()


# ---------------------------------------------------------------------------
# GET /api/v1/auth/users  (admin only)
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(admin: AdminUser) -> list[dict]:
    """List all operator accounts (admin only)."""
    return [u.to_dict() for u in User.select()]


# ---------------------------------------------------------------------------
# POST /api/v1/auth/users  (admin only)
# ---------------------------------------------------------------------------


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8)
    role: str = Field(default="operator", pattern="^(admin|operator|viewer)$")


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest, admin: AdminUser) -> dict:
    """Create a new operator account (admin only)."""
    from core.auth import hash_password

    if User.get_or_none(User.username == body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    with database:
        user = User.create(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
            api_key=generate_api_key(),
        )
    return user.to_dict()


# ---------------------------------------------------------------------------
# DELETE /api/v1/auth/users/{user_id}  (admin only)
# ---------------------------------------------------------------------------


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, admin: AdminUser) -> None:
    """Delete an operator account (admin only)."""
    if str(admin["id"]) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    deleted = User.delete().where(User.id == user_id).execute()
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
