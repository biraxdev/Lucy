"""
Redirectors API — manage C2 redirector configurations.

Endpoints:
  GET    /                   — list redirectors
  POST   /                   — add a redirector (operator+)
  DELETE /{redirector_id}    — remove a redirector (operator+)
  POST   /{redirector_id}/test — test connectivity to the redirector
  GET    /config/nginx       — generate nginx config for a redirector
  GET    /config/apache      — generate Apache config for a redirector
"""
import json
import socket
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database import database
from db.models import Redirector
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/redirectors", tags=["redirectors"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RedirectorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    frontend_domain: str = Field(..., min_length=1, max_length=256)
    backend_host: str = Field(..., min_length=1, max_length=256)
    backend_port: int = Field(8000, ge=1, le=65535)
    ssl_enabled: bool = True
    domain_front_host: str = ""
    cdn_provider: str = ""
    listen_port: int = Field(443, ge=1, le=65535)
    extra_config: dict = {}


class RedirectorUpdate(BaseModel):
    name: str | None = None
    frontend_domain: str | None = None
    backend_host: str | None = None
    backend_port: int | None = None
    ssl_enabled: bool | None = None
    domain_front_host: str | None = None
    cdn_provider: str | None = None
    listen_port: int | None = None
    extra_config: dict | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# Routes — config generation endpoints must be before /{redirector_id}
# ---------------------------------------------------------------------------


def _get_redirector_or_404(redirector_id: str) -> Redirector:
    r = Redirector.get_or_none(Redirector.id == redirector_id)
    if not r:
        raise HTTPException(404, "Redirector not found")
    return r


@router.get("/config/nginx")
async def generate_nginx_config(
    current_user: CurrentUser,
    redirector_id: str = Query(..., description="Redirector ID to generate config for"),
) -> dict:
    """Generate an nginx reverse-proxy config for the specified redirector."""
    with database:
        r = _get_redirector_or_404(redirector_id)
        return {"redirector_id": str(r.id), "config": _build_nginx_config(r)}


@router.get("/config/apache")
async def generate_apache_config(
    current_user: CurrentUser,
    redirector_id: str = Query(..., description="Redirector ID to generate config for"),
) -> dict:
    """Generate an Apache reverse-proxy config for the specified redirector."""
    with database:
        r = _get_redirector_or_404(redirector_id)
        return {"redirector_id": str(r.id), "config": _build_apache_config(r)}


@router.get("")
async def list_redirectors(current_user: CurrentUser) -> list[dict]:
    """List all redirectors."""
    with database:
        return [r.to_dict() for r in Redirector.select().order_by(Redirector.created_at)]


@router.post("", status_code=201)
async def create_redirector(body: RedirectorCreate, current_user: OperatorUser) -> dict:
    """Add a new redirector configuration."""
    with database:
        r = Redirector.create(
            name=body.name,
            frontend_domain=body.frontend_domain,
            backend_host=body.backend_host,
            backend_port=body.backend_port,
            ssl_enabled=body.ssl_enabled,
            domain_front_host=body.domain_front_host,
            cdn_provider=body.cdn_provider,
            listen_port=body.listen_port,
            extra_config=json.dumps(body.extra_config) if body.extra_config else None,
        )
    return r.to_dict()


@router.delete("/{redirector_id}", status_code=204)
async def delete_redirector(redirector_id: str, current_user: OperatorUser) -> None:
    """Remove a redirector."""
    with database:
        r = _get_redirector_or_404(redirector_id)
        r.delete_instance()


@router.put("/{redirector_id}")
async def update_redirector(
    redirector_id: str, body: RedirectorUpdate, current_user: OperatorUser
) -> dict:
    """Update a redirector configuration."""
    with database:
        r = _get_redirector_or_404(redirector_id)
        updates = body.model_dump(exclude_none=True)
        if "extra_config" in updates:
            updates["extra_config"] = json.dumps(updates["extra_config"])
        for k, v in updates.items():
            setattr(r, k, v)
        r.save()
    return r.to_dict()


@router.post("/{redirector_id}/test")
async def test_redirector(redirector_id: str, current_user: CurrentUser) -> dict:
    """Test connectivity to the redirector's frontend domain and backend host."""
    with database:
        r = _get_redirector_or_404(redirector_id)

    results: dict = {
        "redirector_id": str(r.id),
        "name": r.name,
        "frontend_reachable": False,
        "backend_reachable": False,
        "frontend_ip": None,
        "backend_latency_ms": None,
        "error": None,
    }

    # Test frontend DNS resolution
    try:
        ip = socket.gethostbyname(r.frontend_domain)
        results["frontend_ip"] = ip
        results["frontend_reachable"] = True
    except socket.gaierror as exc:
        results["error"] = f"Frontend DNS resolution failed: {exc}"

    # Test backend TCP connectivity
    try:
        import time as _time

        start = _time.monotonic()
        sock = socket.create_connection((r.backend_host, r.backend_port), timeout=10)
        elapsed = (_time.monotonic() - start) * 1000
        sock.close()
        results["backend_reachable"] = True
        results["backend_latency_ms"] = round(elapsed, 2)
    except Exception as exc:
        err = results.get("error") or ""
        results["error"] = f"{err}; Backend connection failed: {exc}".strip("; ")

    return results


# ---------------------------------------------------------------------------
# Config generators
# ---------------------------------------------------------------------------


def _build_nginx_config(r: Redirector) -> str:
    """Generate an nginx server block for the redirector."""
    lines: list[str] = []
    lines.append(f"# Redirector: {r.name}")
    lines.append(f"# Frontend: {r.frontend_domain} -> {r.backend_host}:{r.backend_port}")
    lines.append("")

    if r.ssl_enabled:
        lines.append("server {")
        lines.append(f"    listen {r.listen_port} ssl http2;")
        lines.append(f"    server_name {r.frontend_domain};")
        lines.append("")
        lines.append(f"    ssl_certificate     /etc/nginx/ssl/{r.frontend_domain}.crt;")
        lines.append(f"    ssl_certificate_key /etc/nginx/ssl/{r.frontend_domain}.key;")
        lines.append("    ssl_protocols       TLSv1.2 TLSv1.3;")
        lines.append("    ssl_ciphers         HIGH:!aNULL:!MD5;")
        lines.append("")
    else:
        lines.append("server {")
        lines.append(f"    listen {r.listen_port};")
        lines.append(f"    server_name {r.frontend_domain};")
        lines.append("")

    # Domain fronting host header override
    if r.domain_front_host:
        lines.append(f"    # Domain fronting: override Host header to {r.domain_front_host}")
        lines.append(f"    proxy_set_header Host {r.domain_front_host};")
        lines.append("")

    # CDN provider specific headers
    if r.cdn_provider:
        lines.append(f"    # CDN provider: {r.cdn_provider}")
        lines.append('    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;')
        lines.append('    proxy_set_header X-Real-IP $remote_addr;')
        lines.append("")

    backend_scheme = "https" if r.ssl_enabled else "http"
    lines.append("    location / {")
    lines.append(f"        proxy_pass {backend_scheme}://{r.backend_host}:{r.backend_port};")
    lines.append("        proxy_set_header Host $host;")
    lines.append("        proxy_set_header X-Forwarded-Proto $scheme;")
    lines.append("        proxy_read_timeout 300s;")
    lines.append("        proxy_connect_timeout 10s;")
    lines.append("    }")
    lines.append("")

    # Extra config directives
    extra = r.extra_config_dict
    if extra:
        lines.append("    # Extra configuration")
        for key, value in extra.items():
            lines.append(f"    {key} {value};")
        lines.append("")

    lines.append("}")
    return "\n".join(lines)


def _build_apache_config(r: Redirector) -> str:
    """Generate an Apache VirtualHost config for the redirector."""
    lines: list[str] = []
    lines.append(f"# Redirector: {r.name}")
    lines.append(f"# Frontend: {r.frontend_domain} -> {r.backend_host}:{r.backend_port}")
    lines.append("")

    if r.ssl_enabled:
        lines.append(f"<VirtualHost *:{r.listen_port}>")
        lines.append(f"    ServerName {r.frontend_domain}")
        lines.append("")
        lines.append("    SSLEngine on")
        lines.append(f"    SSLCertificateFile      /etc/ssl/certs/{r.frontend_domain}.crt")
        lines.append(f"    SSLCertificateKeyFile   /etc/ssl/private/{r.frontend_domain}.key")
        lines.append("    SSLProtocol             all -SSLv3 -TLSv1 -TLSv1.1")
        lines.append("")
    else:
        lines.append(f"<VirtualHost *:{r.listen_port}>")
        lines.append(f"    ServerName {r.frontend_domain}")
        lines.append("")

    # Proxy directives
    backend_scheme = "https" if r.ssl_enabled else "http"
    backend_url = f"{backend_scheme}://{r.backend_host}:{r.backend_port}"
    lines.append("    ProxyRequests Off")
    lines.append("    ProxyPreserveHost On")
    lines.append(f"    ProxyPass / {backend_url}/")
    lines.append(f"    ProxyPassReverse / {backend_url}/")
    lines.append("")

    # Domain fronting
    if r.domain_front_host:
        lines.append(f"    # Domain fronting: {r.domain_front_host}")
        lines.append(f'    RequestHeader set Host "{r.domain_front_host}"')
        lines.append("")

    # CDN headers
    if r.cdn_provider:
        lines.append(f"    # CDN provider: {r.cdn_provider}")
        lines.append('    RequestHeader set X-Forwarded-Proto "https"')
        lines.append("")

    # Extra config
    extra = r.extra_config_dict
    if extra:
        lines.append("    # Extra configuration")
        for key, value in extra.items():
            lines.append(f"    {key} {value}")
        lines.append("")

    lines.append("    ErrorLog ${APACHE_LOG_DIR}/redirector_error.log")
    lines.append("    CustomLog ${APACHE_LOG_DIR}/redirector_access.log combined")
    lines.append("</VirtualHost>")
    return "\n".join(lines)
