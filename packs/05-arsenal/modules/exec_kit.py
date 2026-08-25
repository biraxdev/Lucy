"""
exec_kit — Silent-Exec.
Execution de commandes/shell avec capture de sortie, timeout,
processus detaches (avocat/procdump style). Multi-plateforme.
Actions: shell, cmd, powershell, run, detached, spawn
"""
NAME = "exec_kit"
VERSION = "1.0.0"
DESCRIPTION = "Execution de commandes et processus avec capture et timeout (Silent-Exec)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import os
import platform
import shlex
import subprocess
import sys
import tempfile
import time


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def _decode(b):
    if not b:
        return ""
    for enc in ("utf-8", "latin1", "cp1252"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", "replace")


def run(action, params):
    try:
        if action == "shell":
            return _shell(params)
        if action == "cmd":
            return _shell(params)
        if action == "powershell":
            return _powershell(params)
        if action == "run":
            return _run(params)
        if action == "detached":
            return _detached(params)
        if action == "spawn":
            return _spawn(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="exec_kit: " + str(exc), status="failed")


def _shell(params):
    cmd = params.get("cmd", "")
    if not cmd:
        return _result(error="No cmd", status="failed")
    timeout = int(params.get("timeout", 30))
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           timeout=timeout, text=True)
    except subprocess.TimeoutExpired:
        return _result(error="Timeout after " + str(timeout) + "s", status="failed")
    return _result(data={"cmd": cmd, "rc": p.returncode,
                         "stdout": p.stdout[:200000],
                         "stderr": p.stderr[:50000]})


def _powershell(params):
    if os.name != "nt":
        return _result(error="powershell requires Windows", status="failed")
    ps = params.get("cmd", "")
    if not ps:
        return _result(error="No ps cmd", status="failed")
    timeout = int(params.get("timeout", 60))
    b64 = base64.b64encode(ps.encode("utf-16-le")).decode()
    cl = "powershell -NoProfile -NonInteractive -EncodedCommand " + b64
    try:
        p = subprocess.run(cl, shell=True, capture_output=True,
                           timeout=timeout, text=True)
    except subprocess.TimeoutExpired:
        return _result(error="Timeout", status="failed")
    return _result(data={"rc": p.returncode, "stdout": p.stdout[:200000],
                         "stderr": p.stderr[:50000]})


def _run(params):
    args = params.get("args", [])
    if isinstance(args, str):
        args = shlex.split(args)
    if not args:
        return _result(error="No args", status="failed")
    timeout = int(params.get("timeout", 30))
    cwd = params.get("cwd")
    env = dict(os.environ)
    if params.get("env"):
        env.update(params["env"])
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout,
                           cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        return _result(error="Timeout", status="failed")
    except FileNotFoundError:
        return _result(error="Binary not found: " + str(args[0]), status="failed")
    return _result(data={"rc": p.returncode, "stdout": _decode(p.stdout),
                         "stderr": _decode(p.stderr)})


def _detached(params):
    args = params.get("args", [])
    if isinstance(args, str):
        args = shlex.split(args)
    if not args:
        return _result(error="No args", status="failed")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    p = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True)
    return _result(data={"pid": p.pid, "detached": True})


def _spawn(params):
    return _detached(params)
