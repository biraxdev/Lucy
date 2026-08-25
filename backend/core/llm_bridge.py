"""
LLM bridge for Lucy chat engine.

When CHAT_LOCAL_LLM_URL is configured (e.g., http://localhost:11434 for Ollama),
the chat engine can offload natural-language parsing and response generation to a
local LLM. This module handles the HTTP communication with Ollama/LM Studio
compatible APIs (OpenAI-compatible /chat/completions endpoint).

If the LLM is unavailable or returns an error, the engine falls back to the
keyword-based parser.
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class LLMBridge:
    """Bridge to a local LLM (Ollama / LM Studio) for chat enhancement."""

    def __init__(self, url: Optional[str] = None, model: Optional[str] = None):
        self.url = (url or settings.CHAT_LOCAL_LLM_URL or "").rstrip("/")
        self.model = model or settings.CHAT_LLM_MODEL
        self.system_prompt = settings.CHAT_LLM_SYSTEM_PROMPT
        self._available: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    async def is_available(self) -> bool:
        """Check if the LLM endpoint is reachable."""
        if not self.enabled:
            return False
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(
                f"{self.url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
            logger.debug("LLM bridge: endpoint %s not reachable", self.url)
        return self._available

    async def parse_intent(self, query: str) -> Optional[dict[str, Any]]:
        """
        Ask the LLM to parse a natural-language query into a structured intent.
        Returns None if the LLM is unavailable or fails (fall back to keyword parser).
        """
        if not await self.is_available():
            return None

        prompt = (
            f"Parse this operator command into a JSON intent. Respond with ONLY JSON, no markdown.\n"
            f"Query: \"{query}\"\n\n"
            f"Format: {{\"name\": \"<intent_name>\", \"params\": {{\"agent_id\": \"\", \"module\": \"\", "
            f"\"action\": \"\", \"group_id\": \"\", \"timeline_id\": \"\", \"campaign_name\": \"\", "
            f"\"playbook_name\": \"\", \"note\": \"\", \"mitre_id\": \"\", \"os\": \"\", \"stealth_pack\": false}}}}\n\n"
            f"Intent names: AGENT_STATUS, LIST_AGENTS, RUN_TASK, RUN_ON_GROUP, BULK_TASK, RUN_TIMELINE, "
            f"RUN_PLAYBOOK, FILE_OPERATION, SHOW_CREDENTIALS, SHOW_FINDINGS, SHOW_TASKS, SHOW_LOGS, "
            f"BUILD_AGENT, SELF_DESTRUCT, CREATE_CAMPAIGN, CAMPAIGN_SUMMARY, ADD_AGENT_NOTE, "
            f"MAP_TECHNIQUE, HELP, SUMMARIZE, GREETING, UNKNOWN\n\n"
            f"Only include params that are relevant. Use UNKNOWN if the query is unclear."
        )

        try:
            response = self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.1, max_tokens=200)

            # Extract JSON from response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            parsed = json.loads(text)
            if isinstance(parsed, dict) and "name" in parsed:
                parsed.setdefault("params", {})
                parsed["raw_query"] = query
                parsed["confidence"] = 0.9
                logger.info("LLM parsed intent: %s", parsed["name"])
                return parsed
        except Exception as exc:
            logger.debug("LLM intent parsing failed: %s", exc)

        return None

    async def generate_response(self, query: str, context: dict[str, Any]) -> Optional[str]:
        """
        Generate a natural-language response using the LLM and current context.
        Returns None if unavailable (fall back to persona renderer).
        """
        if not await self.is_available():
            return None

        context_summary = self._summarize_context(context)
        prompt = (
            f"Operator asked: \"{query}\"\n\n"
            f"Current context:\n{context_summary}\n\n"
            f"Respond concisely (1-3 sentences) as Lucy, the C2 AI assistant. "
            f"Be tactical and helpful. If you dispatched a task, confirm it. "
            f"If there's a problem, explain it clearly."
        )

        try:
            response = self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.7, max_tokens=150)
            return response.strip()
        except Exception as exc:
            logger.debug("LLM response generation failed: %s", exc)
            return None

    async def summarize_activity(self, events: list[dict]) -> Optional[str]:
        """Ask the LLM to summarize recent agent activity/events."""
        if not await self.is_available():
            return None

        events_text = "\n".join(
            f"- [{e.get('type', '?')}] {e.get('message', '')}"
            for e in events[:20]
        )
        prompt = (
            f"Summarize this recent agent activity in 2-3 sentences. "
            f"Highlight any anomalies, failures, or notable successes:\n\n{events_text}"
        )

        try:
            return self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.5, max_tokens=200).strip()
        except Exception:
            return None

    async def suggest_next_steps(self, context: dict[str, Any]) -> Optional[str]:
        """Ask the LLM to suggest next tactical steps based on current state."""
        if not await self.is_available():
            return None

        context_summary = self._summarize_context(context)
        prompt = (
            f"Based on this current mission state, suggest 2-3 tactical next steps:\n\n"
            f"{context_summary}\n\n"
            f"Be specific and actionable. Format as a short numbered list."
        )

        try:
            return self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ], temperature=0.6, max_tokens=200).strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _summarize_context(self, context: dict[str, Any]) -> str:
        lines = []
        agents = context.get("agents", [])
        if agents:
            online = [a for a in agents if a.get("status") == "online"]
            lines.append(f"Agents: {len(online)} online / {len(agents)} total")
            for a in agents[:5]:
                lines.append(f"  - {a.get('hostname', '?')}: {a.get('status', '?')} ({a.get('os', '?')})")

        tasks = context.get("tasks", [])
        if tasks:
            failed = [t for t in tasks if t.get("status") == "failed"]
            running = [t for t in tasks if t.get("status") == "running"]
            lines.append(f"Tasks: {len(running)} running, {len(failed)} failed, {len(tasks)} total")

        creds = context.get("credential_count", 0)
        if creds:
            lines.append(f"Credentials harvested: {creds}")

        findings = context.get("finding_count", 0)
        if findings:
            lines.append(f"Findings: {findings}")

        alerts = context.get("unread_alerts", 0)
        if alerts:
            lines.append(f"Unread alerts: {alerts}")

        return "\n".join(lines) if lines else "No active context available."

    def _chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 200) -> str:
        """Call the LLM /api/chat endpoint (Ollama-compatible)."""
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "")


# Shared instance
bridge = LLMBridge()
