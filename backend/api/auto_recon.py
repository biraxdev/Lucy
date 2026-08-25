"""
Auto-recon API for Project Lucy.
POST   /auto-recon/trigger/{agent_id} — trigger recon on an agent
GET    /auto-recon/results/{agent_id} — get recon results for an agent
GET    /auto-recon/results             — get all recent recon results
GET    /auto-recon/analysis/{agent_id} — get the AI analysis of recon results
POST   /auto-recon/auto                — enable auto-recon on new agent connections
GET    /auto-recon/status              — check if auto-recon is enabled
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.auto_recon import AutoReconEngine
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/auto-recon", tags=["auto-recon"])

engine = AutoReconEngine()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AutoToggleBody(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/trigger/{agent_id}")
async def trigger_recon(agent_id: str, current_user: OperatorUser = None) -> dict:
    """Trigger a recon chain on a specific agent."""
    result = await engine.trigger_recon(agent_id)
    return result


@router.get("/results/{agent_id}")
async def get_recon_results(agent_id: str, current_user: CurrentUser = None) -> dict:
    """Get the latest recon results for an agent."""
    results = engine.get_recon_results(agent_id)
    if not results:
        raise HTTPException(404, "No recon results found for this agent")
    return results


@router.get("/results")
async def get_all_results(
    limit: int = 50,
    current_user: CurrentUser = None,
) -> dict:
    """Get all recent recon results across all agents."""
    return {"results": engine.get_all_results(limit=limit)}


@router.get("/analysis/{agent_id}")
async def get_analysis(agent_id: str, current_user: CurrentUser = None) -> dict:
    """Get the AI analysis of recon results for an agent."""
    analysis = engine.get_analysis(agent_id)
    if not analysis:
        raise HTTPException(404, "No recon analysis found for this agent")
    return analysis


@router.post("/auto")
async def toggle_auto_recon(body: AutoToggleBody, current_user: OperatorUser = None) -> dict:
    """Enable or disable auto-recon on new agent connections."""
    engine.set_auto_enabled(body.enabled)
    return {"auto_enabled": body.enabled}


@router.get("/status")
async def get_status(current_user: CurrentUser = None) -> dict:
    """Check if auto-recon is enabled."""
    return {"auto_enabled": engine.is_auto_enabled()}
