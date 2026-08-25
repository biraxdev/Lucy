"""
Clipboard capture module for Project Lucy agent.
Cross-platform clipboard read/write/monitor using ctypes on Windows,
xclip on Linux, and pbpaste/pbcopy on macOS.
Actions: capture, monitor, set.
"""
import platform
import subprocess
import time
from datetime import datetime

name = "clipboard"
version = "1.0.0"
os_compat = ["Windows", "Linux", "Darwin"]
dependencies: list[str] = []

SYSTEM = platform.system()

CF_UNICODETEXT = 13


def _win_capture() -> str:
    """Capture clipboard text on Windows via ctypes."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if not user32.OpenClipboard(0):
        raise RuntimeError("OpenClipboard failed")

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""

        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""

        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""

        try:
            text = ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)

        return text
    finally:
        user32.CloseClipboard()


def _win_set(text: str) -> None:
    """Set clipboard text on Windows via ctypes."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    GMEM_MOVEABLE = 0x0002

    if not user32.OpenClipboard(0):
        raise RuntimeError("OpenClipboard failed")
    try:
        user32.EmptyClipboard()
        data = text + "\0"
        data_bytes = data.encode("utf-16-le")
        size = len(data_bytes)

        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h_global:
            raise RuntimeError("GlobalAlloc failed")

        ptr = kernel32.GlobalLock(h_global)
        if not ptr:
            raise RuntimeError("GlobalLock failed")

        try:
            ctypes.memmove(ptr, data_bytes, size)
        finally:
            kernel32.GlobalUnlock(h_global)

        user32.SetClipboardData(CF_UNICODETEXT, h_global)
    finally:
        user32.CloseClipboard()


def _linux_capture() -> str:
    """Capture clipboard text on Linux via xclip."""
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout
    except FileNotFoundError:
        # Try xsel as fallback
        try:
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout
        except FileNotFoundError:
            raise RuntimeError("Neither xclip nor xsel available")


def _linux_set(text: str) -> None:
    """Set clipboard text on Linux via xclip."""
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text, text=True, timeout=5,
        )
    except FileNotFoundError:
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text, text=True, timeout=5,
            )
        except FileNotFoundError:
            raise RuntimeError("Neither xclip nor xsel available")


def _mac_capture() -> str:
    """Capture clipboard text on macOS via pbpaste."""
    result = subprocess.run(
        ["pbpaste"], capture_output=True, text=True, timeout=5,
    )
    return result.stdout


def _mac_set(text: str) -> None:
    """Set clipboard text on macOS via pbcopy."""
    subprocess.run(
        ["pbcopy"], input=text, text=True, timeout=5,
    )


def _capture() -> str:
    """Capture clipboard text — dispatch by OS."""
    if SYSTEM == "Windows":
        return _win_capture()
    elif SYSTEM == "Linux":
        return _linux_capture()
    elif SYSTEM == "Darwin":
        return _mac_capture()
    raise RuntimeError(f"Unsupported OS: {SYSTEM}")


def _set(text: str) -> None:
    """Set clipboard text — dispatch by OS."""
    if SYSTEM == "Windows":
        _win_set(text)
    elif SYSTEM == "Linux":
        _linux_set(text)
    elif SYSTEM == "Darwin":
        _mac_set(text)
    else:
        raise RuntimeError(f"Unsupported OS: {SYSTEM}")


def _monitor(duration: int) -> list[dict]:
    """Poll clipboard every 1s for duration seconds, collect unique values."""
    changes = []
    last_text = None
    end_time = time.time() + duration

    while time.time() < end_time:
        try:
            current = _capture()
            if current != last_text:
                last_text = current
                changes.append({
                    "text": current,
                    "timestamp": datetime.utcnow().isoformat(timespec="milliseconds"),
                })
        except Exception:
            pass
        time.sleep(1.0)

    return changes


def run(action: str = "capture", **params) -> dict:
    try:
        if action == "capture":
            text = _capture()
            return {"status": "completed", "data": {"text": text}}

        elif action == "set":
            text = params.get("text", "")
            _set(text)
            return {"status": "completed", "data": {"text": text, "set": True}}

        elif action == "monitor":
            duration = int(params.get("duration", 60))
            changes = _monitor(duration)
            return {
                "status": "completed",
                "data": {
                    "changes": changes,
                    "count": len(changes),
                    "duration": duration,
                },
            }

        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
