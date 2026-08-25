#!/usr/bin/env python3
"""
binary_packer.py — Binary-Packer-Custom (outil #48 du mapping Fifty).
Emballage d'un agent/script Python en artefact deployable :
  - zipapp autonome (stdlib, toujours disponible)
  - PyInstaller onefile (si installe)
  - compression UPX (si binaire upx present)
Genere un manifest JSON avec empreintes SHA-256.

Usage:
  python binary_packer.py --src agent/main.py --name lucy_agent --upx
  python binary_packer.py --src agent/ --name lucy_agent --pyinstaller --noconsole
  python binary_packer.py --src tool.py --name tool --out dist/ --no-zipapp
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipapp

ICON = "lucy.ico"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_wrapper(src_file: str, name: str) -> str:
    """Cree un dossier contenant __main__.py qui importe/execute src_file."""
    tmp = tempfile.mkdtemp(prefix="lucy_pack_")
    dst_main = os.path.join(tmp, "__main__.py")
    with open(src_file, "r", encoding="utf-8") as fh:
        code = fh.read()
    with open(dst_main, "w", encoding="utf-8") as fh:
        fh.write("import runpy\n")
        fh.write("_f = %r\n" % os.path.basename(src_file))
        fh.write("runpy.run_path(_f, run_name='__main__')\n")
    shutil.copy2(src_file, os.path.join(tmp, os.path.basename(src_file)))
    return tmp


def build_zipapp(src: str, name: str, out_dir: str) -> str:
    """Retourne le chemin du .pyz genere (ou None)."""
    if os.path.isfile(src):
        work = _make_wrapper(src, name)
    else:
        work = src
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name + ".pyz")
    zipapp.create_archive(work, out, interpreter="/usr/bin/env python3", compressed=True)
    return out


def build_pyinstaller(src: str, name: str, out_dir: str, console: bool) -> str | None:
    if shutil.which("pyinstaller") is None:
        print("  [skip] pyinstaller non installe")
        return None
    os.makedirs(out_dir, exist_ok=True)
    cmd = ["pyinstaller", "--onefile", "--distpath", out_dir, "--workpath",
           os.path.join(out_dir, ".build"), "--specpath", os.path.join(out_dir, ".build"),
           "--name", name]
    if not console:
        cmd.append("--noconsole")
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), ICON)
    if os.path.isfile(icon):
        cmd += ["--icon", icon]
    cmd.append(src)
    print("  pyinstaller:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  [warn] pyinstaller: " + (r.stderr or r.stdout)[-400:])
        return None
    exe = name + (".exe" if os.name == "nt" else "")
    path = os.path.join(out_dir, exe)
    return path if os.path.isfile(path) else None


def upx_compress(paths: list[str]) -> list[str]:
    upx = shutil.which("upx")
    if upx is None:
        print("  [skip] upx non trouve sur PATH")
        return paths
    out = []
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        r = subprocess.run([upx, "-9", "-q", p], capture_output=True, text=True)
        if r.returncode == 0:
            out.append(p)
        else:
            print("  [warn] upx: " + (r.stderr or r.stdout)[-200:])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Binary-Packer Lucy (zipapp / PyInstaller / UPX)")
    p.add_argument("--src", required=True, help="fichier ou dossier source")
    p.add_argument("--name", required=True, help="nom de l'artefact")
    p.add_argument("--out", default="dist", help="dossier de sortie (defaut: dist)")
    p.add_argument("--zipapp", dest="zipapp", action="store_true", default=True,
                   help="generer un zipapp (defaut)")
    p.add_argument("--no-zipapp", dest="zipapp", action="store_false")
    p.add_argument("--pyinstaller", action="store_true", help="tenter PyInstaller onefile")
    p.add_argument("--noconsole", action="store_true", help="PyInstaller sans console")
    p.add_argument("--upx", action="store_true", help="compresser avec UPX si dispo")
    args = p.parse_args(argv)

    if not os.path.exists(args.src):
        sys.exit("ERREUR: source introuvable: " + args.src)
    os.makedirs(args.out, exist_ok=True)

    artifacts = []
    if args.zipapp:
        path = build_zipapp(args.src, args.name, args.out)
        if path:
            artifacts.append(path)
    if args.pyinstaller:
        path = build_pyinstaller(args.src, args.name, args.out, args.noconsole)
        if path:
            artifacts.append(path)

    if args.upx:
        artifacts = upx_compress(artifacts)

    manifest = {
        "name": args.name,
        "src": args.src,
        "artifacts": [
            {"path": a, "size": os.path.getsize(a), "sha256": sha256_file(a)}
            for a in artifacts
        ],
    }
    mpath = os.path.join(args.out, args.name + "_manifest.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print("binary_packer:", json.dumps(manifest))
    return manifest


if __name__ == "__main__":
    main()
