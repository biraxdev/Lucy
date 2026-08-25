"""
Orchestrator — timeline execution engine for Project Lucy.
Manages step sequencing, group dispatch, triggers, and loop scheduling.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from database import database
from db.models import Agent, AgentGroup, Task, Timeline

logger = logging.getLogger(__name__)


class Orchestrator:
    """Singleton timeline orchestrator."""

    _instance: Optional["Orchestrator"] = None

    def __new__(cls) -> "Orchestrator":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._running: dict[str, asyncio.Task] = {}
            inst._loop_tasks: dict[str, asyncio.Task] = {}
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Execute a timeline now
    # ------------------------------------------------------------------

    async def execute(self, timeline_id: str, agent_ids: list[str] | None = None) -> dict:
        """
        Execute a timeline immediately.
        If agent_ids is None, resolves from the timeline's agent_group field.
        Returns {dispatched: int, timeline_id: str}
        """
        tl = Timeline.get_or_none(Timeline.id == timeline_id)
        if not tl:
            raise ValueError(f"Timeline {timeline_id} not found")

        steps = tl.steps_list
        if not steps:
            raise ValueError("Timeline has no steps")

        if agent_ids is None:
            agent_ids = self._resolve_agents(tl)

        if not agent_ids:
            logger.warning("Timeline %s: no agents resolved, nothing to dispatch.", timeline_id)
            return {"dispatched": 0, "timeline_id": timeline_id}

        with database:
            Timeline.update(status="active").where(Timeline.id == timeline_id).execute()

        dispatched = 0
        for agent_id in agent_ids:
            asyncio.create_task(self._run_steps(tl, steps, agent_id))
            dispatched += 1

        return {"dispatched": dispatched, "timeline_id": timeline_id}

    async def _run_steps(self, tl, steps: list[dict], agent_id: str) -> None:
        """Execute each step sequentially for one agent."""
        from core.ws_manager import ConnectionManager, build_message
        manager = ConnectionManager()

        for step in sorted(steps, key=lambda s: s.get("order", 0)):
            delay = float(step.get("delay", 0))
            if delay:
                await asyncio.sleep(delay)

            module = step.get("module", "")
            action = step.get("action", "run")
            params = step.get("params", {})
            timeout = int(step.get("timeout", 60))

            # Strip internal underscore-prefixed metadata before sending to agent.
            # Task retains the full params for frontend live-tracking (e.g. _node_id).
            agent_params = {k: v for k, v in params.items() if not k.startswith("_")}

            task = self._create_task(
                agent_id=agent_id,
                module=module,
                action=action,
                params=params,
                timeout=timeout,
                timeline_id=str(tl.id),
                priority=step.get("priority", "normal"),
            )

            msg = build_message("task", {
                "task_id": str(task.id),
                "module": module,
                "action": action,
                "params": agent_params,
                "timeout": timeout,
            }, agent_id=agent_id)

            conn = manager._agents.get(agent_id)
            if conn:
                await conn.send(msg)
            else:
                conn_obj = manager._agents.get(agent_id)
                if conn_obj:
                    conn_obj.enqueue_offline(msg)
                logger.warning("Agent %s offline, task %s queued.", agent_id, task.id)

        with database:
            Timeline.update(status="completed").where(Timeline.id == tl.id).execute()

    def _create_task(
        self,
        agent_id: str,
        module: str,
        action: str,
        params: dict,
        timeout: int,
        timeline_id: str,
        priority: str = "normal",
    ) -> Task:
        with database:
            return Task.create(
                agent=agent_id,
                module=module,
                action=action,
                params=json.dumps(params),
                timeout=timeout,
                status="queued",
                priority=priority,
                timeline_id=timeline_id,
            )

    # ------------------------------------------------------------------
    # Agent resolution
    # ------------------------------------------------------------------

    def _resolve_agents(self, tl) -> list[str]:
        group_ids = tl.agent_group_list
        agent_ids: set[str] = set()

        for gid in group_ids:
            if gid == "all":
                ids = [str(a.id) for a in Agent.select(Agent.id).where(Agent.status == "online")]
                agent_ids.update(ids)
                continue

            group = AgentGroup.get_or_none(AgentGroup.id == gid)
            if not group:
                continue

            if group.dynamic_query:
                ids = self._eval_dynamic_query(group.dynamic_query)
            else:
                members = json.loads(group.members or "[]")
                ids = members

            agent_ids.update(ids)

        return list(agent_ids)

    def _eval_dynamic_query(self, query: str) -> list[str]:
        """
        Evaluate a simple dynamic group query.
        Supported: os = "value", status = "value", last_seen > NOW() - INTERVAL X HOUR
        Returns list of matching agent IDs.
        """
        from datetime import timedelta
        import re

        conditions = []
        query = query.strip()

        for part in re.split(r"\s+AND\s+", query, flags=re.IGNORECASE):
            part = part.strip()
            m = re.match(r'(\w+)\s*=\s*["\']?([^"\']+)["\']?', part)
            if m:
                field, value = m.group(1).lower(), m.group(2).strip()
                if field == "os":
                    conditions.append(Agent.os == value)
                elif field == "status":
                    conditions.append(Agent.status == value)
                elif field == "username":
                    conditions.append(Agent.username == value)
                continue

            m = re.match(r"last_seen\s*>\s*NOW\(\)\s*-\s*INTERVAL\s+(\d+)\s+HOUR", part, re.IGNORECASE)
            if m:
                hours = int(m.group(1))
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                conditions.append(Agent.last_seen >= cutoff)

        if not conditions:
            return []

        q = Agent.select(Agent.id)
        for cond in conditions:
            q = q.where(cond)

        return [str(a.id) for a in q]

    # ------------------------------------------------------------------
    # Trigger loop (cron-based)
    # ------------------------------------------------------------------

    async def start_scheduler(self) -> None:
        asyncio.create_task(self._scheduler_loop())

    async def _scheduler_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self._check_scheduled_timelines()
            except Exception as exc:
                logger.error("Scheduler error: %s", exc)

    async def _check_scheduled_timelines(self) -> None:
        timelines = list(
            Timeline.select().where(
                (Timeline.status == "active") & (Timeline.trigger.startswith("schedule"))
            )
        )
        now = datetime.now(timezone.utc)
        for tl in timelines:
            try:
                from croniter import croniter
                cron_expr = tl.trigger.replace("schedule(", "").rstrip(")")
                cron = croniter(cron_expr, now)
                prev = cron.get_prev(datetime)
                if (now - prev).total_seconds() < 60:
                    await self.execute(str(tl.id))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # On-connect trigger
    # ------------------------------------------------------------------

    async def on_agent_connect(self, agent_id: str) -> None:
        """Called when an agent connects — fires on_connect timelines."""
        timelines = list(
            Timeline.select().where(
                (Timeline.status == "active") & (Timeline.trigger == "on_connect")
            )
        )
        for tl in timelines:
            agents = self._resolve_agents(tl)
            if agent_id in agents:
                await self.execute(str(tl.id), agent_ids=[agent_id])

    # ------------------------------------------------------------------
    # Loop (repeat) scheduler
    # ------------------------------------------------------------------

    async def schedule_loop(self, timeline_id: str, interval_seconds: int) -> None:
        async def _loop():
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    await self.execute(timeline_id)
                except Exception as exc:
                    logger.error("Loop timeline %s error: %s", timeline_id, exc)

        task = asyncio.create_task(_loop())
        self._loop_tasks[timeline_id] = task

    def cancel_loop(self, timeline_id: str) -> None:
        task = self._loop_tasks.pop(timeline_id, None)
        if task:
            task.cancel()
