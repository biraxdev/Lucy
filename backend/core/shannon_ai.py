"""
ShannonAi — Dynamic chat engine for Project Lucy.

Transforms raw logs, heartbeats, task results and alerts into a flowing
narrative dialogue. Instead of one-line persona messages, ShannonAi weaves
events into contextual paragraphs that read like a mission log novel.

Design goals:
- Context-aware: remembers the last N events per agent/group and references them.
- Streaming-friendly: yields token-sized chunks for SSE / WS streaming.
- Fallback-friendly: degrades gracefully when no LLM is configured (uses a
  local narrative templating engine inspired by Shannon's information theory —
  higher-information events get more narrative weight).
- Pluggable: can layer on top of the existing LLM bridge when available.

The name is a nod to Claude Shannon — the engine tries to maximize information
density per message while staying readable.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from .chat_persona import _agent_name, _human_ago
from .llm_bridge import bridge as llm_bridge
from peewee import SQL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event memory — keeps recent events per agent for contextual references
# ---------------------------------------------------------------------------

MAX_MEMORY_PER_AGENT = 20
MAX_MEMORY_GLOBAL = 60


@dataclass
class ShannonEvent:
    """A normalized event stored in ShannonAi's short-term memory."""
    event_type: str           # heartbeat | result | log | alert | connect | disconnect
    agent_id: Optional[str]
    timestamp: datetime
    summary: str              # one-line summary
    severity: str = "info"    # info | success | warning | error
    metadata: dict[str, Any] = field(default_factory=dict)


class ShannonMemory:
    """Rolling window of recent events, indexed by agent and globally."""

    def __init__(self) -> None:
        self._by_agent: dict[str, deque[ShannonEvent]] = {}
        self._global: deque[ShannonEvent] = deque(maxlen=MAX_MEMORY_GLOBAL)

    def remember(self, event: ShannonEvent) -> None:
        self._global.append(event)
        if event.agent_id:
            dq = self._by_agent.setdefault(event.agent_id, deque(maxlen=MAX_MEMORY_PER_AGENT))
            dq.append(event)

    def recent_for(self, agent_id: Optional[str], limit: int = 5) -> list[ShannonEvent]:
        if not agent_id:
            return list(self._global)[-limit:]
        return list(self._by_agent.get(agent_id, []))[-limit:]

    def recent_global(self, limit: int = 10) -> list[ShannonEvent]:
        return list(self._global)[-limit:]

    def clear(self) -> None:
        self._by_agent.clear()
        self._global.clear()


# ---------------------------------------------------------------------------
# Narrative engine — turns events into prose without an LLM
# ---------------------------------------------------------------------------

# Information weight per event type — higher = more narrative attention.
EVENT_WEIGHT: dict[str, int] = {
    "heartbeat": 1,
    "log": 2,
    "result": 3,
    "alert": 4,
    "connect": 5,
    "disconnect": 5,
    "credential": 6,
    "finding": 5,
}

SEVERITY_VERB: dict[str, str] = {
    "info": "noted",
    "success": "completed",
    "warning": "flagged",
    "error": "failed",
}

# Connective phrases to weave multiple events into a paragraph.
CONNECTIVES = [
    "Meanwhile, ",
    "Around the same time, ",
    "Not long after, ",
    "On top of that, ",
    "Elsewhere, ",
    "In parallel, ",
    "Shortly after, ",
]


def _severity_from_event(event_type: str, payload: dict[str, Any]) -> str:
    if event_type in ("disconnect", "alert") and payload.get("level") in ("error", "critical"):
        return "error"
    if event_type == "result" and (payload.get("status") == "failed" or payload.get("error")):
        return "error"
    if event_type in ("connect", "credential", "finding"):
        return "success"
    if event_type == "disconnect":
        return "warning"
    if payload.get("level") == "warning":
        return "warning"
    return "info"


def _event_summary(event_type: str, payload: dict[str, Any]) -> str:
    """Produce a one-line factual summary of an event."""
    name = _agent_name(payload.get("agent_id"))
    if event_type == "heartbeat":
        ago = _human_ago(payload.get("timestamp"))
        return f"{name} checked in {ago} ago"
    if event_type == "connect":
        return f"{name} came online"
    if event_type == "disconnect":
        reason = payload.get("reason", "unknown")
        return f"{name} went offline ({reason})"
    if event_type == "result":
        module = payload.get("module", "task")
        status = payload.get("status", "completed")
        if status == "failed" or payload.get("error"):
            err = payload.get("error", "unknown error")
            return f"{name}'s {module} task failed: {err}"
        return f"{name} finished its {module} task"
    if event_type == "log":
        level = payload.get("level", "INFO")
        msg = payload.get("message", "")
        return f"{name} logged [{level}] {msg}"
    if event_type == "alert":
        return f"Alert: {payload.get('message', 'unnamed alert')}"
    if event_type == "credential":
        count = payload.get("count", 1)
        return f"{name} yielded {count} credential(s)"
    if event_type == "finding":
        return f"New finding from {name}: {payload.get('title', 'unspecified')}"
    return f"Event: {event_type}"


def _narrate_single(event: ShannonEvent, memory: ShannonMemory) -> str:
    """Turn a single event into a contextual sentence, referencing prior events."""
    base = event.summary
    prior = [e for e in memory.recent_for(event.agent_id, 4) if e is not event]
    if not prior:
        return base + "."

    # Reference the most recent prior event of the same agent for continuity.
    last = prior[-1]
    if last.event_type == event.event_type and event.event_type == "heartbeat":
        # Heartbeats are repetitive — compress.
        count = sum(1 for e in prior if e.event_type == "heartbeat") + 1
        return f"{base} — that's heartbeat #{count} for this agent."
    if last.event_type == "result" and event.event_type == "result":
        return f"{base}, building on the previous {last.metadata.get('module', 'task')} result."
    if last.event_type == "disconnect" and event.event_type == "connect":
        return f"{base} — good to see it back after going silent."
    if last.event_type == "connect" and event.event_type == "disconnect":
        return f"{base} — short session this time."
    return base + "."


def narrate_events(events: list[ShannonEvent], memory: ShannonMemory) -> str:
    """
    Weave a list of events into a single narrative paragraph.
    Higher-weight events get more emphasis; low-weight events are compressed.
    """
    if not events:
        return "All quiet on the network."

    # Sort by weight descending so important events lead.
    ordered = sorted(events, key=lambda e: EVENT_WEIGHT.get(e.event_type, 1), reverse=True)

    # Compress consecutive heartbeats into a single mention.
    seen_heartbeats: dict[str, int] = {}
    lines: list[str] = []
    for idx, event in enumerate(ordered):
        if event.event_type == "heartbeat":
            aid = event.agent_id or "?"
            seen_heartbeats[aid] = seen_heartbeats.get(aid, 0) + 1
            if seen_heartbeats[aid] > 1:
                continue  # skip duplicate heartbeats for same agent
        sentence = _narrate_single(event, memory)
        if idx > 0 and lines:
            # Add a connective to the second sentence onward.
            connective = CONNECTIVES[idx % len(CONNECTIVES)]
            sentence = connective + sentence[0].lower() + sentence[1:]
        lines.append(sentence)

    # Append a heartbeat compression summary if any were skipped.
    skipped = sum(v - 1 for v in seen_heartbeats.values() if v > 1)
    if skipped:
        lines.append(f"({skipped} additional routine heartbeats suppressed for brevity.)")

    return " ".join(lines)


# ---------------------------------------------------------------------------
# Log-to-dialogue transformation
# ---------------------------------------------------------------------------

def transform_log_to_dialogue(
    logs: list[dict[str, Any]],
    memory: ShannonMemory,
    agent_id: Optional[str] = None,
) -> str:
    """
    Convert a batch of raw log entries into a dialogue-style narrative.

    Each log is classified, weighted, and woven into prose that reads like
    a mission log rather than a raw syslog dump.
    """
    events: list[ShannonEvent] = []
    for log in logs:
        level = (log.get("level") or "INFO").upper()
        event_type = "log"
        severity = _severity_from_event("log", {"level": level.lower()})
        if level in ("ERROR", "CRITICAL"):
            severity = "error"
            event_type = "alert"
        elif level == "WARNING":
            severity = "warning"

        summary = _event_summary("log", {
            "agent_id": log.get("agent_id") or agent_id,
            "level": level,
            "message": log.get("message", ""),
        })
        events.append(ShannonEvent(
            event_type=event_type,
            agent_id=log.get("agent_id") or agent_id,
            timestamp=_parse_ts(log.get("timestamp")),
            summary=summary,
            severity=severity,
            metadata={"level": level, "message": log.get("message", "")},
        ))

    if not events:
        return "No recent log activity to narrate."

    # Remember them so future narratives can reference.
    for e in events:
        memory.remember(e)

    return narrate_events(events, memory)


def transform_event_to_dialogue(
    event_type: str,
    payload: dict[str, Any],
    memory: ShannonMemory,
) -> str:
    """Convert a single live event into a narrative line and record it."""
    severity = _severity_from_event(event_type, payload)
    summary = _event_summary(event_type, payload)
    event = ShannonEvent(
        event_type=event_type,
        agent_id=payload.get("agent_id"),
        timestamp=_parse_ts(payload.get("timestamp")) or datetime.now(timezone.utc),
        summary=summary,
        severity=severity,
        metadata=payload,
    )
    memory.remember(event)
    return _narrate_single(event, memory)


# ---------------------------------------------------------------------------
# Streaming narrative generator
# ---------------------------------------------------------------------------

async def stream_narrative(
    text: str,
    chunk_size: int = 8,
    delay_ms: int = 20,
) -> AsyncIterator[str]:
    """
    Yield a string in word-sized chunks for SSE / WS streaming.
    Simulates token streaming for a more dynamic chat feel.
    """
    words = text.split(" ")
    buffer: list[str] = []
    for word in words:
        buffer.append(word)
        if len(buffer) >= chunk_size:
            yield " ".join(buffer) + " "
            buffer.clear()
            await asyncio.sleep(delay_ms / 1000.0)
    if buffer:
        yield " ".join(buffer)


# ---------------------------------------------------------------------------
# ShannonAi engine — orchestrates memory + narrative + optional LLM
# ---------------------------------------------------------------------------

class ShannonAi:
    """
    Main ShannonAi engine. Singleton-style — one instance shared across the app.

    Three modes:
    - "narrative"  : pure local narrative engine (no LLM needed).
    - "hybrid"     : local narrative + LLM polish when available.
    - "llm"        : full LLM generation (requires CHAT_LOCAL_LLM_URL).
    """

    def __init__(self, mode: str = "hybrid") -> None:
        self.mode = mode
        self.memory = ShannonMemory()

    def set_mode(self, mode: str) -> None:
        if mode not in ("narrative", "hybrid", "llm"):
            raise ValueError(f"Unknown ShannonAi mode: {mode}")
        self.mode = mode

    def ingest_event(self, event_type: str, payload: dict[str, Any]) -> str:
        """Ingest a live event and return a narrative line (synchronous)."""
        return transform_event_to_dialogue(event_type, payload, self.memory)

    def narrate_recent(self, limit: int = 10) -> str:
        """Narrate the last N events from memory."""
        events = self.memory.recent_global(limit)
        return narrate_events(events, self.memory)

    def narrate_agent(self, agent_id: str, limit: int = 8) -> str:
        events = self.memory.recent_for(agent_id, limit)
        if not events:
            return f"No recent activity for {_agent_name(agent_id)}."
        return narrate_events(events, self.memory)

    def transform_logs(self, logs: list[dict[str, Any]], agent_id: Optional[str] = None) -> str:
        return transform_log_to_dialogue(logs, self.memory, agent_id)

    async def respond(
        self,
        user_query: str,
        context: dict[str, Any],
    ) -> str:
        """
        Generate a full (non-streaming) ShannonAi response to an operator query.
        Falls back to narrative mode if LLM is unavailable.
        """
        if self.mode == "llm" or (self.mode == "hybrid" and await llm_bridge.is_available()):
            try:
                llm_resp = await llm_bridge.generate_response(user_query, {
                    **context,
                    "recent_events": [e.summary for e in self.memory.recent_global(8)],
                })
                if llm_resp:
                    return llm_resp
            except Exception as exc:
                logger.debug("ShannonAi LLM response failed: %s", exc)

        # Narrative fallback — context-aware response based on query + DB state.
        return self._narrative_fallback(user_query, context)

    async def stream_response(
        self,
        user_query: str,
        context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """
        Stream a ShannonAi response in word chunks.
        Tries LLM streaming first (if available), falls back to narrative streaming.
        """
        text = await self.respond(user_query, context)
        async for chunk in stream_narrative(text):
            yield chunk

    async def stream_log_dialogue(
        self,
        logs: list[dict[str, Any]],
        agent_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream a log-to-dialogue transformation."""
        text = self.transform_logs(logs, agent_id)
        async for chunk in stream_narrative(text, chunk_size=6, delay_ms=15):
            yield chunk

    def reset(self) -> None:
        """Clear short-term memory (e.g. on channel switch)."""
        self.memory.clear()

    # ------------------------------------------------------------------
    # Narrative fallback — context-aware responses without an LLM
    # ------------------------------------------------------------------

    _FRENCH_HINTS = (
        "parle", "salut", "bonjour", "coucou", "ça va", "ca va",
        "montre", "affiche", "donne", "liste", "status", "état", "etat",
        "agents", "tâches", "taches", "credentials", "trouves", "alertes",
        "résumé", "resume", "aide", "help", "narrate", "logs",
        "qu'est", "c'est", "comment", "pourquoi", "où", "ou",
    )

    @staticmethod
    def _is_french(query: str) -> bool:
        q = query.lower()
        return any(h in q for h in ShannonAi._FRENCH_HINTS) or any(
            "\u00e0" <= c <= "\u017f" for c in q
        )

    def _narrative_fallback(self, query: str, context: dict[str, Any]) -> str:
        """Build a context-aware response from DB state + memory, no LLM needed."""
        fr = self._is_french(query)
        q = query.lower().strip()

        # --- Greetings / "parle moi" ---
        if any(w in q for w in ("parle", "salut", "bonjour", "coucou", "hello", "hi ", "hey")) or q in ("hi", "hey", "yo"):
            return self._greeting(fr)

        # --- Help ---
        if q in ("help", "aide", "?", "help me"):
            return self._help_text(fr)

        # --- Status / summary ---
        if any(w in q for w in ("status", "summarize", "summary", "résumé", "resume", "overview", "situation", "état", "etat")):
            return self._status_summary(fr)

        # --- List agents ---
        if "agent" in q and any(w in q for w in ("list", "show", "affiche", "montre", "donne", "liste")):
            return self._agents_summary(fr)

        # --- List tasks ---
        if any(w in q for w in ("task", "tâche", "tache", "jobs")) and any(w in q for w in ("list", "show", "affiche", "montre", "donne", "liste")):
            return self._tasks_summary(fr)

        # --- Credentials ---
        if "credential" in q or "cred" in q:
            return self._creds_summary(fr)

        # --- Findings ---
        if "finding" in q or "trouv" in q:
            return self._findings_summary(fr)

        # --- Alerts ---
        if "alert" in q or "alerte" in q:
            return self._alerts_summary(fr)

        # --- Narrate recent ---
        if "narrate" in q or "recent" in q:
            recent = self.narrate_recent(limit=10)
            if recent == "All quiet on the network.":
                return (
                    "Aucune activité récente à narrer. Le système vient probablement de démarrer."
                    if fr else
                    "No recent log activity to narrate."
                )
            return recent

        # --- Default: weave recent events + general status ---
        recent = self.narrate_recent(limit=8)
        if recent == "All quiet on the network.":
            return self._status_summary(fr)
        prefix = "Voici ce que je vois en ce moment." if fr else "Here's what I'm seeing right now."
        return f"{prefix} {recent}"

    def _greeting(self, fr: bool) -> str:
        stats = self._db_stats()
        if fr:
            return (
                f"Salut ! Je suis Shannon, l'IA de Lucy C2. "
                f"Voici la situation : {stats['agents_online']} agent(s) en ligne sur {stats['agents_total']}, "
                f"{stats['tasks_total']} tâche(s) au total, {stats['creds']} credential(s), "
                f"{stats['findings']} finding(s), {stats['alerts_unread']} alerte(s) non lue(s). "
                f"Tu peux me demander un résumé, la liste des agents, des tâches, ou de narrer les logs récents."
            )
        return (
            f"Hi! I'm Shannon, Lucy C2's AI. "
            f"Current status: {stats['agents_online']} agent(s) online out of {stats['agents_total']}, "
            f"{stats['tasks_total']} task(s) total, {stats['creds']} credential(s), "
            f"{stats['findings']} finding(s), {stats['alerts_unread']} unread alert(s). "
            f"You can ask me for a summary, list agents, list tasks, or narrate recent logs."
        )

    def _help_text(self, fr: bool) -> str:
        if fr:
            return (
                "Voici ce que tu peux me demander :\n"
                "• \"résumé\" — vue d'ensemble de la mission\n"
                "• \"liste les agents\" — agents connectés\n"
                "• \"liste les tâches\" — tâches en cours\n"
                "• \"credentials\" — credentials récoltés\n"
                "• \"findings\" — découvertes\n"
                "• \"alertes\" — alertes non lues\n"
                "• \"narrate recent\" — narration des événements récents\n"
                "• \"narrate logs\" — transformation des logs en dialogue"
            )
        return (
            "Here's what you can ask me:\n"
            "• \"summary\" — mission overview\n"
            "• \"list agents\" — connected agents\n"
            "• \"list tasks\" — running tasks\n"
            "• \"credentials\" — harvested credentials\n"
            "• \"findings\" — discovered findings\n"
            "• \"alerts\" — unread alerts\n"
            "• \"narrate recent\" — narrate recent events\n"
            "• \"narrate logs\" — transform logs into dialogue"
        )

    def _status_summary(self, fr: bool) -> str:
        stats = self._db_stats()
        if fr:
            parts = [f"**Situation actuelle**"]
            parts.append(f"• Agents : {stats['agents_online']} en ligne / {stats['agents_total']} total")
            parts.append(f"• Tâches : {stats['tasks_running']} en cours, {stats['tasks_failed']} échouées, {stats['tasks_total']} total")
            if stats['creds']:
                parts.append(f"• Credentials : {stats['creds']}")
            if stats['findings']:
                parts.append(f"• Findings : {stats['findings']}")
            if stats['alerts_unread']:
                parts.append(f"• Alertes non lues : {stats['alerts_unread']}")
            if not stats['agents_total']:
                parts.append("Aucun agent n'est encore connecté. Construis et déploie un agent pour commencer.")
            return "\n".join(parts)
        parts = ["**Current situation**"]
        parts.append(f"• Agents: {stats['agents_online']} online / {stats['agents_total']} total")
        parts.append(f"• Tasks: {stats['tasks_running']} running, {stats['tasks_failed']} failed, {stats['tasks_total']} total")
        if stats['creds']:
            parts.append(f"• Credentials: {stats['creds']}")
        if stats['findings']:
            parts.append(f"• Findings: {stats['findings']}")
        if stats['alerts_unread']:
            parts.append(f"• Unread alerts: {stats['alerts_unread']}")
        if not stats['agents_total']:
            parts.append("No agents connected yet. Build and deploy an agent to get started.")
        return "\n".join(parts)

    def _agents_summary(self, fr: bool) -> str:
        agents = self._db_agents()
        if not agents:
            return "Aucun agent enregistré. Utilise l'Agent Builder pour en créer un." if fr else "No agents registered. Use the Agent Builder to create one."
        if fr:
            lines = [f"**{len(agents)} agent(s)** :"]
            for a in agents[:10]:
                status_icon = {"online": "🟢", "offline": "🔴", "idle": "🟡"}.get(a.get("status", ""), "⚪")
                lines.append(f"{status_icon} {a.get('hostname', '?')} — {a.get('status', '?')} ({a.get('os', '?')})")
            if len(agents) > 10:
                lines.append(f"... et {len(agents) - 10} autre(s).")
            return "\n".join(lines)
        lines = [f"**{len(agents)} agent(s)**:"]
        for a in agents[:10]:
            status_icon = {"online": "🟢", "offline": "🔴", "idle": "🟡"}.get(a.get("status", ""), "⚪")
            lines.append(f"{status_icon} {a.get('hostname', '?')} — {a.get('status', '?')} ({a.get('os', '?')})")
        if len(agents) > 10:
            lines.append(f"... and {len(agents) - 10} more.")
        return "\n".join(lines)

    def _tasks_summary(self, fr: bool) -> str:
        tasks = self._db_tasks()
        if not tasks:
            return "Aucune tâche enregistrée." if fr else "No tasks recorded."
        running = [t for t in tasks if t.get("status") == "running"]
        failed = [t for t in tasks if t.get("status") == "failed"]
        completed = [t for t in tasks if t.get("status") == "completed"]
        if fr:
            return (f"**Tâches** : {len(running)} en cours, {len(completed)} terminées, {len(failed)} échouées "
                    f"(total: {len(tasks)}).")
        return (f"**Tasks**: {len(running)} running, {len(completed)} completed, {len(failed)} failed "
                f"(total: {len(tasks)}).")

    def _creds_summary(self, fr: bool) -> str:
        count = self._db_count("Credential")
        if fr:
            return f"**Credentials** : {count} credential(s) récolté(s)." if count else "Aucun credential récolté pour le moment."
        return f"**Credentials**: {count} harvested." if count else "No credentials harvested yet."

    def _findings_summary(self, fr: bool) -> str:
        count = self._db_count("Finding")
        if fr:
            return f"**Findings** : {count} finding(s)." if count else "Aucun finding pour le moment."
        return f"**Findings**: {count}." if count else "No findings yet."

    def _alerts_summary(self, fr: bool) -> str:
        count = self._db_count("AlertEvent", extra_filter="read = 0")
        if fr:
            return f"**Alertes** : {count} alerte(s) non lue(s)." if count else "Aucune alerte non lue. Tout va bien."
        return f"**Alerts**: {count} unread." if count else "No unread alerts. All clear."

    # --- DB helpers ---

    def _db_stats(self) -> dict[str, int]:
        try:
            from database import database
            from db.models import Agent, Task, Credential, Finding, AlertEvent
            with database:
                agents = list(Agent.select())
                tasks = list(Task.select())
                creds = Credential.select().count()
                findings = Finding.select().count()
                alerts_unread = AlertEvent.select().where(AlertEvent.read == False).count()
                return {
                    "agents_total": len(agents),
                    "agents_online": sum(1 for a in agents if a.status == "online"),
                    "tasks_total": len(tasks),
                    "tasks_running": sum(1 for t in tasks if t.status == "running"),
                    "tasks_failed": sum(1 for t in tasks if t.status == "failed"),
                    "creds": creds,
                    "findings": findings,
                    "alerts_unread": alerts_unread,
                }
        except Exception as exc:
            logger.debug("ShannonAi DB stats failed: %s", exc)
            return {k: 0 for k in (
                "agents_total", "agents_online", "tasks_total",
                "tasks_running", "tasks_failed", "creds", "findings", "alerts_unread",
            )}

    def _db_agents(self) -> list[dict]:
        try:
            from database import database
            from db.models import Agent
            with database:
                return [a.to_dict() for a in Agent.select().limit(20)]
        except Exception:
            return []

    def _db_tasks(self) -> list[dict]:
        try:
            from database import database
            from db.models import Task
            with database:
                return [t.to_dict() for t in Task.select().limit(50)]
        except Exception:
            return []

    def _db_count(self, model_name: str, extra_filter: str = "") -> int:
        try:
            from database import database
            from db import models as m
            model = getattr(m, model_name, None)
            if not model:
                return 0
            with database:
                q = model.select()
                if extra_filter:
                    q = q.where(SQL(extra_filter))
                return q.count()
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


# Shared singleton instance
shannon = ShannonAi()
