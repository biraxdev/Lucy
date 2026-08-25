"""
Port scanner module for Project Lucy agent.
Actions: scan (single host), subnet (CIDR range), top (top N ports on host).
Uses concurrent threads — no external dependencies.
"""
import ipaddress
import socket
import threading
from datetime import datetime

_COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 88, 110, 111, 135, 139, 143, 389,
    443, 445, 464, 465, 587, 636, 993, 995, 1433, 1521, 3268, 3269,
    3306, 3389, 5432, 5985, 5986, 6379, 8080, 8443, 8888, 9200, 9389,
    27017,
]


def run(action: str = "scan", **params) -> dict:
    if action == "scan":
        return _scan_host(params)
    elif action == "subnet":
        return _scan_subnet(params)
    elif action == "top":
        return _scan_top(params)
    return {"error": f"Unknown port_scan action: {action}"}


def _scan_host(params: dict) -> dict:
    host = params.get("host", "127.0.0.1")
    ports = params.get("ports", _COMMON_PORTS)
    timeout = float(params.get("timeout", 0.5))

    open_ports = []
    lock = threading.Lock()

    def _check(port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((host, int(port))) == 0:
                service = _get_service(int(port))
                with lock:
                    open_ports.append({"port": int(port), "service": service})
            s.close()
        except Exception:
            pass

    threads = [threading.Thread(target=_check, args=(p,), daemon=True) for p in ports]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout + 1)

    open_ports.sort(key=lambda x: x["port"])
    return {
        "host": host,
        "open_ports": open_ports,
        "total_scanned": len(ports),
        "open_count": len(open_ports),
        "timestamp": datetime.utcnow().isoformat(),
    }


def _scan_subnet(params: dict) -> dict:
    cidr = params.get("cidr", "192.168.1.0/24")
    ports = params.get("ports", [22, 80, 443, 445, 3389])
    timeout = float(params.get("timeout", 0.5))
    max_hosts = int(params.get("max_hosts", 254))

    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        return {"error": str(exc)}

    hosts_up = []
    lock = threading.Lock()
    sem = threading.Semaphore(50)

    def _check_host(ip_str):
        with sem:
            open_ports = []
            for port in ports:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(timeout)
                    if s.connect_ex((ip_str, int(port))) == 0:
                        open_ports.append({"port": int(port), "service": _get_service(int(port))})
                    s.close()
                except Exception:
                    pass
            if open_ports:
                with lock:
                    hosts_up.append({"ip": ip_str, "open_ports": open_ports})

    hosts = list(network.hosts())[:max_hosts]
    threads = [threading.Thread(target=_check_host, args=(str(ip),), daemon=True) for ip in hosts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    hosts_up.sort(key=lambda x: x["ip"])
    return {
        "cidr": cidr,
        "hosts_scanned": len(hosts),
        "hosts_up": hosts_up,
        "hosts_up_count": len(hosts_up),
        "ports_checked": ports,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _scan_top(params: dict) -> dict:
    host = params.get("host", "127.0.0.1")
    top_n = int(params.get("top", 100))
    timeout = float(params.get("timeout", 0.5))
    ports = _COMMON_PORTS[:top_n]
    return _scan_host({**params, "host": host, "ports": ports, "timeout": timeout})


def _get_service(port: int) -> str:
    _services: dict[int, str] = {
        21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
        80: "http", 88: "kerberos", 110: "pop3", 111: "rpcbind",
        135: "msrpc", 139: "netbios", 143: "imap", 389: "ldap",
        443: "https", 445: "smb", 464: "kpasswd", 465: "smtps",
        587: "smtp-sub", 636: "ldaps", 993: "imaps", 995: "pop3s",
        1433: "mssql", 1521: "oracle", 3268: "ldap-gc", 3269: "ldaps-gc",
        3306: "mysql", 3389: "rdp", 5432: "postgres", 5985: "winrm-http",
        5986: "winrm-https", 6379: "redis", 8080: "http-alt", 8443: "https-alt",
        8888: "http-alt2", 9200: "elasticsearch", 9389: "adws", 27017: "mongodb",
    }
    return _services.get(port, "unknown")
