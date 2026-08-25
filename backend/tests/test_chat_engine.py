"""
Tests for the Lucy chat engine (intent parsing and persona rendering).

Run from the backend directory:
    python -m pytest tests/test_chat_engine.py -v
"""
import pytest

from core.chat_engine import ChatEngine
from core.chat_intents import Intent
from core.chat_persona import PersonaRenderer


class TestIntentParser:
    @pytest.fixture
    def engine(self):
        return ChatEngine()

    def test_greeting(self, engine):
        intent = engine.parse("hello Lucy")
        assert intent.name == "GREETING"

    def test_agent_status(self, engine):
        intent = engine.parse("check on Agent 01")
        assert intent.name == "AGENT_STATUS"
        assert intent.params.get("agent_id") == "01"

    def test_run_task(self, engine):
        intent = engine.parse("run recon on agent abc123")
        assert intent.name == "RUN_TASK"
        assert intent.params.get("agent_id") == "abc123"
        assert intent.params.get("module") == "info"
        assert intent.params.get("action") == "run"

    def test_run_on_group(self, engine):
        intent = engine.parse("execute shell on group Alpha")
        assert intent.name == "RUN_ON_GROUP"
        assert intent.params.get("group_id") == "alpha"
        assert intent.params.get("module") == "shell"

    def test_self_destruct(self, engine):
        intent = engine.parse("self-destruct Agent 01 in 5 minutes")
        assert intent.name == "SELF_DESTRUCT"
        assert intent.params.get("agent_id") == "01"
        assert intent.params.get("delay_seconds") == 300

    def test_build_agent(self, engine):
        intent = engine.parse("build a stealth windows agent")
        assert intent.name == "BUILD_AGENT"
        assert intent.params.get("os") == "windows"
        assert intent.params.get("stealth_pack") is True

    def test_show_credentials(self, engine):
        intent = engine.parse("show credentials from Agent 01")
        assert intent.name == "SHOW_CREDENTIALS"
        assert intent.params.get("agent_id") == "01"

    def test_unknown(self, engine):
        intent = engine.parse("do the hokey pokey")
        assert intent.name == "UNKNOWN"


class TestPersonaRenderer:
    @pytest.fixture
    def renderer(self):
        return PersonaRenderer()

    def test_heartbeat_message(self, renderer):
        text = renderer.render(
            "heartbeat",
            {"agent_id": "abc-123", "ram_available": 4_000_000_000},
        )
        assert "Agent abc-123" in text or "the agent" in text
        assert len(text) > 0

    def test_agent_connected(self, renderer):
        text = renderer.render("agent_connected", {"agent_id": "abc-123"})
        assert "abc-123" in text or "Agent" in text
        assert (
            "came online" in text
            or "connected" in text
            or "arrived" in text
            or "welcome back" in text.lower()
        )

    def test_task_completed(self, renderer):
        text = renderer.render(
            "task_completed",
            {"agent_id": "abc-123", "module": "screenshot"},
        )
        assert "screenshot" in text.lower()
        assert "finished" in text.lower() or "completed" in text.lower()

    def test_task_failed(self, renderer):
        text = renderer.render(
            "task_failed",
            {"agent_id": "abc-123", "module": "shell", "error": "timeout"},
        )
        assert "shell" in text.lower()
        assert "timeout" in text.lower()

    def test_credential_found(self, renderer):
        text = renderer.render(
            "credential_found",
            {"agent_id": "abc-123", "count": 3},
        )
        assert "3" in text
        assert "credential" in text.lower()


class TestChatEngineExecution:
    @pytest.fixture
    def engine(self):
        return ChatEngine()

    @pytest.mark.asyncio
    async def test_greeting_callback(self, engine):
        calls = []

        async def callback(intent, ctx):
            calls.append(intent.name)
            return {"status": "ok"}

        engine.register_action("GREETING", callback)
        intent = engine.parse("hi")
        result = await engine.execute(intent, {})
        assert result["status"] == "ok"
        assert calls == ["GREETING"]
        assert "Hello" in result["message"] or "Hey" in result["message"]

    @pytest.mark.asyncio
    async def test_unregistered_intent(self, engine):
        intent = engine.parse("show tasks")
        result = await engine.execute(intent, {})
        assert result["status"] == "noop"
