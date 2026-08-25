"""
AI Agent API — Security Engineering Architect endpoints.

Provides operator-controlled access to the Lucy AI Agent for:
- Threat analysis
- Script generation
- Sandbox execution
- Tactical suggestions
- Result analysis
"""
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.ai_agent import agent as ai_agent
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/ai-agent", tags=["ai-agent"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalyzeThreatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Threat scenario or question to analyze")


class GenerateScriptRequest(BaseModel):
    task_description: str = Field(..., min_length=1)
    language: str = "python"


class SandboxExecuteRequest(BaseModel):
    command: str = Field(..., min_length=1)
    timeout: int = 60


class SandboxWriteFileRequest(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class RunScriptRequest(BaseModel):
    script_path: str = Field(..., min_length=1)
    args: str = ""


class SuggestStepsRequest(BaseModel):
    current_state: dict = Field(default_factory=dict)


class AnalyzeResultsRequest(BaseModel):
    task_results: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def ai_agent_status(current_user: CurrentUser) -> dict:
    """Check AI Agent LLM availability and configuration."""
    available = await ai_agent.is_available()
    # Determine sandbox mode
    sandbox_mode = "disabled"
    if ai_agent.sandbox_container:
        try:
            check = subprocess.run(
                ["docker", "inspect", ai_agent.sandbox_container],
                capture_output=True, timeout=3,
            )
            sandbox_mode = "docker" if check.returncode == 0 else "local"
        except Exception:
            sandbox_mode = "local"
    else:
        sandbox_mode = "local"
    return {
        "enabled": ai_agent.enabled,
        "available": available,
        "model": ai_agent.model,
        "url": ai_agent.url,
        "sandbox_container": ai_agent.sandbox_container,
        "sandbox_workspace": ai_agent.sandbox_workspace,
        "sandbox_mode": sandbox_mode,
    }


@router.post("/analyze-threat")
async def analyze_threat(body: AnalyzeThreatRequest, current_user: OperatorUser) -> dict:
    """Analyze a threat scenario using Lucy resources and AI reasoning."""
    result = await ai_agent.analyze_threat(body.query)
    if result.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "message": "AI Agent LLM (Ollama) is not running. Start Ollama and pull a model to enable AI analysis.",
            "url": ai_agent.url,
            "model": ai_agent.model,
            "suggestion": "Run: ollama pull deepseek-coder-v2:lite",
        }
    return result


@router.post("/generate-script")
async def generate_script(body: GenerateScriptRequest, current_user: OperatorUser) -> dict:
    """Generate a modular security script for the sandbox."""
    result = await ai_agent.generate_script(body.task_description, body.language)
    if result.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "message": "AI Agent LLM (Ollama) is not running. Start Ollama and pull a model to enable script generation.",
            "url": ai_agent.url,
            "model": ai_agent.model,
        }
    return result


@router.post("/sandbox/execute")
async def sandbox_execute(body: SandboxExecuteRequest, current_user: OperatorUser) -> dict:
    """Execute a command in the sandbox container."""
    result = await ai_agent.execute_in_sandbox(body.command, body.timeout)
    return result


@router.post("/sandbox/write-file")
async def sandbox_write_file(body: SandboxWriteFileRequest, current_user: OperatorUser) -> dict:
    """Write a file to the sandbox workspace."""
    result = await ai_agent.write_file_to_sandbox(body.path, body.content)
    return result


@router.post("/sandbox/run-script")
async def sandbox_run_script(body: RunScriptRequest, current_user: OperatorUser) -> dict:
    """Run a script in the sandbox and return structured output."""
    result = await ai_agent.run_script(body.script_path, body.args)
    return result


@router.post("/suggest-steps")
async def suggest_steps(body: SuggestStepsRequest, current_user: OperatorUser) -> dict:
    """Suggest next tactical steps based on current Lucy state."""
    if not body.current_state:
        body.current_state = ai_agent.get_context()
    result = await ai_agent.suggest_next_steps(body.current_state)
    if result.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "message": "AI Agent LLM (Ollama) is not running.",
            "url": ai_agent.url,
            "model": ai_agent.model,
        }
    return result


@router.post("/analyze-results")
async def analyze_results(body: AnalyzeResultsRequest, current_user: OperatorUser) -> dict:
    """Analyze task execution results and provide insights."""
    result = await ai_agent.analyze_results(body.task_results)
    if result.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "message": "AI Agent LLM (Ollama) is not running.",
            "url": ai_agent.url,
            "model": ai_agent.model,
        }
    return result


@router.get("/context")
async def get_context(current_user: OperatorUser) -> dict:
    """Get a comprehensive snapshot of Lucy resources for AI context."""
    return ai_agent.get_context()
