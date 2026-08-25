# Lucy — Security Model

## Authentication

Lucy supports two credential mechanisms:

- **JWT access tokens** — Issued on successful login at `/api/v1/auth/login` and validated on every protected route by `JWTAuthMiddleware` (`backend/middleware.py`). Access tokens are short-lived (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`); refresh tokens are stored in `JWT_REFRESH_SECRET`.
- **API keys** — Used by agents and service accounts. The middleware accepts an `X-API-Key` header and maps it to a service identity.

Public paths such as `/health`, login, registration, setup status, agent registration, docs, and module downloads are excluded from JWT validation.

## Authorization and RBAC

`RBACMiddleware` enforces role-based access control. Each authenticated request carries a user object in `request.state.user` with associated scopes. Endpoints declare required roles or permissions through FastAPI dependencies. Unauthorized requests are rejected before they reach the route handler.

## Encrypted Communications

Agent-to-server traffic is protected with an ECDH key exchange plus AES encryption:

- **Key exchange** — Ephemeral ECDH keys are negotiated per session to derive a shared secret.
- **Payload encryption** — Task instructions, results, and heartbeat metadata are AES-encrypted using the derived key before transit.
- **Transport security** — HTTPS/WSS is enforced in production. The agent can be configured to verify server certificates (`verify_ssl=true`); certificate validation is disabled only for controlled lab deployments.

## Rate Limiting

Rate limiting is implemented with SlowAPI (`backend/dependencies.py`) and mounted as `SlowAPIMiddleware` in `backend/main.py`:

- `RATE_LIMIT_PER_IP` — 100 requests/minute per IP.
- `RATE_LIMIT_PER_APIKEY` — 1,000 requests/minute per API key.
- `RATE_LIMIT_AUTH` — 10 requests/minute on authentication endpoints to slow credential-stuffing attempts.

Exceeding a limit returns `429 Too Many Requests`.

## Input Sanitization and Validation

- **Pydantic models** — All request bodies and query parameters are validated through Pydantic schemas in the API layer.
- **SQL injection prevention** — The Peewee ORM uses parameterized queries. Raw SQL is avoided.
- **Output encoding** — Library metadata and user-provided strings are rendered through the frontend without being interpreted as executable code.
- **File uploads** — Module and pack uploads are size-limited, type-checked, and scanned before registration in the library.

## CORS

CORS is configured in `backend/config.py` and applied through `CORSMiddleware` in `backend/main.py`. Only explicitly listed origins (`CORS_ORIGINS`) are allowed, and credentials are permitted only when required. In production, the allowed origins should match the deployed frontend URL exactly.

## Secret Validation

`backend/config.py` runs `validate_secrets()` at startup to confirm that security-critical values are not defaults or placeholders. It checks `JWT_SECRET`, `JWT_REFRESH_SECRET`, `MASTER_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` against a blocklist (`admin`, `changeme`, `password`, `CHANGE_ME_*`, etc.) and an empty string. The application refuses to start if insecure values are detected.

Generate strong secrets before deployment:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## Agent Module HMAC Verification

Modules published to the library are signed with an HMAC. When an agent downloads a module from `/api/v1/modules/{module_id}/download`, the server attaches a signature. The agent verifies the HMAC before loading the module to ensure integrity and provenance. Tampered or unsigned modules are rejected.

## Operational Security Notes

- Never commit the active `.env` file or generated JWT secrets.
- Rotate `JWT_SECRET` and `JWT_REFRESH_SECRET` on a regular schedule.
- Run the backend and agent on separate, restricted networks during lab testing.
- Review `CORS_ORIGINS` and `ALLOWED_HOSTS` before every production deployment.
