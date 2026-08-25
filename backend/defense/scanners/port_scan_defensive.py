import ipaddress
import socket
import threading
from datetime import datetime

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 3389, 5985, 5986, 8080, 8443]


def _check_port(host: str, port: int, timeout: float, results: list, lock: threading.Lock):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) == 0:
                try:
                    service = socket.getservbyport(port)
                except (OSError, ValueError):
                    service = "unknown"
                with lock:
                    results.append({"port": port, "service": service})
    except Exception:
        pass


def run(action: str = "scan", **params) -> dict:
    """Authorized port scanner for internal asset discovery on owned networks."""
    if action == "scan":
        return _scan_host(params)
    if action == "subnet":
        return _scan_subnet(params)
    return {"status": "failed", "error": f"Unknown action: {action}"}


def _scan_host(params: dict) -> dict:
    host = params.get("host", "127.0.0.1")
    ports = params.get("ports", COMMON_PORTS)
    timeout = float(params.get("timeout", 1.0))

    results = []
    lock = threading.Lock()
    threads = [
        threading.Thread(target=_check_port, args=(host, int(p), timeout, results, lock), daemon=True)
        for p in ports
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout + 1)

    results.sort(key=lambda x: x["port"])
    return {
        "status": "completed",
        "host": host,
        "open_ports": results,
        "open_count": len(results),
        "scanned": len(ports),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _scan_subnet(params: dict) -> dict:
    cidr = params.get("cidr", "192.168.1.0/24")
    ports = params.get("ports", [22, 80, 443, 445, 3389])
    timeout = float(params.get("timeout", 1.0))
    max_hosts = int(params.get("max_hosts", 254))

    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        return {"status": "failed", "error": f"Invalid CIDR: {exc}"}

    hosts = list(network.hosts())[:max_hosts]
    up_hosts = []
    lock = threading.Lock()
    sem = threading.Semaphore(50)

    def _check_host(ip_obj):
        ip_str = str(ip_obj)
        host_open = []
        hl = threading.Lock()
        threads = [
            threading.Thread(
                target=_check_port,
                args=(ip_str, int(p), timeout, host_open, hl),
                daemon=True,
            )
            for p in ports
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout + 1)
        if host_open:
            with lock:
                up_hosts.append({"host": ip_str, "open_ports": sorted(host_open, key=lambda x: x["port"])})

    threads = [
        threading.Thread(target=_check_host, args=(h,), daemon=True) for h in hosts
    ]
    for t in threads:
        sem.acquire()
        t.start()
    for t in threads:
        t.join()
        sem.release()

    return {
        "status": "completed",
        "cidr": cidr,
        "hosts_scanned": len(hosts),
        "hosts_with_open_ports": len(up_hosts),
        "results": up_hosts,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
