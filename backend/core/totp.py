"""
TOTP (Time-based One-Time Password) helpers for MFA.

Implements RFC 6238 using HMAC-SHA1 with a 6-digit code and 30-second step.
"""
import base64
import hashlib
import hmac
import secrets
import struct
from datetime import datetime, timezone
from typing import Optional


def _base32_secret(length: int = 20) -> str:
    """Generate a random Base32-encoded TOTP secret."""
    raw = secrets.token_bytes(length)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    """Decode a Base32-encoded secret, ignoring padding differences."""
    cleaned = secret.upper().replace(" ", "")
    padded = cleaned + "=" * ((8 - len(cleaned) % 8) % 8)
    return base64.b32decode(padded)


def _totp(secret: bytes, timestamp: int) -> str:
    """Compute the 6-digit TOTP code for a given Unix timestamp."""
    counter = struct.pack(">Q", timestamp // 30)
    mac = hmac.new(secret, counter, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def generate_secret() -> str:
    """Generate a new TOTP secret for a user."""
    return _base32_secret()


def get_provisioning_uri(secret: str, username: str, issuer: str = "Lucy C2") -> str:
    """Build the otpauth:// URI used by authenticator apps."""
    label = f"{issuer}:{username}"
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"


def verify(secret: str, code: str, window: int = 2) -> bool:
    """Verify a TOTP code against the current time, allowing a window of steps."""
    if not secret or not code:
        return False
    try:
        key = _decode_secret(secret)
    except Exception:
        return False

    now = int(datetime.now(timezone.utc).timestamp())
    for delta in range(-window, window + 1):
        if _totp(key, now + delta * 30) == code.strip():
            return True
    return False


def generate_code(secret: str, timestamp: Optional[int] = None) -> str:
    """Generate a TOTP code for testing or verification."""
    if timestamp is None:
        timestamp = int(datetime.now(timezone.utc).timestamp())
    return _totp(_decode_secret(secret), timestamp)
