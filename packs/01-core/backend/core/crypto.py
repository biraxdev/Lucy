import base64
import hashlib
import hmac
import os
import secrets
from typing import NamedTuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDH,
    SECP256R1,
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
    generate_private_key,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class HandshakeResult(NamedTuple):
    aes_key: bytes
    server_public_key_pem: bytes
    nonce_b64: str
    nonce_encrypted_b64: str


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate ECDH P-256 keypair. Returns (private_key_pem, public_key_pem)."""
    private_key: EllipticCurvePrivateKey = generate_private_key(SECP256R1())
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


def derive_shared_secret(private_key_pem: bytes, peer_public_key_pem: bytes) -> bytes:
    """ECDH key exchange → raw 32-byte shared secret."""
    private_key: EllipticCurvePrivateKey = serialization.load_pem_private_key(
        private_key_pem, password=None
    )
    peer_public_key: EllipticCurvePublicKey = serialization.load_pem_public_key(
        peer_public_key_pem
    )
    shared_secret = private_key.exchange(ECDH(), peer_public_key)
    return shared_secret


def derive_aes_key(shared_secret: bytes, salt: bytes = b"lucy") -> bytes:
    """HKDF-SHA256 expansion → 32-byte AES key."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"lucy-aes-key",
    )
    return hkdf.derive(shared_secret)


def encrypt(plaintext: bytes, aes_key: bytes) -> str:
    """AES-256-GCM encrypt. Returns base64(nonce[12] + ciphertext + tag[16])."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext_with_tag).decode("utf-8")


def decrypt(cipher_b64: str, aes_key: bytes) -> bytes:
    """AES-256-GCM decrypt. Raises ValueError on auth failure."""
    raw = base64.b64decode(cipher_b64)
    nonce = raw[:12]
    ciphertext_with_tag = raw[12:]
    aesgcm = AESGCM(aes_key)
    try:
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except Exception as exc:
        raise ValueError("Decryption failed — invalid key or tampered data") from exc


def sign_message(payload: bytes, hmac_key: bytes) -> str:
    """HMAC-SHA256 signature → hex string."""
    return hmac.new(hmac_key, payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, signature: str, hmac_key: bytes) -> bool:
    """Constant-time HMAC-SHA256 verification."""
    expected = sign_message(payload, hmac_key)
    return hmac.compare_digest(expected, signature)


def generate_session_nonce() -> bytes:
    """Generate a cryptographically secure 32-byte session nonce."""
    return secrets.token_bytes(32)


def server_handshake(agent_public_key_pem: bytes) -> HandshakeResult:
    """
    Full server-side ECDH handshake.

    Steps:
      1. Generate server ECDH keypair
      2. Derive shared secret with agent's public key
      3. Generate random nonce (32 bytes)
      4. Derive AES key: HKDF(shared_secret, salt=nonce, info="lucy-aes-key")
      5. Encrypt nonce with derived AES key (proof-of-key)

    Returns HandshakeResult with everything needed for the HTTP response.
    """
    server_priv_pem, server_pub_pem = generate_keypair()
    shared_secret = derive_shared_secret(server_priv_pem, agent_public_key_pem)
    nonce = generate_session_nonce()
    aes_key = derive_aes_key(shared_secret, salt=nonce)
    nonce_encrypted = encrypt(nonce, aes_key)

    return HandshakeResult(
        aes_key=aes_key,
        server_public_key_pem=server_pub_pem,
        nonce_b64=base64.b64encode(nonce).decode("utf-8"),
        nonce_encrypted_b64=nonce_encrypted,
    )


def verify_handshake_proof(
    agent_private_key_pem: bytes,
    server_public_key_pem: bytes,
    nonce_b64: str,
    nonce_encrypted_b64: str,
) -> tuple[bool, bytes]:
    """
    Agent-side handshake verification.

    Derives the same AES key and decrypts the nonce proof to confirm
    the server holds the matching private key.

    Returns (verified: bool, aes_key: bytes).
    """
    shared_secret = derive_shared_secret(agent_private_key_pem, server_public_key_pem)
    nonce = base64.b64decode(nonce_b64)
    aes_key = derive_aes_key(shared_secret, salt=nonce)

    try:
        decrypted_nonce = decrypt(nonce_encrypted_b64, aes_key)
        verified = hmac.compare_digest(decrypted_nonce, nonce)
        return verified, aes_key
    except ValueError:
        return False, b""


def encrypt_field(value: str, master_key_hex: str) -> str:
    """Encrypt a string field using the master key (for credential storage)."""
    key = bytes.fromhex(master_key_hex)[:32]
    return encrypt(value.encode("utf-8"), key)


def decrypt_field(cipher_b64: str, master_key_hex: str) -> str:
    """Decrypt a string field using the master key."""
    key = bytes.fromhex(master_key_hex)[:32]
    return decrypt(cipher_b64, key).decode("utf-8")


class CryptoService:
    @staticmethod
    def generate_keypair() -> tuple[bytes, bytes]:
        return generate_keypair()

    @staticmethod
    def derive_shared_secret(private_key_pem: bytes, peer_public_key_pem: bytes) -> bytes:
        return derive_shared_secret(private_key_pem, peer_public_key_pem)

    @staticmethod
    def derive_aes_key(shared_secret: bytes, salt: bytes = b"lucy") -> bytes:
        return derive_aes_key(shared_secret, salt)

    @staticmethod
    def encrypt(plaintext: bytes, aes_key: bytes) -> str:
        return encrypt(plaintext, aes_key)

    @staticmethod
    def decrypt(cipher_b64: str, aes_key: bytes) -> bytes:
        return decrypt(cipher_b64, aes_key)

    @staticmethod
    def sign_message(payload: bytes, hmac_key: bytes) -> str:
        return sign_message(payload, hmac_key)

    @staticmethod
    def verify_signature(payload: bytes, signature: str, hmac_key: bytes) -> bool:
        return verify_signature(payload, signature, hmac_key)

    @staticmethod
    def server_handshake(agent_public_key_pem: bytes) -> HandshakeResult:
        return server_handshake(agent_public_key_pem)

    @staticmethod
    def verify_handshake_proof(
        agent_private_key_pem: bytes,
        server_public_key_pem: bytes,
        nonce_b64: str,
        nonce_encrypted_b64: str,
    ) -> tuple[bool, bytes]:
        return verify_handshake_proof(
            agent_private_key_pem, server_public_key_pem, nonce_b64, nonce_encrypted_b64
        )

    @staticmethod
    def encrypt_field(value: str, master_key_hex: str) -> str:
        return encrypt_field(value, master_key_hex)

    @staticmethod
    def decrypt_field(cipher_b64: str, master_key_hex: str) -> str:
        return decrypt_field(cipher_b64, master_key_hex)
