"""
Live agent activity heatmap engine.

Produces a matrix of activity intensity usable by frontend heatmap libraries
(e.g., Chart.js matrix, D3, ECharts). Two modes:
  - "time"  : 24 hours x 7 days (default), aggregated across all agents.
  - "agent" : agents x hours, aggregated over the last N hours.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from database import database
from db.models import Agent, Credential, FileEvent, Log, Task


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class HeatmapEngine:
    """Compute activity heatmaps from task, log, credential and file events."""

    def heatmap(
        self,
        by: str = "time",
        hours_window: int = 24,
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if by == "agent":
            return self._agent_heatmap(hours_window, tenant_id)
        return self._time_heatmap(tenant_id)

    # ------------------------------------------------------------------
    # Time-based heatmap : 24 hours x 7 days
    # ------------------------------------------------------------------
    def _time_heatmap(self, tenant_id: Optional[str]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)

        activities = self._collect_activities(start, tenant_id)

        # Matrix: 7 rows (days) x 24 columns (hours)
        matrix = [[0 for _ in range(24)] for _ in range(7)]
        for ts, _ in activities:
            dt = self._normalize_dt(ts)
            if dt is None or dt < start or dt > now:
                continue
            day_index = dt.weekday()
            hour = dt.hour
            matrix[day_index][hour] += 1

        flat = []
        for day_index, row in enumerate(matrix):
            for hour, value in enumerate(row):
                flat.append({"x": hour, "y": _DAYS[day_index], "v": value})

        max_v = max((c["v"] for c in flat), default=0)

        return {
            "mode": "time",
            "x_label": "Hour of day (UTC)",
            "y_label": "Day of week",
            "x_axis": list(range(24)),
            "y_axis": _DAYS,
            "max": max_v,
            "cells": flat,
        }

    # ------------------------------------------------------------------
    # Agent-based heatmap : agents x hours over the last N hours
    # ------------------------------------------------------------------
    def _agent_heatmap(self, hours_window: int, tenant_id: Optional[str]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours_window)

        # Build hour buckets (start hour -> end hour)
        bucket_count = min(hours_window, 24)
        bucket_start = now - timedelta(hours=bucket_count)
        buckets: list[datetime] = [bucket_start + timedelta(hours=i) for i in range(bucket_count)]
        bucket_labels = [b.strftime("%H:%M") for b in buckets]

        with database:
            agents = list(Agent.select())
            if tenant_id:
                agents = [a for a in agents if str(a.tenant_id) == tenant_id]

        agent_names = [a.hostname or str(a.id) for a in agents]
        agent_ids = [str(a.id) for a in agents]
        matrix = {aid: [0] * bucket_count for aid in agent_ids}

        activities = self._collect_activities(start, tenant_id)
        for ts, agent_id in activities:
            if not agent_id:
                continue
            dt = self._normalize_dt(ts)
            if dt is None or dt < bucket_start or dt > now:
                continue
            # find bucket index
            for idx, bucket in enumerate(buckets):
                if idx == len(buckets) - 1 or (bucket <= dt < buckets[idx + 1]):
                    if agent_id in matrix:
                        matrix[agent_id][idx] += 1
                    break

        flat = []
        for idx, agent_id in enumerate(agent_ids):
            for bidx, value in enumerate(matrix[agent_id]):
                flat.append({"x": bidx, "y": agent_names[idx], "v": value})

        max_v = max((c["v"] for c in flat), default=0)

        return {
            "mode": "agent",
            "x_label": f"Last {bucket_count} hours",
            "y_label": "Agent",
            "x_axis": bucket_labels,
            "y_axis": agent_names,
            "max": max_v,
            "cells": flat,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize_dt(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return None
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------
    def _collect_activities(self, start: datetime, tenant_id: Optional[str]):
        """Yield (timestamp, agent_id) tuples for tasks, logs, credentials and file events."""
        with database:
            # Tasks created
            query = Task.select().where(Task.created_at >= start)
            if tenant_id and hasattr(Task, "tenant_id"):
                query = query.where(Task.tenant_id == tenant_id)
            for row in query:
                yield (row.created_at, str(row.agent_id) if row.agent_id else None)

            # Logs
            query = Log.select().where(Log.timestamp >= start)
            if tenant_id and hasattr(Log, "tenant_id"):
                query = query.where(Log.tenant_id == tenant_id)
            for row in query:
                yield (row.timestamp, str(row.agent_id) if row.agent_id else None)

            # Credentials
            query = Credential.select().where(Credential.captured_at >= start)
            if tenant_id and hasattr(Credential, "tenant_id"):
                query = query.where(Credential.tenant_id == tenant_id)
            for row in query:
                yield (row.captured_at, str(row.agent_id) if row.agent_id else None)

            # File events
            query = FileEvent.select().where(FileEvent.timestamp >= start)
            if tenant_id and hasattr(FileEvent, "tenant_id"):
                query = query.where(FileEvent.tenant_id == tenant_id)
            for row in query:
                yield (row.timestamp, str(row.agent_id) if row.agent_id else None)


def heatmap(by: str = "time", hours_window: int = 24, tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Convenience wrapper."""
    return HeatmapEngine().heatmap(by=by, hours_window=hours_window, tenant_id=tenant_id)
