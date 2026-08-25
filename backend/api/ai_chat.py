"""
AI Chat Interactive API — Natural language conversation with the AI Architect.

Endpoints:
  POST /ai-chat/message       — Send a message and get AI response (with reflection/clarification/execution)
  POST /ai-chat/stream        — Streaming chat via SSE (token by token)
  POST /ai-chat/execute       — Force execution mode (skip clarification)
  GET  /ai-chat/history       — Get conversation history for session
  POST /ai-chat/clear         — Clear conversation history
  GET  /ai-chat/status        — Get session status (idle, clarifying, executing, done)
  GET  /ai-chat/context       — Get Lucy context summary (agents, tasks, modules)
  POST /ai-chat/web-search    — Search the web
  POST /ai-chat/fetch-url     — Fetch URL content as text
  POST /ai-chat/dispatch-task — Dispatch a task to an agent
  POST /ai-chat/execute-poc   — Import and execute a PoC
  POST /ai-chat/mission       — Execute a multi-step mission with live SSE progress
  GET  /ai-chat/missions      — List available mission definitions
"""
import asyncio
import json
import time
import urllib.request
import urllib.parse
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from core.ai_chat_engine import engine, get_conversation
from core.ai_agent import agent as ai_agent
from core.task_queue import TaskQueue
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/ai-chat", tags=["ai-chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message in natural language")
    session_id: str = Field(default="default", description="Conversation session ID")
    force_execute: bool = Field(default=False, description="Skip clarification, execute immediately")


class ExecuteRequest(BaseModel):
    session_id: str = "default"
    plan_index: int = Field(0, ge=0, description="Index of plan step to execute (or -1 for all)")


class ClearRequest(BaseModel):
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/message")
async def chat_message(body: ChatMessageRequest, current_user: OperatorUser) -> dict:
    """
    Send a natural language message to the AI Architect.

    The AI will:
    1. Reflect on the request
    2. Ask clarifying questions if needed (returns type=clarification)
    3. Build an execution plan
    4. Execute the plan (generate code, create modules, run sandbox, etc.)
    5. Report results

    If force_execute=True, skip clarification and execute immediately.
    """
    try:
        # Check LLM availability first — return graceful unavailable response
        if not await ai_agent.is_available():
            return {
                "type": "chat",
                "status": "unavailable",
                "message": (
                    "Le LLM n'est pas disponible. Démarre Ollama et installe le modèle "
                    f"pour activer le Copilot. Run: ollama pull {settings.AI_AGENT_LLM_MODEL}"
                ),
                "url": ai_agent.url,
                "model": ai_agent.model,
            }

        if body.force_execute:
            # Force execution mode: bypass reflection, build plan directly
            state = get_conversation(body.session_id)
            state.add_message("user", body.message)

            # Fast path: direct module search without waiting for the LLM
            search_report = await engine._search_modules(body.message)
            if search_report:
                state.current_plan = search_report.get("results", [])
                state.plan_status = "done"
                state.add_message("assistant", search_report["message"], search_report)
                return search_report

            reflection = {"needs_clarification": False, "suggested_approach": "Forced execution"}
            plan = await engine._build_plan(state, body.message, reflection)
            state.current_plan = plan
            state.plan_status = "executing"

            results = await engine._execute_plan(state, plan)
            state.plan_status = "done"

            report = await engine._generate_report(state, results)
            state.add_message("assistant", report["message"], report)
            return report

        # Normal interactive flow
        result = await engine.process(body.session_id, body.message)
        return result
    except TimeoutError:
        raise HTTPException(503, "LLM timeout: try again later or check Ollama.")
    except Exception as exc:
        raise HTTPException(500, f"AI processing error: {exc}")


@router.get("/history")
async def chat_history(current_user: CurrentUser, session_id: str = "default") -> dict:
    """Get the full conversation history for a session."""
    state = get_conversation(session_id)
    return {
        "session_id": session_id,
        "status": state.plan_status,
        "messages": state.messages,
        "pending_clarification": state.pending_clarification,
        "current_plan": state.current_plan,
        "created_at": state.created_at.isoformat(),
    }


@router.post("/clear")
async def chat_clear(body: ClearRequest, current_user: OperatorUser) -> dict:
    """Clear conversation history for a session."""
    await engine.clear_session(body.session_id)
    return {"status": "cleared", "session_id": body.session_id}


@router.get("/status")
async def chat_status(current_user: CurrentUser, session_id: str = "default") -> dict:
    """Get current session status."""
    state = get_conversation(session_id)
    return {
        "session_id": session_id,
        "status": state.plan_status,
        "message_count": len(state.messages),
        "pending_clarification": state.pending_clarification is not None,
        "current_plan_steps": len(state.current_plan),
    }


@router.post("/execute")
async def chat_execute(body: ExecuteRequest, current_user: OperatorUser) -> dict:
    """
    Re-execute the current plan or a specific step.
    Useful when the user has provided clarifications and wants to proceed.
    """
    state = get_conversation(body.session_id)
    if not state.current_plan:
        raise HTTPException(400, "No plan to execute. Send a message first.")

    if body.plan_index >= 0:
        plan = [state.current_plan[body.plan_index]] if body.plan_index < len(state.current_plan) else []
    else:
        plan = state.current_plan

    state.plan_status = "executing"
    results = await engine._execute_plan(state, plan)
    state.plan_status = "done"

    report = await engine._generate_report(state, results)
    state.add_message("assistant", report["message"], report)
    return report


# ---------------------------------------------------------------------------
# Copilot endpoints — streaming, context, web, dispatch
# ---------------------------------------------------------------------------

class StreamChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(default="copilot")
    context_page: str | None = Field(default=None, description="Current page for context")


class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)


class FetchUrlRequest(BaseModel):
    url: str = Field(..., min_length=1)


class DispatchTaskRequest(BaseModel):
    agent_id: str
    module: str
    action: str
    params: dict = Field(default_factory=dict)
    priority: str = Field(default="normal")


class ExecutePocRequest(BaseModel):
    poc_id: str
    agent_id: str


def _build_copilot_system_prompt(context_page: str | None = None) -> str:
    """Build a rich system prompt with Lucy context for the copilot."""
    from db.models import Agent, Task, Module, Timeline, PocTemplate
    parts = [settings.AI_AGENT_SYSTEM_PROMPT]

    # Live Lucy context
    try:
        agents = list(Agent.select().limit(20))
        agent_lines = []
        for a in agents:
            agent_lines.append(f"  - {a.hostname} (id={a.id}, os={a.os}, status={a.status}, ip={a.ip_private or '?'})")
        parts.append(f"=== CONNECTED AGENTS ({len(agents)}) ===\n" + "\n".join(agent_lines) if agent_lines else "=== CONNECTED AGENTS ===\n  (none)")
    except Exception:
        parts.append("=== CONNECTED AGENTS ===\n  (error loading)")

    try:
        tasks = list(Task.select().order_by(Task.created_at.desc()).limit(10))
        task_lines = [f"  - {t.module}/{t.action} → {t.status}" for t in tasks]
        parts.append(f"=== RECENT TASKS ({len(tasks)}) ===\n" + "\n".join(task_lines) if task_lines else "=== RECENT TASKS ===\n  (none)")
    except Exception:
        pass

    try:
        modules = list(Module.select().limit(30))
        mod_names = [f"{m.name}({m.category})" for m in modules]
        parts.append(f"=== AVAILABLE MODULES ({Module.select().count()} total) ===\n  " + ", ".join(mod_names))
    except Exception:
        pass

    try:
        poc_count = PocTemplate.select().count()
        parts.append(f"=== POC LIBRARY ===\n  {poc_count} PoC templates available")
    except Exception:
        pass

    if context_page:
        parts.append(f"=== CURRENT PAGE ===\n  User is viewing: {context_page}")

    parts.append(
        "=== YOUR CAPABILITIES ===\n"
        "  - dispatch_task: send a task to an agent (module, action, params)\n"
        "  - search_modules: find modules by name/description\n"
        "  - search_pocs: find PoC templates\n"
        "  - list_agents: list all connected agents\n"
        "  - web_search: search the internet\n"
        "  - create_timeline: create an execution timeline\n"
        "  - generate_code: generate Python/React code\n"
        "  - execute_sandbox: run commands in sandbox\n"
        "  When the user asks to do something on an agent, use dispatch_task.\n"
        "  Respond concisely and in the user's language (French if they speak French)."
    )
    return "\n\n".join(parts)


@router.post("/stream")
async def chat_stream(body: StreamChatRequest, current_user: OperatorUser):
    """Stream a chat response token by token via Server-Sent Events."""
    if not await ai_agent.is_available():
        async def unavailable():
            yield f"data: {json.dumps({'type': 'error', 'message': 'LLM non disponible. Démarre Ollama.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(unavailable(), media_type="text/event-stream")

    state = get_conversation(body.session_id)
    state.add_message("user", body.message)

    system_prompt = _build_copilot_system_prompt(body.context_page)
    messages = [{"role": "system", "content": system_prompt}] + state.to_llm_context()

    # Model routing: use long-context model for lengthy messages or analysis requests
    msg_len = len(body.message)
    needs_long_context = msg_len > 2000 or any(
        kw in body.message.lower() for kw in ["analyse", "analyze", "résume", "resume", "document", "long", "complet", "détaillé", "detailed"]
    )
    selected_model = settings.AI_AGENT_LLM_MODEL_LONG if needs_long_context else settings.AI_AGENT_LLM_MODEL

    async def event_stream():
        full_response = []
        try:
            payload = json.dumps({
                "model": selected_model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.4, "num_predict": 4096},
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{settings.AI_AGENT_LLM_URL}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            # Stream from Ollama — this is synchronous, run in thread
            import asyncio
            import io

            def do_stream():
                resp = urllib.request.urlopen(req, timeout=180)
                buffer = []
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        done = chunk.get("done", False)
                        if content:
                            buffer.append(("token", content))
                        if done:
                            buffer.append(("done", None))
                    except json.JSONDecodeError:
                        continue
                resp.close()
                return buffer

            buffer = await asyncio.to_thread(do_stream)

            for event_type, content in buffer:
                if event_type == "token":
                    full_response.append(content)
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                elif event_type == "done":
                    break

            response_text = "".join(full_response)
            state.add_message("assistant", response_text, {"type": "copilot_stream"})
            yield f"data: {json.dumps({'type': 'done', 'message': response_text})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/context")
async def get_context(current_user: CurrentUser) -> dict:
    """Get a summary of Lucy's current state for the copilot."""
    from db.models import Agent, Task, Module, Timeline, PocTemplate, Credential, Finding
    context = {"agents": [], "recent_tasks": [], "modules": [], "stats": {}}
    try:
        for a in Agent.select().limit(50):
            context["agents"].append({
                "id": str(a.id), "hostname": a.hostname, "os": a.os,
                "status": a.status, "ip": a.ip_private, "username": a.username,
            })
    except Exception:
        pass
    try:
        for t in Task.select().order_by(Task.created_at.desc()).limit(20):
            context["recent_tasks"].append({
                "id": str(t.id), "module": t.module, "action": t.action,
                "status": t.status, "agent_id": str(t.agent_id) if t.agent_id else None,
            })
    except Exception:
        pass
    try:
        for m in Module.select().limit(100):
            context["modules"].append({
                "id": str(m.id), "name": m.name, "category": m.category,
                "description": m.description,
            })
    except Exception:
        pass
    try:
        context["stats"] = {
            "agents": Agent.select().count(),
            "agents_online": Agent.select().where(Agent.status == "online").count(),
            "tasks": Task.select().count(),
            "modules": Module.select().count(),
            "timelines": Timeline.select().count(),
            "pocs": PocTemplate.select().count(),
            "credentials": Credential.select().count(),
            "findings": Finding.select().count(),
        }
    except Exception:
        pass
    return context


@router.post("/web-search")
async def web_search(body: WebSearchRequest, current_user: OperatorUser) -> dict:
    """Search the web using DuckDuckGo Instant Answer API + fallback search links."""
    import re

    def do_search():
        results = []
        query = body.query

        # 1. Try DuckDuckGo Instant Answer API
        try:
            api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # Abstract (main answer)
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["AbstractText"][:200],
                })

            # Related topics
            for topic in (data.get("RelatedTopics") or [])[:body.max_results]:
                if isinstance(topic, dict) and topic.get("FirstURL"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic["FirstURL"],
                        "snippet": topic.get("Text", "")[:150],
                    })
                if len(results) >= body.max_results:
                    break
        except Exception:
            pass

        # 2. If no results from API, build clickable search links
        if not results:
            encoded = urllib.parse.quote(query)
            results = [
                {"title": f"Search DuckDuckGo: {query}", "url": f"https://duckduckgo.com/?q={encoded}", "snippet": "Open in DuckDuckGo"},
                {"title": f"Search Google: {query}", "url": f"https://www.google.com/search?q={encoded}", "snippet": "Open in Google"},
                {"title": f"Search Bing: {query}", "url": f"https://www.bing.com/search?q={encoded}", "snippet": "Open in Bing"},
                {"title": f"MITRE ATT&CK: {query}", "url": f"https://attack.mitre.org/search/?term={encoded}", "snippet": "Search MITRE ATT&CK"},
                {"title": f"Exploit-DB: {query}", "url": f"https://www.exploit-db.com/search?q={encoded}", "snippet": "Search Exploit-DB"},
            ]

        return results[:body.max_results]

    import asyncio
    try:
        results = await asyncio.to_thread(do_search)
        return {"query": body.query, "results": results, "count": len(results)}
    except Exception as exc:
        return {"query": body.query, "results": [], "error": str(exc)}


@router.post("/fetch-url")
async def fetch_url(body: FetchUrlRequest, current_user: OperatorUser) -> dict:
    """Fetch a URL and return its content as text (stripped of HTML)."""
    import re
    def do_fetch():
        req = urllib.request.Request(body.url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "text" in content_type or "html" in content_type or "json" in content_type:
                text = raw.decode("utf-8", errors="replace")
                # Strip HTML tags for text content
                if "<html" in text.lower() or "<body" in text.lower():
                    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                return text[:5000], content_type
            return f"(binary content, {len(raw)} bytes, type={content_type})", content_type

    import asyncio
    try:
        text, ctype = await asyncio.to_thread(do_fetch)
        return {"url": body.url, "content": text, "content_type": ctype, "length": len(text)}
    except Exception as exc:
        return {"url": body.url, "content": "", "error": str(exc)}


@router.post("/dispatch-task")
async def dispatch_task(body: DispatchTaskRequest, current_user: OperatorUser) -> dict:
    """Dispatch a task directly to an agent from the copilot."""
    tq = TaskQueue()
    task = await tq.enqueue(
        agent_id=body.agent_id,
        module=body.module,
        action=body.action,
        params=body.params,
        priority=body.priority,
    )
    return {"task_id": str(task.id), "agent_id": body.agent_id, "module": body.module, "action": body.action, "status": task.status}


@router.post("/execute-poc")
async def execute_poc(body: ExecutePocRequest, current_user: OperatorUser) -> dict:
    """Import a PoC and dispatch its first step against an agent.
    Returns the template info and the first dispatched task."""
    from core.poc_library import get_template_by_puid
    from core.task_queue import TaskQueue
    import json as _json

    tpl = get_template_by_puid(body.poc_id)
    if not tpl:
        raise HTTPException(404, f"PoC {body.poc_id} not found")

    # Parse steps from the JSON field
    try:
        steps = _json.loads(tpl.steps) if tpl.steps else []
    except Exception:
        steps = []

    if not steps:
        raise HTTPException(400, f"PoC {body.poc_id} has no steps")

    # Dispatch the first step to get the agent working immediately
    tq = TaskQueue()
    first = steps[0]
    task = await tq.enqueue(
        agent_id=body.agent_id,
        module=first.get("module", ""),
        action=first.get("action", ""),
        params=first.get("params", {}),
        priority=first.get("priority", "high"),
    )

    return {
        "poc_id": body.poc_id,
        "poc_name": tpl.name,
        "total_steps": len(steps),
        "first_task_id": str(task.id),
        "first_step": f"{first.get('module')}/{first.get('action')}",
        "status": "dispatched",
        "message": f"PoC '{tpl.name}' imported. First step dispatched. {len(steps)} total steps.",
    }


# ---------------------------------------------------------------------------
# Mission execution — multi-step guided operations with live progress
# ---------------------------------------------------------------------------

class MissionStepRequest(BaseModel):
    module: str
    action: str
    params: dict = Field(default_factory=dict)
    label: str = ""
    insight: str = ""
    timeout: int = Field(default=30, ge=1, le=600)


class MissionRequest(BaseModel):
    mission_id: str
    agent_id: str
    steps: list[MissionStepRequest]
    title: str = ""


@router.post("/mission")
async def execute_mission(body: MissionRequest, current_user: OperatorUser):
    """
    Execute a multi-step mission with live SSE progress.
    Each step dispatches a task, waits for completion, and streams the result.
    All missions are audit-logged.
    """
    tq = TaskQueue()

    # Audit log the mission start
    try:
        from middleware import log_event
        log_event(
            action="mission_started",
            actor=current_user.get("username", "unknown"),
            resource_type="mission",
            resource_id=body.mission_id,
            details={
                "title": body.title,
                "agent_id": body.agent_id,
                "steps": len(body.steps),
                "modules": [f"{s.module}/{s.action}" for s in body.steps],
            },
        )
    except Exception:
        pass

    async def mission_stream():
        total = len(body.steps)
        completed = 0
        results = []

        # Mission started event
        yield f"data: {json.dumps({'type': 'mission_start', 'mission_id': body.mission_id, 'title': body.title, 'total_steps': total, 'agent_id': body.agent_id})}\n\n"

        for i, step in enumerate(body.steps):
            step_num = i + 1
            # Step started
            yield f"data: {json.dumps({'type': 'step_start', 'step': step_num, 'total': total, 'label': step.label, 'insight': step.insight, 'module': step.module, 'action': step.action})}\n\n"

            try:
                # Dispatch task
                task = await tq.enqueue(
                    agent_id=body.agent_id,
                    module=step.module,
                    action=step.action,
                    params=step.params,
                    priority="high",
                )

                # Poll for completion
                deadline = time.time() + step.timeout + 30  # grace period
                poll_interval = 1.0
                final_status = "timeout"
                task_result = None
                task_error = None

                while time.time() < deadline:
                    await asyncio.sleep(poll_interval)
                    # Re-read task from DB
                    from db.models import Task as TaskModel
                    t = TaskModel.get_or_none(TaskModel.id == task.id)
                    if not t:
                        final_status = "error"
                        task_error = "Task disappeared"
                        break
                    if t.status in ("completed", "ok", "failed", "error", "cancelled"):
                        final_status = t.status
                        task_result = t.result
                        task_error = t.error
                        break

                completed += 1
                step_result = {
                    'type': 'step_done',
                    'step': step_num,
                    'total': total,
                    'label': step.label,
                    'status': final_status,
                    'insight': step.insight,
                    'task_id': str(task.id),
                    'result': task_result,
                    'error': task_error,
                }
                results.append(step_result)
                yield f"data: {json.dumps(step_result, default=str)}\n\n"

            except Exception as exc:
                completed += 1
                err_result = {
                    'type': 'step_error',
                    'step': step_num,
                    'total': total,
                    'label': step.label,
                    'error': str(exc),
                }
                results.append(err_result)
                yield f"data: {json.dumps(err_result)}\n\n"

        # Mission complete
        success_count = sum(1 for r in results if r.get('status') in ('completed', 'ok'))
        summary = {
            'type': 'mission_done',
            'mission_id': body.mission_id,
            'title': body.title,
            'total_steps': total,
            'completed': success_count,
            'failed': total - success_count,
            'agent_id': body.agent_id,
        }
        yield f"data: {json.dumps(summary)}\n\n"
        yield "data: [DONE]\n\n"

        # Audit log the mission completion
        try:
            from middleware import log_event
            log_event(
                action="mission_completed",
                actor=current_user.get("username", "unknown"),
                resource_type="mission",
                resource_id=body.mission_id,
                details={
                    "title": body.title,
                    "agent_id": body.agent_id,
                    "total_steps": total,
                    "completed": success_count,
                    "failed": total - success_count,
                },
            )
        except Exception:
            pass

    return StreamingResponse(mission_stream(), media_type="text/event-stream")


@router.get("/missions")
async def list_missions(current_user: CurrentUser) -> dict:
    """List available mission definitions (static, defined in frontend)."""
    return {
        "count": 0,
        "missions": [],
        "note": "Mission definitions are defined in the frontend. Use /ai-chat/mission to execute."
    }
