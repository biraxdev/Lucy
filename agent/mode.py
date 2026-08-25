"""Lucy agent mode manager.

Runtime mode switching: dormant, living, dead.
Dormant : heartbeat allongé pour consommer le moins possible.
Living  : heartbeat normal.
Dead    : arrêt propre du processus.
"""
import threading
from typing import Any


def set_mode(config: dict, stop_event: threading.Event, mode: str) -> dict[str, Any]:
    """Switch agent runtime mode. Mutates config and stop_event in place."""
    mode = (mode or "living").lower().strip()
    if mode == "dead":
        stop_event.set()
        return {"mode": "dead", "status": "stopping"}
    if mode == "dormant":
        sleep_min = int(config.get("dormant_sleep_minutes", 30))
        config["dormant_mode"] = True
        config["heartbeat_min"] = max(sleep_min * 60 - 60, 60)
        config["heartbeat_max"] = max(sleep_min * 60 + 60, 120)
        return {
            "mode": "dormant",
            "heartbeat_min": config["heartbeat_min"],
            "heartbeat_max": config["heartbeat_max"],
        }
    config["dormant_mode"] = False
    config["heartbeat_min"] = 5
    config["heartbeat_max"] = 10
    return {"mode": "living", "heartbeat_min": 5, "heartbeat_max": 10}
