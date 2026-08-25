"""
Tests for the agent stealth module.

Run from the project root:
    cd agent
    python -m pytest tests/test_stealth.py -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.stealth import StealthController, get_idle_seconds


class TestStealthController:
    def test_disabled_never_delays(self):
        ctrl = StealthController(enabled=False, idle_threshold=60, active_delay=5)
        assert ctrl.adaptive_delay("screenshot") == 0.0
        assert ctrl.adaptive_delay("keylog") == 0.0

    def test_non_noisy_module_never_delayed(self):
        ctrl = StealthController(enabled=True, idle_threshold=60, active_delay=5)
        assert ctrl.adaptive_delay("shell") == 0.0
        assert ctrl.adaptive_delay("info") == 0.0

    def test_indicators_structure(self):
        ctrl = StealthController(enabled=True, idle_threshold=60, active_delay=5)
        indicators = ctrl.get_indicators()
        assert "idle_seconds" in indicators
        assert "user_active" in indicators
        assert "screen_locked" in indicators
        assert "timestamp" in indicators

    def test_idle_seconds_is_non_negative(self):
        idle = get_idle_seconds()
        assert idle >= 0.0

    def test_user_active_when_idle_low(self, monkeypatch):
        ctrl = StealthController(enabled=True, idle_threshold=60, active_delay=5)
        monkeypatch.setattr(ctrl, "get_indicators", lambda: {"idle_seconds": 10.0})
        assert ctrl.user_is_active is True
        assert ctrl.should_delay("screenshot") is True
        assert ctrl.adaptive_delay("screenshot") == 5.0

    def test_user_inactive_when_idle_high(self, monkeypatch):
        ctrl = StealthController(enabled=True, idle_threshold=60, active_delay=5)
        monkeypatch.setattr(ctrl, "get_indicators", lambda: {"idle_seconds": 120.0})
        assert ctrl.user_is_active is False
        assert ctrl.should_delay("screenshot") is False
        assert ctrl.adaptive_delay("screenshot") == 0.0
