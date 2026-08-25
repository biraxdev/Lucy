NAME = "process"
VERSION = "1.0.0"
DESCRIPTION = "Process enumeration, kill, and injection stubs."
AUTHOR = "lucy"
DEPENDENCIES = ["psutil>=5.9"]
OS_COMPAT = ["windows", "linux", "darwin"]


import os
import platform
import signal
import subprocess


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    if action == "list":
        return _list(params)
    elif action == "kill":
        return _kill(params)
    elif action == "info":
        return _info(params)
    elif action == "search":
        return _search(params)
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _list(params: dict) -> dict:
    procs = _enum_psutil() or _enum_fallback()
    return {"status": "completed", "data": {"processes": procs, "count": len(procs)}}


def _kill(params: dict) -> dict:
    pid = params.get("pid")
    name = params.get("name")

    if not pid and not name:
        return {"status": "failed", "data": None, "error": "pid or name required"}

    killed = []

    try:
        import psutil
        targets = []
        if pid:
            try:
                targets.append(psutil.Process(int(pid)))
            except psutil.NoSuchProcess:
                return {"status": "failed", "data": None, "error": f"PID {pid} not found"}
        elif name:
            targets = [p for p in psutil.process_iter(["name"]) if p.info["name"] == name]

        for proc in targets:
            try:
                proc.terminate()
                killed.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                pass

        return {"status": "completed", "data": {"killed": killed}}
    except ImportError:
        pass

    if pid:
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=True, capture_output=True)
            else:
                os.kill(int(pid), signal.SIGTERM)
            return {"status": "completed", "data": {"killed": [int(pid)]}}
        except Exception as exc:
            return {"status": "failed", "data": None, "error": str(exc)}

    return {"status": "failed", "data": None, "error": "psutil required for kill-by-name"}


def _info(params: dict) -> dict:
    pid = params.get("pid")
    if not pid:
        return {"status": "failed", "data": None, "error": "pid required"}
    try:
        import psutil
        p = psutil.Process(int(pid))
        return {"status": "completed", "data": {
            "pid": p.pid,
            "name": p.name(),
            "exe": p.exe(),
            "cmdline": p.cmdline(),
            "status": p.status(),
            "username": p.username(),
            "cpu_percent": p.cpu_percent(interval=0.1),
            "memory_mb": p.memory_info().rss / 1024 / 1024,
            "create_time": p.create_time(),
            "connections": [c._asdict() for c in p.connections()],
        }}
    except ImportError:
        return {"status": "failed", "data": None, "error": "psutil required for process info"}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _search(params: dict) -> dict:
    term = params.get("name", "").lower()
    if not term:
        return {"status": "failed", "data": None, "error": "name param required"}
    all_procs = _enum_psutil() or _enum_fallback()
    matches = [p for p in all_procs if term in str(p.get("name", "")).lower()]
    return {"status": "completed", "data": {"matches": matches, "count": len(matches)}}


def _enum_psutil() -> list | None:
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "username", "status", "memory_info"]):
            try:
                info = p.info
                if info.get("memory_info"):
                    info["memory_mb"] = round(info["memory_info"].rss / 1024 / 1024, 2)
                    del info["memory_info"]
                procs.append(info)
            except Exception:
                pass
        return procs
    except ImportError:
        return None


def _enum_fallback() -> list:
    procs = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(["tasklist", "/fo", "csv", "/nh"], text=True, timeout=10)
            for line in out.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    procs.append({"name": parts[0], "pid": parts[1]})
        else:
            out = subprocess.check_output(["ps", "aux"], text=True, timeout=10)
            for line in out.strip().splitlines()[1:]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    procs.append({"user": parts[0], "pid": parts[1], "name": parts[10][:60]})
    except Exception:
        pass
    return procs
