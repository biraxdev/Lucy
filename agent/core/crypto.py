"""
Agent-side crypto layer — mirrors backend/core/crypto.py exactly.
Uses only: cryptography (or pycryptodome fallback) — no stdlib crypto.
All keys stored in memory, never written to disk.
"""
import base64
import hashlib
import hmac as _hmac_mod
import os

# ---------------------------------------------------------------------------
# Dependency: prefer `cryptography`, fall back to `pycryptodome`
# ---------------------------------------------------------------------------

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ec import (
        ECDH,
        SECP256R1,
        generate_private_key,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    _BACKEND = "cryptography"

except ImportError:
    try:
        from Crypto.PublicKey import ECC
        from Crypto.Cipher import AES
        from Crypto.Hash import HMAC, SHA256
        from Crypto.Protocol.KDF import HKDF as _HKDF_pycrypto

        _BACKEND = "pycryptodome"
    except ImportError:
        _BACKEND = "none"


# ---------------------------------------------------------------------------
# ECDH P-256 Key Generation
# ---------------------------------------------------------------------------


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate ECDH P-256 keypair. Returns (private_key_pem, public_key_pem)."""
    if _BACKEND == "cryptography":
        private_key = generate_private_key(SECP256R1())
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem, public_pem

    elif _BACKEND == "pycryptodome":
        key = ECC.generate(curve="P-256")
        private_pem = key.export_key(format="PEM", use_pkcs8=True).encode()
        public_pem = key.public_key().export_key(format="PEM").encode()
        return private_pem, public_pem

    raise RuntimeError("No supported crypto library available (cryptography / pycryptodome)")


# ---------------------------------------------------------------------------
# ECDH Shared Secret Derivation
# ---------------------------------------------------------------------------


def derive_shared_secret(private_key_pem: bytes, peer_public_key_pem: bytes) -> bytes:
    """ECDH → raw 32-byte shared secret."""
    if _BACKEND == "cryptography":
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        peer_public = serialization.load_pem_public_key(peer_public_key_pem)
        return private_key.exchange(ECDH(), peer_public)

    elif _BACKEND == "pycryptodome":
        private_key = ECC.import_key(private_key_pem)
        peer_public = ECC.import_key(peer_public_key_pem)
        shared_point = private_key.d * peer_public.pointQ
        x_bytes = int(shared_point.x).to_bytes(32, "big")
        return x_bytes

    raise RuntimeError("No supported crypto library")


# ---------------------------------------------------------------------------
# AES Key Derivation via HKDF-SHA256
# ---------------------------------------------------------------------------


def derive_aes_key(shared_secret: bytes, salt: bytes = b"lucy") -> bytes:
    """HKDF-SHA256 expansion → 32-byte AES key."""
    if _BACKEND == "cryptography":
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"lucy-aes-key",
        )
        return hkdf.derive(shared_secret)

    elif _BACKEND == "pycryptodome":
        return _HKDF_pycrypto(
            master=shared_secret,
            key_len=32,
            salt=salt,
            hashmod=SHA256,
            context=b"lucy-aes-key",
        )

    raise RuntimeError("No supported crypto library")


# ---------------------------------------------------------------------------
# AES-256-GCM Encrypt / Decrypt
# ---------------------------------------------------------------------------


def encrypt(plaintext: bytes, aes_key: bytes) -> str:
    """AES-256-GCM encrypt. Returns base64(nonce[12] + ciphertext + tag[16])."""
    nonce = os.urandom(12)

    if _BACKEND == "cryptography":
        aesgcm = AESGCM(aes_key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext_with_tag).decode("utf-8")

    elif _BACKEND == "pycryptodome":
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return base64.b64encode(nonce + ciphertext + tag).decode("utf-8")

    raise RuntimeError("No supported crypto library")


def decrypt(cipher_b64: str, aes_key: bytes) -> bytes:
    """AES-256-GCM decrypt. Raises ValueError on auth failure."""
    raw = base64.b64decode(cipher_b64)
    nonce = raw[:12]
    data = raw[12:]

    if _BACKEND == "cryptography":
        aesgcm = AESGCM(aes_key)
        try:
            return aesgcm.decrypt(nonce, data, None)
        except Exception as exc:
            raise ValueError("Decryption failed") from exc

    elif _BACKEND == "pycryptodome":
        ciphertext, tag = data[:-16], data[-16:]
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        try:
            return cipher.decrypt_and_verify(ciphertext, tag)
        except Exception as exc:
            raise ValueError("Decryption failed") from exc

    raise RuntimeError("No supported crypto library")


# ---------------------------------------------------------------------------
# HMAC-SHA256
# ---------------------------------------------------------------------------


def sign_message(payload: bytes, hmac_key: bytes) -> str:
    """HMAC-SHA256 → hex string."""
    return _hmac_mod.new(hmac_key, payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, signature: str, hmac_key: bytes) -> bool:
    """Constant-time HMAC-SHA256 verification."""
    expected = sign_message(payload, hmac_key)
    return _hmac_mod.compare_digest(expected, signature)
