NAME = "webcam"
VERSION = "1.0.0"
DESCRIPTION = "Webcam capture — single frame or burst. OpenCV primary, platform fallbacks."
AUTHOR = "lucy"
DEPENDENCIES = ["opencv-python>=4.8"]
OS_COMPAT = ["windows", "linux", "darwin"]


import base64
import io
import os
import platform
import subprocess
import tempfile
import time


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    if action in ("capture", "run", "snap"):
        return _capture(params)
    elif action == "burst":
        return _burst(params)
    elif action == "list":
        return _list_devices()
    return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}


def _capture(params: dict) -> dict:
    device = int(params.get("device", 0))
    quality = int(params.get("quality", 85))
    fmt = params.get("format", "jpeg").lower()
    width = params.get("width")
    height = params.get("height")

    img_b64 = (
        _capture_opencv(device, quality, fmt, width, height)
        or _capture_ffmpeg(device, fmt)
        or _capture_imagesnap(device)
    )

    if not img_b64:
        return {"status": "failed", "data": None, "error": "No webcam backend available"}

    return {"status": "completed", "data": {
        "image_b64": img_b64,
        "format": fmt,
        "device": device,
    }}


def _burst(params: dict) -> dict:
    count = int(params.get("count", 3))
    interval = float(params.get("interval", 1.0))
    device = int(params.get("device", 0))

    frames = []
    for _ in range(count):
        r = _capture({"device": device, "quality": 75, "format": "jpeg"})
        if r.get("status") == "completed":
            frames.append(r["data"]["image_b64"])
        time.sleep(interval)

    return {"status": "completed", "data": {"frames": frames, "count": len(frames)}}


def _list_devices() -> dict:
    devices = []
    try:
        import cv2
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                devices.append({"index": i, "backend": "opencv"})
                cap.release()
    except ImportError:
        pass

    return {"status": "completed", "data": {"devices": devices}}


def _capture_opencv(device: int, quality: int, fmt: str, width=None, height=None) -> str | None:
    try:
        import cv2
        cap = cv2.VideoCapture(device)
        if not cap.isOpened():
            return None

        if width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        if height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))

        time.sleep(0.3)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return None

        ext = ".jpg" if fmt == "jpeg" else ".png"
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality] if fmt == "jpeg" else []
        _, buf = cv2.imencode(ext, frame, encode_params)
        return base64.b64encode(buf.tobytes()).decode()
    except Exception:
        return None


def _capture_ffmpeg(device: int, fmt: str) -> str | None:
    try:
        system = platform.system()
        ext = ".jpg" if fmt == "jpeg" else ".png"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            tmp = f.name

        if system == "Windows":
            cmd = ["ffmpeg", "-f", "dshow", "-i", f"video={device}", "-frames:v", "1", "-y", tmp]
        elif system == "Darwin":
            cmd = ["ffmpeg", "-f", "avfoundation", "-i", str(device), "-frames:v", "1", "-y", tmp]
        else:
            cmd = ["ffmpeg", "-f", "v4l2", "-i", f"/dev/video{device}", "-frames:v", "1", "-y", tmp]

        subprocess.run(cmd, timeout=10, capture_output=True, check=True)

        with open(tmp, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def _capture_imagesnap(device: int) -> str | None:
    if platform.system() != "Darwin":
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp = f.name
        subprocess.run(["imagesnap", tmp], timeout=10, capture_output=True, check=True)
        with open(tmp, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
