"""Tests for the ShannonAi dynamic chat engine."""
import pytest

from core.shannon_ai import (
    ShannonAi,
    ShannonMemory,
    ShannonEvent,
    narrate_events,
    transform_event_to_dialogue,
    transform_log_to_dialogue,
    stream_narrative,
)
from datetime import datetime, timezone


@pytest.fixture
def memory():
    return ShannonMemory()


@pytest.fixture
def shannon():
    eng = ShannonAi(mode="narrative")
    eng.reset()
    return eng


class TestShannonMemory:
    def test_remember_and_recall(self, memory):
        event = ShannonEvent(
            event_type="heartbeat",
            agent_id="agent-123",
            timestamp=datetime.now(timezone.utc),
            summary="Agent 123 checked in 5s ago",
        )
        memory.remember(event)
        assert len(memory.recent_for("agent-123")) == 1
        assert len(memory.recent_global()) == 1

    def test_global_limit(self, memory):
        for i in range(70):
            memory.remember(ShannonEvent(
                event_type="log",
                agent_id=f"agent-{i}",
                timestamp=datetime.now(timezone.utc),
                summary=f"event {i}",
            ))
        assert len(memory.recent_global(limit=9999)) == 60  # MAX_MEMORY_GLOBAL

    def test_per_agent_limit(self, memory):
        for i in range(30):
            memory.remember(ShannonEvent(
                event_type="heartbeat",
                agent_id="agent-1",
                timestamp=datetime.now(timezone.utc),
                summary=f"hb {i}",
            ))
        assert len(memory.recent_for("agent-1", limit=9999)) == 20  # MAX_MEMORY_PER_AGENT

    def test_clear(self, memory):
        memory.remember(ShannonEvent(
            event_type="log", agent_id="a", timestamp=datetime.now(timezone.utc),
            summary="x",
        ))
        memory.clear()
        assert len(memory.recent_global()) == 0


class TestNarrativeEngine:
    def test_narrate_empty(self, memory):
        assert narrate_events([], memory) == "All quiet on the network."

    def test_narrate_single_event(self, memory):
        event = ShannonEvent(
            event_type="connect",
            agent_id="agent-abc",
            timestamp=datetime.now(timezone.utc),
            summary="Agent abc12345 came online",
        )
        result = narrate_events([event], memory)
        assert "came online" in result

    def test_narrate_compresses_heartbeats(self, memory):
        events = [
            ShannonEvent(
                event_type="heartbeat",
                agent_id="agent-1",
                timestamp=datetime.now(timezone.utc),
                summary=f"Agent 1 checked in {i}s ago",
            )
            for i in range(5)
        ]
        result = narrate_events(events, memory)
        # Should mention suppression of duplicate heartbeats.
        assert "suppressed" in result.lower() or "heartbeat" in result.lower()


class TestEventTransformation:
    def test_transform_heartbeat(self, memory):
        text = transform_event_to_dialogue("heartbeat", {
            "agent_id": "abc12345",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, memory)
        assert "checked in" in text

    def test_transform_connect(self, memory):
        text = transform_event_to_dialogue("connect", {
            "agent_id": "abc12345",
        }, memory)
        assert "came online" in text

    def test_transform_disconnect(self, memory):
        text = transform_event_to_dialogue("disconnect", {
            "agent_id": "abc12345",
            "reason": "timeout",
        }, memory)
        assert "went offline" in text

    def test_transform_result_failed(self, memory):
        text = transform_event_to_dialogue("result", {
            "agent_id": "abc12345",
            "module": "shell",
            "status": "failed",
            "error": "permission denied",
        }, memory)
        assert "failed" in text


class TestLogToDialogue:
    def test_empty_logs(self, memory):
        result = transform_log_to_dialogue([], memory)
        assert "No recent log activity" in result

    def test_transform_logs(self, memory):
        logs = [
            {"agent_id": "abc12345", "level": "INFO", "message": "started", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"agent_id": "abc12345", "level": "ERROR", "message": "crashed", "timestamp": datetime.now(timezone.utc).isoformat()},
        ]
        result = transform_log_to_dialogue(logs, memory)
        assert "started" in result or "crashed" in result
        assert len(result) > 20


class TestShannonAiEngine:
    def test_set_mode(self, shannon):
        shannon.set_mode("narrative")
        assert shannon.mode == "narrative"
        shannon.set_mode("hybrid")
        assert shannon.mode == "hybrid"

    def test_set_invalid_mode(self, shannon):
        with pytest.raises(ValueError):
            shannon.set_mode("invalid")

    def test_ingest_event(self, shannon):
        text = shannon.ingest_event("connect", {"agent_id": "abc12345"})
        assert "came online" in text
        assert len(shannon.memory.recent_global()) == 1

    def test_narrate_recent_empty(self, shannon):
        result = shannon.narrate_recent()
        assert "quiet" in result.lower()

    def test_narrate_agent_no_data(self, shannon):
        result = shannon.narrate_agent("unknown-agent")
        assert "No recent activity" in result

    @pytest.mark.asyncio
    async def test_stream_narrative(self):
        text = "Hello world this is a test of streaming"
        chunks = []
        async for chunk in stream_narrative(text, chunk_size=2, delay_ms=0):
            chunks.append(chunk)
        full = "".join(chunks)
        assert "Hello" in full
        assert "streaming" in full

    @pytest.mark.asyncio
    async def test_respond_narrative_mode(self, shannon):
        shannon.set_mode("narrative")
        # Ingest some events first
        shannon.ingest_event("connect", {"agent_id": "abc12345"})
        result = await shannon.respond("what's happening?", {})
        assert len(result) > 10
