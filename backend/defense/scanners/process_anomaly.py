import json
import re
import subprocess
from datetime import datetime

SUSPICIOUS_PATTERNS = [
    ("credential_dump", re.compile(r"sekurlsa::|mimikatz|DumpCreds|lsadump", re.IGNORECASE), "T1003"),
    ("bypass_uac", re.compile(r"fodhelper|computerdefaults|sdclt|eventvwr", re.IGNORECASE), "T1548.002"),
    ("encoded_powershell", re.compile(r"-enc\s+| -encodedcommand |IEX\(|Invoke-Expression", re.IGNORECASE), "T1059.001"),
    ("suspicious_download", re.compile(r"bitsadmin|certutil\s+-urlcache|Invoke-WebRequest", re.IGNORECASE), "T1105"),
    ("wmi_persistence", re.compile(r"wmic.*process\s+call\s+create|WMIC.*Create", re.IGNORECASE), "T1546.003"),
    ("psexec", re.compile(r"psexec|\\ADMIN\$|svcctl", re.IGNORECASE), "T1021.002"),
    ("kerberoast", re.compile(r"kerberoast|tgsrepcrack|rc4_hmac", re.IGNORECASE), "T1558.003"),
]


def _get_processes() -> list[dict]:
    processes = []
    try:
        # PowerShell one-liner to list processes with command lines (Windows-friendly).
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout)
        if isinstance(data, dict):
            data = [data]
        for item in data:
            processes.append({
                "pid": item.get("ProcessId"),
                "name": item.get("Name") or "unknown",
                "command_line": item.get("CommandLine") or "",
            })
    except Exception as exc:
        processes.append({"pid": 0, "name": "error", "command_line": str(exc)})
    return processes


def run(action: str = "scan", **params) -> dict:
    """Lightweight process anomaly detector for authorized internal hosts."""
    processes = _get_processes()
    findings = []
    seen_pids = set()

    for proc in processes:
        text = f"{proc['name']} {proc['command_line']}"
        for label, pattern, mitre in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                if proc["pid"] in seen_pids:
                    continue
                seen_pids.add(proc["pid"])
                findings.append({
                    "pid": proc["pid"],
                    "name": proc["name"],
                    "command_line": proc["command_line"],
                    "detection": label,
                    "mitre": mitre,
                })

    return {
        "status": "completed",
        "action": action,
        "total_processes": len(processes),
        "suspicious_count": len(findings),
        "findings": findings,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
