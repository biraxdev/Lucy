"""
Healthcheck and monitoring API for Project Lucy.
"""
import os
import platform
import time
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter

from db.models import Agent, Task, Credential, Log
from dependencies import CurrentUser

router = APIRouter(prefix="/monitor", tags=["monitor"])

_start_time = time.time()


@router.get("")
async def monitor_root(current_user: CurrentUser) -> dict:
    """Quick server vitals used by Settings page."""
    import os as _os
    proc = psutil.Process(_os.getpid())
    mem  = psutil.virtual_memory()
    cpu  = psutil.cpu_percent(interval=0.1)
    db_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "data", "lucy.db")
    db_size_mb = round(_os.path.getsize(db_path) / 1024 / 1024, 2) if _os.path.exists(db_path) else None
    from core.ws_manager import ConnectionManager
    ws = ConnectionManager()
    agent_conns   = len(ws._agents) if hasattr(ws, "_agents") else 0
    frontend_conns = len(ws._frontends) if hasattr(ws, "_frontends") and isinstance(ws._frontends, list) else 0
    return {
        "cpu_percent": round(cpu, 1),
        "ram_percent": round(mem.percent, 1),
        "ram_used_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
        "ws_connections": agent_conns + frontend_conns,
        "db_size_mb": db_size_mb,
        "uptime": _fmt_uptime(int(time.time() - _start_time)),
        "version": "1.0.0",
        "platform": platform.system(),
    }


def _fmt_uptime(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"


@router.get("/agent-history")
async def agent_history(current_user: CurrentUser) -> dict:
    """Return hourly online agent counts for the last 24h."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    hourly = []
    for i in range(23, -1, -1):
        slot_start = now - timedelta(hours=i + 1)
        slot_end   = now - timedelta(hours=i)
        label = slot_end.strftime("%H:00")
        count = Agent.select().where(
            Agent.last_seen >= slot_start,
            Agent.last_seen < slot_end,
        ).count()
        hourly.append({"time": label, "online": count})
    return {"hourly": hourly}


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - _start_time),
        "version": "1.0.0",
    }


@router.get("/stats")
async def stats(current_user: CurrentUser) -> dict:
    proc = psutil.Process(os.getpid())
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)

    agents_online  = Agent.select().where(Agent.status == "online").count()
    agents_offline = Agent.select().where(Agent.status == "offline").count()
    agents_total   = Agent.select().count()
    tasks_queued   = Task.select().where(Task.status == "queued").count()
    tasks_running  = Task.select().where(Task.status == "running").count()
    tasks_done     = Task.select().where(Task.status == "completed").count()
    tasks_failed   = Task.select().where(Task.status == "failed").count()
    cred_count     = Credential.select().count()
    log_count      = Log.select().count()

    return {
        "system": {
            "cpu_percent": cpu,
            "memory_used_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
            "memory_total_mb": round(mem.total / 1024 / 1024, 1),
            "memory_percent": mem.percent,
            "platform": platform.system(),
            "uptime_seconds": int(time.time() - _start_time),
        },
        "agents": {
            "total": agents_total,
            "online": agents_online,
            "offline": agents_offline,
        },
        "tasks": {
            "queued": tasks_queued,
            "running": tasks_running,
            "completed": tasks_done,
            "failed": tasks_failed,
        },
        "credentials": cred_count,
        "logs": log_count,
    }


@router.get("/agents/status")
async def agents_status(current_user: CurrentUser) -> list[dict]:
    """Quick status list of all agents."""
    return [
        {"id": str(a.id), "hostname": a.hostname, "status": a.status, "last_seen": str(a.last_seen)}
        for a in Agent.select(Agent.id, Agent.hostname, Agent.status, Agent.last_seen)
    ]


@router.get("/agents/metrics")
async def agent_metrics(current_user: CurrentUser) -> list[dict]:
    """Per-agent CPU/RAM metrics for the live dashboard widget."""
    results = []
    for a in Agent.select(
        Agent.id, Agent.hostname, Agent.status,
        Agent.cpu_percent, Agent.ram_total, Agent.ram_available,
    ):
        ram_used_pct = None
        if a.ram_total and a.ram_total > 0 and a.ram_available is not None:
            ram_used_pct = round((1 - a.ram_available / a.ram_total) * 100, 1)
        results.append({
            "id": str(a.id),
            "hostname": a.hostname,
            "status": a.status,
            "cpu_percent": a.cpu_percent,
            "ram_total_mb": round(a.ram_total / 1024 / 1024, 1) if a.ram_total else None,
            "ram_available_mb": round(a.ram_available / 1024 / 1024, 1) if a.ram_available else None,
            "ram_used_pct": ram_used_pct,
        })
    return results


@router.get("/heatmap")
async def heatmap_data(
    by: str = "time",
    hours: int = 24,
    current_user: CurrentUser = None,
) -> dict:
    """Return activity heatmap data (time x day or agent x hour)."""
    from core.heatmap_engine import heatmap
    return heatmap(by=by, hours_window=hours)
