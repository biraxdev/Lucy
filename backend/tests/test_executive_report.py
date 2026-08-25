"""
Tests for the executive report with AI summary and embedded charts.
"""
import json
import pytest
from pathlib import Path

from database import database
from db.models import Agent, Task, Credential, Finding
from core.report_engine import ReportEngine, REPORTS_DIR


def _load_json_result(result: dict) -> dict:
    return json.loads(Path(result["path"]).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean_report_data():
    with database:
        Task.delete().execute()
        Credential.delete().execute()
        Finding.delete().execute()
        Agent.delete().execute()
    yield


class TestExecutiveReport:
    @pytest.fixture
    def engine(self):
        return ReportEngine()

    def test_executive_report_has_ai_summary(self, engine):
        with database:
            Agent.create(hostname="target-1", os="windows", status="online", username="user1")
        result = engine.generate("executive", "json")
        data = _load_json_result(result)
        assert "executive_summary" in data
        assert "key_takeaways" in data
        assert "target-1" in data["executive_summary"] or "1 agent" in data["executive_summary"]

    def test_executive_report_has_charts(self, engine):
        with database:
            Agent.create(hostname="target-1", os="windows", status="online", username="user1")
            Task.create(agent=Agent.get(), module="keylog", status="completed", action="run", params="{}")
        result = engine.generate("executive", "json")
        data = _load_json_result(result)
        assert "charts" in data
        assert "tasks_pie" in data["charts"]
        assert "modules_bar" in data["charts"]
        assert "os_pie" in data["charts"]
        assert "creds_bar" in data["charts"]
        assert "severity_bar" in data["charts"]
        assert "<svg" in data["charts"]["tasks_pie"]

    def test_executive_html_uses_template(self, engine):
        with database:
            Agent.create(hostname="target-2", os="linux", status="offline", username="user2")
        result = engine.generate("executive", "html")
        path = Path(result["path"])
        assert path.exists()
        html = path.read_text(encoding="utf-8")
        assert "AI-Generated Executive Summary" in html
        assert "<svg" in html
        assert "Executive Engagement Report" in html

    def test_report_data_summary(self, engine):
        with database:
            a = Agent.create(hostname="target-3", os="windows", status="online", username="user3")
            Task.create(agent=a, module="shell", status="completed", action="run", params="{}")
            Task.create(agent=a, module="info", status="failed", action="run", params="{}")
            Credential.create(agent=a, username="alice", source="chrome", confidence="high", url="https://example.com", password_encrypted="encrypted_stub")
        result = engine.generate("executive", "json")
        data = _load_json_result(result)
        s = data["summary"]
        assert s["total_agents"] == 1
        assert s["total_tasks"] == 2
        assert s["completed_tasks"] == 1
        assert s["failed_tasks"] == 1
        assert s["total_credentials"] == 1
        assert "chrome" in data["cred_by_source"]

    def test_top_modules_in_data(self, engine):
        with database:
            a = Agent.create(hostname="target-4", os="macos", status="online", username="user4")
            Task.create(agent=a, module="shell", status="completed", action="run", params="{}")
            Task.create(agent=a, module="shell", status="completed", action="run", params="{}")
            Task.create(agent=a, module="info", status="completed", action="run", params="{}")
        result = engine.generate("executive", "json")
        data = _load_json_result(result)
        top = data["top_modules"]
        assert any(m[0] == "shell" and m[1] == 2 for m in top)
