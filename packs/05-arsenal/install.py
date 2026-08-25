#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py - Installation de l'arsenal Lucy (packs/05-arsenal).

Etapes :
  1. copie modules/*.py  -> backend/modules/
  2. seed registry (table 'modules', signature HMAC-SHA256, enabled=1)
  3. copie build/*.py    -> tools/arsenal/
  4. verification de l'enregistrement (modules actifs + signatures)
  5. ecriture de packs/05-arsenal/INSTALLED.json

Signature : HMAC-SHA256, cle = sha256(MASTER_KEY + b":module-signing").
La cle MASTER_KEY et DATABASE_URL sont lues depuis backend/.env.
Le seed prefere le ModuleManager reel (peewee) et retombe sur sqlite3 stdlib
(schema miroir) si le backend n'est pas importable.

Usage:
    python install.py [--dry-run] [--db CHEMIN] [--no-seed] [--no-copy]
                      [--venv CHEMIN] [--quiet]
"""
import argparse
import ast
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = HERE
ROOT = os.path.dirname(os.path.dirname(HERE))
MODULES_SRC = os.path.join(PACK_DIR, "modules")
BUILD_SRC = os.path.join(PACK_DIR, "build")
BACKEND_DIR = os.path.join(ROOT, "backend")
BACKEND_MODULES = os.path.join(BACKEND_DIR, "modules")
TOOLS_DIR = os.path.join(ROOT, "tools", "arsenal")
ENV_FILE = os.path.join(BACKEND_DIR, ".env")
DEFAULT_DB = os.path.join(BACKEND_DIR, "lucy.db")
REEXEC_FLAG = "LUCY_INSTALL_REEXEC"


def parse_env(path):
    env = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def hmac_key(master_key):
    return hashlib.sha256(master_key.encode("utf-8") + b":module-signing").digest()


def sign_code(code, master_key):
    return hmac.new(hmac_key(master_key), code.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def extract_meta(path):
    meta = {"name": "", "version": "1.0.0", "description": "", "author": "",
            "dependencies": [], "os_compat": ["windows", "linux", "darwin"]}
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            key = node.targets[0].id
            if key in ("NAME", "VERSION", "DESCRIPTION", "AUTHOR",
                       "DEPENDENCIES", "OS_COMPAT"):
                try:
                    meta[key.lower()] = ast.literal_eval(node.value)
                except Exception:
                    pass
    return meta


def sqlite_connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS modules ("
        "id TEXT PRIMARY KEY, "
        "name VARCHAR(64) UNIQUE NOT NULL, "
        "version VARCHAR(16) NOT NULL, "
        "description TEXT, "
        "author VARCHAR(64), "
        "code TEXT NOT NULL, "
        "dependencies TEXT, "
        "os_compat TEXT, "
        "signature VARCHAR(128) NOT NULL, "
        "enabled INTEGER NOT NULL, "
        "install_count INTEGER NOT NULL, "
        "created_at DATETIME NOT NULL, "
        "updated_at DATETIME NOT NULL)"
    )
    conn.commit()
    return conn


def sqlite_upsert(conn, name, meta, code, signature, enabled=1):
    now = datetime.now(timezone.utc).isoformat()
    deps = json.dumps(meta["dependencies"] or [])
    oscompat = json.dumps(meta["os_compat"] or ["windows", "linux", "darwin"])
    row = conn.execute("SELECT id FROM modules WHERE name=?", (name,)).fetchone()
    if row:
        conn.execute(
            "UPDATE modules SET version=?, description=?, author=?, code=?, "
            "dependencies=?, os_compat=?, signature=?, updated_at=? WHERE name=?",
            (meta["version"], meta["description"], meta["author"], code,
             deps, oscompat, signature, now, name),
        )
        mod_id = row[0]
    else:
        mod_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO modules (id, name, version, description, author, code, "
            "dependencies, os_compat, signature, enabled, install_count, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?)",
            (mod_id, name, meta["version"], meta["description"], meta["author"],
             code, deps, oscompat, signature, enabled, now, now),
        )
    conn.commit()
    return mod_id


def backend_importable():
    if not os.path.isfile(os.path.join(BACKEND_DIR, "main.py")):
        return False
    try:
        import peewee  # noqa: F401
        return True
    except Exception:
        return False


def find_venv_python():
    for base in (os.path.join(BACKEND_DIR, ".venv"), os.path.join(BACKEND_DIR, "venv")):
        for rel in ("Scripts/python.exe", "bin/python"):
            cand = os.path.join(base, rel)
            if os.path.isfile(cand):
                return cand
    return None


def seed_backend(modules, master_key, quiet, dry_run):
    cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, BACKEND_DIR)
    rows = []
    try:
        from core.module_manager import ModuleManager
        mm = ModuleManager()
        for path, meta in modules:
            code = open(path, encoding="utf-8").read()
            if dry_run:
                sig = sign_code(code, master_key)
            else:
                mod = mm.register(
                    name=meta["name"], version=meta["version"], code=code,
                    description=meta["description"], author=meta["author"],
                    dependencies=meta["dependencies"], os_compat=meta["os_compat"],
                )
                sig = mod.signature
            rows.append({"name": meta["name"], "version": meta["version"],
                         "signature": sig})
            if not quiet:
                print("  seed:", meta["name"], meta["version"], "->", sig[:12], "...")
        return rows
    finally:
        os.chdir(cwd)


def seed_sqlite(modules, db_path, master_key, quiet, dry_run):
    conn = sqlite_connect(db_path)
    rows = []
    for path, meta in modules:
        code = open(path, encoding="utf-8").read()
        sig = sign_code(code, master_key)
        if not dry_run:
            sqlite_upsert(conn, meta["name"], meta, code, sig)
        rows.append({"name": meta["name"], "version": meta["version"],
                     "signature": sig})
        if not quiet:
            print("  seed:", meta["name"], meta["version"], "->", sig[:12], "...")
    conn.close()
    return rows


def resolve_db_path(url, env):
    if not url:
        return DEFAULT_DB
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
    elif url.startswith("sqlite:"):
        p = url[len("sqlite:"):]
    else:
        return DEFAULT_DB
    if not os.path.isabs(p):
        p = os.path.join(BACKEND_DIR, p)
    return p


def copy_tree_patterns(src, dst, quiet, dry_run):
    copied = []
    if not os.path.isdir(src):
        return copied
    os.makedirs(dst, exist_ok=True)
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".py") or fn.startswith("_") or fn == "__init__.py":
            continue
        s = os.path.join(src, fn)
        d = os.path.join(dst, fn)
        if not dry_run:
            shutil.copy2(s, d)
        copied.append(fn)
        if not quiet:
            print("  copy:", fn)
    return copied


def verify_registry(backend, db_path, master_key, quiet):
    active = []
    if backend:
        cwd = os.getcwd()
        os.chdir(BACKEND_DIR)
        sys.path.insert(0, BACKEND_DIR)
        try:
            from db.models import Module
            from core.module_manager import ModuleManager
            mm = ModuleManager()
            for mod in Module.select().where(Module.enabled == True):  # noqa: E712
                ok = mm.verify_code_signature(mod.code, mod.signature)
                active.append({"name": mod.name, "version": mod.version,
                               "enabled": True, "signature_ok": ok})
        finally:
            os.chdir(cwd)
    else:
        conn = sqlite3.connect(db_path)
        for row in conn.execute(
                "SELECT name, version, code, signature FROM modules WHERE enabled=1"):
            name, version, code, sig = row
            ok = hmac.compare_digest(sign_code(code, master_key), sig)
            active.append({"name": name, "version": version,
                           "enabled": True, "signature_ok": ok})
        conn.close()
    if not quiet:
        for a in active:
            print("  actif:", a["name"], a["version"],
                  "| signature:", "OK" if a["signature_ok"] else "ECHEC")
    return active


def main(argv=None):
    ap = argparse.ArgumentParser(description="Installation arsenal Lucy")
    ap.add_argument("--dry-run", action="store_true",
                    help="affiche le plan sans rien ecrire")
    ap.add_argument("--db", default=None, help="chemin DB alternatif (scratch)")
    ap.add_argument("--no-seed", action="store_true",
                    help="copie sans seed registry")
    ap.add_argument("--no-copy", action="store_true",
                    help="seed sans copie des fichiers")
    ap.add_argument("--venv", default=None, help="python du venv backend")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if os.environ.get(REEXEC_FLAG) != "1":
        vp = args.venv
        if vp is None and not args.dry_run and not args.no_seed \
                and args.db is None and not backend_importable():
            vp = find_venv_python()
        if vp:
            env = dict(os.environ)
            env[REEXEC_FLAG] = "1"
            os.execvpe(vp, [vp] + sys.argv, env)

    env = parse_env(ENV_FILE)
    master_key = env.get("MASTER_KEY", "")
    if not master_key and not args.no_seed:
        print("ERREUR: MASTER_KEY introuvable dans", ENV_FILE, file=sys.stderr)
        return 2

    db_path = args.db or resolve_db_path(env.get("DATABASE_URL", ""), env)

    modules = []
    if os.path.isdir(MODULES_SRC):
        for fn in sorted(os.listdir(MODULES_SRC)):
            if fn.endswith(".py") and not fn.startswith("_"):
                path = os.path.join(MODULES_SRC, fn)
                modules.append((path, extract_meta(path)))
    build_tools = []
    if os.path.isdir(BUILD_SRC):
        build_tools = sorted(fn for fn in os.listdir(BUILD_SRC)
                             if fn.endswith(".py"))

    print("== installation arsenal Lucy ==")
    print("racine:", ROOT)
    print("modules:", len(modules), "| build tools:", len(build_tools))
    print("DB:", db_path, "(dry-run)" if args.dry_run else "")

    mcopied = []
    bcopied = []
    if not args.no_copy:
        print("copie modules ->", BACKEND_MODULES)
        mcopied = copy_tree_patterns(MODULES_SRC, BACKEND_MODULES,
                                     args.quiet, args.dry_run)
        print("copie build ->", TOOLS_DIR)
        bcopied = copy_tree_patterns(BUILD_SRC, TOOLS_DIR,
                                     args.quiet, args.dry_run)
    else:
        print("copie desactivee (--no-copy)")

    seeded = []
    backend = backend_importable()
    if not args.no_seed:
        print("seed registry (HMAC-SHA256, enabled=1)")
        if backend and not args.db and not args.dry_run:
            print("  backend: ModuleManager reel (peewee)")
            seeded = seed_backend(modules, master_key, args.quiet, args.dry_run)
        else:
            print("  backend: sqlite3 stdlib (schema miroir)")
            seeded = seed_sqlite(modules, db_path, master_key,
                                 args.quiet, args.dry_run)
    else:
        print("seed desactive (--no-seed)")

    active = []
    if not args.dry_run and not args.no_seed:
        print("verification enregistrement")
        active = verify_registry(backend, db_path, master_key, args.quiet)
        ok = all(a["signature_ok"] for a in active) and len(active) == len(modules)
        print("  modules actifs:", len(active), "| signatures:",
              "OK" if ok else "ECHEC")
        if not ok:
            print("ECHEC: verification incomplete", file=sys.stderr)
            return 3

    inst = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "root": ROOT,
        "db": db_path,
        "backend_seed": backend,
        "modules_copied": mcopied,
        "build_tools_copied": bcopied,
        "seeded": seeded,
        "active_modules": active,
        "paths": {"backend_modules": BACKEND_MODULES,
                  "tools_arsenal": TOOLS_DIR},
    }
    out_json = os.path.join(PACK_DIR, "INSTALLED.json")
    if not args.dry_run:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(inst, fh, indent=2, ensure_ascii=False)
        print("INSTALLED.json:", out_json)
    else:
        print("INSTALLED.json (dry-run, non ecrit):", out_json)
    print("== installation terminee ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
