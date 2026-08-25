NAME = "screenshot"
VERSION = "1.0.0"
DESCRIPTION = "Screen capture — single, interval stream, or region. PIL + ctypes fallbacks."
AUTHOR = "lucy"
DEPENDENCIES = ["Pillow>=10.0", "mss>=9.0"]
OS_COMPAT = ["windows", "linux", "darwin"]


import base64
import io
import os
import platform
import threading
import time


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    mode = params.get("mode", "single")
    quality = int(params.get("quality", 85))
    max_width = int(params.get("max_width", 1920))
    fmt = params.get("format", "jpeg").lower()
    region = params.get("region", None)

    if mode == "single":
        img_b64 = _capture(quality, max_width, fmt, region)
        return {"status": "completed", "data": {"image_b64": img_b64, "format": fmt}}

    elif mode == "interval":
        duration = int(params.get("stream_duration", 30))
        interval = int(params.get("stream_interval", 3))
        frames = []
        end = time.time() + duration
        while time.time() < end:
            frames.append(_capture(quality, max_width, fmt, region))
            time.sleep(interval)
        return {"status": "completed", "data": {"frames": frames, "count": len(frames)}}

    elif mode == "region":
        if not region:
            raise ModuleError("region params required: {x, y, width, height}")
        img_b64 = _capture(quality, max_width, fmt, region)
        return {"status": "completed", "data": {"image_b64": img_b64, "format": fmt}}

    return {"status": "failed", "data": None, "error": f"Unknown mode: {mode}"}


def _capture(quality: int, max_width: int, fmt: str, region=None) -> str:
    img_bytes = (
        _capture_pil(region)
        or _capture_mss(region)
        or _capture_ctypes_win()
        or _capture_scrot()
    )
    if img_bytes is None:
        raise ModuleError("No screenshot backend available")

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes))
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)))
        buf = io.BytesIO()
        save_fmt = "JPEG" if fmt == "jpeg" else "PNG"
        if save_fmt == "JPEG" and img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(buf, format=save_fmt, quality=quality if save_fmt == "JPEG" else None)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return base64.b64encode(img_bytes).decode()


def _capture_pil(region=None) -> bytes | None:
    try:
        from PIL import ImageGrab
        box = (region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"]) if region else None
        img = ImageGrab.grab(bbox=box)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _capture_mss(region=None) -> bytes | None:
    try:
        import mss, mss.tools
        with mss.mss() as sct:
            mon = region or sct.monitors[1]
            shot = sct.grab(mon)
            return mss.tools.to_png(shot.rgb, shot.size)
    except Exception:
        return None


def _capture_ctypes_win() -> bytes | None:
    if platform.system() != "Windows":
        return None
    try:
        import ctypes, ctypes.wintypes
        import struct

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        hdc = user32.GetDC(0)
        hbm = gdi32.CreateCompatibleBitmap(hdc, w, h)
        hmem = gdi32.CreateCompatibleDC(hdc)
        gdi32.SelectObject(hmem, hbm)
        gdi32.BitBlt(hmem, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)

        bmi = b'\x28\x00\x00\x00' + struct.pack('<i', w) + struct.pack('<i', -h) + b'\x01\x00\x20\x00' + b'\x00' * 24
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hmem, hbm, 0, h, buf, bmi, 0)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hmem)
        user32.ReleaseDC(0, hdc)

        from PIL import Image
        img = Image.frombytes("RGBA", (w, h), buf.raw, "raw", "BGRA")
        out = io.BytesIO()
        img.convert("RGB").save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def _capture_scrot() -> bytes | None:
    try:
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        subprocess.run(["scrot", tmp], timeout=5, check=True)
        with open(tmp, "rb") as f:
            data = f.read()
        os.unlink(tmp)
        return data
    except Exception:
        return None
