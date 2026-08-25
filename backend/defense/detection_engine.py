"""
Lightweight defensive detection engine for Lucy.

Ingests security events, evaluates them against built-in detection rules,
and produces alerts. Designed for authorized internal monitoring only.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from config import settings

MAX_EVENTS = 10_000
MAX_ALERTS = 2_000


class DetectionEngine:
    """Singleton in-memory detection engine with rule evaluation."""

    _instance: Optional["DetectionEngine"] = None

    def __new__(cls) -> "DetectionEngine":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._events: list[dict] = []
            inst._alerts: list[dict] = []
            inst._rules = cls._load_builtin_rules()
            cls._instance = inst
        return cls._instance

    @staticmethod
    def _load_builtin_rules() -> list[dict]:
        return [
            {
                "id": "def-001",
                "name": "Suspicious Process Injection",
                "description": "Detects process injection techniques such as CreateRemoteThread or NtMapViewOfSection.",
                "severity": "critical",
                "mitre": "T1055",
                "pattern": re.compile(
                    r"createRemoteThread|NtMapViewOfSection|ProcessHollowing|QueueUserAPC",
                    re.IGNORECASE,
                ),
                "fields": ["event_type", "image", "command_line", "details"],
            },
            {
                "id": "def-002",
                "name": "Credential Dumping Indicator",
                "description": "Detects access to LSASS or SAM/SYSTEM hives.",
                "severity": "critical",
                "mitre": "T1003",
                "pattern": re.compile(
                    r"lsass\.exe|SamSs|SECURITY\s+SAM|mimikatz|sekurlsa|DumpCreds",
                    re.IGNORECASE,
                ),
                "fields": ["image", "target_image", "command_line", "details"],
            },
            {
                "id": "def-003",
                "name": "Persistence via Registry Run Key",
                "description": "Detects writes to registry run keys used for persistence.",
                "severity": "high",
                "mitre": "T1547.001",
                "pattern": re.compile(
                    r"Software\\Microsoft\\Windows\\CurrentVersion\\Run|RunOnce",
                    re.IGNORECASE,
                ),
                "fields": ["event_type", "object", "details"],
            },
            {
                "id": "def-004",
                "name": "Outbound Connection to Rare Port",
                "description": "Flags outbound network connections to high/uncommon ports.",
                "severity": "medium",
                "mitre": "T1041",
                "pattern": re.compile(r"destination_port", re.IGNORECASE),
                "fields": ["event_type", "destination_port"],
                "condition": "port_check",
            },
            {
                "id": "def-005",
                "name": "Keylogger-like Activity",
                "description": "Detects hooks or repeated low-level keyboard input reads.",
                "severity": "high",
                "mitre": "T1056.001",
                "pattern": re.compile(
                    r"SetWindowsHookEx|GetAsyncKeyState|LLMHF|WH_KEYBOARD_LL|keylog",
                    re.IGNORECASE,
                ),
                "fields": ["image", "command_line", "details"],
            },
            {
                "id": "def-006",
                "name": "Webcam or Screenshot Capture",
                "description": "Detects attempts to access camera or screen capture APIs.",
                "severity": "medium",
                "mitre": "T1125",
                "pattern": re.compile(
                    r"capCreateCaptureWindow|DirectShow|PrintWindow|BitBlt|MagnificationAPI",
                    re.IGNORECASE,
                ),
                "fields": ["image", "command_line", "details"],
            },
            {
                "id": "def-007",
                "name": "UAC Bypass Attempt",
                "description": "Detects known UAC bypass techniques.",
                "severity": "high",
                "mitre": "T1548.002",
                "pattern": re.compile(
                    r"fodhelper|computerdefaults|sdclt|eventvwr|dccwlaunch",
                    re.IGNORECASE,
                ),
                "fields": ["image", "command_line", "parent_image"],
            },
            {
                "id": "def-008",
                "name": "Lateral Movement via SMB/PSExec",
                "description": "Detects SMB exec or service creation patterns.",
                "severity": "high",
                "mitre": "T1021.002",
                "pattern": re.compile(
                    r"psexec|\\\\ADMIN\$|svcctl|PsExec|remcom|C\$|IPC\$",
                    re.IGNORECASE,
                ),
                "fields": ["image", "command_line", "destination_host"],
            },
            {
                "id": "def-009",
                "name": "Kerberoasting Request",
                "description": "Detects Kerberos service ticket requests with weak encryption.",
                "severity": "high",
                "mitre": "T1558.003",
                "pattern": re.compile(
                    r"Kerberos Service Ticket|RC4|DES|kerberoast|TGS-REQ",
                    re.IGNORECASE,
                ),
                "fields": ["event_type", "service_name", "encryption_type"],
            },
            {
                "id": "def-010",
                "name": "Encoded PowerShell / IEX",
                "description": "Detects encoded PowerShell commands, Invoke-Expression, or common download cradles.",
                "severity": "high",
                "mitre": "T1059.001",
                "pattern": re.compile(
                    r"-enc\s+|-EncodedCommand\s+|IEX\(|Invoke-Expression|bitsadmin|certutil\s+-urlcache|Invoke-WebRequest",
                    re.IGNORECASE,
                ),
                "fields": ["image", "command_line", "parent_image"],
            },
            {
                "id": "def-011",
                "name": "Ingress Tool Transfer",
                "description": "Detects commands used to download and execute payloads from remote hosts.",
                "severity": "medium",
                "mitre": "T1105",
                "pattern": re.compile(
                    r"certutil\s+-urlcache|bitsadmin\s+/transfer|Invoke-WebRequest.*-OutFile|wget\s+.*\|\s*bash|curl\s+.*\|\s*sh",
                    re.IGNORECASE,
                ),
                "fields": ["image", "command_line"],
            },
        ]

    def ingest(self, event: dict) -> dict:
        """Ingest a single security event and return it with an assigned id."""
        event = {
            "id": event.get("id") or str(uuid.uuid4()),
            "timestamp": event.get("timestamp")
            or datetime.now(timezone.utc).isoformat(),
            "source": event.get("source", "unknown"),
            "hostname": event.get("hostname", "unknown"),
            "event_type": event.get("event_type", "generic"),
            **event,
        }
        # Normalize
        event.setdefault("severity", "info")
        event.setdefault("mitre", None)

        self._events.append(event)
        if len(self._events) > MAX_EVENTS:
            self._events = self._events[-MAX_EVENTS:]

        self._evaluate(event)
        return event

    def ingest_bulk(self, events: list[dict]) -> list[dict]:
        return [self.ingest(e) for e in events]

    def _evaluate(self, event: dict) -> None:
        text_blob = " ".join(str(event.get(k, "")) for k in event).lower()
        for rule in self._rules:
            matched = bool(rule["pattern"].search(text_blob))
            if not matched and rule.get("condition") == "port_check":
                matched = self._rare_port_check(event)
            if matched:
                self._alert(event, rule)

    @staticmethod
    def _rare_port_check(event: dict) -> bool:
        try:
            port = int(event.get("destination_port", 0))
        except (ValueError, TypeError):
            return False
        common_ports = {80, 443, 53, 22, 25, 587, 993, 995, 8080}
        return port > 1024 and port not in common_ports

    def _alert(self, event: dict, rule: dict) -> None:
        alert = {
            "id": str(uuid.uuid4()),
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "severity": rule["severity"],
            "mitre": rule.get("mitre"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_event_id": event["id"],
            "hostname": event.get("hostname", "unknown"),
            "summary": f"{rule['name']} detected on {event.get('hostname', 'unknown')}",
            "details": {k: event.get(k) for k in rule.get("fields", [])},
            "read": False,
        }
        self._alerts.append(alert)
        if len(self._alerts) > MAX_ALERTS:
            self._alerts = self._alerts[-MAX_ALERTS:]

    def list_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        hostname: Optional[str] = None,
    ) -> list[dict]:
        events = list(reversed(self._events))
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if hostname:
            events = [e for e in events if e.get("hostname") == hostname]
        return events[:limit]

    def list_alerts(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        unread_only: bool = False,
    ) -> list[dict]:
        alerts = list(reversed(self._alerts))
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        if unread_only:
            alerts = [a for a in alerts if not a.get("read")]
        return alerts[:limit]

    def mark_alert_read(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a["id"] == alert_id:
                a["read"] = True
                return True
        return False

    def mark_all_alerts_read(self) -> int:
        count = 0
        for a in self._alerts:
            if not a.get("read"):
                a["read"] = True
                count += 1
        return count

    def unread_alert_count(self) -> int:
        return sum(1 for a in self._alerts if not a.get("read"))

    def get_rules(self) -> list[dict]:
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "severity": r["severity"],
                "mitre": r.get("mitre"),
                "enabled": True,
            }
            for r in self._rules
        ]

    def stats(self) -> dict:
        return {
            "events_ingested": len(self._events),
            "alerts_generated": len(self._alerts),
            "unread_alerts": self.unread_alert_count(),
            "rules_active": len(self._rules),
            "by_severity": {
                "critical": sum(1 for a in self._alerts if a["severity"] == "critical"),
                "high": sum(1 for a in self._alerts if a["severity"] == "high"),
                "medium": sum(1 for a in self._alerts if a["severity"] == "medium"),
                "low": sum(1 for a in self._alerts if a["severity"] == "low"),
                "info": sum(1 for a in self._alerts if a["severity"] == "info"),
            },
        }
