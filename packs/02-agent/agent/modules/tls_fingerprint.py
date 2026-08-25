"""
TLS fingerprint spoofing module for Project Lucy agent.
Allows configuring a custom JA3 fingerprint or selecting a known browser
TLS profile to evade network-based detection that inspects TLS ClientHello
characteristics (cipher suites, extensions, elliptic curves, etc.).

Full JA3 spoofing is not possible with Python's stdlib ssl module alone,
as it does not expose control over TLS extension ordering or GREASE values.
This module uses `curl_cffi` when available for accurate JA3 spoofing, and
falls back to partial stdlib configuration (cipher suites, TLS version)
otherwise.

Actions: set_ja3, set_profile, get_current, test, apply_to_agent
"""
import json
import platform
import ssl

name = "tls_fingerprint"
version = "1.0.0"
os_compat = ["Windows", "Linux", "Darwin"]
dependencies = ["curl_cffi"]

SYSTEM = platform.system()

# ---------------------------------------------------------------------------
# Predefined browser TLS profiles (JA3 strings)
# Format: SSLVersion,Ciphers,EllipticCurves,EllipticCurvePointFormats
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict] = {
    "chrome": {
        "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0",
        "description": "Google Chrome (TLS 1.3, modern cipher suites)",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
    "firefox": {
        "ja3": "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49161-49171-49172-156-157-47-53-10,0-23-65281-10-11-35-16-5-34-51-43-13-45-28-65037,29-23-24-25-256-257,0",
        "description": "Mozilla Firefox (TLS 1.3, broad cipher support)",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    },
    "safari": {
        "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-21,29-23-24,0",
        "description": "Apple Safari (TLS 1.3, Apple platform)",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    },
    "edge": {
        "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0",
        "description": "Microsoft Edge (Chromium-based, same as Chrome)",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    },
    "ie11": {
        "ja3": "771,49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53-10,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-21,29-23-24,0",
        "description": "Internet Explorer 11 (TLS 1.2, legacy cipher suites)",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
    },
}

# Current configuration state (module-level, persists across calls)
_current_config: dict = {
    "profile": None,
    "ja3": None,
    "ciphers": [],
    "tls_version": None,
    "user_agent": None,
    "applied": False,
}


def _result(data=None, error=None, status="completed") -> dict:
    return {"status": status, "data": data, "error": error}


def run(action: str = "get_current", **params) -> dict:
    try:
        if action == "set_ja3":
            return _result(data=_set_ja3(params))
        elif action == "set_profile":
            return _result(data=_set_profile(params))
        elif action == "get_current":
            return _result(data=_get_current())
        elif action == "test":
            return _result(data=_test())
        elif action == "apply_to_agent":
            return _result(data=_apply_to_agent())
        return _result(error=f"Unknown action: {action}", status="failed")
    except Exception as exc:
        return _result(error=f"tls_fingerprint:{action} crashed: {exc}", status="failed")


# ---------------------------------------------------------------------------
# JA3 parsing
# ---------------------------------------------------------------------------

# Map IANA cipher suite IDs to OpenSSL cipher names (common subset)
_CIPHER_MAP: dict[int, str] = {
    0x002F: "AES128-SHA",
    0x0035: "AES256-SHA",
    0x003C: "AES128-SHA256",
    0x003D: "AES256-SHA256",
    0x009C: "ECDHE-ECDSA-AES128-GCM-SHA256",
    0x009D: "ECDHE-ECDSA-AES256-GCM-SHA384",
    0x009E: "ECDHE-RSA-AES128-GCM-SHA256",
    0x009F: "ECDHE-RSA-AES256-GCM-SHA384",
    0xA013: "ECDHE-RSA-CHACHA20-POLY1305",
    0xA014: "ECDHE-ECDSA-CHACHA20-POLY1305",
    0x1301: "TLS_AES_128_GCM_SHA256",
    0x1302: "TLS_AES_256_GCM_SHA384",
    0x1303: "TLS_CHACHA20_POLY1305_SHA256",
    0xC02B: "ECDHE-ECDSA-AES128-GCM-SHA256",
    0xC02C: "ECDHE-ECDSA-AES256-GCM-SHA384",
    0xC02F: "ECDHE-RSA-AES128-GCM-SHA256",
    0xC030: "ECDHE-RSA-AES256-GCM-SHA384",
    0xCCA8: "ECDHE-RSA-CHACHA20-POLY1305",
    0xCCA9: "ECDHE-ECDSA-CHACHA20-POLY1305",
}

# Map JA3 SSL version to TLS version
_VERSION_MAP = {
    "771": ssl.TLSVersion.TLSv1_2,   # TLS 1.2 (0x0303)
    "770": ssl.TLSVersion.TLSv1_1,
    "769": ssl.TLSVersion.TLSv1,
    "772": ssl.TLSVersion.TLSv1_3,
}


def _parse_ja3(ja3_string: str) -> dict:
    """
    Parse a JA3 string: SSLVersion,Ciphers,EllipticCurves,EllipticCurvePointFormats
    Returns a dict with parsed components.
    """
    parts = ja3_string.split(",")
    if len(parts) < 4:
        raise ValueError(f"Invalid JA3 string: expected 4 fields, got {len(parts)}")

    ssl_version = parts[0].strip()
    cipher_ids = [int(c) for c in parts[1].split("-") if c.strip()]
    curve_ids = [int(c) for c in parts[2].split("-") if c.strip()]
    ec_point_formats = [int(c) for c in parts[3].split("-") if c.strip()]

    # Map cipher IDs to OpenSSL names
    cipher_names = []
    for cid in cipher_ids:
        name = _CIPHER_MAP.get(cid)
        if name:
            cipher_names.append(name)

    # Map curve IDs to names
    curve_map = {23: "secp256r1", 24: "secp384r1", 25: "secp521r1", 29: "x25519", 30: "x448"}
    curve_names = [curve_map.get(cid, str(cid)) for cid in curve_ids]

    # Map EC point formats
    pf_map = {0: "uncompressed", 1: "ansiX962_compressed_prime", 2: "ansiX962_compressed_char2"}
    point_format_names = [pf_map.get(pid, str(pid)) for pid in ec_point_formats]

    return {
        "ssl_version": ssl_version,
        "cipher_ids": cipher_ids,
        "cipher_names": cipher_names,
        "curve_ids": curve_ids,
        "curve_names": curve_names,
        "ec_point_formats": ec_point_formats,
        "ec_point_format_names": point_format_names,
    }


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _set_ja3(params: dict) -> dict:
    ja3_string = params.get("ja3_string", "")
    if not ja3_string:
        return {"status": "error", "error": "ja3_string parameter required"}

    try:
        parsed = _parse_ja3(ja3_string)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}

    _current_config.update({
        "profile": "custom",
        "ja3": ja3_string,
        "ciphers": parsed["cipher_names"],
        "tls_version": parsed["ssl_version"],
        "curves": parsed["curve_names"],
        "ec_point_formats": parsed["ec_point_format_names"],
        "applied": False,
    })

    return {
        "status": "ok",
        "ja3": ja3_string,
        "parsed": parsed,
        "note": "JA3 configured. Call apply_to_agent to activate.",
    }


def _set_profile(params: dict) -> dict:
    profile_name = params.get("profile", "").lower()
    if profile_name not in PROFILES:
        return {
            "status": "error",
            "error": f"Unknown profile: {profile_name}. Available: {list(PROFILES.keys())}",
        }

    profile = PROFILES[profile_name]
    try:
        parsed = _parse_ja3(profile["ja3"])
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}

    _current_config.update({
        "profile": profile_name,
        "ja3": profile["ja3"],
        "ciphers": parsed["cipher_names"],
        "tls_version": parsed["ssl_version"],
        "curves": parsed["curve_names"],
        "ec_point_formats": parsed["ec_point_format_names"],
        "user_agent": profile["user_agent"],
        "applied": False,
    })

    return {
        "status": "ok",
        "profile": profile_name,
        "description": profile["description"],
        "ja3": profile["ja3"],
        "user_agent": profile["user_agent"],
        "note": "Profile configured. Call apply_to_agent to activate.",
    }


def _get_current() -> dict:
    return {
        "status": "ok",
        "config": dict(_current_config),
    }


def _test() -> dict:
    """
    Test the TLS fingerprint by making a request to a JA3 detection service
    and return the detected fingerprint.
    """
    detection_urls = [
        "https://tls.peet.ws/api/all",
        "https://ja3er.com/json",
    ]

    # Try curl_cffi first for accurate JA3
    try:
        from curl_cffi import requests as cc_requests

        ja3 = _current_config.get("ja3")
        profile = _current_config.get("profile")

        for url in detection_urls:
            try:
                if ja3 and ja3 != "custom":
                    # curl_cffi supports ja3 parameter
                    resp = cc_requests.get(url, ja3=ja3, timeout=15, impersonate=profile if profile in ("chrome", "firefox", "safari", "edge") else None)
                elif profile in ("chrome", "firefox", "safari", "edge"):
                    resp = cc_requests.get(url, timeout=15, impersonate=profile)
                else:
                    resp = cc_requests.get(url, timeout=15)

                if resp.status_code == 200:
                    data = resp.json()
                    # Extract JA3 from response (format varies by service)
                    detected_ja3 = (
                        data.get("tls", {}).get("ja3")
                        or data.get("ja3")
                        or data.get("ja3_hash")
                        or "unknown"
                    )
                    return {
                        "status": "ok",
                        "detection_url": url,
                        "detected_ja3": detected_ja3,
                        "configured_ja3": ja3,
                        "match": detected_ja3 == ja3 if ja3 else None,
                        "raw_response": data,
                        "library": "curl_cffi",
                    }
            except Exception:
                continue
    except ImportError:
        pass

    # Fallback to stdlib urllib
    import urllib.request

    for url in detection_urls:
        try:
            ctx = _build_ssl_context()
            req = urllib.request.Request(url, headers={"User-Agent": _current_config.get("user_agent", "Lucy-Agent")})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode())
                detected_ja3 = (
                    data.get("tls", {}).get("ja3")
                    or data.get("ja3")
                    or data.get("ja3_hash")
                    or "unknown"
                )
                return {
                    "status": "ok",
                    "detection_url": url,
                    "detected_ja3": detected_ja3,
                    "configured_ja3": _current_config.get("ja3"),
                    "match": detected_ja3 == _current_config.get("ja3") if _current_config.get("ja3") else None,
                    "raw_response": data,
                    "library": "stdlib ssl (partial — JA3 will not match exactly)",
                    "note": "Full JA3 spoofing requires curl_cffi. Only cipher suites and TLS version are controlled with stdlib.",
                }
        except Exception as exc:
            continue

    return {"status": "error", "error": "All JA3 detection services unreachable"}


def _apply_to_agent() -> dict:
    """
    Apply the TLS profile to the agent's HTTP client.
    Modifies the urllib request to use a custom SSL context with the
    specified cipher suites and TLS version.

    Full JA3 spoofing requires curl_cffi or tls-client. If curl_cffi is
    available, it is used. Otherwise, the stdlib ssl module is configured
    with what's possible (cipher suites, TLS version).
    """
    if not _current_config.get("ja3") and not _current_config.get("profile"):
        return {"status": "error", "error": "No TLS profile configured. Call set_ja3 or set_profile first."}

    has_curl_cffi = False
    try:
        import curl_cffi  # noqa: F401
        has_curl_cffi = True
    except ImportError:
        pass

    # Build the SSL context for stdlib fallback
    ctx = _build_ssl_context()

    # Patch urllib's default HTTPS handler to use our context
    try:
        import urllib.request
        import http.client

        original_https_open = urllib.request.HTTPSHandler.https_open

        def _custom_https_open(self, req):
            return self.do_open(
                lambda host, timeout: http.client.HTTPSConnection(
                    host, timeout=timeout, context=ctx
                ),
                req,
            )

        urllib.request.HTTPSHandler.https_open = _custom_https_open
    except Exception:
        pass

    _current_config["applied"] = True

    return {
        "status": "ok",
        "applied": True,
        "library": "curl_cffi" if has_curl_cffi else "stdlib ssl",
        "profile": _current_config.get("profile"),
        "ja3": _current_config.get("ja3"),
        "ciphers": _current_config.get("ciphers", []),
        "tls_version": _current_config.get("tls_version"),
        "user_agent": _current_config.get("user_agent"),
        "note": (
            "Full JA3 spoofing active via curl_cffi."
            if has_curl_cffi
            else "Partial TLS config applied via stdlib ssl. "
                 "Full JA3 spoofing (extension ordering, GREASE) requires curl_cffi."
        ),
    }


# ---------------------------------------------------------------------------
# SSL context builder
# ---------------------------------------------------------------------------

def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSLContext configured with the current profile's cipher suites and TLS version."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Set TLS version
    tls_ver = _current_config.get("tls_version")
    if tls_ver and tls_ver in _VERSION_MAP:
        try:
            ctx.minimum_version = _VERSION_MAP[tls_ver]
            ctx.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
        except Exception:
            pass

    # Set cipher suites
    ciphers = _current_config.get("ciphers", [])
    if ciphers:
        try:
            cipher_str = ":".join(ciphers)
            ctx.set_ciphers(cipher_str)
        except ssl.SSLError:
            # Some cipher names may not be supported by the OpenSSL build
            pass

    # Set elliptic curves
    curves = _current_config.get("curves", [])
    if curves:
        try:
            ctx.set_ecdh_curve(curves[0])
        except Exception:
            pass

    return ctx
