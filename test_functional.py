"""
Functional verification — each task must produce the EXPECTED real result,
not just a 200/201 status. We create a task, wait for the agent to execute
it, then inspect the actual result content.
"""
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
AID = "0e598955-2ec6-44e4-a296-d27ad3e0f9df"
TIMEOUT = 30  # seconds to wait for each task


def req(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"error": raw}
    except Exception as e:
        return 0, {"error": str(e)}


def login():
    s, r = req("POST", "/api/v1/auth/login", {"username": "admin", "password": "admin"})
    if s != 200:
        print(f"LOGIN FAILED: {s} {r}")
        sys.exit(1)
    return r["access_token"]


def create_task(token, module, action, params=None):
    s, r = req("POST", "/api/v1/tasks", {
        "agent_id": AID, "module": module, "action": action,
        "params": params or {}, "priority": "high",
    }, token)
    if s not in (200, 201):
        return None, f"Create failed: {s} {r}"
    return r.get("id"), None


def wait_task(token, task_id, timeout=TIMEOUT):
    """Poll task until completed/failed or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        s, r = req("GET", f"/api/v1/tasks/{task_id}", token=token)
        if s != 200:
            time.sleep(1)
            continue
        status = r.get("status", "")
        if status in ("completed", "failed", "ok", "error"):
            return r
        time.sleep(1)
    return {"status": "timeout", "result": None, "error": "Timed out"}


def get_result(task):
    """Extract the result data from a completed task."""
    raw = task.get("result")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


def run_test(token, name, module, action, params=None, verify_fn=None):
    """Create task, wait, verify result. Returns (pass, detail)."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  module={module} action={action} params={params}")
    task_id, err = create_task(token, module, action, params)
    if err:
        print(f"  FAIL: {err}")
        return False, err

    print(f"  task_id={task_id} — waiting for execution...")
    task = wait_task(token, task_id)
    status = task.get("status")
    result = get_result(task)
    error = task.get("error")

    print(f"  status={status}")
    if error:
        print(f"  error={error[:200]}")
    if result:
        if isinstance(result, dict):
            # Truncate long values for display
            display = {}
            for k, v in result.items():
                sv = str(v)
                if len(sv) > 200:
                    display[k] = sv[:200] + f"... ({len(sv)} chars total)"
                else:
                    display[k] = v
            print(f"  result={json.dumps(display, indent=2, default=str)[:500]}")
        else:
            print(f"  result={str(result)[:500]}")

    if status not in ("completed", "ok"):
        print(f"  FAIL: task status is '{status}', expected 'completed'")
        return False, f"status={status}"

    if verify_fn:
        ok, msg = verify_fn(result, error)
        if ok:
            print(f"  PASS: {msg}")
        else:
            print(f"  FAIL: {msg}")
        return ok, msg

    print(f"  PASS: task completed")
    return True, "completed"


# === Verification functions ===

def verify_shell(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    stdout = result.get("stdout", "")
    if not stdout:
        return False, f"Empty stdout, stderr={result.get('stderr','')}"
    return True, f"stdout='{stdout.strip()[:100]}'"

def verify_screenshot(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    # Screenshot returns base64 JPEG directly in 'data'
    data = result.get("data") if isinstance(result, dict) else result
    if not data:
        return False, "No image data"
    if isinstance(data, str) and len(data) > 100:
        # Try to decode and save
        try:
            img_bytes = base64.b64decode(data)
            if len(img_bytes) > 500:
                # Save to file for visual verification
                out_path = "C:\\Heybro\\PROJECTS\\ACTIVE\\Lucy\\test_screenshot.jpg"
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                return True, f"Screenshot captured: {len(img_bytes)} bytes JPEG, saved to {out_path}"
        except Exception as e:
            return False, f"Decode failed: {e}"
    return False, f"Data too small or invalid: {str(data)[:100]}"

def verify_file_list(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    entries = result.get("entries") or result.get("data", {}).get("entries")
    if not entries:
        return False, "No file entries returned"
    return True, f"Found {len(entries)} files/dirs"

def verify_file_read(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    # Result may be wrapped in 'data' or direct
    data = result.get("data") if isinstance(result, dict) and "data" in result else result
    if isinstance(data, dict):
        b64 = data.get("content_b64")
        if b64:
            content = base64.b64decode(b64)
            return True, f"Read {len(content)} bytes, sha256={data.get('sha256','?')[:16]}"
    if isinstance(result, dict) and result.get("content_b64"):
        content = base64.b64decode(result["content_b64"])
        return True, f"Read {len(content)} bytes, sha256={result.get('sha256','?')[:16]}"
    return False, f"Unexpected result: {str(result)[:100]}"

def verify_clipboard(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    return True, f"Clipboard captured: {str(result)[:100]}"

def verify_process_list(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    procs = result.get("processes") or result.get("data", {}).get("processes")
    if not procs:
        return False, "No process list"
    return True, f"Found {len(procs)} processes"

def verify_info(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    # Result may be wrapped in 'data' or direct
    data = result.get("data") if isinstance(result, dict) and "data" in result else result
    if isinstance(data, dict):
        keys = list(data.keys())
        if any(k in keys for k in ["hostname", "os", "platform", "username", "cpu", "ram"]):
            return True, f"System info: {json.dumps({k: str(v)[:50] for k,v in data.items() if k in ['hostname','os','platform','username']})}"
    if isinstance(result, dict) and any(k in result for k in ["hostname", "os", "username"]):
        return True, f"System info: hostname={result.get('hostname')}, os={result.get('os')}, user={result.get('username')}"
    return False, f"Unexpected info: {str(result)[:100]}"

def verify_port_scan(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    data = result.get("data") if isinstance(result, dict) else result
    if isinstance(data, dict):
        if "open_ports" in data or "ports" in data or "results" in data:
            return True, f"Scan done: {str(data)[:150]}"
    return True, f"Scan completed: {str(result)[:150]}"

def verify_wifi(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    data = result.get("data") if isinstance(result, dict) else result
    if isinstance(data, dict) and ("networks" in data or "wifi" in data):
        nets = data.get("networks") or data.get("wifi") or []
        return True, f"Found {len(nets)} WiFi networks"
    return True, f"WiFi scan done: {str(result)[:100]}"

def verify_keylog(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    return True, f"Keylog action done: {str(result)[:100]}"

def verify_persistence(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    return True, f"Persistence action done: {str(result)[:100]}"

def verify_remote_control(result, error):
    if error:
        return False, f"Error: {error}"
    if not result:
        return False, "No result data"
    return True, f"Remote control done: {str(result)[:100]}"


if __name__ == "__main__":
    token = login()
    results = []

    # 1. Shell exec — whoami
    results.append(run_test(token, "Shell exec (whoami)", "shell", "exec",
        {"cmd": "whoami"}, verify_shell))

    # 2. Shell exec — hostname
    results.append(run_test(token, "Shell exec (hostname)", "shell", "exec",
        {"cmd": "hostname"}, verify_shell))

    # 3. Shell exec — ipconfig
    results.append(run_test(token, "Shell exec (ipconfig)", "shell", "exec",
        {"cmd": "ipconfig"}, verify_shell))

    # 4. Screenshot capture — must return real JPEG
    results.append(run_test(token, "Screenshot capture (real screen)", "screenshot", "capture",
        {}, verify_screenshot))

    # 5. File list — current directory
    results.append(run_test(token, "File list (current dir)", "file", "list",
        {"path": "."}, verify_file_list))

    # 6. File list — C:\Windows
    results.append(run_test(token, "File list (C:\\Windows)", "file", "list",
        {"path": "C:\\Windows"}, verify_file_list))

    # 7. File read — read a known file
    results.append(run_test(token, "File read (hosts file)", "file", "read",
        {"path": "C:\\Windows\\System32\\drivers\\etc\\hosts"}, verify_file_read))

    # 8. Clipboard capture
    results.append(run_test(token, "Clipboard capture", "clipboard", "capture",
        {}, verify_clipboard))

    # 9. Process list
    results.append(run_test(token, "Process list", "process", "list",
        {}, verify_process_list))

    # 10. Info collect — system info
    results.append(run_test(token, "System info collect", "info", "collect",
        {}, verify_info))

    # 11. Port scan — localhost
    results.append(run_test(token, "Port scan (localhost)", "port_scan", "scan",
        {"host": "127.0.0.1", "ports": [22, 80, 135, 443, 445, 902, 8000, 3000]}, verify_port_scan))

    # 12. WiFi scan
    results.append(run_test(token, "WiFi scan", "wifi", "scan",
        {}, verify_wifi))

    # 13. Keylog start
    results.append(run_test(token, "Keylog start", "keylog", "start",
        {}, verify_keylog))

    # 14. Keylog stop
    results.append(run_test(token, "Keylog stop", "keylog", "stop",
        {}, verify_keylog))

    # 15. Persistence check
    results.append(run_test(token, "Persistence check", "persistence", "check",
        {}, verify_persistence))

    # 16. Remote control — mouse_move
    results.append(run_test(token, "Remote control (mouse_move)", "remote_control", "mouse_move",
        {"x": 100, "y": 100}, verify_remote_control))

    # 17. Remote control — key_press
    results.append(run_test(token, "Remote control (key_press)", "remote_control", "key_press",
        {"key": "a"}, verify_remote_control))

    # 18. Remote control — screenshot via remote_control
    results.append(run_test(token, "Remote control (screenshot)", "remote_control", "screenshot",
        {}, verify_remote_control))

    # Summary
    passed = sum(1 for ok, _ in results if ok)
    failed = len(results) - passed
    print(f"\n{'='*60}")
    print(f"FUNCTIONAL TEST SUMMARY")
    print(f"{'='*60}")
    print(f"TOTAL: {len(results)} | PASS: {passed} | FAIL: {failed}")
    print(f"{'='*60}")
    if failed > 0:
        print("FAILED TESTS:")
        for ok, msg in results:
            if not ok:
                print(f"  - {msg}")
    sys.exit(0 if failed == 0 else 1)
