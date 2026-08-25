#!/usr/bin/env python3
"""
Lucy C2 — Portable launcher (no Docker).

Usage:
    python tools/portable/launcher.py
    python tools/portable/launcher.py --browser
    python tools/portable/launcher.py --offline
    python tools/portable/launcher.py --runtime-deps

What it does:
1. Ensures a Python interpreter is available (downloads embedded Python on Windows if needed).
2. Creates a local virtual environment under portable/.venv.
3. Installs backend requirements (use --runtime-deps for a smaller trimmed venv).
4. Builds the frontend if dist/ is missing (skipped in --offline mode if stale/missing).
5. Starts the backend on http://127.0.0.1:8000 with PORTABLE_MODE=true.
6. Opens the dashboard in a native desktop window (or browser with --browser).

The whole Lucy folder can be moved/copied to a USB drive.

Flags:
    --offline        Do not attempt pip install or npm build. The venv and
                     frontend dist/ must already be populated (run once
                     without --offline first, or pre-populate manually).
    --runtime-deps   Use requirements-runtime.txt instead of requirements.txt
                     for a smaller venv (~80 MB vs ~158 MB).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

_log_file: "io.TextIOWrapper | None" = None

# Root of the Lucy repository
ROOT = Path(__file__).resolve().parent.parent.parent
PORTABLE_DIR = ROOT / "tools" / "portable"
VENV_DIR = PORTABLE_DIR / ".venv"

PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip"
PYTHON_EMBED_DIR = PORTABLE_DIR / "python-embedded"


def log(msg: str) -> None:
    line = f"[Lucy Portable] {msg}"
    print(line)
    if _log_file is not None and not _log_file.closed:
        _log_file.write(line + "\n")
        _log_file.flush()


def run(cmd: list[str | Path], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd or ROOT),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 and check:
        log(f"Command failed (exit {proc.returncode}):")
        log(proc.stdout)
        log(proc.stderr)
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)
    return proc


def find_python() -> Path | None:
    """Look for a usable Python 3.12+ interpreter."""
    for candidate in (sys.executable, "python3", "python"):
        exe = shutil.which(candidate)
        if not exe:
            continue
        try:
            out = subprocess.run(
                [exe, "--version"],
                text=True,
                capture_output=True,
                check=True,
            )
            version = out.stdout.strip() or out.stderr.strip()
            if "3.12" in version or "3.13" in version or "3.11" in version:
                return Path(exe).resolve()
        except Exception:
            pass
    return None


def download_embedded_python() -> Path:
    """Download and unpack Windows embedded Python."""
    PYTHON_EMBED_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PORTABLE_DIR / "python-embed.zip"

    if not zip_path.exists():
        log("Downloading embedded Python 3.12...")
        urllib.request.urlretrieve(PYTHON_EMBED_URL, zip_path)
        log("Download complete.")

    if not (PYTHON_EMBED_DIR / "python.exe").exists():
        log("Extracting embedded Python...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(PYTHON_EMBED_DIR)
        # Enable site packages / pip support
        pth = next(PYTHON_EMBED_DIR.glob("*._pth"), None)
        if pth:
            text = pth.read_text(encoding="utf-8")
            pth.write_text(text.replace("#import site", "import site"), encoding="utf-8")
        log("Embedded Python ready.")

    return PYTHON_EMBED_DIR / "python.exe"


def ensure_python() -> Path:
    """Return a usable Python interpreter, downloading one if necessary."""
    py = find_python()
    if py:
        return py
    system = platform.system()
    if system == "Windows":
        return download_embedded_python()
    raise RuntimeError(
        "Python 3.11+ is required. Install it from python.org, then re-run this launcher."
    )


def _requirements_hash(req_file: Path) -> str:
    """Return sha256 of requirements.txt for cache invalidation."""
    return hashlib.sha256(req_file.read_bytes()).hexdigest()[:16]


def ensure_venv(
    python: Path,
    requirements_file: str = "requirements.txt",
    offline: bool = False,
) -> Path:
    """Create local venv and install requirements if missing or requirements changed.

    Parameters
    ----------
    python:
        Python interpreter to use for venv creation.
    requirements_file:
        Filename of the requirements file inside ``backend/`` (e.g.
        ``requirements.txt`` or ``requirements-runtime.txt``).
    offline:
        When *True*, do **not** attempt any pip installs.  If the venv is
        missing or the requirements hash has changed, log an error and exit
        instead of trying to fetch packages.
    """
    req_file = ROOT / "backend" / requirements_file
    marker = VENV_DIR / "lucy-ready"
    expected_hash = _requirements_hash(req_file)

    if marker.exists():
        cached = marker.read_text(encoding="utf-8").strip().splitlines()
        # First line is the hash; remaining lines may store installed version metadata.
        if cached and cached[0] == expected_hash:
            log("Virtual environment is up to date.")
            return VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin") / "python"

    # --- Offline path: cannot create or update the venv -----------------------
    if offline:
        if not VENV_DIR.exists():
            log(
                "ERROR: Virtual environment does not exist and --offline is set.\n"
                "       The launcher cannot install packages without network access.\n"
                "       Run the launcher once WITHOUT --offline to populate the venv,\n"
                "       or pre-populate tools/portable/.venv manually."
            )
            sys.exit(1)
        log(
            "WARNING: Virtual environment exists but requirements may have changed.\n"
            "         --offline is set, so pip install was skipped. If the backend\n"
            "         fails to start, run without --offline once to update packages."
        )
        return VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin") / "python"

    # --- Normal path: create / recreate venv and pip install ------------------
    log("Virtual environment missing or requirements changed — preparing...")
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    run([python, "-m", "venv", str(VENV_DIR)])

    pip = VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin") / "pip"
    log(f"Installing backend requirements from {requirements_file}...")
    run([pip, "install", "--disable-pip-version-check", "-r", str(req_file)])
    marker.write_text(f"{expected_hash}\n", encoding="utf-8")
    log("Virtual environment ready.")

    return VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin") / "python"


def build_frontend(skip_if_present: bool = True, offline: bool = False) -> None:
    """Build frontend static files if dist/ is missing or stale.

    When *offline* is *True* and the dist directory is missing or stale,
    the build is skipped with a warning instead of attempting npm install.
    """
    dist = ROOT / "frontend" / "dist"
    src = ROOT / "frontend" / "src"
    lock = ROOT / "frontend" / "package-lock.json"

    if skip_if_present and dist.exists() and any(dist.iterdir()):
        dist_mtime = max((p.stat().st_mtime for p in dist.rglob("*") if p.is_file()), default=0)
        src_mtime = max((p.stat().st_mtime for p in src.rglob("*") if p.is_file()), default=0)
        lock_mtime = lock.stat().st_mtime if lock.exists() else 0
        if dist_mtime >= max(src_mtime, lock_mtime):
            log("Frontend build is up to date.")
            return

    # --- Offline path: skip build, warn about staleness -----------------------
    if offline:
        if not dist.exists() or not any(dist.iterdir()):
            log(
                "WARNING: frontend dist/ is missing and --offline is set.\n"
                "         Skipping frontend build. The dashboard may not load.\n"
                "         Run the launcher once WITHOUT --offline to build the frontend."
            )
        else:
            log(
                "WARNING: frontend dist/ may be stale and --offline is set.\n"
                "         Skipping frontend rebuild. The dashboard may show outdated content."
            )
        return

    node_candidates = ["node", "npm"]
    if platform.system() == "Windows":
        node_candidates += [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\node.exe"),
            os.path.expandvars(r"%PROGRAMDATA%\chocolatey\bin\node.exe"),
        ]
    node = None
    for candidate in node_candidates:
        node = shutil.which(candidate)
        if node:
            break
    if not node:
        raise RuntimeError(
            "Node.js is required to build the frontend. Install it from nodejs.org."
        )

    node_path = Path(node)
    npm_cmd = "npm"
    if platform.system() == "Windows":
        npm_path = node_path.parent / "npm.cmd"
        if npm_path.exists():
            npm_cmd = str(npm_path)
        elif shutil.which("npm.cmd"):
            npm_cmd = "npm.cmd"
        else:
            npm_cmd = "npm"

    node_modules = ROOT / "frontend" / "node_modules"
    if node_modules.exists() and lock.exists():
        nm_mtime = max((p.stat().st_mtime for p in node_modules.rglob("*") if p.is_file()), default=0)
        if nm_mtime >= lock.stat().st_mtime:
            log("Frontend dependencies already installed.")
        else:
            log("Installing frontend dependencies...")
            run([npm_cmd, "ci"], cwd=ROOT / "frontend")
    else:
        log("Installing frontend dependencies...")
        run([npm_cmd, "ci"], cwd=ROOT / "frontend")

    log("Building frontend...")
    run([npm_cmd, "run", "build"], cwd=ROOT / "frontend")
    log("Frontend build complete.")


def wait_for_backend(url: str = "http://127.0.0.1:8000/health", timeout: int = 30) -> bool:
    """Poll the backend health endpoint until it responds."""
    start = time.time()
    deadline = start + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def open_window(python: Path, url: str = "http://127.0.0.1:8000") -> None:
    """Open Lucy in a native desktop window using pywebview inside the venv."""
    log("Opening native window...")
    script = Path(__file__).resolve().parent / "window.py"
    subprocess.run(
        [str(python), str(script)],
        cwd=str(ROOT),
        check=True,
    )


def open_browser(url: str = "http://127.0.0.1:8000") -> None:
    """Open Lucy in the default system browser."""
    log("Opening browser...")
    system = platform.system()
    if system == "Windows":
        os.startfile(url)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["open", url], check=False)
    else:
        subprocess.run(["xdg-open", url], check=False)


def start_backend(python: Path) -> subprocess.Popen[str]:
    """Launch backend in portable mode as a background subprocess."""
    log("Starting Lucy C2 backend on http://127.0.0.1:8000 ...")
    env = os.environ.copy()
    env["PORTABLE_MODE"] = "true"
    env["FRONTEND_DIST_PATH"] = str(ROOT / "frontend" / "dist")
    env["DATABASE_URL"] = f"sqlite:///{PORTABLE_DIR / 'lucy.db'}"
    env["REDIS_URL"] = ""
    env["CELERY_BROKER_URL"] = ""
    env["CELERY_RESULT_BACKEND"] = ""
    env["LOG_LEVEL"] = "warning"

    return subprocess.Popen(
        [str(python), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000",
         "--no-access-log", "--log-level", "warning"],
        cwd=str(ROOT / "backend"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def tail_backend(proc: subprocess.Popen[str]) -> None:
    """Forward backend logs to stdout until the process ends."""
    if proc.stdout is None:
        return
    for line in iter(proc.stdout.readline, ""):
        print(line, end="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lucy C2 portable launcher")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open in the system browser instead of a native window",
    )
    parser.add_argument(
        "--no-shortcut",
        action="store_true",
        help="Skip creating the desktop shortcut",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="Skip frontend build even if dist/ is missing (useful for backend-only tests)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: skip shortcut creation and only build frontend if dist/ is missing",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Redirect launcher logs to a file instead of stdout",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline mode: do not attempt pip install or npm build. "
        "The venv and frontend must already be populated (run without "
        "--offline once first).",
    )
    parser.add_argument(
        "--runtime-deps",
        action="store_true",
        help="Use requirements-runtime.txt (trimmed deps, ~80 MB venv) "
        "instead of requirements.txt (~158 MB venv).",
    )
    return parser.parse_args()


def create_desktop_shortcut() -> None:
    """Create a Windows desktop shortcut pointing to start.bat with the Lucy icon."""
    if platform.system() != "Windows":
        return

    import ctypes.wintypes

    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)  # 0 = Desktop
    desktop = Path(buf.value)
    shortcut = desktop / "Lucy C2.lnk"

    if shortcut.exists():
        log(f"Desktop shortcut already exists: {shortcut}")
        return

    bat = (ROOT / "tools" / "portable" / "start.bat").resolve()
    icon = (ROOT / "tools" / "portable" / "lucy.ico").resolve()

    ps = (
        "$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut}'); "
        f"$Shortcut.TargetPath = '{bat}'; "
        f"$Shortcut.WorkingDirectory = '{ROOT}'; "
        f"$Shortcut.IconLocation = '{icon},0'; "
        "$Shortcut.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=True,
            capture_output=True,
            text=True,
        )
        log(f"Desktop shortcut created: {shortcut}")
    except Exception as exc:
        log(f"Could not create desktop shortcut: {exc}")


def main() -> None:
    args = parse_args()
    global _log_file
    if args.log_file:
        _log_file = open(args.log_file, "a", encoding="utf-8")
    log("Initializing Lucy portable mode...")
    python = ensure_python()
    requirements_file = "requirements-runtime.txt" if args.runtime_deps else "requirements.txt"
    venv_python = ensure_venv(python, requirements_file=requirements_file, offline=args.offline)

    if not args.skip_frontend_build:
        build_frontend(skip_if_present=not args.fast, offline=args.offline)

    if not args.no_shortcut and not args.fast:
        create_desktop_shortcut()

    proc = start_backend(venv_python)

    # Stream backend logs in a background thread so the user sees startup messages.
    threading.Thread(target=tail_backend, args=(proc,), daemon=True).start()

    if not wait_for_backend():
        log("ERROR: Backend failed to start. Check the logs above.")
        proc.terminate()
        sys.exit(1)

    try:
        if args.browser:
            open_browser()
        else:
            try:
                open_window(venv_python)
            except Exception as exc:
                log(f"Native window failed ({exc}); falling back to browser.")
                open_browser()
        # Keep backend alive until the user stops the launcher.
        proc.wait()
    except KeyboardInterrupt:
        log("Interrupted by user.")
    finally:
        log("Stopping backend...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log("Backend stopped.")
        if _log_file is not None:
            _log_file.close()


if __name__ == "__main__":
    main()
