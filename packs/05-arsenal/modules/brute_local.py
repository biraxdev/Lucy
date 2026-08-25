"""
brute_local — Vault-Breaker (audit de mots de passe locaux).
Cracking hors-ligne de hashs locaux: md5, sha1, sha256, sha512, ntlm.
MD4 pur Python (aucune dependance). Wordlist embarque + dictionnaire externe.
Actions: crack, check, hash, add_words, algorithms
"""
NAME = "brute_local"
VERSION = "1.0.0"
DESCRIPTION = "Audit de hashs locaux (md5/sha1/sha256/sha512/ntlm) avec wordlist embarque (Vault-Breaker)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import hashlib
import os
import time

_EMBEDDED = [
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "letmein",
    "dragon", "111111", "baseball", "iloveyou", "trustno1", "sunshine",
    "master", "welcome", "shadow", "admin", "root", "toor", "1234", "12345",
    "password1", "password123", "P@ssw0rd", "Passw0rd!", "qwerty123", "admin123",
    "changeme", "letmein1", "welcome1", "p@ssword", "p@ssw0rd", "secret",
    "default", "test", "test123", "guest", "user", "temp", "temporary",
    "linkedin", "yankees", "michael", "football", "jennifer", "password!",
    "zaq12wsx", "qwertyuiop", "asdfghjkl", "zxcvbnm", "1qaz2wsx", "qwe123",
    "Passw0rd123", "Summer2024", "Winter2024", "Admin@123", "Welcome@123",
]


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "crack":
            return _crack(params)
        if action == "check":
            return _check(params)
        if action == "hash":
            return _hash(params)
        if action == "add_words":
            return _add_words(params)
        if action == "algorithms":
            return _result(data={"algorithms": ["md5", "sha1", "sha256",
                                                "sha512", "ntlm"]})
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="brute_local: " + str(exc), status="failed")


# ------------------------------------------------------- MD4 (RFC 1320, pur Python)
def _md4(data):
    def rol(x, n):
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
    msg = bytearray(data)
    ml = len(msg) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += ml.to_bytes(8, "little")
    A, B, C, D = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    X = [0] * 16
    for i in range(0, len(msg), 64):
        for j in range(16):
            X[j] = int.from_bytes(msg[i + j * 4:i + j * 4 + 4], "little")
        a, b, c, d = A, B, C, D
        for rnd in range(3):
            if rnd == 0:
                def f(x, y, z):
                    return (x & y) | (~x & z)
                def g(i):
                    return i
                const = 0
                shifts = (3, 7, 11, 19)
            elif rnd == 1:
                def f(x, y, z):
                    return (x & y) | (x & z) | (y & z)
                def g(i):
                    return [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15][i]
                const = 0x5A827999
                shifts = (3, 5, 9, 13)
            else:
                def f(x, y, z):
                    return x ^ y ^ z
                def g(i):
                    return [0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15][i]
                const = 0x6ED9EBA1
                shifts = (3, 9, 11, 15)
            for i in range(16):
                s = shifts[i % 4]
                t = (a + f(b, c, d) + X[g(i)] + const) & 0xFFFFFFFF
                a, b, c, d = d, rol(t, s), b, c
        A = (A + a) & 0xFFFFFFFF
        B = (B + b) & 0xFFFFFFFF
        C = (C + c) & 0xFFFFFFFF
        D = (D + d) & 0xFFFFFFFF
    return b"".join(x.to_bytes(4, "little") for x in (A, B, C, D)).hex()


def _digest(algo, word):
    w = word.encode("utf-8", "replace")
    if algo == "md5":
        return hashlib.md5(w).hexdigest()
    if algo == "sha1":
        return hashlib.sha1(w).hexdigest()
    if algo == "sha256":
        return hashlib.sha256(w).hexdigest()
    if algo == "sha512":
        return hashlib.sha512(w).hexdigest()
    if algo == "ntlm":
        return _md4(w.decode("utf-8", "replace").encode("utf-16-le"))
    raise ValueError("Unknown algorithm: " + algo)


def _words(params):
    words = list(_EMBEDDED)
    dict_file = params.get("dict", "")
    if dict_file and os.path.isfile(dict_file):
        with open(dict_file, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                w = line.strip()
                if w:
                    words.append(w)
    extra = params.get("words", [])
    if isinstance(extra, str):
        extra = [extra]
    words.extend(str(w) for w in extra)
    return words


def _crack(params):
    hashes = params.get("hashes", [])
    if isinstance(hashes, str):
        hashes = [h.strip() for h in hashes.replace(",", " ").split() if h.strip()]
    if not hashes:
        return _result(error="No hashes", status="failed")
    algo = params.get("algo", "auto")
    if algo == "auto":
        hlen = len(hashes[0])
        algo = {"32": "md5", "40": "sha1", "56": "ntlm", "64": "sha256",
                "128": "sha512"}.get(str(hlen), "md5")
    targets = {h.lower(): None for h in hashes}
    words = _words(params)
    t0 = time.time()
    attempts = 0
    for w in words:
        attempts += 1
        d = _digest(algo, w)
        if d in targets and targets[d] is None:
            targets[d] = w
            if all(v is not None for v in targets.values()):
                break
    results = [{"hash": h, "password": targets[h.lower()]} for h in hashes]
    cracked = sum(1 for r in results if r["password"])
    return _result(data={"algo": algo, "attempts": attempts,
                         "cracked": cracked, "total": len(results),
                         "elapsed_s": round(time.time() - t0, 3),
                         "results": results})


def _check(params):
    algo = params.get("algo", "md5")
    word = params.get("password", "")
    expected = params.get("hash", "")
    if not word:
        return _result(error="No password", status="failed")
    d = _digest(algo, word)
    return _result(data={"algo": algo, "hash": d,
                         "matches": bool(expected) and d.lower() == expected.lower()})


def _hash(params):
    algo = params.get("algo", "md5")
    word = params.get("password", "")
    if not word:
        return _result(error="No password", status="failed")
    return _result(data={"algo": algo, "hash": _digest(algo, word)})


def _add_words(params):
    words = params.get("words", [])
    if isinstance(words, str):
        words = [words]
    _EMBEDDED.extend(str(w) for w in words)
    return _result(data={"added": len(words), "total": len(_EMBEDDED)})
