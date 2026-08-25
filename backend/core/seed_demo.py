"""
Seed demo data — MITRE ATT&CK tactics/techniques, sample campaign, findings,
credentials, and playbooks. Runs at startup if the strategy tables are empty.
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from database import database
from db.models import (
    Agent, Campaign, Credential, Finding, Playbook, Tactic, Technique,
)

logger = logging.getLogger(__name__)

# MITRE ATT&CK Enterprise tactics (14)
TACTICS = [
    ("TA0001", "Initial Access", "initial-access",
     "The adversary is trying to get into your network."),
    ("TA0002", "Execution", "execution",
     "The adversary is trying to run malicious code."),
    ("TA0003", "Persistence", "persistence",
     "The adversary is trying to keep their foothold."),
    ("TA0004", "Privilege Escalation", "privilege-escalation",
     "The adversary is trying to gain higher-level permissions."),
    ("TA0005", "Defense Evasion", "defense-evasion",
     "The adversary is trying to avoid being detected."),
    ("TA0006", "Credential Access", "credential-access",
     "The adversary is trying to steal account names and passwords."),
    ("TA0007", "Discovery", "discovery",
     "The adversary is trying to figure out your environment."),
    ("TA0008", "Lateral Movement", "lateral-movement",
     "The adversary is trying to move through your environment."),
    ("TA0009", "Collection", "collection",
     "The adversary is trying to gather data of interest to their goal."),
    ("TA0010", "Exfiltration", "exfiltration",
     "The adversary is trying to steal data."),
    ("TA0011", "Command and Control", "command-and-control",
     "The adversary is trying to communicate with compromised systems."),
    ("TA0040", "Impact", "impact",
     "The adversary is trying to manipulate, interrupt, or destroy your systems and data."),
    ("TA0043", "Reconnaissance", "reconnaissance",
     "The adversary is trying to gather information they can use to plan future operations."),
    ("TA0042", "Resource Development", "resource-development",
     "The adversary is trying to establish resources they can use to support operations."),
]

# Key techniques mapped to Lucy modules
TECHNIQUES = [
    ("T1059", "Command and Scripting Interpreter", "TA0002", "windows", "shell/exec"),
    ("T1059.001", "PowerShell", "TA0002", "windows", "shell/exec"),
    ("T1059.003", "Windows Command Shell", "TA0002", "windows", "shell/exec"),
    ("T1083", "File and Directory Discovery", "TA0007", "all", "file/list"),
    ("T1005", "Data from Local System", "TA0009", "all", "file/read"),
    ("T1113", "Screen Capture", "TA0009", "all", "screenshot/capture"),
    ("T1119", "Automated Collection", "TA0009", "all", "clipboard/capture"),
    ("T1056", "Input Capture", "TA0009", "all", "keylog/start"),
    ("T1056.001", "Keylogging", "TA0009", "all", "keylog/start"),
    ("T1040", "Network Sniffing", "TA0007", "all", "wifi/scan"),
    ("T1046", "Network Service Discovery", "TA0007", "all", "port_scan/scan"),
    ("T1003", "OS Credential Dumping", "TA0006", "windows", "credential_dump/lsass"),
    ("T1003.001", "LSASS Memory", "TA0006", "windows", "credential_dump/lsass"),
    ("T1003.002", "Security Account Manager", "TA0006", "windows", "credential_dump/registry"),
    ("T1555", "Credentials from Password Stores", "TA0006", "all", "browser/passwords"),
    ("T1555.003", "Credentials from Web Browsers", "TA0006", "all", "browser/passwords"),
    ("T1547", "Boot or Logon Autostart Execution", "TA0003", "windows", "persistence/install"),
    ("T1547.001", "Registry Run Keys", "TA0003", "windows", "persistence/install"),
    ("T1021", "Remote Services", "TA0008", "all", "lateral/move"),
    ("T1071", "Application Layer Protocol", "TA0011", "all", "beacon/http"),
    ("T1071.001", "Web Protocols", "TA0011", "all", "beacon/http"),
    ("T1573", "Encrypted Channel", "TA0011", "all", "beacon/wss"),
    ("T1027", "Obfuscated Files or Information", "TA0005", "all", "stealth/enable"),
    ("T1620", "Reflective Code Loading", "TA0005", "windows", "injection/inject"),
    ("T1218", "System Binary Proxy Execution", "TA0005", "windows", "bof/exec"),
    ("T1112", "Modify Registry", "TA0005", "windows", "persistence/install"),
    ("T1087", "Account Discovery", "TA0007", "all", "shell/exec"),
    ("T1018", "Remote System Discovery", "TA0007", "all", "port_scan/scan"),
    ("T1082", "System Information Discovery", "TA0007", "all", "info/collect"),
    ("T1518", "Software Discovery", "TA0007", "all", "process/list"),
]

PLAYBOOKS = [
    {
        "name": "Full Recon Sweep",
        "description": "Complete reconnaissance playbook: system info, port scan, file discovery, user enumeration.",
        "tags": ["recon", "discovery"],
        "steps": [
            {"module": "info", "action": "collect", "params": {}, "delay": 0},
            {"module": "port_scan", "action": "scan", "params": {"host": "127.0.0.1", "ports": [22, 80, 443, 445, 3389]}, "delay": 5},
            {"module": "file", "action": "list", "params": {"path": "."}, "delay": 5},
            {"module": "process", "action": "list", "params": {}, "delay": 5},
        ],
    },
    {
        "name": "Credential Harvest Chain",
        "description": "Dump credentials from LSASS, browser stores, and registry.",
        "tags": ["credentials", "privilege-escalation"],
        "steps": [
            {"module": "credential_dump", "action": "lsass", "params": {}, "delay": 0},
            {"module": "browser", "action": "passwords", "params": {}, "delay": 10},
            {"module": "credential_dump", "action": "registry", "params": {}, "delay": 10},
        ],
    },
    {
        "name": "Persistence + Surveillance",
        "description": "Install persistence mechanism, start keylogger and screenshot capture.",
        "tags": ["persistence", "surveillance"],
        "steps": [
            {"module": "persistence", "action": "install", "params": {"method": "registry_run"}, "delay": 0},
            {"module": "keylog", "action": "start", "params": {}, "delay": 5},
            {"module": "screenshot", "action": "capture", "params": {}, "delay": 5},
        ],
    },
    {
        "name": "Lateral Movement Prep",
        "description": "Discover network hosts, scan for open shares, enumerate active sessions.",
        "tags": ["lateral", "discovery"],
        "steps": [
            {"module": "port_scan", "action": "scan", "params": {"host": "192.168.1.0/24", "ports": [445, 3389, 22]}, "delay": 0},
            {"module": "shell", "action": "exec", "params": {"cmd": "net session"}, "delay": 10},
            {"module": "shell", "action": "exec", "params": {"cmd": "net view /all"}, "delay": 10},
        ],
    },
]

FINDINGS = []  # Findings are now auto-generated by core/finding_engine.py from real task results


def seed_strategy_data() -> None:
    """Seed MITRE tactics, techniques, playbooks, campaigns, and findings."""
    if Tactic.select().count() > 0:
        return

    logger.info("Seeding MITRE ATT&CK strategy data…")

    with database.atomic():
        # Tactics
        tactic_map = {}
        for mitre_id, name, phase, desc in TACTICS:
            t = Tactic.create(
                mitre_id=mitre_id,
                name=name,
                phase=phase,
                description=desc,
            )
            tactic_map[mitre_id] = t

        # Techniques
        for mitre_id, name, tactic_id, platform, module_ref in TECHNIQUES:
            tactic = tactic_map.get(tactic_id)
            Technique.create(
                mitre_id=mitre_id,
                name=name,
                tactic=tactic if tactic else None,
                description=f"MITRE ATT&CK technique {mitre_id}: {name}. Lucy module ref: {module_ref}",
                platform=platform,
                data_sources=json.dumps(["process_monitoring", "file_monitoring", "network_traffic"]),
            )

        # Playbooks
        for pb in PLAYBOOKS:
            Playbook.create(
                name=pb["name"],
                description=pb["description"],
                steps=json.dumps(pb["steps"]),
                tags=json.dumps(pb["tags"]),
            )

        # Campaign
        Campaign.create(
            name="OP RED TEAM ASSESSMENT",
            description="Annual red team engagement targeting internal network and endpoint security controls.",
            objective="Assess detection and response capabilities against simulated APT tactics.",
            status="active",
            start_date=datetime.now(timezone.utc),
        )

        # Findings
        for f in FINDINGS:
            Finding.create(
                title=f["title"],
                severity=f["severity"],
                status=f["status"],
                description=f["description"],
                recommendation=f["recommendation"],
                cvss=f["cvss"],
            )

    logger.info(
        "Seeded %d tactics, %d techniques, %d playbooks, 1 campaign, %d findings.",
        len(TACTICS), len(TECHNIQUES), len(PLAYBOOKS), len(FINDINGS),
    )
