"""
secret_hunter — Vault-Breaker (recherche secrets) / Key-Grabber-Rust (cotes).
Recherche de secrets dans les fichiers: clefs API, mots de passe, clefs
privees, tokens cloud, URI de connexion. Multi-plateforme, stdlib.
Actions: scan, scan_path, patterns, report
"""
NAME = "secret_hunter"
VERSION = "1.0.0"
DESCRIPTION = "Recherche de secrets (API keys, tokens, mots de passe) dans les fichiers."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import json
import os
import re
import time

PATTERNS = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret": r"(?i)aws(.{0,20})?['\"]?[=:]['\"]?[A-Za-z0-9/+=]{40}",
    "gcp_api": r"AIza[0-9A-Za-z\-_]{35}",
    "azure_tenant": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "github_token": r"gh[pousr]_[0-9A-Za-z]{36,255}",
    "github_old": r"gitub|github.{0,20}['\"]?[=:]['\"]?[0-9a-f]{40}",
    "slack_token": r"xox[baprs]-[0-9A-Za-z-]{10,200}",
    "stripe_live": r"sk_live_[0-9a-zA-Z]{24,}",
    "private_key": r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "jwt": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "generic_password": r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)(['\"]?\s*[:=]\s*['\"]?)[^\s'\"]{8,64}",
    "conn_string": r"(?i)(mysql|postgres|mongodb(\+srv)?|redis|amqp)://[^\s'\"]+",
    "twilio": r"SK[0-9a-fA-F]{32}",
    "sendgrid": r"SG\.[0-9A-Za-z\-_]{22}\.[0-9A-Za-z\-_]{43}",
}

BINARY_EXT = {".exe", ".dll", ".so", ".dylib", ".png", ".jpg", ".jpeg", ".gif",
              ".bmp", ".zip", ".gz", ".7z", ".rar", ".pyc", ".woff", ".ttf"}


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "scan":
            return _scan(params)
        if action == "scan_path":
            return _scan(params)
        if action == "patterns":
            return _result(data={"patterns": list(PATTERNS)})
        if action == "report":
            return _report(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="secret_hunter: " + str(exc), status="failed")


def _compile(which):
    if not which:
        return {k: re.compile(v) for k, v in PATTERNS.items()}
    return {k: re.compile(PATTERNS[k]) for k in which if k in PATTERNS}


def _scan(params):
    root = params.get("path") or params.get("dir") or os.path.expanduser("~")
    if not os.path.isdir(root):
        return _result(error="Path not a directory: " + str(root), status="failed")
    depth = int(params.get("depth", 3))
    max_size = int(params.get("max_size", 1048576))
    max_files = int(params.get("max_files", 2000))
    which = params.get("patterns") or list(PATTERNS)
    regexes = _compile(which)
    exts = set(params.get("ext", "").split(",")) if params.get("ext") else None
    base = os.path.abspath(root)
    found = []
    scanned = 0
    t0 = time.time()
    for dirpath, dirnames, filenames in os.walk(base):
        rel = os.path.relpath(dirpath, base)
        if rel != "." and rel.count(os.sep) >= depth:
            dirnames[:] = []
            continue
        for fn in filenames:
            if scanned >= max_files:
                break
            fp = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext in BINARY_EXT:
                continue
            if exts is not None and ext not in exts:
                continue
            try:
                size = os.path.getsize(fp)
                if size > max_size:
                    continue
                with open(fp, "rb") as fh:
                    data = fh.read(max_size)
                text = data.decode("utf-8", "replace")
                scanned += 1
                for name, rx in regexes.items():
                    for m in rx.finditer(text):
                        snippet = text[max(0, m.start() - 30):m.end() + 30]
                        found.append({"file": fp, "pattern": name,
                                      "match": m.group(0)[:120],
                                      "snippet": snippet.replace("\n", " ")[:180]})
                        if len(found) >= int(params.get("limit", 100)):
                            return _result(data={"scanned": scanned,
                                                 "elapsed_s": round(time.time() - t0, 2),
                                                 "findings": found})
            except (OSError, PermissionError):
                continue
        if scanned >= max_files:
            break
    return _result(data={"scanned": scanned,
                         "elapsed_s": round(time.time() - t0, 2),
                         "findings": found})


def _report(params):
    path = params.get("path", "")
    if not path or not os.path.isfile(path):
        return _result(error="No report file", status="failed")
    with open(path, "r") as fh:
        content = fh.read()
    try:
        return _result(data={"report": json.loads(content)})
    except Exception:
        return _result(data={"report_raw": content[:10000]})
