"""
Tests for the predictive alerting engine.

Run:
    cd backend
    pytest tests/test_predictive_alerting.py -v
"""
import pytest
from datetime import datetime, timedelta, timezone


@pytest.fixture(scope="session", autouse=True)
def setup_test_db(tmp_path_factory):
    import os

    tmp = tmp_path_factory.mktemp("db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test_lucy.db"
    os.environ["DEBUG"] = "true"
    os.environ["ADMIN_USERNAME"] = "testadmin"
    os.environ["ADMIN_PASSWORD"] = "testpassword"


@pytest.fixture
def fresh_engine():
    """Provide a fresh singleton instance for each test."""
    from core.predictive_alerting import PredictiveAlertEngine
    engine = PredictiveAlertEngine()
    engine._predictions.clear()
    return engine


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate predictive-relevant tables before each test."""
    from database import database
    from db.models import Agent, Task, Credential, Log

    with database:
        Task.delete().execute()
        Credential.delete().execute()
        Log.delete().execute()
        Agent.delete().execute()
    yield


def _seed_agent_and_tasks(
    failed: int = 0,
    completed: int = 0,
    hours_back: int = 24,
    failed_in_last_hour: int = 0,
):
    from database import database
    from db.models import Agent, Task

    now = datetime.now(timezone.utc)
    with database:
        agent = Agent.create(
            hostname="testhost",
            os="windows",
            username="testuser",
            first_seen=now - timedelta(hours=hours_back),
            last_seen=now,
            status="online",
        )
        # Baseline tasks spread over the previous 23 hours
        for i in range(failed):
            Task.create(
                agent=agent,
                module="shell",
                action="run",
                status="failed",
                created_at=now - timedelta(hours=1, minutes=(i + 1) * 5),
            )
        for i in range(completed):
            Task.create(
                agent=agent,
                module="info",
                action="run",
                status="completed",
                created_at=now - timedelta(hours=1, minutes=(i + 1) * 5 + 2),
            )
        # Spike tasks in the last hour
        for i in range(failed_in_last_hour):
            Task.create(
                agent=agent,
                module="shell",
                action="run",
                status="failed",
                created_at=now - timedelta(minutes=i * 5),
            )
    return agent


class TestStatisticsHelpers:
    def test_mean_and_stdev(self):
        from core.predictive_alerting import _mean, _stdev

        values = [3.0, 5.0, 7.0]
        assert _mean(values) == 5.0
        assert _stdev(values) == 2.0

    def test_z_score(self):
        from core.predictive_alerting import _z_score

        assert _z_score(7.0, 5.0, 2.0) == 1.0
        assert _z_score(5.0, 5.0, 2.0) == 0.0
        assert _z_score(7.0, 5.0, 0.0) == 0.0


class TestPredictiveAlertEngine:
    @pytest.mark.asyncio
    async def test_task_failure_spike(self, fresh_engine):
        _seed_agent_and_tasks(failed=5, completed=15, failed_in_last_hour=12)
        predictions = await fresh_engine.run_analysis()
        assert any(p["kind"] == "task_failure_spike" for p in predictions)

    @pytest.mark.asyncio
    async def test_no_predictions_with_normal_data(self, fresh_engine):
        _seed_agent_and_tasks(failed=0, completed=3, hours_back=2)
        predictions = await fresh_engine.run_analysis()
        assert not predictions

    @pytest.mark.asyncio
    async def test_predictions_are_stored(self, fresh_engine):
        _seed_agent_and_tasks(failed=5, completed=15, failed_in_last_hour=12)
        await fresh_engine.run_analysis()
        stored = fresh_engine.get_predictions()
        assert len(stored) >= 1
        assert all("id" in p and "timestamp" in p for p in stored)

    @pytest.mark.asyncio
    async def test_get_active_threats(self, fresh_engine):
        _seed_agent_and_tasks(failed=5, completed=15, failed_in_last_hour=12)
        await fresh_engine.run_analysis()
        active = fresh_engine.get_active_threats()
        assert all(p["severity"] in ("warning", "critical") for p in active)
