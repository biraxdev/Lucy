"""End-to-end API test — all endpoints, loop until 100% OK."""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
AID = "0e598955-2ec6-44e4-a296-d27ad3e0f9df"

def req(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode()) if resp.status != 204 else {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def login():
    s, r = req("POST", "/api/v1/auth/login", {"username": "admin", "password": "admin"})
    if s != 200:
        print(f"LOGIN FAILED: {s}")
        sys.exit(1)
    return r["access_token"], r.get("refresh_token", "")

def run_all(token, rtok):
    results = []

    def t(name, method, path, body=None, auth=True):
        tok = token if auth else None
        s, _ = req(method, path, body, tok)
        ok = 200 <= s < 300
        results.append((name, s, ok))
        print(f"{'OK ' if ok else 'FAIL'} {name} => {s}")
        return s

    # GET endpoints
    gets = [
        "/api/v1/agents", f"/api/v1/agents/{AID}", "/api/v1/tasks?limit=50",
        f"/api/v1/tasks?agent_id={AID}", "/api/v1/modules", "/api/v1/groups",
        "/api/v1/groups/summaries/all", "/api/v1/timelines", "/api/v1/pocs",
        "/api/v1/credentials", "/api/v1/findings", "/api/v1/alerts",
        "/api/v1/defense/status", "/api/v1/defense/rules", "/api/v1/defense/alerts",
        "/api/v1/defense/scanners", "/api/v1/defense/mitre-map", "/api/v1/defense/events?limit=5",
        "/api/v1/rbac/roles", "/api/v1/rbac/permissions", "/api/v1/rbac/matrix",
        "/api/v1/rbac/users", "/api/v1/rbac/me", "/api/v1/monitor",
        "/api/v1/build-packs", "/api/v1/strategy/tactics", "/api/v1/strategy/techniques",
        "/api/v1/strategy/campaigns", "/api/v1/strategy/playbooks", "/api/v1/strategy/notes",
        "/api/v1/reports", "/api/v1/chat/history?limit=5", "/api/v1/operators/online",
        "/api/v1/ai-agent/status", "/api/v1/ai-chat/status", "/api/v1/ai-agent/context",
        "/api/v1/logs?limit=5", "/api/v1/auth/me", "/health",
    ]
    for ep in gets:
        t(f"GET {ep}", "GET", ep)

    # POST tasks
    modules = [
        ("shell", "exec", {"cmd": "whoami"}),
        ("screenshot", "capture", {}),
        ("file", "list", {"path": "."}),
        ("port_scan", "scan", {"host": "127.0.0.1", "ports": [22, 80, 443]}),
        ("clipboard", "capture", {}),
        ("persistence", "check", {}),
        ("keylog", "start", {}),
        ("wifi", "scan", {}),
        ("info", "collect", {}),
        ("process", "list", {}),
    ]
    for m, a, p in modules:
        t(f"POST task {m}/{a}", "POST", "/api/v1/tasks",
          {"agent_id": AID, "module": m, "action": a, "params": p, "priority": "normal"})

    # AI Agent
    t("POST AI analyze-threat", "POST", "/api/v1/ai-agent/analyze-threat", {"query": "test"})
    t("POST AI suggest-steps", "POST", "/api/v1/ai-agent/suggest-steps", {"current_state": {}})
    t("POST AI analyze-results", "POST", "/api/v1/ai-agent/analyze-results", {"task_results": []})
    t("POST AI generate-script", "POST", "/api/v1/ai-agent/generate-script",
      {"task_description": "hello", "language": "python"})

    # Chat
    t("POST Chat command", "POST", "/api/v1/chat/command", {"message": "list agents"})

    # Defense
    t("POST Defense event", "POST", "/api/v1/defense/events",
      {"source": "sensor", "hostname": "FBOX", "event_type": "test", "details": {}, "severity": "info"})
    t("POST Defense bulk", "POST", "/api/v1/defense/events/bulk",
      {"events": [{"source": "sensor", "hostname": "FBOX", "event_type": "proc", "details": {}, "severity": "info"}]})
    t("POST Defense scanner", "POST", "/api/v1/defense/scanners/dispatch",
      {"agent_id": AID, "scanner": "port_scan"})

    # Strategy
    t("POST Strategy tactic", "POST", "/api/v1/strategy/tactics",
      {"mitre_id": "TA9999", "name": "Test Tactic", "phase": "test", "description": "test"})
    t("POST Strategy technique", "POST", "/api/v1/strategy/techniques",
      {"mitre_id": "T9999", "name": "Test Tech", "description": "test", "platform": "all"})
    t("POST Strategy campaign", "POST", "/api/v1/strategy/campaigns",
      {"name": "Test Campaign", "description": "test", "objective": "test", "status": "active"})
    t("POST Strategy playbook", "POST", "/api/v1/strategy/playbooks",
      {"name": "Test PB", "description": "test", "steps": [], "tags": ["test"]})
    t("POST Strategy note", "POST", "/api/v1/strategy/notes",
      {"agent_id": AID, "content": "Test note", "category": "observation"})

    # Findings, Reports, Groups
    t("POST Finding", "POST", "/api/v1/findings",
      {"title": "Test Finding", "severity": "medium", "status": "draft", "description": "test"})
    t("POST Report", "POST", "/api/v1/reports",
      {"title": "Test Report", "format": "json", "scope": "all"})
    t("POST Group", "POST", "/api/v1/groups", {"name": "Test Group", "description": "test"})

    # Auth
    t("POST Auth refresh", "POST", "/api/v1/auth/refresh", {"refresh_token": rtok})
    t("POST Auth change-password", "POST", "/api/v1/auth/change-password",
      {"current_password": "admin", "new_password": "admin"})

    # Timeline
    t("POST Timeline create", "POST", "/api/v1/timelines",
      {"name": "Test TL", "description": "test", "steps": []})

    # PoC import (puid)
    s, pocs = req("GET", "/api/v1/pocs", token=token)
    if pocs and len(pocs) > 0 and pocs[0].get("puid"):
        t("POST PoC import", "POST", f"/api/v1/pocs/{pocs[0]['puid']}/import")

    # Build
    t("POST Build agent", "POST", "/api/v1/build",
      {"os": "windows", "arch": "x64", "modules": ["shell", "file", "screenshot"],
       "server_url": "http://localhost:8000", "api_key": "test"})

    # GraphQL
    t("POST GraphQL", "POST", "/graphql", {"query": "{ agents { id hostname status } }"})

    # PUT RBAC user
    s, users = req("GET", "/api/v1/rbac/users", token=token)
    if users and len(users) > 0:
        t("PUT RBAC user", "PUT", f"/api/v1/rbac/users/{users[0]['id']}", {"role": "admin"})

    # Module download (no auth)
    t("GET Module download", "GET", "/api/v1/modules/shell/download", auth=False)

    # Summary
    ok_count = sum(1 for _, _, ok in results if ok)
    fail_count = len(results) - ok_count
    print(f"\n{'='*50}")
    print(f"TOTAL: {len(results)} | OK: {ok_count} | FAIL: {fail_count}")
    print(f"{'='*50}")
    if fail_count > 0:
        print("FAILED:")
        for name, s, ok in results:
            if not ok:
                print(f"  {name} => {s}")
    return ok_count, fail_count, results

if __name__ == "__main__":
    token, rtok = login()
    ok, fail, results = run_all(token, rtok)
    sys.exit(0 if fail == 0 else 1)
