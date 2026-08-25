"""
Screenshot module with streaming support for Project Lucy agent.
Captures screen via PIL/mss/scrot and returns base64-encoded JPEG.
Streaming mode sends frames at a given interval via the agent's send callback.
"""
import base64
import io
import platform
import threading
import time

_stream_thread: threading.Thread | None = None
_stream_stop = threading.Event()


def _capture_frame(quality: int = 70, width: int | None = None, height: int | None = None) -> str:
    """Capture one frame and return as base64 JPEG string."""
    img = None

    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
    except Exception:
        pass

    if img is None:
        try:
            import mss
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[0])
                from PIL import Image
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        except Exception:
            pass

    if img is None and platform.system() == "Linux":
        try:
            import subprocess
            result = subprocess.run(
                ["scrot", "-", "-z"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                from PIL import Image
                img = Image.open(io.BytesIO(result.stdout))
        except Exception:
            pass

    if img is None:
        raise RuntimeError("No screenshot backend available")

    if width or height:
        orig_w, orig_h = img.size
        nw = width or int(orig_w * (height / orig_h))
        nh = height or int(orig_h * (width / orig_w))
        img = img.resize((nw, nh))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def run(
    action: str = "capture",
    quality: int = 70,
    width: int | None = None,
    height: int | None = None,
    interval: float = 2.0,
    max_frames: int = 60,
    send_callback=None,
    **kwargs,
) -> dict:
    global _stream_thread, _stream_stop

    if action == "capture":
        data = _capture_frame(quality=quality, width=width, height=height)
        return {"status": "ok", "data": data, "encoding": "base64/jpeg"}

    elif action == "stream_start":
        if _stream_thread and _stream_thread.is_alive():
            return {"status": "already_streaming"}

        _stream_stop.clear()

        def _stream():
            count = 0
            while not _stream_stop.is_set() and count < max_frames:
                try:
                    frame = _capture_frame(quality=quality, width=width, height=height)
                    if send_callback:
                        send_callback({
                            "type": "screenshot_frame",
                            "payload": {"data": frame, "frame": count, "encoding": "base64/jpeg"},
                        })
                    count += 1
                except Exception as exc:
                    if send_callback:
                        send_callback({"type": "error", "payload": {"message": str(exc)}})
                    break
                _stream_stop.wait(interval)

        _stream_thread = threading.Thread(target=_stream, daemon=True)
        _stream_thread.start()
        return {"status": "streaming", "interval": interval, "max_frames": max_frames}

    elif action == "stream_stop":
        _stream_stop.set()
        return {"status": "stopped"}

    return {"error": f"Unknown action: {action}"}
