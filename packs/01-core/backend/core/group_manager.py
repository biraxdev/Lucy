"""
Agent Group Manager for Project Lucy.
Supports static member lists and dynamic SQL-like queries.
"""
import json
import logging
from typing import Optional

from database import database
from db.models import Agent, AgentGroup

logger = logging.getLogger(__name__)


class GroupManager:
    _instance: Optional["GroupManager"] = None

    def __new__(cls) -> "GroupManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_group(
        self,
        name: str,
        description: str = "",
        members: list[str] | None = None,
        dynamic_query: str | None = None,
        color: str = "#22c55e",
    ) -> AgentGroup:
        with database:
            group = AgentGroup.create(
                name=name,
                description=description,
                members=json.dumps(members or []),
                dynamic_query=dynamic_query or "",
                color=color,
            )
        return group

    def add_member(self, group_id: str, agent_id: str) -> AgentGroup:
        group = AgentGroup.get_by_id(group_id)
        members = json.loads(group.members or "[]")
        if agent_id not in members:
            members.append(agent_id)
        with database:
            AgentGroup.update(members=json.dumps(members)).where(AgentGroup.id == group_id).execute()
        return AgentGroup.get_by_id(group_id)

    def remove_member(self, group_id: str, agent_id: str) -> AgentGroup:
        group = AgentGroup.get_by_id(group_id)
        members = json.loads(group.members or "[]")
        members = [m for m in members if m != agent_id]
        with database:
            AgentGroup.update(members=json.dumps(members)).where(AgentGroup.id == group_id).execute()
        return AgentGroup.get_by_id(group_id)

    def resolve_members(self, group_id: str) -> list[str]:
        """Resolve the effective agent IDs for a group (static or dynamic)."""
        group = AgentGroup.get_or_none(AgentGroup.id == group_id)
        if not group:
            return []

        if group.dynamic_query:
            return self._eval_dynamic(group.dynamic_query)
        return json.loads(group.members or "[]")

    def _eval_dynamic(self, query: str) -> list[str]:
        """Evaluate a simple dynamic query and return matching agent IDs."""
        import re
        from datetime import datetime, timezone, timedelta

        conditions = []
        for part in re.split(r"\s+AND\s+", query.strip(), flags=re.IGNORECASE):
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
                elif field == "architecture":
                    conditions.append(Agent.architecture == value)
                continue

            m = re.match(r"last_seen\s*>\s*NOW\(\)\s*-\s*INTERVAL\s+(\d+)\s+HOUR", part, re.IGNORECASE)
            if m:
                hours = int(m.group(1))
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                conditions.append(Agent.last_seen >= cutoff)

        if not conditions:
            return []

        q = Agent.select(Agent.id)
        for c in conditions:
            q = q.where(c)

        return [str(a.id) for a in q]

    def list_groups(self) -> list[dict]:
        return [g.to_dict() for g in AgentGroup.select().order_by(AgentGroup.name)]

    def get_group(self, group_id: str) -> AgentGroup | None:
        return AgentGroup.get_or_none(AgentGroup.id == group_id)

    def delete_group(self, group_id: str) -> bool:
        n = AgentGroup.delete().where(AgentGroup.id == group_id).execute()
        return n > 0

    def update_group(self, group_id: str, **kwargs) -> AgentGroup:
        if "members" in kwargs and isinstance(kwargs["members"], list):
            kwargs["members"] = json.dumps(kwargs["members"])
        with database:
            AgentGroup.update(**kwargs).where(AgentGroup.id == group_id).execute()
        return AgentGroup.get_by_id(group_id)
