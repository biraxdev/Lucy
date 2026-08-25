NAME = "shell"
VERSION = "1.1.0"
DESCRIPTION = "Interactive shell with PTY support (persistent session) and single-shot exec."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


import os
import platform
import queue
import subprocess
import threading
import time
import uuid
import re
import shlex

_DANGEROUS_CMD_RE = re.compile(r"[;&|$\\`\\<>(){}\\[\\]\\n\\r]")
_BLOCKED_COMMANDS = {"rm", "rd", "del", "erase", "format", "mkfs", "dd", "fdisk", "diskpart", "shred", "poweroff", "reboot", "shutdown", "halt"}

_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    if action in ("exec", "run", "cmd"):
        return _exec(params)
    elif action == "open":
        return _open_session(params)
    elif action == "send":
        return _send_to_session(params)
    elif action == "read":
        return _read_from_session(params)
    elif action == "close":
        return _close_session(params)
    elif action == "list":
        return _list_sessions()
    return {"status": "failed", "data": None, "error": f"Unknown shell action: {action}"}


def _exec(params: dict) -> dict:
    cmd = params.get("cmd", "")
    timeout = int(params.get("timeout", 30))
    cwd = params.get("cwd") or None
    env_extra = params.get("env", {})

    if not cmd:
        return {"status": "failed", "data": None, "error": "No command"}

    if isinstance(cmd, list):
        cmd_list = [str(c) for c in cmd]
    else:
        if _DANGEROUS_CMD_RE.search(str(cmd)):
            return {"status": "failed", "data": None, "error": "Command contains dangerous characters"}
        try:
            cmd_list = shlex.split(str(cmd))
        except ValueError:
            return {"status": "failed", "data": None, "error": "Invalid command"}

    if not cmd_list:
        return {"status": "failed", "data": None, "error": "No command"}
    if cmd_list[0].lower() in _BLOCKED_COMMANDS:
        return {"status": "failed", "data": None, "error": f"Blocked command: {cmd_list[0]}"}

    env = os.environ.copy()
    env.update({k: str(v) for k, v in env_extra.items()})

    try:
        result = subprocess.run(
            cmd_list, shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, env=env,
        )
        return {"status": "completed", "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "cmd": shlex.join(cmd_list),
        }}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "data": None, "error": f"Timeout after {timeout}s"}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _open_session(params: dict) -> dict:
    session_id = str(uuid.uuid4())[:8]
    shell = params.get("shell") or ("cmd.exe" if platform.system() == "Windows" else "/bin/bash")

    # Only allow known shell executables to prevent arbitrary process spawn.
    if _DANGEROUS_CMD_RE.search(shell):
        return {"status": "failed", "data": None, "error": "Shell path contains dangerous characters"}
    allowed_shells = {"cmd.exe", "powershell.exe", "bash", "sh", "zsh"}
    if os.path.basename(shell).lower() not in allowed_shells:
        return {"status": "failed", "data": None, "error": "Shell not in allowlist"}

    out_q: queue.Queue = queue.Queue(maxsize=1024)

    try:
        proc = subprocess.Popen(
            shell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}

    def _reader():
        for line in proc.stdout:
            try:
                out_q.put_nowait(line)
            except queue.Full:
                pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    with _sessions_lock:
        _sessions[session_id] = {
            "proc": proc,
            "out_q": out_q,
            "reader": t,
            "shell": shell,
            "created_at": time.time(),
        }

    return {"status": "completed", "data": {"session_id": session_id, "shell": shell}}


def _send_to_session(params: dict) -> dict:
    session_id = params.get("session_id", "")
    cmd = params.get("cmd", "")
    if _DANGEROUS_CMD_RE.search(str(cmd)):
        return {"status": "failed", "data": None, "error": "Command contains dangerous characters"}
    tokens = shlex.split(str(cmd))
    if tokens and tokens[0].lower() in _BLOCKED_COMMANDS:
        return {"status": "failed", "data": None, "error": f"Blocked command: {tokens[0]}"}

    with _sessions_lock:
        sess = _sessions.get(session_id)
    if not sess:
        return {"status": "failed", "data": None, "error": "Session not found"}
    try:
        sess["proc"].stdin.write(cmd + "\n")
        sess["proc"].stdin.flush()
        time.sleep(0.3)
        return _read_from_session({"session_id": session_id, "timeout": 2})
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _read_from_session(params: dict) -> dict:
    session_id = params.get("session_id", "")
    timeout = float(params.get("timeout", 0.5))
    with _sessions_lock:
        sess = _sessions.get(session_id)
    if not sess:
        return {"status": "failed", "data": None, "error": "Session not found"}
    lines = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = sess["out_q"].get(timeout=min(0.1, deadline - time.time()))
            lines.append(line)
        except queue.Empty:
            break
    return {"status": "completed", "data": {"output": "".join(lines), "session_id": session_id}}


def _close_session(params: dict) -> dict:
    session_id = params.get("session_id", "")
    with _sessions_lock:
        sess = _sessions.pop(session_id, None)
    if not sess:
        return {"status": "failed", "data": None, "error": "Session not found"}
    try:
        sess["proc"].terminate()
    except Exception:
        pass
    return {"status": "completed", "data": {"closed": session_id}}


def _list_sessions() -> dict:
    with _sessions_lock:
        sessions = [
            {"session_id": sid, "shell": s["shell"], "created_at": s["created_at"]}
            for sid, s in _sessions.items()
        ]
    return {"status": "completed", "data": {"sessions": sessions}}
