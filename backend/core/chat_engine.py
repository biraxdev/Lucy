"""
Lucy chat engine.

- Parses natural-language operator commands into typed intents.
- Executes the mapped backend actions (task enqueue, build, timeline, etc.).
- Renders emotional persona messages for events and command responses.
- Optionally uses a local LLM (Ollama/LM Studio) for enhanced parsing and responses.
"""
import json
import logging
import re
from typing import Any, Awaitable, Callable

from .chat_intents import (
    INTENT_KEYWORDS,
    DEFAULT_MODULE_ACTIONS,
    AGENT_PREFIXES,
    GROUP_PREFIXES,
    Intent,
)
from .chat_persona import PersonaRenderer, heartbeat_context, _agent_name
from .llm_bridge import bridge as llm_bridge

logger = logging.getLogger(__name__)

# Callbacks injected at startup so the engine stays testable without importing
# the whole FastAPI app.
ActionCallback = Callable[[Intent, dict[str, Any]], Awaitable[dict[str, Any]]]


class ChatEngine:
    """Main chat orchestrator: parse → route → render."""

    def __init__(self):
        self.renderer = PersonaRenderer()
        self.action_callbacks: dict[str, ActionCallback] = {}

    def register_action(self, intent_name: str, callback: ActionCallback) -> None:
        """Register a backend executor for an intent name."""
        self.action_callbacks[intent_name] = callback

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def parse(self, query: str) -> Intent:
        """Convert free text into a structured intent."""
        q = query.lower().strip()
        if not q:
            return Intent(name="UNKNOWN", raw_query=query)

        # Greeting takes precedence.
        if any(k in q for k in INTENT_KEYWORDS["GREETING"]):
            return Intent(name="GREETING", raw_query=query)

        # Try LLM-based parsing first (async, but we call it synchronously here
        # since parse() is called from async context in the chat router).
        # The router will call parse_async which tries LLM first.
        # This sync parse() is the keyword-based fallback.

        # Determine primary intent by keyword overlap.
        scores: dict[str, int] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            if intent == "GREETING":
                continue
            score = sum(1 for k in keywords if k in q)
            if score:
                scores[intent] = score

        # Self-destruct / destructive commands should be detected early.
        if any(k in q for k in INTENT_KEYWORDS["SELF_DESTRUCT"]):
            scores["SELF_DESTRUCT"] = scores.get("SELF_DESTRUCT", 0) + 2

        if not scores:
            return Intent(name="UNKNOWN", raw_query=query)

        intent_name = max(scores, key=scores.get)
        intent = Intent(name=intent_name, raw_query=query)

        # Extract common entities.
        intent.params = self._extract_entities(q)
        intent.params["raw_query"] = query

        # Refine RUN_TASK vs RUN_ON_GROUP vs BULK_TASK.
        if intent.name == "RUN_TASK" and self._mentions_group(q):
            intent.name = "RUN_ON_GROUP"
        if self._mentions_all_agents(q):
            intent.name = "BULK_TASK"

        # Pull module/action from shorthand like "run recon on X".
        if intent.name in ("RUN_TASK", "RUN_ON_GROUP", "BULK_TASK"):
            module, action = self._extract_module_action(q)
            intent.params.setdefault("module", module)
            intent.params.setdefault("action", action)

        # Build intent: default to windows stealth if not specified.
        if intent.name == "BUILD_AGENT":
            intent.params.setdefault("os", "windows")
            intent.params.setdefault("stealth_pack", True)

        # Resolve file operation details.
        if intent.name == "FILE_OPERATION":
            intent.params["operation"] = self._extract_file_operation(q)

        # Resolve campaign / playbook / note / technique names.
        if intent.name in ("CREATE_CAMPAIGN", "CAMPAIGN_SUMMARY"):
            intent.params.setdefault("campaign_name", self._extract_name_after(q, ["campaign", "campagne"]))
        if intent.name == "RUN_PLAYBOOK":
            intent.params.setdefault("playbook_name", self._extract_name_after(q, ["playbook", "procedure"]))
        if intent.name == "ADD_AGENT_NOTE":
            intent.params.setdefault("note", self._extract_note_text(q))
        if intent.name == "MAP_TECHNIQUE":
            intent.params.setdefault("mitre_id", self._extract_mitre_id(q))
            intent.params.setdefault("technique_name", self._extract_name_after(q, ["technique"]))

        return intent

    async def parse_async(self, query: str) -> Intent:
        """
        Try LLM-based intent parsing first, fall back to keyword-based.
        This is the enhanced path used by the chat router when LLM is available.
        """
        # Try LLM first
        if llm_bridge.enabled:
            try:
                llm_result = await llm_bridge.parse_intent(query)
                if llm_result and llm_result.get("name"):
                    name = llm_result["name"].upper()
                    # Validate intent name
                    from .chat_intents import INTENT_NAMES
                    if name in INTENT_NAMES:
                        intent = Intent(
                            name=name,
                            confidence=llm_result.get("confidence", 0.9),
                            params=llm_result.get("params", {}),
                            raw_query=query,
                        )
                        intent.params["raw_query"] = query
                        # Still run entity extraction as a supplement
                        q = query.lower().strip()
                        extracted = self._extract_entities(q)
                        for k, v in extracted.items():
                            intent.params.setdefault(k, v)
                        # Refine task type
                        if intent.name == "RUN_TASK" and self._mentions_group(q):
                            intent.name = "RUN_ON_GROUP"
                        if self._mentions_all_agents(q):
                            intent.name = "BULK_TASK"
                        # Module/action defaults
                        if intent.name in ("RUN_TASK", "RUN_ON_GROUP", "BULK_TASK"):
                            module, action = self._extract_module_action(q)
                            intent.params.setdefault("module", module)
                            intent.params.setdefault("action", action)
                        if intent.name == "BUILD_AGENT":
                            intent.params.setdefault("os", "windows")
                            intent.params.setdefault("stealth_pack", True)
                        logger.info("LLM intent: %s (confidence=%.2f)", name, intent.confidence)
                        return intent
            except Exception as exc:
                logger.debug("LLM parse failed, falling back to keywords: %s", exc)

        # Fall back to keyword-based parsing
        return self.parse(query)

    def _extract_entities(self, query: str) -> dict[str, Any]:
        params: dict[str, Any] = {}

        # Agent identifier: "agent 01", "agent abc123", "machine foo"
        for prefix in AGENT_PREFIXES:
            pattern = rf"{prefix}[\s#-]*(\w+)"
            m = re.search(pattern, query)
            if m:
                params["agent_id"] = m.group(1)
                break

        # Group identifier.
        for prefix in GROUP_PREFIXES:
            pattern = rf"{prefix}[\s#-]*(\w+)"
            m = re.search(pattern, query)
            if m:
                params["group_id"] = m.group(1)
                break

        # Timeline / scenario name/ID.
        m = re.search(r"timeline[\s#-]*(\w+)", query)
        if m:
            params["timeline_id"] = m.group(1)

        # Numeric timeouts / delays.
        m = re.search(r"(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?)", query)
        if m:
            value = int(m.group(1))
            unit = m.group(2)
            if "minute" in unit:
                value *= 60
            elif "hour" in unit:
                value *= 3600
            params["delay_seconds"] = value

        return params

    def _mentions_group(self, query: str) -> bool:
        return any(prefix in query for prefix in GROUP_PREFIXES + ["on group", "on groupe", "everyone"])

    def _extract_module_action(self, query: str) -> tuple[str, str]:
        """Try to guess the module and action from the command text."""
        for alias, (module, action) in DEFAULT_MODULE_ACTIONS.items():
            if re.search(rf"\b{re.escape(alias)}\b", query):
                return module, action
        return "info", "run"

    def _mentions_all_agents(self, query: str) -> bool:
        return any(k in query for k in ["all agents", "every agent", "bulk", "mass", "fleet", "all online"])

    def _extract_file_operation(self, query: str) -> dict[str, str]:
        """Guess file operation and target path from the command."""
        operation = "list"
        if "download" in query:
            operation = "download"
        elif "upload" in query:
            operation = "upload"
        elif "read" in query or "cat " in query:
            operation = "read"

        # Try to pull a path like C:\Users, /etc, or a quoted string.
        path = "."
        m = re.search(r'(?:from|on|in|path)\s+["\']?([A-Za-z]:\\[^"\']+|/[^"\']+|[A-Za-z][A-Za-z0-9_\\./-]+)', query)
        if m:
            path = m.group(1)
        else:
            m = re.search(r'(?:file|fichier)\s+["\']?([^"\']+)', query)
            if m:
                path = m.group(1)
        return {"operation": operation, "path": path}

    def _extract_name_after(self, query: str, prefixes: list[str]) -> str | None:
        """Pull a quoted or unquoted name after a prefix, e.g. 'campaign Alpha'."""
        for prefix in prefixes:
            m = re.search(rf'{re.escape(prefix)}[\s#-]*["\']?([^"\']+)', query)
            if m:
                return m.group(1).strip()
        return None

    def _extract_note_text(self, query: str) -> str | None:
        """Extract the free-text note after note-taking markers."""
        for marker in ["note that", "write down", "remember that", "agent note"]:
            if marker in query:
                return query.split(marker, 1)[1].strip().strip('"\'')
        return None

    def _extract_mitre_id(self, query: str) -> str | None:
        m = re.search(r"\b(T\d{4}(?:\.\d{3})?)\b", query, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return None

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------

    async def execute(self, intent: Intent, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the backend action for an intent and return a result dict."""
        callback = self.action_callbacks.get(intent.name)
        if not callback:
            return {
                "status": "noop",
                "intent": intent.name,
                "message": self.renderer.render("chat_unknown", {}),
            }
        try:
            result = await callback(intent, context)
            result.setdefault("intent", intent.name)
            # Try LLM for response generation, fall back to persona
            if llm_bridge.enabled:
                llm_response = await llm_bridge.generate_response(intent.raw_query, {**context, **result})
                if llm_response:
                    result.setdefault("message", llm_response)
                    result["llm_generated"] = True
            result.setdefault("message", self._ack_message(intent, result))
            return result
        except Exception as exc:
            logger.exception("Chat action failed for intent %s", intent.name)
            return {
                "status": "error",
                "intent": intent.name,
                "message": self.renderer.render(
                    "error", {"message": f"I couldn't do that: {exc}"}
                ),
            }

    def _ack_message(self, intent: Intent, result: dict[str, Any]) -> str:
        """Generate a short persona acknowledgment for a successful action."""
        action = self._describe_action(intent, result)
        return self.renderer.render("command_ack", {"action": action})

    def _describe_action(self, intent: Intent, result: dict[str, Any]) -> str:
        if intent.name == "RUN_TASK":
            agent = result.get("agent_id") or intent.params.get("agent_id", "the agent")
            module = intent.params.get("module", "task")
            return f"I sent a {module} task to {_agent_name(agent)}."
        if intent.name == "RUN_ON_GROUP":
            group = intent.params.get("group_id", "the group")
            module = intent.params.get("module", "task")
            return f"I dispatched {module} to group {group}."
        if intent.name == "RUN_TIMELINE":
            return "I started the timeline."
        if intent.name == "SELF_DESTRUCT":
            agent = intent.params.get("agent_id", "the agent")
            return f"I told {_agent_name(agent)} to self-destruct."
        if intent.name == "BUILD_AGENT":
            return "I queued a stealth agent build."
        if intent.name == "AGENT_STATUS":
            return result.get("status_message", "Status request received.")
        if intent.name == "SUMMARIZE":
            return result.get("summary", "Here's the summary.")
        if intent.name == "HELP":
            return self.renderer.render("chat_help", {})
        if intent.name == "GREETING":
            return self.renderer.render("chat_greeting", {})
        return "Done."

    # ------------------------------------------------------------------
    # Render events
    # ------------------------------------------------------------------

    def render_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Translate a raw WS event into a chat message dict."""
        ctx = payload.copy()
        if event_type == "heartbeat":
            ctx = heartbeat_context(payload)
            content = self.renderer.render("heartbeat", ctx)
        elif event_type == "agent_connected":
            content = self.renderer.render("agent_connected", ctx)
        elif event_type == "agent_disconnected":
            content = self.renderer.render("agent_disconnected", ctx)
        elif event_type == "result":
            content = self._render_result(payload)
        elif event_type == "log":
            level = payload.get("level", "INFO")
            content = self.renderer.render("log", {
                "level": level,
                "name": _agent_name(payload.get("agent_id")),
                "message": payload.get("message", ""),
            })
        else:
            content = ctx.get("fallback", f"Event: {event_type}")

        return {
            "role": "event",
            "content": content,
            "source_event_type": event_type,
            "raw_payload": payload,
            "metadata": {"mood": self.renderer._infer_mood(event_type, ctx)},
        }

    def _render_result(self, payload: dict[str, Any]) -> str:
        status = payload.get("status", "completed")
        module = payload.get("module", "task")
        agent_id = payload.get("agent_id")
        error = payload.get("error")

        if status == "failed" or error:
            return self.renderer.render("task_failed", {
                "name": _agent_name(agent_id),
                "module": module,
                "error": error or "unknown error",
            })
        return self.renderer.render("task_completed", {
            "name": _agent_name(agent_id),
            "module": module,
        })


# ---------------------------------------------------------------------------
# Utility helpers for action callbacks
# ---------------------------------------------------------------------------

def parse_agent_id(text: str) -> str | None:
    """If the user typed a short prefix, return the full identifier when possible."""
    text = text.strip().lower()
    return text if text else None


# Shared engine instance. Import this from routers instead of instantiating a
# new engine so callbacks are registered exactly once.
engine = ChatEngine()
