"""
Finding Engine — Auto-generates findings from real task results.
Analyzes task outputs and creates structured findings with severity,
evidence, and recommendations based on what was actually found.

This replaces the hardcoded demo findings with real, data-driven findings.
"""
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Any

from database import database
from db.models import Finding, Task, Agent

logger = logging.getLogger(__name__)


# --- Rule-based finding generators -------------------------------------------
# Each rule examines a task result and may produce a finding.

def _hash_evidence(data: str) -> str:
    """SHA-256 hash of evidence for chain-of-custody."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def _create_finding(
    title: str,
    severity: str,
    description: str,
    recommendation: str,
    evidence: str,
    cvss: float,
    agent_id: str,
    task_id: str,
) -> Finding | None:
    """Create a finding if one with the same title+agent doesn't already exist."""
    try:
        existing = Finding.select().where(
            (Finding.title == title) & (Finding.agent_id == agent_id)
        ).first()
        if existing:
            # Update evidence with new task reference
            return existing

        with database.atomic():
            f = Finding.create(
                title=title,
                severity=severity,
                status="draft",
                description=description,
                recommendation=recommendation,
                evidence=json.dumps({
                    "task_id": str(task_id),
                    "agent_id": str(agent_id),
                    "hash": _hash_evidence(evidence),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "raw_size": len(evidence),
                }, ensure_ascii=False),
                cvss=str(cvss),
                agent_id=agent_id,
            )
        logger.info("Auto-finding created: %s (severity=%s, agent=%s)", title, severity, agent_id)
        return f
    except Exception as exc:
        logger.error("Failed to create finding '%s': %s", title, exc)
        return None


def _analyze_credential_dump(task: Task, result: Any) -> list[Finding]:
    """Analyze credential_dump results."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)

    # LSASS dump
    if "dump_base64" in data or "dump_size" in data:
        dump_size = data.get("dump_size", 0)
        if dump_size > 0:
            findings.append(_create_finding(
                title="LSASS memory dump successful — credentials exposed",
                severity="critical",
                description=(
                    f"LSASS process memory was dumped successfully ({dump_size} bytes). "
                    "The dump contains NTLM hashes, Kerberos tickets, and potentially plaintext credentials. "
                    "This indicates LSA Protection (RunAsPPL) is not enabled."
                ),
                recommendation=(
                    "Enable LSA Protection (RunAsPPL) via GPO. Deploy Windows Credential Guard. "
                    "Restrict SeDebugPrivilege to Administrators only."
                ),
                evidence=str(data.get("dump_base64", ""))[:1000],
                cvss=9.1,
                agent_id=task.agent_id or "",
                task_id=str(task.id),
            ))

    # DPAPI keys
    master_keys = data.get("master_keys", [])
    if isinstance(master_keys, list) and len(master_keys) > 0:
        findings.append(_create_finding(
            title=f"DPAPI master keys exposed ({len(master_keys)} keys)",
            severity="high",
            description=(
                f"{len(master_keys)} DPAPI master keys were extracted from the user profile. "
                "These keys can decrypt stored browser passwords, WiFi credentials, and other "
                "DPAPI-protected secrets when combined with the user's password."
            ),
            recommendation=(
                "Rotate user credentials. Consider deploying Windows Hello for Business. "
                "Restrict file system access to user profile directories."
            ),
            evidence=f"{len(master_keys)} master keys extracted",
            cvss=7.5,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    # Registry hives
    hives = data.get("hives", [])
    if isinstance(hives, list):
        saved = [h for h in hives if h.get("saved")]
        if saved:
            hive_names = ", ".join(h.get("hive", "?") for h in saved)
            findings.append(_create_finding(
                title=f"Registry hives dumped: {hive_names}",
                severity="critical",
                description=(
                    f"Windows registry hives ({hive_names}) were saved and extracted. "
                    "These contain SAM hashes (NTLM) and can be cracked offline with hashcat/john."
                ),
                recommendation=(
                    "Enable Credential Guard. Use LAPS for local admin password management. "
                    "Monitor for 'reg save' commands via EDR."
                ),
                evidence=f"Hives saved: {hive_names}",
                cvss=8.8,
                agent_id=task.agent_id or "",
                task_id=str(task.id),
            ))

    # Kerberos tickets
    tickets = data.get("tickets", [])
    if isinstance(tickets, list) and len(tickets) > 0:
        findings.append(_create_finding(
            title=f"Kerberos tickets cached ({len(tickets)} tickets)",
            severity="medium",
            description=(
                f"{len(tickets)} Kerberos tickets were found in cache. "
                "These can be used for Pass-the-Ticket attacks to impersonate users."
            ),
            recommendation="Reduce Kerberos ticket lifetime. Monitor for ticket reuse via EDR.",
            evidence=f"{len(tickets)} tickets",
            cvss=5.3,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    return [f for f in findings if f is not None]


def _analyze_browser_passwords(task: Task, result: Any) -> list[Finding]:
    """Analyze browser password extraction results."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)
    passwords = data.get("passwords", [])
    if isinstance(passwords, list) and len(passwords) > 0:
        findings.append(_create_finding(
            title=f"Browser passwords extracted ({len(passwords)} credentials)",
            severity="high" if len(passwords) > 10 else "medium",
            description=(
                f"{len(passwords)} saved passwords were extracted from web browsers. "
                "These credentials may provide access to corporate portals, email, and cloud services."
            ),
            recommendation=(
                "Deploy enterprise password manager. Enforce browser master passwords via GPO. "
                "Rotate credentials for exposed accounts."
            ),
            evidence=f"{len(passwords)} passwords from browsers",
            cvss=7.5 if len(passwords) > 10 else 5.3,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    cookies = data.get("cookies", [])
    if isinstance(cookies, list) and len(cookies) > 0:
        findings.append(_create_finding(
            title=f"Session cookies extracted ({len(cookies)} cookies)",
            severity="high",
            description=(
                f"{len(cookies)} session cookies were extracted. "
                "These can be used for session hijacking attacks to impersonate authenticated users."
            ),
            recommendation="Enable session binding to IP/device. Implement CSRF tokens. Shorten session timeouts.",
            evidence=f"{len(cookies)} cookies",
            cvss=6.5,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    return [f for f in findings if f is not None]


def _analyze_wifi_credentials(task: Task, result: Any) -> list[Finding]:
    """Analyze WiFi credential extraction."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)
    creds = data.get("credentials", [])
    if isinstance(creds, list) and len(creds) > 0:
        findings.append(_create_finding(
            title=f"WiFi credentials extracted ({len(creds)} networks)",
            severity="medium",
            description=(
                f"{len(creds)} WiFi network credentials (WPA/WPA2) were extracted. "
                "These could allow an attacker to access corporate wireless networks."
            ),
            recommendation="Use WPA3 where possible. Implement 802.1X authentication. Rotate WiFi passwords.",
            evidence=f"{len(creds)} WiFi credentials",
            cvss=4.9,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    return [f for f in findings if f is not None]


def _analyze_edr_status(task: Task, result: Any) -> list[Finding]:
    """Analyze EDR evasion status results."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)
    amsi_patched = data.get("amsi_patched", False)
    etw_patched = data.get("etw_patched", False)
    ntdll_unhooked = data.get("ntdll_unhooked", False)

    if amsi_patched:
        findings.append(_create_finding(
            title="AMSI patched — PowerShell scripts undetected",
            severity="high",
            description=(
                "AMSI (Anti-Malware Scan Interface) has been patched in memory. "
                "PowerShell scripts can execute without being scanned by AV/EDR."
            ),
            recommendation="Monitor for AMSI patching attempts. Deploy EDR with behavioral detection.",
            evidence="amsi_patched=true",
            cvss=7.5,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    if etw_patched:
        findings.append(_create_finding(
            title="ETW patched — telemetry suppressed",
            severity="high",
            description=(
                "ETW (Event Tracing for Windows) has been patched. "
                "Security telemetry from .NET and PowerShell is no longer being logged."
            ),
            recommendation="Monitor for ETW tampering. Use kernel-level telemetry that can't be patched from userland.",
            evidence="etw_patched=true",
            cvss=7.5,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    if ntdll_unhooked:
        findings.append(_create_finding(
            title="NTDLL unhooked — EDR userland hooks removed",
            severity="high",
            description=(
                "NTDLL has been restored from a clean copy, removing EDR userland hooks. "
                "This allows direct syscalls that bypass EDR monitoring."
            ),
            recommendation="Deploy EDR with kernel-level hooks. Monitor for ntdll restoration attempts.",
            evidence="ntdll_unhooked=true",
            cvss=7.5,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    return [f for f in findings if f is not None]


def _analyze_port_scan(task: Task, result: Any) -> list[Finding]:
    """Analyze port scan results for exposed services."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)
    open_ports = data.get("open_ports", [])
    if isinstance(open_ports, list) and len(open_ports) > 0:
        # Map ports to service names and risk
        risky_ports = {
            23: ("Telnet", "critical", 9.8),
            21: ("FTP", "high", 7.5),
            445: ("SMB", "high", 8.6),
            3389: ("RDP", "high", 8.6),
            135: ("RPC", "medium", 5.3),
            139: ("NetBIOS", "medium", 5.3),
            1433: ("MSSQL", "high", 7.5),
            3306: ("MySQL", "high", 7.5),
            5432: ("PostgreSQL", "high", 7.5),
            5985: ("WinRM", "medium", 6.5),
            22: ("SSH", "low", 3.7),
        }

        for port_info in open_ports:
            if isinstance(port_info, dict):
                port = port_info.get("port", 0)
            elif isinstance(port_info, (int, str)):
                port = int(port_info)
            else:
                continue

            if port in risky_ports:
                service, severity, cvss = risky_ports[port]
                findings.append(_create_finding(
                    title=f"Exposed {service} service on port {port}",
                    severity=severity,
                    description=(
                        f"{service} service is listening on port {port}. "
                        f"This service may allow unauthorized access or credential attacks."
                    ),
                    recommendation=f"Restrict access to port {port} via firewall. Disable {service} if not needed. "
                                  f"Require VPN for remote access.",
                    evidence=f"port {port} open ({service})",
                    cvss=cvss,
                    agent_id=task.agent_id or "",
                    task_id=str(task.id),
                ))

    return [f for f in findings if f is not None]


def _analyze_persistence(task: Task, result: Any) -> list[Finding]:
    """Analyze persistence check/install results."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)
    mechanisms = data.get("mechanisms", data.get("entries", []))
    if isinstance(mechanisms, list) and len(mechanisms) > 0:
        findings.append(_create_finding(
            title=f"Persistence mechanisms detected ({len(mechanisms)} entries)",
            severity="high",
            description=(
                f"{len(mechanisms)} persistence mechanisms were found. "
                "These allow malware to survive system reboots and maintain access."
            ),
            recommendation="Audit all startup entries. Deploy EDR with persistence monitoring. Use AppLocker.",
            evidence=f"{len(mechanisms)} persistence entries",
            cvss=7.2,
            agent_id=task.agent_id or "",
            task_id=str(task.id),
        ))

    return [f for f in findings if f is not None]


def _analyze_token_privileges(task: Task, result: Any) -> list[Finding]:
    """Analyze token privilege enumeration."""
    findings = []
    if not isinstance(result, dict):
        return findings

    data = result.get("data", result)
    privileges = data.get("privileges", [])
    if isinstance(privileges, list):
        high_priv = {
            "SeDebugPrivilege": ("SeDebugPrivilege", "critical", 9.0, "Allows reading any process memory including LSASS"),
            "SeImpersonatePrivilege": ("SeImpersonatePrivilege", "high", 8.0, "Enables potato attacks for privilege escalation"),
            "SeAssignPrimaryTokenPrivilege": ("SeAssignPrimaryTokenPrivilege", "high", 7.5, "Can create processes as other users"),
            "SeTcbPrivilege": ("SeTcbPrivilege", "critical", 9.5, "Act as part of the operating system"),
            "SeBackupPrivilege": ("SeBackupPrivilege", "high", 7.0, "Can read any file regardless of ACL"),
            "SeRestorePrivilege": ("SeRestorePrivilege", "high", 7.0, "Can write any file regardless of ACL"),
            "SeLoadDriverPrivilege": ("SeLoadDriverPrivilege", "high", 7.5, "Can load kernel drivers — kernel compromise"),
        }

        for priv in privileges:
            if isinstance(priv, dict):
                priv_name = priv.get("name", "")
                priv_enabled = priv.get("enabled", False)
            else:
                continue

            # Check for high-privilege tokens
            for check_name, (name, severity, cvss, desc) in high_priv.items():
                if check_name.lower() in priv_name.lower():
                    findings.append(_create_finding(
                        title=f"High privilege detected: {name}",
                        severity=severity,
                        description=f"{name} is {'enabled' if priv_enabled else 'present but disabled'}. {desc}.",
                        recommendation=f"Restrict {name} to required accounts only. Use Just Enough Administration (JEA).",
                        evidence=f"{name}={'enabled' if priv_enabled else 'disabled'}",
                        cvss=cvss,
                        agent_id=task.agent_id or "",
                        task_id=str(task.id),
                    ))
                    break

    return [f for f in findings if f is not None]


# --- Main entry point --------------------------------------------------------

ANALYZERS = {
    "credential_dump": _analyze_credential_dump,
    "browser": _analyze_browser_passwords,
    "wifi": _analyze_wifi_credentials,
    "edr_evasion": _analyze_edr_status,
    "port_scan": _analyze_port_scan,
    "persistence": _analyze_persistence,
    "persistence_adv": _analyze_persistence,
    "token": _analyze_token_privileges,
}


def generate_findings_from_task(task: Task) -> list[Finding]:
    """Analyze a completed task and auto-generate findings from its results.

    This is the main entry point — called after a task completes.
    Returns the list of findings created (may be empty).
    """
    if task.status not in ("completed", "ok"):
        return []

    # Parse result
    result = task.result
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            return []
    if not isinstance(result, dict):
        return []

    analyzer = ANALYZERS.get(task.module)
    if not analyzer:
        return []

    try:
        return analyzer(task, result)
    except Exception as exc:
        logger.error("Finding analyzer failed for %s/%s: %s", task.module, task.action, exc)
        return []


def process_recent_tasks(limit: int = 100) -> int:
    """Process recent completed tasks and generate findings.
    Returns the number of findings created."""
    total = 0
    try:
        tasks = Task.select().where(
            Task.status.in_(["completed", "ok"])
        ).order_by(Task.created_at.desc()).limit(limit)

        for task in tasks:
            findings = generate_findings_from_task(task)
            total += len(findings)
    except Exception as exc:
        logger.error("Failed to process recent tasks: %s", exc)

    return total
