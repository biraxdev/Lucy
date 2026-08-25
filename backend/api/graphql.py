"""
GraphQL API for Project Lucy — alternative to the REST endpoints.

Exposes agents, tasks, credentials, logs, findings and alert events.
Provides a few mutations to dispatch tasks and fire alerts.

Endpoint: POST /graphql
"""
from datetime import datetime, timezone
from typing import Any

import graphene
import json
from fastapi import APIRouter
from graphene import ObjectType, Schema, String, Int, Boolean, List, Field, ID, Mutation
from starlette_graphene3 import GraphQLApp

from config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat() if not value.tzinfo else value.isoformat()


def _resolve_peewee_list(model, limit: int = 100, **filters):
    query = model.select()
    for field, value in filters.items():
        if value is not None:
            query = query.where(getattr(model, field) == value)
    return [item.to_dict() for item in query.limit(limit)]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AgentType(ObjectType):
    id = ID()
    hostname = String()
    os = String()
    username = String()
    ip_public = String()
    ip_private = String()
    architecture = String()
    status = String()
    first_seen = String()
    last_seen = String()
    tags = List(String)
    metadata = String()


class TaskType(ObjectType):
    id = ID()
    agent_id = ID()
    module = String()
    action = String()
    status = String()
    priority = String()
    params = String()
    result = String()
    error = String()
    created_at = String()
    executed_at = String()


class CredentialType(ObjectType):
    id = ID()
    agent_id = ID()
    url = String()
    hostname = String()
    username = String()
    source = String()
    confidence = String()
    tags = List(String)
    metadata = String()
    captured_at = String()


class LogType(ObjectType):
    id = ID()
    agent_id = ID()
    level = String()
    module = String()
    message = String()
    log_type = String()
    timestamp = String()


class AlertEventType(ObjectType):
    id = ID()
    event = String()
    title = String()
    message = String()
    severity = String()
    agent_id = ID()
    read = Boolean()
    timestamp = String()


class FindingType(ObjectType):
    id = ID()
    title = String()
    severity = String()
    status = String()
    description = String()
    recommendation = String()
    cvss = String()
    agent_id = ID()
    created_at = String()
    updated_at = String()


class StatsType(ObjectType):
    agents_total = Int()
    agents_online = Int()
    tasks_total = Int()
    tasks_failed = Int()
    credentials_total = Int()
    logs_total = Int()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

class Query(ObjectType):
    agents = List(AgentType, status=String(), limit=Int(default_value=100))
    agent = Field(AgentType, id=ID(required=True))

    tasks = List(TaskType, agent_id=ID(), status=String(), limit=Int(default_value=100))
    task = Field(TaskType, id=ID(required=True))

    credentials = List(CredentialType, agent_id=ID(), source=String(), limit=Int(default_value=100))
    credential = Field(CredentialType, id=ID(required=True))

    logs = List(LogType, agent_id=ID(), level=String(), limit=Int(default_value=100))
    log = Field(LogType, id=ID(required=True))

    alerts = List(AlertEventType, severity=String(), limit=Int(default_value=100))
    alert = Field(AlertEventType, id=ID(required=True))

    findings = List(FindingType, severity=String(), status=String(), limit=Int(default_value=100))
    finding = Field(FindingType, id=ID(required=True))

    stats = Field(StatsType)

    # --- Resolvers ---

    def resolve_agents(self, info, status=None, limit=100):
        from db.models import Agent
        query = Agent.select()
        if status:
            query = query.where(Agent.status == status)
        return [AgentType(**{k: v for k, v in a.to_dict().items() if k in AgentType._meta.fields}) for a in query.limit(limit)]

    def resolve_agent(self, info, id):
        from db.models import Agent
        agent = Agent.get_or_none(Agent.id == id)
        return AgentType(**{k: v for k, v in agent.to_dict().items() if k in AgentType._meta.fields}) if agent else None

    def resolve_tasks(self, info, agent_id=None, status=None, limit=100):
        from db.models import Task
        query = Task.select()
        if agent_id:
            query = query.where(Task.agent == agent_id)
        if status:
            query = query.where(Task.status == status)
        return [TaskType(**{k: v for k, v in t.to_dict().items() if k in TaskType._meta.fields}) for t in query.limit(limit)]

    def resolve_task(self, info, id):
        from db.models import Task
        task = Task.get_or_none(Task.id == id)
        return TaskType(**{k: v for k, v in task.to_dict().items() if k in TaskType._meta.fields}) if task else None

    def resolve_credentials(self, info, agent_id=None, source=None, limit=100):
        from db.models import Credential
        query = Credential.select()
        if agent_id:
            query = query.where(Credential.agent == agent_id)
        if source:
            query = query.where(Credential.source == source)
        return [CredentialType(**{k: v for k, v in c.to_dict().items() if k in CredentialType._meta.fields}) for c in query.limit(limit)]

    def resolve_credential(self, info, id):
        from db.models import Credential
        credential = Credential.get_or_none(Credential.id == id)
        return CredentialType(**{k: v for k, v in credential.to_dict().items() if k in CredentialType._meta.fields}) if credential else None

    def resolve_logs(self, info, agent_id=None, level=None, limit=100):
        from db.models import Log
        query = Log.select().order_by(Log.timestamp.desc())
        if agent_id:
            query = query.where(Log.agent == agent_id)
        if level:
            query = query.where(Log.level == level)
        return [LogType(**{k: v for k, v in l.to_dict().items() if k in LogType._meta.fields}) for l in query.limit(limit)]

    def resolve_log(self, info, id):
        from db.models import Log
        log = Log.get_or_none(Log.id == id)
        return LogType(**{k: v for k, v in log.to_dict().items() if k in LogType._meta.fields}) if log else None

    def resolve_alerts(self, info, severity=None, limit=100):
        from db.models import AlertEvent
        query = AlertEvent.select().order_by(AlertEvent.timestamp.desc())
        if severity:
            query = query.where(AlertEvent.severity == severity)
        return [AlertEventType(**{k: v for k, v in a.to_dict().items() if k in AlertEventType._meta.fields}) for a in query.limit(limit)]

    def resolve_alert(self, info, id):
        from db.models import AlertEvent
        alert = AlertEvent.get_or_none(AlertEvent.id == id)
        return AlertEventType(**{k: v for k, v in alert.to_dict().items() if k in AlertEventType._meta.fields}) if alert else None

    def resolve_findings(self, info, severity=None, status=None, limit=100):
        from db.models import Finding
        query = Finding.select().order_by(Finding.created_at.desc())
        if severity:
            query = query.where(Finding.severity == severity)
        if status:
            query = query.where(Finding.status == status)
        return [FindingType(**{k: v for k, v in f.to_dict().items() if k in FindingType._meta.fields}) for f in query.limit(limit)]

    def resolve_finding(self, info, id):
        from db.models import Finding
        finding = Finding.get_or_none(Finding.id == id)
        return FindingType(**{k: v for k, v in finding.to_dict().items() if k in FindingType._meta.fields}) if finding else None

    def resolve_stats(self, info):
        from db.models import Agent, Task, Credential, Log
        return StatsType(
            agents_total=Agent.select().count(),
            agents_online=Agent.select().where(Agent.status == "online").count(),
            tasks_total=Task.select().count(),
            tasks_failed=Task.select().where(Task.status == "failed").count(),
            credentials_total=Credential.select().count(),
            logs_total=Log.select().count(),
        )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

class CreateTask(Mutation):
    class Arguments:
        agent_id = ID(required=True)
        module = String(required=True)
        action = String(required=True)
        params = String()
        priority = String()

    task = Field(TaskType)

    @staticmethod
    def mutate(root, info, agent_id, module, action, params=None, priority="normal"):
        from db.models import Agent, Task

        agent = Agent.get_or_none(Agent.id == agent_id)
        if not agent:
            raise graphene.GraphQLError("Agent not found")

        params_dict = json.loads(params) if params else {}
        task = Task.create(
            agent=agent,
            module=module,
            action=action,
            params=json.dumps(params_dict),
            priority=priority,
        )
        return CreateTask(task=TaskType(**{k: v for k, v in task.to_dict().items() if k in TaskType._meta.fields}))


class UpdateTaskStatus(Mutation):
    class Arguments:
        id = ID(required=True)
        status = String(required=True)

    task = Field(TaskType)

    @staticmethod
    def mutate(root, info, id, status):
        from db.models import Task

        task = Task.get_or_none(Task.id == id)
        if not task:
            raise graphene.GraphQLError("Task not found")
        task.status = status
        task.save()
        return UpdateTaskStatus(task=TaskType(**{k: v for k, v in task.to_dict().items() if k in TaskType._meta.fields}))


class Mutation(ObjectType):
    create_task = CreateTask.Field()
    update_task_status = UpdateTaskStatus.Field()


# ---------------------------------------------------------------------------
# Schema and router
# ---------------------------------------------------------------------------

schema = Schema(query=Query, mutation=Mutation)

graphql_app = GraphQLApp(schema=schema)
graphql_app.__name__ = "GraphQLApp"
graphql_app.__module__ = "api.graphql"

router = APIRouter()
router.add_route("/graphql", graphql_app)
