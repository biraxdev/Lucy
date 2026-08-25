"""
mfa_harvest — Auth-bypass-Stealer (capture MFA/OTP).
TOTP RFC 6238 (HMAC-SHA1/256/512), parsing otpauth:// URIs, generation de
codes, historique des captures. Multi-plateforme, stdlib.
Actions: totp, parse, capture, list, validate
"""
NAME = "mfa_harvest"
VERSION = "1.0.0"
DESCRIPTION = "TOTP RFC 6238 et parsing otpauth:// pour audit MFA (Auth-bypass-Stealer)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import hashlib
import hmac
import struct
import time
import urllib.parse

_CAPTURES = []


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "totp":
            return _totp(params)
        if action == "parse":
            return _parse(params)
        if action == "capture":
            return _capture(params)
        if action == "list":
            return _result(data={"captures": _CAPTURES})
        if action == "validate":
            return _validate(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="mfa_harvest: " + str(exc), status="failed")


def _b32_decode(secret):
    secret = secret.upper().strip().replace(" ", "")
    pad = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + pad)


def _hotp(key, counter, digits=6, algo="sha1"):
    h = hmac.new(key, struct.pack(">Q", counter),
                 getattr(hashlib, algo)).digest()
    off = h[-1] & 0x0F
    code = (struct.unpack(">I", h[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def _totp(params):
    secret = params.get("secret", "")
    if not secret:
        return _result(error="No secret", status="failed")
    try:
        key = _b32_decode(secret)
    except Exception as exc:
        return _result(error="Invalid base32 secret: " + str(exc),
                       status="failed")
    step = int(params.get("step", 30))
    digits = int(params.get("digits", 6))
    algo = params.get("algo", "sha1")
    counter = int(time.time()) // step
    code = _hotp(key, counter, digits, algo)
    remaining = step - (int(time.time()) % step)
    return _result(data={"code": code, "counter": counter,
                         "expires_in_s": remaining, "digits": digits,
                         "algo": algo})


def _parse(params):
    uri = params.get("uri", "")
    if not uri:
        return _result(error="No uri", status="failed")
    if not uri.startswith("otpauth://"):
        return _result(error="Not an otpauth URI", status="failed")
    parsed = urllib.parse.urlparse(uri)
    typ = parsed.netloc
    label = parsed.path.lstrip("/")
    qs = urllib.parse.parse_qs(parsed.query)
    secret = (qs.get("secret") or [""])[0]
    issuer = (qs.get("issuer") or [""])[0]
    algo = (qs.get("algorithm") or ["SHA1"])[0].upper()
    digits = int((qs.get("digits") or ["6"])[0])
    step = int((qs.get("period") or ["30"])[0])
    return _result(data={"type": typ, "label": label, "issuer": issuer,
                         "secret": secret, "algo": algo,
                         "digits": digits, "step": step})


def _capture(params):
    entry = {"service": params.get("service", ""),
             "username": params.get("username", ""),
             "secret": params.get("secret", ""),
             "code": params.get("code", ""),
             "ts": int(time.time())}
    if not (entry["secret"] or entry["code"]):
        return _result(error="Nothing to capture (secret or code)", status="failed")
    _CAPTURES.append(entry)
    return _result(data={"captured": entry, "total": len(_CAPTURES)})


def _validate(params):
    secret = params.get("secret", "")
    code = params.get("code", "")
    if not secret or not code:
        return _result(error="Need secret + code", status="failed")
    try:
        key = _b32_decode(secret)
    except Exception as exc:
        return _result(error="Invalid secret: " + str(exc), status="failed")
    step = int(params.get("step", 30))
    digits = int(params.get("digits", 6))
    algo = params.get("algo", "sha1")
    skew = int(params.get("skew", 1))
    counter = int(time.time()) // step
    for c in range(counter - skew, counter + skew + 1):
        if _hotp(key, c, digits, algo) == str(code).strip():
            return _result(data={"valid": True, "counter": c})
    return _result(data={"valid": False})
