"""
Strategy / operational data API for Project Lucy.

Exposes tactics, techniques, campaigns, playbooks and agent notes.
These resources can be used by the chat engine and the operator UI to
plan, track, and report on an engagement without exposing raw IDs.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from peewee import DoesNotExist

from database import database
from db.models import (
    Agent,
    AgentNote,
    Campaign,
    Playbook,
    Tactic,
    Technique,
    User,
    _json_dumps,
)
from dependencies import CurrentUser, OperatorUser, TenantId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategy", tags=["strategy"])


class TacticCreate(BaseModel):
    mitre_id: str | None = None
    name: str
    phase: str | None = None
    description: str | None = None


class TacticUpdate(BaseModel):
    mitre_id: str | None = None
    name: str | None = None
    phase: str | None = None
    description: str | None = None


class TechniqueCreate(BaseModel):
    mitre_id: str | None = None
    name: str
    tactic_id: str | None = None
    description: str | None = None
    platform: str | None = None
    data_sources: list[str] | None = None


class TechniqueUpdate(BaseModel):
    mitre_id: str | None = None
    name: str | None = None
    tactic_id: str | None = None
    description: str | None = None
    platform: str | None = None
    data_sources: list[str] | None = None


class CampaignCreate(BaseModel):
    name: str
    description: str | None = None
    objective: str | None = None
    status: str = "active"
    start_date: str | None = None
    end_date: str | None = None
    metadata: dict[str, Any] | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    objective: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    metadata: dict[str, Any] | None = None


class PlaybookCreate(BaseModel):
    name: str
    description: str | None = None
    technique_ids: list[str] | None = None
    steps: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


class PlaybookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    technique_ids: list[str] | None = None
    steps: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


class AgentNoteCreate(BaseModel):
    agent_id: str
    content: str
    category: str = "observation"


def _tenant_filter(query, tenant_id, model):
    if tenant_id:
        return query.where(model.tenant == tenant_id)
    return query


# ---------------------------------------------------------------------------
# Tactics
# ---------------------------------------------------------------------------

@router.get("/tactics")
async def list_tactics(
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> list[dict[str, Any]]:
    with database:
        q = _tenant_filter(Tactic.select(), tenant_id, Tactic)
        return [t.to_dict() for t in q.order_by(Tactic.name)]


@router.post("/tactics")
async def create_tactic(
    body: TacticCreate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        tactic = Tactic.create(
            tenant=tenant_id,
            mitre_id=body.mitre_id,
            name=body.name,
            phase=body.phase,
            description=body.description,
        )
        return tactic.to_dict()


@router.get("/tactics/{tactic_id}")
async def get_tactic(
    tactic_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            tactic = _tenant_filter(Tactic.select(), tenant_id, Tactic).where(Tactic.id == tactic_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Tactic not found")
        return tactic.to_dict()


@router.put("/tactics/{tactic_id}")
async def update_tactic(
    tactic_id: str,
    body: TacticUpdate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            tactic = _tenant_filter(Tactic.select(), tenant_id, Tactic).where(Tactic.id == tactic_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Tactic not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(tactic, field, value)
        tactic.save()
        return tactic.to_dict()


@router.delete("/tactics/{tactic_id}")
async def delete_tactic(
    tactic_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, str]:
    with database:
        count = _tenant_filter(Tactic.delete(), tenant_id, Tactic).where(Tactic.id == tactic_id).execute()
        if not count:
            raise HTTPException(404, "Tactic not found")
        return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Techniques
# ---------------------------------------------------------------------------

@router.get("/techniques")
async def list_techniques(
    current_user: CurrentUser,
    tenant_id: TenantId,
    tactic_id: str | None = None,
) -> list[dict[str, Any]]:
    with database:
        q = _tenant_filter(Technique.select(), tenant_id, Technique)
        if tactic_id:
            q = q.where(Technique.tactic == tactic_id)
        return [t.to_dict() for t in q.order_by(Technique.name)]


@router.post("/techniques")
async def create_technique(
    body: TechniqueCreate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        technique = Technique.create(
            tenant=tenant_id,
            mitre_id=body.mitre_id,
            name=body.name,
            tactic=body.tactic_id,
            description=body.description,
            platform=body.platform,
            data_sources=_json_dumps(body.data_sources) if body.data_sources else None,
        )
        return technique.to_dict()


@router.get("/techniques/{technique_id}")
async def get_technique(
    technique_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            technique = _tenant_filter(Technique.select(), tenant_id, Technique).where(Technique.id == technique_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Technique not found")
        return technique.to_dict()


@router.put("/techniques/{technique_id}")
async def update_technique(
    technique_id: str,
    body: TechniqueUpdate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            technique = _tenant_filter(Technique.select(), tenant_id, Technique).where(Technique.id == technique_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Technique not found")
        data = body.model_dump(exclude_unset=True)
        if "data_sources" in data and data["data_sources"] is not None:
            data["data_sources"] = _json_dumps(data["data_sources"])
        for field, value in data.items():
            setattr(technique, field, value)
        technique.save()
        return technique.to_dict()


@router.delete("/techniques/{technique_id}")
async def delete_technique(
    technique_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, str]:
    with database:
        count = _tenant_filter(Technique.delete(), tenant_id, Technique).where(Technique.id == technique_id).execute()
        if not count:
            raise HTTPException(404, "Technique not found")
        return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@router.get("/campaigns")
async def list_campaigns(
    current_user: CurrentUser,
    tenant_id: TenantId,
    status: str | None = None,
) -> list[dict[str, Any]]:
    with database:
        q = _tenant_filter(Campaign.select(), tenant_id, Campaign)
        if status:
            q = q.where(Campaign.status == status)
        return [c.to_dict() for c in q.order_by(Campaign.created_at.desc())]


@router.post("/campaigns")
async def create_campaign(
    body: CampaignCreate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        campaign = Campaign.create(
            tenant=tenant_id,
            name=body.name,
            description=body.description,
            objective=body.objective,
            status=body.status,
            start_date=body.start_date,
            end_date=body.end_date,
            metadata=_json_dumps(body.metadata) if body.metadata else None,
        )
        return campaign.to_dict()


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            campaign = _tenant_filter(Campaign.select(), tenant_id, Campaign).where(Campaign.id == campaign_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Campaign not found")
        return campaign.to_dict()


@router.put("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            campaign = _tenant_filter(Campaign.select(), tenant_id, Campaign).where(Campaign.id == campaign_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Campaign not found")
        data = body.model_dump(exclude_unset=True)
        if "metadata" in data and data["metadata"] is not None:
            data["metadata"] = _json_dumps(data["metadata"])
        for field, value in data.items():
            setattr(campaign, field, value)
        campaign.save()
        return campaign.to_dict()


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, str]:
    with database:
        count = _tenant_filter(Campaign.delete(), tenant_id, Campaign).where(Campaign.id == campaign_id).execute()
        if not count:
            raise HTTPException(404, "Campaign not found")
        return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------

@router.get("/playbooks")
async def list_playbooks(
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> list[dict[str, Any]]:
    with database:
        q = _tenant_filter(Playbook.select(), tenant_id, Playbook)
        return [p.to_dict() for p in q.order_by(Playbook.name)]


@router.post("/playbooks")
async def create_playbook(
    body: PlaybookCreate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        pb = Playbook.create(
            tenant=tenant_id,
            name=body.name,
            description=body.description,
            technique_ids=_json_dumps(body.technique_ids) if body.technique_ids else None,
            steps=_json_dumps(body.steps) if body.steps else None,
            tags=_json_dumps(body.tags) if body.tags else None,
        )
        return pb.to_dict()


@router.get("/playbooks/{playbook_id}")
async def get_playbook(
    playbook_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            pb = _tenant_filter(Playbook.select(), tenant_id, Playbook).where(Playbook.id == playbook_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Playbook not found")
        return pb.to_dict()


@router.put("/playbooks/{playbook_id}")
async def update_playbook(
    playbook_id: str,
    body: PlaybookUpdate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        try:
            pb = _tenant_filter(Playbook.select(), tenant_id, Playbook).where(Playbook.id == playbook_id).get()
        except DoesNotExist:
            raise HTTPException(404, "Playbook not found")
        data = body.model_dump(exclude_unset=True)
        for list_field in ("technique_ids", "steps", "tags"):
            if list_field in data and data[list_field] is not None:
                data[list_field] = _json_dumps(data[list_field])
        for field, value in data.items():
            setattr(pb, field, value)
        pb.save()
        return pb.to_dict()


@router.delete("/playbooks/{playbook_id}")
async def delete_playbook(
    playbook_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, str]:
    with database:
        count = _tenant_filter(Playbook.delete(), tenant_id, Playbook).where(Playbook.id == playbook_id).execute()
        if not count:
            raise HTTPException(404, "Playbook not found")
        return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Agent notes
# ---------------------------------------------------------------------------

@router.get("/notes")
async def list_agent_notes(
    current_user: CurrentUser,
    tenant_id: TenantId,
    agent_id: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    with database:
        q = _tenant_filter(AgentNote.select(), tenant_id, AgentNote)
        if agent_id:
            q = q.where(AgentNote.agent == agent_id)
        if category:
            q = q.where(AgentNote.category == category)
        return [n.to_dict() for n in q.order_by(AgentNote.created_at.desc())]


@router.post("/notes")
async def create_agent_note(
    body: AgentNoteCreate,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    with database:
        agent = Agent.get_or_none(Agent.id == body.agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        note = AgentNote.create(
            tenant=tenant_id,
            agent=body.agent_id,
            user=current_user.get("id"),
            content=body.content,
            category=body.category,
        )
        return note.to_dict()


@router.delete("/notes/{note_id}")
async def delete_agent_note(
    note_id: str,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict[str, str]:
    with database:
        count = _tenant_filter(AgentNote.delete(), tenant_id, AgentNote).where(AgentNote.id == note_id).execute()
        if not count:
            raise HTTPException(404, "Note not found")
        return {"status": "deleted"}
