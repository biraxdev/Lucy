import base64
import json

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from core.credential_manager import CredentialManager
from core.tag_manager import TagManager
from database import database
from db.models import Credential
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/credentials", tags=["credentials"])
cm = CredentialManager()
tag_manager = TagManager()


class IngestPayload(BaseModel):
    agent_id: str
    source: str
    credentials: list[dict]


class TagOperationRequest(BaseModel):
    tags: list[str]


class MetadataOperationRequest(BaseModel):
    metadata: dict


class BulkTagRequest(BaseModel):
    ids: list[str]
    tags: list[str]


class BulkMetadataRequest(BaseModel):
    ids: list[str]
    metadata: dict
    merge: bool = True


@router.post("/ingest", status_code=201)
async def ingest(body: IngestPayload, current_user: OperatorUser) -> dict:
    return cm.ingest(body.agent_id, body.source, body.credentials)


@router.get("")
async def search_credentials(
    current_user: CurrentUser,
    q: str = Query(""),
    agent_id: str | None = Query(None),
    source: str | None = Query(None),
    tags: str | None = Query(None),
    metadata: str | None = Query(None),
    min_score: int = Query(0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0),
    match_all_tags: bool = True,
) -> list[dict]:
    results = cm.search(
        query=q,
        agent_id=agent_id,
        source=source,
        tags=tags,
        metadata=metadata,
        min_score=min_score,
        limit=limit,
        offset=offset,
        match_all_tags=match_all_tags,
    )
    return results


@router.get("/export")
async def export_credentials(
    current_user: CurrentUser,
    q: str = Query(""),
    agent_id: str | None = Query(None),
    source: str | None = Query(None),
    tags: str | None = Query(None),
    metadata: str | None = Query(None),
    min_score: int = Query(0),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0),
    match_all_tags: bool = True,
) -> Response:
    """Export matching credentials as a CSV download."""
    import csv
    import io as _io

    results = cm.search(
        query=q,
        agent_id=agent_id,
        source=source,
        tags=tags,
        metadata=metadata,
        min_score=min_score,
        limit=limit,
        offset=offset,
        match_all_tags=match_all_tags,
    )
    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "agent_id", "url", "hostname", "username", "password", "source", "confidence", "tags", "captured_at"])
    for c in results:
        raw = c.get("password_encrypted") or ""
        try:
            password = base64.b64decode(raw).decode("utf-8")
        except Exception:
            password = raw
        writer.writerow([
            c.get("id", ""),
            c.get("agent_id", ""),
            c.get("url") or "",
            c.get("hostname") or "",
            c.get("username", ""),
            password,
            c.get("source", ""),
            c.get("confidence", ""),
            ",".join(c.get("tags") or []),
            c.get("captured_at", ""),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="credentials_export.csv"'},
    )


@router.get("/stats")
async def credential_stats(current_user: CurrentUser) -> dict:
    with database:
        total = Credential.select().count()
        by_source: dict = {}
        for c in Credential.select(Credential.source, Credential.id):
            by_source[c.source] = by_source.get(c.source, 0) + 1
        by_confidence: dict = {}
        for c in Credential.select(Credential.confidence, Credential.id):
            by_confidence[c.confidence] = by_confidence.get(c.confidence, 0) + 1
    return {"total": total, "by_source": by_source, "by_confidence": by_confidence}


@router.delete("/{credential_id}", status_code=204)
async def delete_credential(credential_id: str, current_user: OperatorUser) -> None:
    with database:
        n = Credential.delete().where(Credential.id == credential_id).execute()
    if not n:
        raise HTTPException(404, "Credential not found")


@router.delete("", status_code=204)
async def delete_all_credentials(current_user: OperatorUser) -> None:
    with database:
        Credential.delete().execute()


@router.get("/{credential_id}/reveal")
async def reveal_credential(credential_id: str, current_user: OperatorUser) -> dict:
    cred = Credential.get_or_none(Credential.id == credential_id)
    if not cred:
        raise HTTPException(404, "Credential not found")
    try:
        password = base64.b64decode(cred.password_encrypted).decode("utf-8")
    except Exception:
        password = cred.password_encrypted
    d = cred.to_dict()
    d["password"] = password
    return d


# ---------------------------------------------------------------------------
# POST /api/v1/credentials/bulk/tags  — operator (before /{credential_id}/tags)
# ---------------------------------------------------------------------------


@router.post("/bulk/tags")
async def bulk_update_credential_tags(
    body: BulkTagRequest,
    current_user: OperatorUser,
    mode: str = "add",
) -> dict:
    if mode not in {"add", "set", "remove"}:
        raise HTTPException(status_code=400, detail="mode must be add, set, or remove")
    try:
        if mode == "add":
            return tag_manager.bulk_add_tags("credential", body.ids, body.tags)
        if mode == "set":
            return tag_manager.bulk_set_tags("credential", body.ids, body.tags)
        return tag_manager.bulk_remove_tags("credential", body.ids, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /api/v1/credentials/bulk/metadata  — operator (before /{credential_id}/metadata)
# ---------------------------------------------------------------------------


@router.post("/bulk/metadata")
async def bulk_update_credential_metadata(
    body: BulkMetadataRequest,
    current_user: OperatorUser,
) -> dict:
    try:
        if body.merge:
            return tag_manager.bulk_update_metadata("credential", body.ids, body.metadata)
        return tag_manager.bulk_set_metadata("credential", body.ids, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /api/v1/credentials/{id}/tags  — operator
# ---------------------------------------------------------------------------


@router.post("/{credential_id}/tags")
async def add_credential_tags(
    credential_id: str, body: TagOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.add_tags("credential", credential_id, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{credential_id}/tags")
async def remove_credential_tags(
    credential_id: str, body: TagOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.remove_tags("credential", credential_id, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# PUT/PATCH /api/v1/credentials/{id}/metadata  — operator
# ---------------------------------------------------------------------------


@router.put("/{credential_id}/metadata")
async def set_credential_metadata(
    credential_id: str, body: MetadataOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.set_metadata("credential", credential_id, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{credential_id}/metadata")
async def merge_credential_metadata(
    credential_id: str, body: MetadataOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.update_metadata("credential", credential_id, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /api/v1/credentials/tags  — operator
# ---------------------------------------------------------------------------


@router.get("/tags/unique")
async def list_credential_tags(current_user: CurrentUser) -> list[str]:
    """Return all unique tags across credentials."""
    return tag_manager.get_unique_tags("credential")
