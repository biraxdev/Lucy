"""
Intent definitions for the Lucy chat engine.

Intents map natural-language operator input to concrete backend actions.
Each intent carries normalized parameters used by the ActionRouter.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    """Resolved intent from an operator chat command."""

    name: str
    confidence: float = 1.0
    params: dict[str, Any] = field(default_factory=dict)
    raw_query: str = ""


INTENT_NAMES = {
    "GREETING",
    "UNKNOWN",
    "AGENT_STATUS",
    "LIST_AGENTS",
    "LIST_GROUPS",
    "RUN_TASK",
    "RUN_ON_GROUP",
    "RUN_TIMELINE",
    "RUN_PLAYBOOK",
    "BULK_TASK",
    "FILE_OPERATION",
    "SHOW_CREDENTIALS",
    "SHOW_FINDINGS",
    "SHOW_TASKS",
    "SHOW_LOGS",
    "SHOW_NOTES",
    "BUILD_AGENT",
    "SELF_DESTRUCT",
    "CREATE_CAMPAIGN",
    "LIST_CAMPAIGNS",
    "CAMPAIGN_SUMMARY",
    "ADD_AGENT_NOTE",
    "MAP_TECHNIQUE",
    "HELP",
    "SUMMARIZE",
}

# Default module/action when the operator says something like "run recon on X"
DEFAULT_MODULE_ACTIONS = {
    "recon": ("info", "run"),
    "info": ("info", "run"),
    "shell": ("shell", "run"),
    "cmd": ("shell", "run"),
    "command": ("shell", "run"),
    "screenshot": ("screenshot", "capture"),
    "capture": ("screenshot", "capture"),
    "keylog": ("keylog", "start"),
    "keylogger": ("keylog", "start"),
    "portscan": ("port_scan", "run"),
    "scan": ("port_scan", "run"),
    "browser": ("browser", "dump"),
    "wifi": ("wifi", "scan"),
    "files": ("file", "list"),
}

# Keywords used by the keyword-based intent parser.
INTENT_KEYWORDS: dict[str, list[str]] = {
    "GREETING": ["hello", "hi", "hey", "salut", "bonjour"],
    "AGENT_STATUS": ["status", "statut", "how is", "how's", "check on", "state of", "health of"],
    "LIST_AGENTS": ["agents", "list agents", "show agents", "mes agents", "mes machines"],
    "LIST_GROUPS": ["groups", "groupes", "list groups", "show groups"],
    "RUN_TASK": ["run", "execute", "launch", "start", "run task", "exécute", "lance"],
    "RUN_ON_GROUP": ["on group", "on groupe", "group ", "groupe ", "everyone in"],
    "RUN_TIMELINE": ["timeline", "scenario", "play timeline", "run timeline"],
    "RUN_PLAYBOOK": ["playbook", "run playbook", "execute playbook", "procedure"],
    "BULK_TASK": ["all agents", "every agent", "bulk", "mass", "fleet", "all online"],
    "FILE_OPERATION": ["list files", "download file", "upload file", "file on", "files on", "directory"],
    "SHOW_CREDENTIALS": ["credentials", "passwords", "creds", "identifiants", "mots de passe"],
    "SHOW_FINDINGS": ["findings", "find", "vulnerabilities", "vuln", "weakness"],
    "SHOW_TASKS": ["tasks", "jobs", "runs", "activité", "activity"],
    "SHOW_LOGS": ["logs", "log", "events", "history"],
    "SHOW_NOTES": ["notes", "observations", "note for", "agent note"],
    "BUILD_AGENT": ["build", "create agent", "generate agent", "payload", "builder"],
    "SELF_DESTRUCT": ["self destruct", "self-destruct", "kill", "destroy", "remove agent", "terminate"],
    "CREATE_CAMPAIGN": ["create campaign", "new campaign", "start campaign", "campaign named"],
    "LIST_CAMPAIGNS": ["list campaigns", "show campaigns", "campaigns"],
    "CAMPAIGN_SUMMARY": ["campaign summary", "campaign status", "how is the campaign"],
    "ADD_AGENT_NOTE": ["note that", "write down", "remember that", "agent note"],
    "MAP_TECHNIQUE": ["map technique", "mitre", "technique", "ttp", "tactic"],
    "HELP": ["help", "aide", "commands", "what can you do"],
    "SUMMARIZE": ["summarize", "summary", "overview", "résumé", "what's happening"],
}

# Entities we try to extract from free text.
AGENT_PREFIXES = ["agent", "machine", "host", "cible", "target"]
GROUP_PREFIXES = ["group", "groupe", "team"]
