"""
Auto-recon chain engine for Project Lucy.

Runs as a background async task (like PredictiveAlertEngine).
When triggered (manually or on new agent connection), dispatches a chain
of recon tasks to the agent, collects results, and analyzes them to
suggest next-step actions (privilege escalation, evasion, lateral
movement, credential dumping, session hijacking).

Results and analysis are stored in memory and surfaced through the
AlertManager when interesting findings are discovered.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Recon task chain definition
# ---------------------------------------------------------------------------

RECON_CHAIN: list[dict] = [
    {"label": "sysinfo",            "module": "builtin",  "action": "sysinfo",       "params": {},            "timeout": 30},
    {"label": "whoami_all",         "module": "shell",    "action": "run",           "params": {"cmd": "whoami /all"}, "timeout": 15},
    {"label": "local_admins",       "module": "shell",    "action": "run",           "params": {"cmd": "net localgroup administrators"}, "timeout": 15},
    {"label": "local_users",        "module": "shell",    "action": "run",           "params": {"cmd": "net user"}, "timeout": 15},
    {"label": "tasklist_svc",       "module": "shell",    "action": "run",           "params": {"cmd": "tasklist /svc"}, "timeout": 20},
    {"label": "netstat_ano",        "module": "shell",    "action": "run",           "params": {"cmd": "netstat -ano"}, "timeout": 20},
    {"label": "systeminfo",         "module": "shell",    "action": "run",           "params": {"cmd": "systeminfo"}, "timeout": 30},
    {"label": "arp_a",              "module": "shell",    "action": "run",           "params": {"cmd": "arp -a"}, "timeout": 15},
    {"label": "route_print",        "module": "shell",    "action": "run",           "params": {"cmd": "route print"}, "timeout": 15},
    {"label": "ipconfig_all",       "module": "shell",    "action": "run",           "params": {"cmd": "ipconfig /all"}, "timeout": 15},
    {"label": "query_session",      "module": "shell",    "action": "run",           "params": {"cmd": "query session"}, "timeout": 15},
    {"label": "net_share",          "module": "shell",    "action": "run",           "params": {"cmd": "net share"}, "timeout": 15},
    {"label": "sc_query_all",       "module": "shell",    "action": "run",           "params": {"cmd": "sc query state= all"}, "timeout": 20},
    {"label": "reg_query_software", "module": "shell",    "action": "run",           "params": {"cmd": "reg query HKLM\\SOFTWARE"}, "timeout": 20},
]

# Interesting process names that indicate security tooling.
_AV_EDR_PROCESSES = {
    "msmpeng", "msmpeng.exe", "mssense", "sensece", "atpworker",
    "csfalcon", "csfalconcontainer", "csfalconhealth",  # CrowdStrike
    "tdrsaio", "tdwinext", "tam", "tamwatchdog",        # ThreatDefender
    "mbam", "mbamtray", "mbamservice",                  # Malwarebytes
    "avp", "kavfs", "klnagent",                         # Kaspersky
    "avg", "avgsvc", "avgrsa",                          # AVG
    "avshadow", "avscan",                               # Avira
    "bdservicehost", "vsserv",                          # Bitdefender
    "mcshield", "mcafee", "masvc",                      # McAfee
    "sep", "rtvscan", "smc",                            # Symantec
    "edpa", "wrsa",                                     # Webroot
    " Sophos", "sophos",                                # Sophos
    "tnb", "f-secure",                                  # F-Secure
    "eset", "ekrn",                                     # ESET
    "carbonblack", "cb",                                # Carbon Black
    "sentinel", "sentinelagent",                        # SentinelOne
    " Sophos MCS Agent",
    "veeam",                                            # Veeam backup
    "backupexec",                                       # Backup Exec
}

# Interesting share names that may be useful for lateral movement.
_INTERESTING_SHARES = {"c$", "admin$", "ipc$", "sysvol", "netlogon"}


class AutoReconEngine:
    """Singleton auto-recon chain engine."""

    _instance: Optional["AutoReconEngine"] = None

    def __new__(cls) -> "AutoReconEngine":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._results: dict[str, dict] = {}          # agent_id -> latest recon
            inst._analyses: dict[str, dict] = {}          # agent_id -> latest analysis
            inst._task: Optional[asyncio.Task] = None
            inst._loop: Optional[asyncio.AbstractEventLoop] = None
            inst._lock = asyncio.Lock()
            inst._running = False
            inst._auto_enabled = False                    # auto-recon on new connections
            inst._active_recons: dict[str, asyncio.Task] = {}  # agent_id -> running task
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        current_loop = asyncio.get_running_loop()
        if self._running and self._loop is current_loop and self._task and not self._task.done():
            return
        if self._task and self._loop is not current_loop:
            self._task.cancel()
        self._running = True
        self._loop = current_loop
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("AutoReconEngine started.")

    async def stop(self) -> None:
        self._running = False
        current_loop = asyncio.get_running_loop()
        if self._task:
            if self._loop is current_loop:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            else:
                self._task.cancel()
            self._task = None
        # Cancel any active recon tasks
        for task in list(self._active_recons.values()):
            task.cancel()
        self._active_recons.clear()
        logger.info("AutoReconEngine stopped.")

    async def _monitor_loop(self) -> None:
        """Background loop — currently a no-op placeholder for future scheduling."""
        while self._running:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("AutoRecon monitor loop error")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recon_results(self, agent_id: str) -> dict | None:
        """Return the latest recon results for an agent."""
        return self._results.get(agent_id)

    def get_all_results(self, limit: int = 50) -> list[dict]:
        """Return recent recon results across all agents."""
        items = sorted(
            self._results.values(),
            key=lambda r: r.get("timestamp", ""),
            reverse=True,
        )
        return items[:limit]

    def get_analysis(self, agent_id: str) -> dict | None:
        """Return the AI analysis of recon results for an agent."""
        return self._analyses.get(agent_id)

    def is_auto_enabled(self) -> bool:
        return self._auto_enabled

    def set_auto_enabled(self, enabled: bool) -> None:
        self._auto_enabled = enabled
        logger.info("Auto-recon on new connections %s.", "enabled" if enabled else "disabled")

    async def trigger_recon(self, agent_id: str) -> dict:
        """
        Trigger a recon chain on an agent.
        Dispatches all recon tasks, waits for completion, analyzes results,
        and stores everything in memory.
        """
        # Cancel any existing recon for this agent
        existing = self._active_recons.pop(agent_id, None)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(self._run_recon_chain(agent_id))
        self._active_recons[agent_id] = task
        return {"agent_id": agent_id, "status": "started", "tasks": len(RECON_CHAIN)}

    async def on_agent_connect(self, agent_id: str) -> None:
        """Called when an agent connects — triggers recon if auto is enabled."""
        if not self._auto_enabled:
            return
        logger.info("Auto-recon triggered for new agent %s.", agent_id)
        await self.trigger_recon(agent_id)

    # ------------------------------------------------------------------
    # Internal: recon chain execution
    # ------------------------------------------------------------------

    async def _run_recon_chain(self, agent_id: str) -> None:
        """Dispatch all recon tasks, collect results, and analyze."""
        from core.task_queue import TaskQueue

        task_queue = TaskQueue()
        dispatched: dict[str, dict] = {}  # task_id -> chain step

        # Dispatch all recon tasks
        for step in RECON_CHAIN:
            try:
                task = await task_queue.enqueue(
                    agent_id=agent_id,
                    module=step["module"],
                    action=step["action"],
                    params=step["params"],
                    priority="normal",
                    timeout=step["timeout"],
                )
                dispatched[str(task.id)] = {
                    "label": step["label"],
                    "task_id": str(task.id),
                    "module": step["module"],
                    "action": step["action"],
                }
            except Exception as exc:
                logger.warning("Failed to dispatch recon task '%s': %s", step["label"], exc)

        if not dispatched:
            logger.warning("No recon tasks dispatched for agent %s.", agent_id)
            return

        # Wait for all tasks to complete (poll the Task model)
        results = await self._collect_results(dispatched, agent_id)

        # Store raw results
        recon_record = {
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_count": len(dispatched),
            "results": results,
        }

        async with self._lock:
            self._results[agent_id] = recon_record

        # Analyze results
        analysis = self._analyze_results(results, agent_id)

        async with self._lock:
            self._analyses[agent_id] = {
                "agent_id": agent_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "analysis": analysis,
            }

        # Emit alerts for interesting findings
        await self._emit_findings_alerts(agent_id, analysis)

        self._active_recons.pop(agent_id, None)
        logger.info("Recon complete for agent %s — %d findings.", agent_id, len(analysis.get("findings", [])))

    async def _collect_results(self, dispatched: dict[str, dict], agent_id: str) -> dict:
        """Poll the Task model until all dispatched tasks complete or timeout."""
        from database import database
        from db.models import Task

        results: dict[str, dict] = {}
        task_ids = list(dispatched.keys())
        max_wait = 120  # seconds
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait:
            with database:
                pending = []
                for task_id in task_ids:
                    if task_id in results:
                        continue
                    task = Task.get_or_none(Task.id == task_id)
                    if task and task.status in ("completed", "failed"):
                        step = dispatched[task_id]
                        result_data = None
                        if task.result:
                            try:
                                result_data = json.loads(task.result)
                            except (json.JSONDecodeError, TypeError):
                                result_data = task.result
                        results[step["label"]] = {
                            "task_id": task_id,
                            "status": task.status,
                            "data": result_data,
                            "error": task.error,
                        }
                    else:
                        pending.append(task_id)

            if not pending:
                break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Mark any remaining as timed out
        for task_id in task_ids:
            step = dispatched[task_id]
            if step["label"] not in results:
                results[step["label"]] = {
                    "task_id": task_id,
                    "status": "timeout",
                    "data": None,
                    "error": "Timed out waiting for result",
                }

        return results

    # ------------------------------------------------------------------
    # Analysis engine
    # ------------------------------------------------------------------

    def _analyze_results(self, results: dict, agent_id: str) -> dict:
        """Analyze recon results and suggest next-step actions."""
        findings: list[dict] = []
        suggestions: list[dict] = []

        # --- Check if user is admin / SYSTEM ---
        whoami = _extract_stdout(results.get("whoami_all", {}))
        if whoami:
            if "S-1-5-18" in whoami or "NT AUTHORITY\\SYSTEM" in whoami:
                findings.append({"category": "privilege", "severity": "critical",
                                 "detail": "Process is running as SYSTEM"})
                suggestions.append({"action": "credential_dump", "reason": "Running as SYSTEM — dump LSASS/registry credentials"})
            elif "S-1-16-12288" in whoami or "High Mandatory Level" in whoami:
                findings.append({"category": "privilege", "severity": "warning",
                                 "detail": "Process running at High integrity (elevated)"})
                suggestions.append({"action": "credential_dump", "reason": "Elevated process — credential dump viable"})
            elif "S-1-5-32-544" in whoami or "Administrators" in whoami:
                findings.append({"category": "privilege", "severity": "warning",
                                 "detail": "User is a member of the local Administrators group"})
                suggestions.append({"action": "uac_bypass", "reason": "Admin user but not elevated — try UAC bypass for high integrity"})

        # --- Check for AV / EDR / backup agents ---
        tasklist = _extract_stdout(results.get("tasklist_svc", {}))
        if tasklist:
            tasklist_lower = tasklist.lower()
            detected_tools = []
            for proc in _AV_EDR_PROCESSES:
                if proc.lower() in tasklist_lower:
                    detected_tools.append(proc)
            if detected_tools:
                findings.append({"category": "security_tools", "severity": "warning",
                                 "detail": f"Security tooling detected: {', '.join(detected_tools)}"})
                suggestions.append({"action": "evasion", "reason": f"AV/EDR detected ({', '.join(detected_tools)}) — consider evasion or disable_defender"})

        # --- Check for open shares ---
        netshare = _extract_stdout(results.get("net_share", {}))
        if netshare:
            found_shares = []
            for share in _INTERESTING_SHARES:
                if share.lower() in netshare.lower():
                    found_shares.append(share)
            if found_shares:
                findings.append({"category": "shares", "severity": "info",
                                 "detail": f"Interesting shares found: {', '.join(found_shares)}"})
                suggestions.append({"action": "lateral_movement", "reason": f"Administrative shares available ({', '.join(found_shares)}) — lateral movement possible"})

        # --- Check for RDP sessions ---
        query_session = _extract_stdout(results.get("query_session", {}))
        if query_session and query_session.strip() and "No sessions" not in query_session:
            findings.append({"category": "rdp_sessions", "severity": "info",
                             "detail": "Active RDP sessions detected"})
            suggestions.append({"action": "session_hijacking", "reason": "Active RDP sessions — consider session hijacking"})

        # --- Check for cached credentials ---
        whoami_groups = whoami or ""
        if "SeTcbPrivilege" in whoami_groups or "SeImpersonatePrivilege" in whoami_groups:
            findings.append({"category": "privileges", "severity": "warning",
                             "detail": "Process has impersonation privileges (SeImpersonate/SeTcb)"})
            suggestions.append({"action": "privilege_escalation", "reason": "SeImpersonatePrivilege available — Potato attacks viable"})

        # --- Check network connections for interesting ports ---
        netstat = _extract_stdout(results.get("netstat_ano", {}))
        if netstat:
            interesting_ports = []
            for port in ["445", "3389", "22", "5985", "5986", "1433", "3306", "5432"]:
                if f":{port}" in netstat:
                    interesting_ports.append(port)
            if interesting_ports:
                findings.append({"category": "network", "severity": "info",
                                 "detail": f"Interesting open ports: {', '.join(interesting_ports)}"})
                if "445" in interesting_ports:
                    suggestions.append({"action": "lateral_movement", "reason": "SMB (445) open — lateral movement via SMB possible"})
                if "3389" in interesting_ports:
                    suggestions.append({"action": "lateral_movement", "reason": "RDP (3389) open — lateral movement via RDP possible"})

        # --- Check installed software for interesting apps ---
        reg_software = _extract_stdout(results.get("reg_query_software", {}))
        if reg_software:
            software_lower = reg_software.lower()
            interesting_apps = []
            for app in ["microsoft sql server", "mysql", "postgresql", "oracle", "vmware", "vnc", "putty", "filezilla"]:
                if app in software_lower:
                    interesting_apps.append(app)
            if interesting_apps:
                findings.append({"category": "software", "severity": "info",
                                 "detail": f"Interesting software installed: {', '.join(interesting_apps)}"})

        return {
            "agent_id": agent_id,
            "findings": findings,
            "suggestions": suggestions,
            "summary": {
                "total_findings": len(findings),
                "critical": sum(1 for f in findings if f["severity"] == "critical"),
                "warnings": sum(1 for f in findings if f["severity"] == "warning"),
                "info": sum(1 for f in findings if f["severity"] == "info"),
            },
        }

    # ------------------------------------------------------------------
    # Alert emission
    # ------------------------------------------------------------------

    async def _emit_findings_alerts(self, agent_id: str, analysis: dict) -> None:
        """Emit alerts via AlertManager when interesting findings are discovered."""
        try:
            from core.alert_manager import AlertManager
            alert_manager = AlertManager()

            for finding in analysis.get("findings", []):
                if finding["severity"] not in ("warning", "critical"):
                    continue
                await alert_manager.fire(
                    event="auto_recon_finding",
                    title=f"Recon finding: {finding['category']}",
                    message=finding["detail"],
                    severity=finding["severity"],
                    agent_id=agent_id,
                    data={
                        "category": finding["category"],
                        "recon_id": str(uuid.uuid4()),
                    },
                )

            # Emit a summary alert if there are suggestions
            suggestions = analysis.get("suggestions", [])
            if suggestions:
                suggestion_lines = [f"  - {s['action']}: {s['reason']}" for s in suggestions]
                await alert_manager.fire(
                    event="auto_recon_complete",
                    title=f"Auto-recon complete for agent {agent_id[:8]}",
                    message=(
                        f"Recon discovered {analysis['summary']['total_findings']} findings "
                        f"({analysis['summary']['critical']} critical, "
                        f"{analysis['summary']['warnings']} warnings).\n"
                        f"Suggested actions:\n" + "\n".join(suggestion_lines)
                    ),
                    severity="warning" if analysis["summary"]["critical"] else "info",
                    agent_id=agent_id,
                    data={"findings": analysis.get("findings", [])},
                )
        except Exception as exc:
            logger.debug("Failed to emit recon alerts: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_stdout(result_entry: dict) -> str:
    """Extract stdout text from a task result entry."""
    if not result_entry:
        return ""
    data = result_entry.get("data")
    if not data:
        return ""
    # Shell module returns {stdout, stderr, returncode}
    if isinstance(data, dict):
        return data.get("stdout", "") or ""
    if isinstance(data, str):
        return data
    return ""
