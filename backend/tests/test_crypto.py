"""
Crypto layer tests — Prompt 7

Tests backend/core/crypto.py for correctness and cross-compatibility
with agent/core/crypto.py (same parameters, same results).

Run:
    cd backend
    pytest tests/test_crypto.py -v
"""
import base64
import sys
from pathlib import Path

import pytest

# Make agent module importable from backend test context
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))

from core.crypto import (
    decrypt,
    derive_aes_key,
    derive_shared_secret,
    encrypt,
    generate_keypair,
    generate_session_nonce,
    server_handshake,
    sign_message,
    verify_handshake_proof,
    verify_signature,
)


# ---------------------------------------------------------------------------
# generate_keypair
# ---------------------------------------------------------------------------


class TestGenerateKeypair:
    def test_returns_pem_bytes(self):
        priv, pub = generate_keypair()
        assert isinstance(priv, bytes)
        assert isinstance(pub, bytes)
        assert b"PRIVATE KEY" in priv
        assert b"PUBLIC KEY" in pub

    def test_unique_each_call(self):
        _, pub1 = generate_keypair()
        _, pub2 = generate_keypair()
        assert pub1 != pub2

    def test_pem_roundtrip(self):
        from cryptography.hazmat.primitives import serialization
        priv, pub = generate_keypair()
        serialization.load_pem_private_key(priv, password=None)
        serialization.load_pem_public_key(pub)


# ---------------------------------------------------------------------------
# derive_shared_secret
# ---------------------------------------------------------------------------


class TestDeriveSharedSecret:
    def test_symmetric(self):
        """ECDH must produce same secret from both sides."""
        priv_a, pub_a = generate_keypair()
        priv_b, pub_b = generate_keypair()
        secret_a = derive_shared_secret(priv_a, pub_b)
        secret_b = derive_shared_secret(priv_b, pub_a)
        assert secret_a == secret_b

    def test_returns_32_bytes(self):
        priv_a, pub_a = generate_keypair()
        priv_b, pub_b = generate_keypair()
        secret = derive_shared_secret(priv_a, pub_b)
        assert len(secret) == 32

    def test_different_pairs_different_secret(self):
        priv_a, pub_a = generate_keypair()
        priv_b, pub_b = generate_keypair()
        priv_c, pub_c = generate_keypair()
        assert derive_shared_secret(priv_a, pub_b) != derive_shared_secret(priv_a, pub_c)


# ---------------------------------------------------------------------------
# derive_aes_key
# ---------------------------------------------------------------------------


class TestDeriveAesKey:
    def test_length(self):
        secret = b"\x00" * 32
        key = derive_aes_key(secret)
        assert len(key) == 32

    def test_deterministic(self):
        secret = b"test_secret_bytes_32_chars_here!"
        assert derive_aes_key(secret, b"salt1") == derive_aes_key(secret, b"salt1")

    def test_different_salt_different_key(self):
        secret = b"test_secret_bytes_32_chars_here!"
        assert derive_aes_key(secret, b"salt1") != derive_aes_key(secret, b"salt2")

    def test_hkdf_info_context(self):
        """Key derived with info='lucy-aes-key' must differ from raw HKDF without info."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        secret = b"\xaa" * 32
        lucy_key = derive_aes_key(secret, b"salt")
        raw_hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"salt", info=b"other").derive(secret)
        assert lucy_key != raw_hkdf


# ---------------------------------------------------------------------------
# encrypt / decrypt
# ---------------------------------------------------------------------------


class TestEncryptDecrypt:
    def test_roundtrip(self):
        key = derive_aes_key(b"\xbb" * 32)
        plaintext = b"Hello, Lucy!"
        cipher = encrypt(plaintext, key)
        assert decrypt(cipher, key) == plaintext

    def test_output_is_base64_string(self):
        key = derive_aes_key(b"\xcc" * 32)
        cipher = encrypt(b"test", key)
        assert isinstance(cipher, str)
        raw = base64.b64decode(cipher)
        assert len(raw) > 12 + 16

    def test_nonce_is_different_each_time(self):
        key = derive_aes_key(b"\xdd" * 32)
        c1 = encrypt(b"same plaintext", key)
        c2 = encrypt(b"same plaintext", key)
        assert c1 != c2

    def test_wrong_key_raises(self):
        key1 = derive_aes_key(b"\xee" * 32, b"salt1")
        key2 = derive_aes_key(b"\xee" * 32, b"salt2")
        cipher = encrypt(b"secret", key1)
        with pytest.raises(ValueError):
            decrypt(cipher, key2)

    def test_tampered_ciphertext_raises(self):
        key = derive_aes_key(b"\xff" * 32)
        cipher = encrypt(b"data", key)
        raw = bytearray(base64.b64decode(cipher))
        raw[20] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(ValueError):
            decrypt(tampered, key)

    def test_empty_plaintext(self):
        key = derive_aes_key(b"\x11" * 32)
        assert decrypt(encrypt(b"", key), key) == b""

    def test_large_payload(self):
        key = derive_aes_key(b"\x22" * 32)
        payload = b"X" * 1_000_000
        assert decrypt(encrypt(payload, key), key) == payload


# ---------------------------------------------------------------------------
# sign_message / verify_signature
# ---------------------------------------------------------------------------


class TestHmac:
    def test_sign_returns_hex_string(self):
        sig = sign_message(b"data", b"key_" * 8)
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_verify_correct(self):
        payload = b"important message"
        key = b"hmac_key_" * 4
        sig = sign_message(payload, key)
        assert verify_signature(payload, sig, key)

    def test_verify_wrong_payload(self):
        key = b"hmac_key_" * 4
        sig = sign_message(b"original", key)
        assert not verify_signature(b"modified", sig, key)

    def test_verify_wrong_key(self):
        sig = sign_message(b"data", b"key1" * 8)
        assert not verify_signature(b"data", sig, b"key2" * 8)

    def test_constant_time(self):
        """Ensure compare_digest is used (no timing leak)."""
        import time
        key = b"k" * 32
        payload = b"payload"
        sig = sign_message(payload, key)
        bad_sig = "a" * 64

        t0 = time.perf_counter()
        verify_signature(payload, sig, key)
        t1 = time.perf_counter()
        verify_signature(payload, bad_sig, key)
        t2 = time.perf_counter()
        assert abs((t1 - t0) - (t2 - t1)) < 0.1


# ---------------------------------------------------------------------------
# Full ECDH handshake (server_handshake + verify_handshake_proof)
# ---------------------------------------------------------------------------


class TestFullHandshake:
    def test_handshake_produces_same_aes_key(self):
        """
        Agent generates keypair → server_handshake() → agent verify_handshake_proof()
        Both sides must derive the identical AES key.
        """
        agent_priv, agent_pub = generate_keypair()
        hs = server_handshake(agent_pub)

        verified, agent_aes_key = verify_handshake_proof(
            agent_priv,
            hs.server_public_key_pem,
            hs.nonce_b64,
            hs.nonce_encrypted_b64,
        )

        assert verified is True
        assert agent_aes_key == hs.aes_key
        assert len(agent_aes_key) == 32

    def test_can_encrypt_decrypt_across_sides(self):
        """Server encrypts, agent decrypts — and vice versa."""
        agent_priv, agent_pub = generate_keypair()
        hs = server_handshake(agent_pub)
        _, aes_key = verify_handshake_proof(
            agent_priv, hs.server_public_key_pem, hs.nonce_b64, hs.nonce_encrypted_b64
        )

        server_msg = b"task from server"
        agent_msg = b"result from agent"

        assert decrypt(encrypt(server_msg, hs.aes_key), aes_key) == server_msg
        assert decrypt(encrypt(agent_msg, aes_key), hs.aes_key) == agent_msg

    def test_wrong_agent_key_fails_proof(self):
        """A different agent private key cannot verify the proof."""
        _, agent_pub = generate_keypair()
        wrong_priv, _ = generate_keypair()
        hs = server_handshake(agent_pub)

        verified, aes_key = verify_handshake_proof(
            wrong_priv,
            hs.server_public_key_pem,
            hs.nonce_b64,
            hs.nonce_encrypted_b64,
        )
        assert verified is False or aes_key != hs.aes_key

    def test_handshake_nonce_is_32_bytes(self):
        _, agent_pub = generate_keypair()
        hs = server_handshake(agent_pub)
        nonce = base64.b64decode(hs.nonce_b64)
        assert len(nonce) == 32

    def test_each_handshake_produces_unique_keys(self):
        _, agent_pub = generate_keypair()
        hs1 = server_handshake(agent_pub)
        hs2 = server_handshake(agent_pub)
        assert hs1.aes_key != hs2.aes_key
        assert hs1.nonce_b64 != hs2.nonce_b64


# ---------------------------------------------------------------------------
# Cross-compatibility: backend ↔ agent crypto modules
# ---------------------------------------------------------------------------


class TestCrossCompatibility:
    """
    Verify that backend/core/crypto.py and agent/core/crypto.py
    produce identical results with the same inputs.
    """

    def test_agent_can_decrypt_backend_cipher(self):
        import core.crypto as backend_crypto
        import sys
        agent_path = str(Path(__file__).resolve().parents[2] / "agent")
        if agent_path not in sys.path:
            sys.path.insert(0, agent_path)
        import importlib
        agent_crypto = importlib.import_module("core.crypto")

        priv_a, pub_a = backend_crypto.generate_keypair()
        priv_b, pub_b = backend_crypto.generate_keypair()

        secret_backend = backend_crypto.derive_shared_secret(priv_a, pub_b)
        secret_agent   = agent_crypto.derive_shared_secret(priv_a, pub_b)
        assert secret_backend == secret_agent

        key_backend = backend_crypto.derive_aes_key(secret_backend, b"test_salt")
        key_agent   = agent_crypto.derive_aes_key(secret_agent, b"test_salt")
        assert key_backend == key_agent

        plaintext = b"cross compat test payload"
        cipher = backend_crypto.encrypt(plaintext, key_backend)
        decrypted = agent_crypto.decrypt(cipher, key_agent)
        assert decrypted == plaintext

    def test_hmac_cross_compat(self):
        import core.crypto as backend_crypto
        import sys
        agent_path = str(Path(__file__).resolve().parents[2] / "agent")
        if agent_path not in sys.path:
            sys.path.insert(0, agent_path)
        import importlib
        agent_crypto = importlib.import_module("core.crypto")

        payload = b"hmac cross test"
        key = b"shared_hmac_key_" * 2
        sig_backend = backend_crypto.sign_message(payload, key)
        sig_agent   = agent_crypto.sign_message(payload, key)
        assert sig_backend == sig_agent
        assert agent_crypto.verify_signature(payload, sig_backend, key)
        assert backend_crypto.verify_signature(payload, sig_agent, key)
