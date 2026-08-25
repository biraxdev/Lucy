#!/usr/bin/env python3
"""
ghost_deployer.py — Ghost-Deployer (outil #50 du mapping Fifty).
Deploiement automatise d'agents Lucy sur une flotte d'hotes via SSH/SCP :
copie de l'artefact + config, lancement detache (nohup / schtasks),
verification de processus, rapport JSON par hote.
--dry-run: valide le plan sans rien copier.

Usage:
  python ghost_deployer.py --hosts hosts.json --artifact dist/lucy_agent.pyz --dry-run
  python ghost_deployer.py --hosts hosts.json --artifact dist/lucy_agent.exe --user root --key ~/.ssh/id_ed25519
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def _load_hosts(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("hosts", [])
    hosts = []
    for h in data:
        hosts.append({
            "host": h["host"],
            "user": h.get("user", os.environ.get("USER", "root")),
            "port": h.get("port", 22),
            "key": h.get("key", ""),
            "artifact": h.get("artifact", ""),
            "remote_dir": h.get("remote_dir", "/tmp/lucy"),
            "windows": h.get("windows", False),
            "args": h.get("args", []),
        })
    return hosts


def _ssh_cmd(host: dict, remote_cmd: str) -> list[str]:
    cmd = ["ssh", "-p", str(host["port"]), "-o", "StrictHostKeyChecking=no",
           "-o", "ConnectTimeout=15", "-o", "BatchMode=yes"]
    if host["key"]:
        cmd += ["-i", host["key"]]
    cmd += ["%s@%s" % (host["user"], host["host"]), remote_cmd]
    return cmd


def _scp_cmd(host: dict, local: str, remote: str) -> list[str]:
    cmd = ["scp", "-P", str(host["port"]), "-o", "StrictHostKeyChecking=no",
           "-o", "ConnectTimeout=15", "-o", "BatchMode=yes"]
    if host["key"]:
        cmd += ["-i", host["key"]]
    cmd += [local, "%s@%s:%s" % (host["user"], host["host"], remote)]
    return cmd


def deploy_host(host: dict, artifact: str, config: str | None, dry_run: bool) -> dict:
    res = {"host": host["host"], "status": "ok"}
    if shutil.which("ssh") is None or shutil.which("scp") is None:
        return {"host": host["host"], "status": "failed",
                "error": "ssh/scp introuvable sur PATH"}
    if not os.path.isfile(artifact):
        return {"host": host["host"], "status": "failed",
                "error": "artefact introuvable: " + artifact}

    rdir = host["remote_dir"]
    name = os.path.basename(artifact)
    mkdir = "mkdir -p %s" % rdir

    if dry_run:
        steps = [
            "ssh %s@%s (%s)" % (host["user"], host["host"], mkdir),
            "scp %s -> %s:%s/%s" % (artifact, host["host"], rdir, name),
        ]
        if config:
            steps.append("scp %s -> %s:%s/%s" % (config, host["host"], rdir, os.path.basename(config)))
        steps.append("lancement: " + _start_cmd(host, rdir, name))
        res.update({"dry_run": True, "plan": steps})
        return res

    r = subprocess.run(_ssh_cmd(host, mkdir), capture_output=True, text=True)
    if r.returncode != 0:
        return {"host": host["host"], "status": "failed",
                "error": "mkdir: " + (r.stderr or r.stdout)[-300:]}
    for local in (artifact, config):
        if not local:
            continue
        r = subprocess.run(_scp_cmd(host, local, rdir + "/"), capture_output=True, text=True)
        if r.returncode != 0:
            return {"host": host["host"], "status": "failed",
                    "error": "scp %s: %s" % (local, (r.stderr or r.stdout)[-300:])}

    r = subprocess.run(_ssh_cmd(host, _start_cmd(host, rdir, name)),
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"host": host["host"], "status": "failed",
                "error": "start: " + (r.stderr or r.stdout)[-300:]}
    time.sleep(2)
    check = "tasklist /FI \"IMAGENAME eq %s\" 2>nul | findstr /I %s" % (name, name)
    if host["windows"]:
        rc = subprocess.run(_ssh_cmd(host, check), capture_output=True)
        res["process_check"] = "found" if rc.returncode == 0 else "not_found"
    else:
        rc = subprocess.run(_ssh_cmd(host, "pgrep -f %s >/dev/null && echo up || echo down" % name),
                            capture_output=True, text=True)
        res["process_check"] = (rc.stdout or "").strip()
    return res


def _start_cmd(host: dict, rdir: str, name: str) -> str:
    exe = os.path.join(rdir, name)
    args = " ".join(shlex_quote(a) for a in host["args"])
    if host["windows"]:
        return ('schtasks /create /tn LucyDeploy /tr "%s %s" /sc once /st 00:00 /f && '
                "schtasks /run /tn LucyDeploy" % (exe, args)).strip()
    return "cd %s && nohup python3 %s %s >/dev/null 2>&1 & echo $!" % (rdir, name, args)


def shlex_quote(s: str) -> str:
    return "'" + s.replace("'", "'\''") + "'" if s else s


def main(argv=None):
    p = argparse.ArgumentParser(description="Ghost-Deployer Lucy (deploiement SSH MaaS)")
    p.add_argument("--hosts", required=True, help="fichier hosts.json")
    p.add_argument("--artifact", required=True, help="agent/artefact a deployer")
    p.add_argument("--config", default=None, help="agent.ini optionnel")
    p.add_argument("--user", default=None, help="user SSH par defaut")
    p.add_argument("--key", default=None, help="cle SSH par defaut")
    p.add_argument("--dry-run", action="store_true", help="valide le plan sans deployer")
    p.add_argument("--parallel", type=int, default=5, help="hotes simultanes")
    p.add_argument("--out", default="deploy_report.json", help="rapport JSON")
    args = p.parse_args(argv)

    hosts = _load_hosts(args.hosts)
    if args.user:
        for h in hosts:
            h["user"] = args.user
    if args.key:
        for h in hosts:
            h["key"] = args.key

    report = {"dry_run": args.dry_run, "artifact": args.artifact,
              "hosts": [], "summary": {"ok": 0, "failed": 0}}
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(deploy_host, h, args.artifact, args.config, args.dry_run): h["host"]
                for h in hosts}
        for fut in as_completed(futs):
            r = fut.result()
            report["hosts"].append(r)
            report["summary"]["ok" if r["status"] == "ok" else "failed"] += 1

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("ghost_deployer:", json.dumps(report["summary"]))
    return report


if __name__ == "__main__":
    main()
