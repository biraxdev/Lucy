"""
Tests for the GraphQL endpoint (/graphql) as an alternative to REST.

Run:
    cd backend
    pytest tests/test_graphql.py -v
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def gql_client():
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_graphql_data():
    from database import database

    with database:
        database.execute_sql("PRAGMA foreign_keys = OFF")
        database.execute_sql("DELETE FROM tasks")
        database.execute_sql("DELETE FROM agents")
        database.execute_sql("PRAGMA foreign_keys = ON")
    yield


@pytest.fixture
def auth_headers(gql_client):
    resp = gql_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _query(client, query, headers=None):
    return client.post(
        "/graphql",
        json={"query": query},
        headers=headers or {},
    )


class TestGraphQLQueries:
    def test_stats_requires_auth(self, gql_client):
        resp = _query(gql_client, "{ stats { agentsTotal tasksTotal } }")
        assert resp.status_code == 401

    def test_stats_authenticated(self, gql_client, auth_headers):
        resp = _query(gql_client, "{ stats { agentsTotal tasksTotal } }", auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "errors" not in body
        assert body["data"]["stats"]["agentsTotal"] == 0

    def test_agents_and_tasks(self, gql_client, auth_headers):
        from database import database
        from db.models import Agent, Task

        with database:
            agent = Agent.create(
                hostname="gqlhost",
                os="linux",
                username="root",
                status="online",
            )
            Task.create(
                agent=agent,
                module="shell",
                action="whoami",
                status="completed",
            )

        resp = _query(
            gql_client,
            "{ agents { id hostname status } tasks { id module status } }",
            auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "errors" not in body
        assert len(body["data"]["agents"]) == 1
        assert body["data"]["agents"][0]["hostname"] == "gqlhost"
        assert len(body["data"]["tasks"]) == 1


class TestGraphQLMutations:
    def test_create_task(self, gql_client, auth_headers):
        from database import database
        from db.models import Agent

        with database:
            agent = Agent.create(
                hostname="gqlhost",
                os="linux",
                username="root",
                status="online",
            )
            agent_id = str(agent.id)

        resp = _query(
            gql_client,
            f'mutation {{ createTask(agentId: "{agent_id}", module: "shell", action: "whoami") {{ task {{ id module status }} }} }}',
            auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "errors" not in body, body
        assert body["data"]["createTask"]["task"]["module"] == "shell"
        assert body["data"]["createTask"]["task"]["status"] == "queued"

    def test_update_task_status(self, gql_client, auth_headers):
        from database import database
        from db.models import Agent, Task

        with database:
            agent = Agent.create(
                hostname="gqlhost",
                os="linux",
                username="root",
                status="online",
            )
            task = Task.create(
                agent=agent,
                module="shell",
                action="whoami",
                status="queued",
            )
            task_id = str(task.id)

        resp = _query(
            gql_client,
            f'mutation {{ updateTaskStatus(id: "{task_id}", status: "running") {{ task {{ id status }} }} }}',
            auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "errors" not in body, body
        assert body["data"]["updateTaskStatus"]["task"]["status"] == "running"
