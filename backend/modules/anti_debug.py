"""
anti_debug — Rust-Rootkit-X (evasion) / anti-debugging.
Detection de debogueurs: IsDebuggerPresent, PEB BeingDebugged, DebugPort,
breakpoints materiels, timing. Echec gracieux hors Windows.
Actions: check, peb, ports, timing, hardware, summary
"""
NAME = "anti_debug"
VERSION = "1.0.0"
DESCRIPTION = "Detection de debogage: PEB, DebugPort, breakpoints, timing."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import os
import subprocess
import time

try:
    import ctypes
except Exception:
    ctypes = None

DEBUGGER_PROCESSES = ["ollydbg", "x64dbg", "x32dbg", "windbg", "ida64", "ida",
                      "radare2", "ghidra", "dbgserv", "procmon", "fiddler"]
K32 = None
NTDLL = None


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "check":
            return _check(params)
        if action == "peb":
            return _peb(params)
        if action == "ports":
            return _ports(params)
        if action == "timing":
            return _timing(params)
        if action == "hardware":
            return _hardware(params)
        if action == "summary":
            return _check(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="anti_debug: " + str(exc), status="failed")


def _init():
    global K32, NTDLL
    if os.name == "nt" and K32 is None:
        K32 = ctypes.windll.kernel32
        NTDLL = ctypes.windll.ntdll


def _peb(params):
    if os.name != "nt":
        return _result(error="PEB check requires Windows", status="failed")
    _init()
    is_debug = bool(K32.IsDebuggerPresent())
    being_debugged = False
    try:
        peb = ctypes.c_void_p()
        class PBI:
            _fields_ = [("ExitStatus", ctypes.c_uint32),
                        ("PebBaseAddress", ctypes.c_void_p),
                        ("AffinityMask", ctypes.c_void_p),
                        ("BasePriority", ctypes.c_int32),
                        ("UniqueProcessId", ctypes.c_void_p),
                        ("InheritedFromUniqueProcessId", ctypes.c_void_p)]
        pbi = PBI()
        ntdll.NtQueryInformationProcess(ctypes.c_void_p(-1), 0,
                                        ctypes.byref(pbi), ctypes.sizeof(pbi),
                                        None)
        peb_addr = pbi.PebBaseAddress
        if peb_addr:
            being_debugged = ctypes.c_uint8.from_address(
                ctypes.c_void_p(peb_addr).value + 2).value
    except Exception:
        pass
    return _result(data={"IsDebuggerPresent": bool(is_debug),
                         "PEB_BeingDebugged": bool(being_debugged),
                         "debugged": bool(is_debug or being_debugged)})


def _ports(params):
    if os.name != "nt":
        return _result(error="DebugPort check requires Windows", status="failed")
    _init()
    debug_port = None
    try:
        val = ctypes.c_void_p(0)
        ntdll.NtQueryInformationProcess(ctypes.c_void_p(-1), 7,
                                        ctypes.byref(val),
                                        ctypes.sizeof(val), None)
        debug_port = val.value
    except Exception:
        pass
    processes = []
    try:
        p = subprocess.run("tasklist /fo csv /nh", shell=True,
                           capture_output=True, text=True, timeout=20)
        for line in (p.stdout or "").splitlines():
            name = line.split(",")[0].strip(chr(34)).lower().split(".")[0]
            if name in DEBUGGER_PROCESSES and name not in processes:
                processes.append(name)
    except Exception:
        pass
    return _result(data={"DebugPort": debug_port,
                         "debugger_processes": processes,
                         "debugged": bool(debug_port) or bool(processes)})


def _timing(params):
    """Detection par mesure de temps: un debogueur ralentit l'execution."""
    if os.name == "nt":
        _init()
        qpc = ctypes.c_uint64(0)
        qpf = ctypes.c_uint64(0)
        K32.QueryPerformanceFrequency(ctypes.byref(qpf))
        K32.QueryPerformanceCounter(ctypes.byref(qpc))
        t0 = qpc.value / float(qpf.value)
        for _ in range(int(params.get("iters", 2000000))):
            pass
        K32.QueryPerformanceCounter(ctypes.byref(qpc))
        dt = qpc.value / float(qpf.value) - t0
    else:
        t0 = time.perf_counter()
        for _ in range(int(params.get("iters", 2000000))):
            pass
        dt = time.perf_counter() - t0
    threshold = float(params.get("threshold", 0.5))
    return _result(data={"elapsed_s": round(dt, 4),
                         "suspicious": dt > threshold})


def _hardware(params):
    if os.name != "nt":
        return _result(error="Hardware breakpoints require Windows", status="failed")
    _init()
    dr = {}
    try:
        ctx = (ctypes.c_byte * 1232)()
        ctypes.c_uint32.from_address(ctypes.addressof(ctx)).value = 0x100010
        K32.GetThreadContext(ctypes.c_void_p(-2), ctx)
        base = ctypes.addressof(ctx)
        offs = {"Dr0": 0x48, "Dr1": 0x50, "Dr2": 0x58, "Dr3": 0x60,
                "Dr6": 0x68, "Dr7": 0x70}
        for name, off in offs.items():
            dr[name] = ctypes.c_uint64.from_address(base + off).value
    except Exception:
        return _result(error="GetThreadContext failed", status="failed")
    active = [k for k in ("Dr0", "Dr1", "Dr2", "Dr3") if dr.get(k)]
    return _result(data={"registers": dr, "hardware_bps": active,
                         "suspicious": bool(active)})


def _check(params):
    out = {}
    out["peb"] = _peb(params).get("data", {})
    out["ports"] = _ports(params).get("data", {})
    hw = _hardware(params).get("data", {})
    out["hardware"] = hw
    tm = _timing(params).get("data", {})
    out["timing"] = tm
    flags = [out["peb"].get("debugged", False),
             out["ports"].get("debugged", False),
             hw.get("suspicious", False),
             tm.get("suspicious", False)]
    return _result(data={"score": sum(1 for f in flags if f),
                         "verdict": "debugged" if any(flags) else "clean",
                         "checks": out})
