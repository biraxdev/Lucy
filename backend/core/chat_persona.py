"""
Persona renderer for the Lucy chat interface.

Translates raw technical events into emotional, natural-language messages.
The default persona is a calm, slightly protective operator assistant named
"Lucy". Templates are grouped by event type and mood to avoid repetition.
"""
import random
from datetime import datetime, timezone
from typing import Any


DEFAULT_PERSONA = {
    "name": "Lucy",
    "avatar": "🕊️",
    "tone": "calm",
    "self_reference": ["I", "Lucy"],
}


# ---------------------------------------------------------------------------
# Event templates
# ---------------------------------------------------------------------------

EVENT_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "heartbeat": {
        "calm": [
            "{name} is still breathing — last seen {ago}s ago.",
            "{name} checked in {ago}s ago. Everything looks quiet.",
            "I heard from {name} {ago}s ago. It's alive and well.",
        ],
        "celebratory": [
            "Good news — {name} is still with us! Last heartbeat {ago}s ago.",
            "{name} just whispered. Still online after {ago}s.",
        ],
    },
    "agent_connected": {
        "calm": [
            "{name} just came online.",
            "{name} connected. I'm tracking it now.",
        ],
        "celebratory": [
            "{name} has arrived! 🎉",
            "Welcome back, {name}.",
        ],
    },
    "agent_disconnected": {
        "worried": [
            "I lost contact with {name}.",
            "{name} went offline. I'll keep listening.",
        ],
        "calm": [
            "{name} disconnected ({reason}).",
        ],
    },
    "task_queued": {
        "calm": [
            "I queued a {module} task for {name}.",
            "Request noted: {module} on {name} is in line.",
        ],
    },
    "task_running": {
        "calm": [
            "{name} started the {module} task.",
            "{module} is now running on {name}.",
        ],
    },
    "task_completed": {
        "celebratory": [
            "{name} finished the {module} task successfully.",
            "Done! {name} completed {module}.",
        ],
    },
    "task_failed": {
        "worried": [
            "The {module} task on {name} failed: {error}.",
            "Something went wrong with {module} on {name}: {error}.",
        ],
    },
    "credential_found": {
        "celebratory": [
            "{name} found {count} credential(s). I secured them in the vault.",
            "Score! {count} new credential(s) harvested by {name}.",
        ],
        "urgent": [
            "Critical: {name} captured {count} credential(s).",
        ],
    },
    "log": {
        "calm": [
            "[{level}] {name}: {message}",
        ],
    },
    "error": {
        "worried": [
            "I ran into a problem: {message}",
            "Something isn't right: {message}",
        ],
    },
    "command_ack": {
        "calm": [
            "On it. {action}",
            "Copy that. {action}",
            "Understood. {action}",
        ],
    },
    "command_result": {
        "calm": [
            "{result}",
        ],
    },
    "chat_greeting": {
        "calm": [
            "Hello. I'm Lucy. Tell me what you'd like to do — or ask for help.",
            "Hey. I'm listening. What are we doing today?",
        ],
    },
    "chat_help": {
        "calm": [
            "I understand commands like:\n"
            "- \"check on Agent 01\"\n"
            "- \"run recon on group Alpha\"\n"
            "- \"run whoami on all online agents\"\n"
            "- \"list files on Agent 01 in C:\\\\Users\"\n"
            "- \"note that Agent 01 is a domain controller\"\n"
            "- \"create campaign Alpha\"\n"
            "- \"campaign summary\"\n"
            "- \"run playbook recon on Agent 01\"\n"
            "- \"map technique T1059\"\n"
            "- \"show credentials from Agent 01\"\n"
            "- \"self-destruct Agent 01\"\n"
            "- \"build a stealth windows agent\"",
        ],
    },
    "bulk_task_queued": {
        "calm": [
            "Dispatched {module} to {count} agent(s). I'm watching for results.",
            "Fleet task queued: {module} on {count} agent(s).",
        ],
    },
    "file_operation": {
        "calm": [
            "I'll {operation} {path} on {name} for you.",
            "Sending a {operation} request to {name} for {path}.",
        ],
    },
    "agent_note_added": {
        "calm": [
            "Noted. I'll remember that about {name}.",
            "Got it — observation for {name} saved.",
        ],
    },
    "notes_list": {
        "calm": [
            "Here are {count} note(s) I have on record.",
            "I found {count} observation(s).",
        ],
    },
    "campaign_created": {
        "celebratory": [
            "Campaign \"{name}\" is live.",
            "Started \"{name}\". Ready when you are.",
        ],
    },
    "campaigns_list": {
        "calm": [
            "We have {count} campaign(s) on file.",
            "{count} campaign(s) tracked so far.",
        ],
    },
    "campaign_summary": {
        "calm": [
            "\"{name}\" is {status}. We have {online}/{total_agents} agents online and {tasks} task(s) on record.",
        ],
    },
    "playbook_started": {
        "calm": [
            'Playbook "{name}" started — {count} task(s) queued.',
            'Running "{name}". {count} step(s) dispatched.',
        ],
    },
    "technique_mapped": {
        "calm": [
            "Mapped {mitre_id}: {name}.",
            "Technique {mitre_id} ({name}) is now in the library.",
        ],
    },
    "chat_unknown": {
        "worried": [
            "I'm not sure I understood. Try 'help' for things I can do.",
            "Could you rephrase? I can show help if you type 'help'.",
        ],
    },
    "chat_summary": {
        "calm": [
            "Right now we have {online} agent(s) online, {queued} queued task(s), and {credentials} credential(s) in the vault.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class PersonaRenderer:
    """Render technical events as persona-driven natural language."""

    def __init__(self, persona: dict[str, Any] | None = None):
        self.persona = persona or DEFAULT_PERSONA

    def render(
        self,
        event_type: str,
        context: dict[str, Any] | None = None,
        mood: str | None = None,
    ) -> str:
        """Pick and fill a template for the given event type."""
        context = _build_context(event_type, context or {})
        context.setdefault("name", "the agent")
        context.setdefault("avatar", self.persona.get("avatar", "🕊️"))

        templates_by_mood = EVENT_TEMPLATES.get(event_type)
        if not templates_by_mood:
            return context.get("fallback", "Something happened.")

        if mood is None:
            mood = self._infer_mood(event_type, context)

        candidates = templates_by_mood.get(mood) or list(templates_by_mood.values())[0]
        template = random.choice(candidates)

        try:
            return template.format(**context)
        except (KeyError, ValueError):
            # If formatting fails, return the template with available placeholders
            # stripped so we never crash the chat.
            return template

    def _infer_mood(self, event_type: str, context: dict[str, Any]) -> str:
        """Choose a mood based on event type and payload context."""
        if event_type in ("agent_disconnected", "task_failed", "error", "chat_unknown"):
            return "worried"
        if event_type in ("credential_found", "agent_connected", "task_completed"):
            count = context.get("count", 0)
            if isinstance(count, int) and count > 0:
                return random.choice(["celebratory", "urgent"])
            return "celebratory"
        if event_type == "heartbeat":
            return random.choice(["calm", "celebratory"])
        return "calm"


def _human_ago(timestamp: str | datetime | None) -> str:
    """Return a short human-readable elapsed time."""
    if timestamp is None:
        return "a while"
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        delta = (datetime.now(timezone.utc) - timestamp).total_seconds()
        if delta < 60:
            return f"{int(delta)}s"
        if delta < 3600:
            return f"{int(delta / 60)}m"
        return f"{int(delta / 3600)}h"
    except Exception:
        return "a while"


def heartbeat_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Build rendering context from a heartbeat payload."""
    return {
        "name": _agent_name(payload.get("agent_id")),
        "ago": _human_ago(payload.get("timestamp")),
        **payload,
    }


def _build_context(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw payloads into template variables."""
    ctx = payload.copy()
    if event_type == "heartbeat":
        return heartbeat_context(ctx)
    if event_type in ("agent_connected", "agent_disconnected"):
        ctx.setdefault("name", _agent_name(ctx.get("agent_id")))
        ctx.setdefault("reason", ctx.get("reason", "disconnect"))
    if event_type in ("task_queued", "task_running", "task_completed", "task_failed"):
        ctx.setdefault("name", _agent_name(ctx.get("agent_id")))
        ctx.setdefault("module", ctx.get("module", "task"))
        ctx.setdefault("error", ctx.get("error", "unknown error"))
    if event_type == "credential_found":
        ctx.setdefault("name", _agent_name(ctx.get("agent_id")))
        ctx.setdefault("count", ctx.get("count", 0))
    if event_type == "log":
        ctx.setdefault("level", ctx.get("level", "INFO"))
        ctx.setdefault("name", _agent_name(ctx.get("agent_id")))
        ctx.setdefault("message", ctx.get("message", ""))
    return ctx


def _agent_name(agent_id: str | None) -> str:
    if not agent_id:
        return "the agent"
    return f"Agent {agent_id[:8]}"
