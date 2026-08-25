"""
screen_stream — continuous screen capture module.
Captures frames at a configurable FPS, JPEG-compresses them,
and sends them back as base64 payloads over the agent's WS channel.

Actions:
    start   — begin streaming (returns first frame immediately)
    stop    — stop the stream loop
    frame   — capture a single frame on demand
    info    — return screen resolution and current FPS
"""
import base64
import io
import logging
import threading
import time

name = "screen_stream"
version = "1.1.0"
os_compat = ["windows", "linux", "darwin"]
dependencies = ["Pillow"]

logger = logging.getLogger(__name__)

_stream_thread: threading.Thread | None = None
_stop_event = threading.Event()
_send_callback = None  # set by agent runtime when starting stream


def _capture_frame(quality: int = 60) -> str:
    """Capture a single screenshot, return as base64 JPEG string."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
    except Exception:
        try:
            import subprocess, tempfile, os
            tmp = tempfile.mktemp(suffix=".png")
            subprocess.run(["scrot", tmp], capture_output=True, timeout=3)
            from PIL import Image
            img = Image.open(tmp)
            os.unlink(tmp)
        except Exception as e:
            logger.error("screen capture failed: %s", e)
            return ""

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _get_resolution() -> dict:
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        return {"width": img.width, "height": img.height}
    except Exception:
        return {"width": 1920, "height": 1080}


def _stream_loop(fps: int, quality: int, send_fn):
    interval = 1.0 / max(1, min(fps, 30))
    logger.info("screen_stream: starting loop @ %d FPS", fps)
    while not _stop_event.is_set():
        t0 = time.monotonic()
        frame = _capture_frame(quality)
        if frame and send_fn:
            send_fn({
                "type": "screen_frame",
                "module": name,
                "data": frame,
                "ts": time.time(),
            })
        elapsed = time.monotonic() - t0
        sleep_for = max(0, interval - elapsed)
        _stop_event.wait(timeout=sleep_for)
    logger.info("screen_stream: loop stopped")


def run(
    action: str = "frame",
    fps: int = 10,
    quality: int = 60,
    send_fn=None,
    **kwargs,
) -> dict:
    global _stream_thread, _send_callback

    if action == "frame":
        frame = _capture_frame(quality)
        res = _get_resolution()
        return {
            "status": "completed",
            "data": {"frame": frame, **res},
        }

    elif action == "start":
        if _stream_thread and _stream_thread.is_alive():
            return {"status": "completed", "data": {"streaming": True, "message": "already running"}}
        _stop_event.clear()
        _send_callback = send_fn
        _stream_thread = threading.Thread(
            target=_stream_loop,
            args=(fps, quality, send_fn),
            daemon=True,
            name="screen_stream_loop",
        )
        _stream_thread.start()
        first_frame = _capture_frame(quality)
        res = _get_resolution()
        return {
            "status": "completed",
            "data": {"streaming": True, "fps": fps, "first_frame": first_frame, **res},
        }

    elif action == "stop":
        _stop_event.set()
        return {"status": "completed", "data": {"streaming": False}}

    elif action == "info":
        res = _get_resolution()
        return {
            "status": "completed",
            "data": {
                "streaming": bool(_stream_thread and _stream_thread.is_alive()),
                **res,
            },
        }

    return {"status": "error", "data": {"message": f"unknown action: {action}"}}
