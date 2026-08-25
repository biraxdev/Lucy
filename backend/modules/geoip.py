NAME = "geoip"
VERSION = "1.0.0"
DESCRIPTION = "IP geolocation via ip-api.com and local fallback."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


import json
import socket
import urllib.request


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    if action in ("run", "lookup", "locate"):
        return _lookup(params)
    elif action == "self":
        return _self_lookup()
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _lookup(params: dict) -> dict:
    ip = params.get("ip", "")
    if not ip:
        return _self_lookup()

    result = _query_ipapi(ip) or _query_ipinfo(ip)
    if result:
        return {"status": "completed", "data": result}
    return {"status": "failed", "data": None, "error": "All geo providers failed"}


def _self_lookup() -> dict:
    ip = _get_public_ip()
    data = _query_ipapi(ip) or _query_ipinfo(ip) or {}
    data["query_ip"] = ip
    return {"status": "completed", "data": data}


def _get_public_ip() -> str:
    for url in ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.read().decode().strip()
        except Exception:
            continue
    return ""


def _query_ipapi(ip: str) -> dict | None:
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org,lat,lon,timezone,query"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        if data.get("status") == "success":
            return {
                "ip": data.get("query", ip),
                "country": data.get("country"),
                "region": data.get("regionName"),
                "city": data.get("city"),
                "isp": data.get("isp"),
                "org": data.get("org"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "timezone": data.get("timezone"),
                "provider": "ip-api.com",
            }
    except Exception:
        pass
    return None


def _query_ipinfo(ip: str) -> dict | None:
    try:
        url = f"https://ipinfo.io/{ip}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        loc = data.get("loc", ",").split(",")
        return {
            "ip": data.get("ip", ip),
            "country": data.get("country"),
            "region": data.get("region"),
            "city": data.get("city"),
            "org": data.get("org"),
            "lat": float(loc[0]) if len(loc) == 2 else None,
            "lon": float(loc[1]) if len(loc) == 2 else None,
            "timezone": data.get("timezone"),
            "provider": "ipinfo.io",
        }
    except Exception:
        pass
    return None
