#!/usr/bin/env python3
"""
polymorph_engine.py — Polymorph-Engine / Dark-Rust-Agent / LLVM-Obfuscator-Pro
(outils #11, #36, #37 du mapping Fifty).
Mutation deterministe (seed) d'un arbre source Python + passes LLVM pour
sources C/C++ (-mllvm -fla/-sub/-bcf) + build zipapp de la mutation.
Chaque build produit un MANIFEST.json (seed, mutations, commandes).

Usage:
  python polymorph_engine.py --src agent --seed 42 --llvm-fla --build
  python polymorph_engine.py --src payload.c --seed 7 --llvm-fla --llvm-sub --cc clang
  python polymorph_engine.py --src tool.py --seed 1 --build --out out/
"""
import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import zipapp

_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "bytes", "type", "isinstance", "getattr", "setattr", "hasattr", "open",
    "exec", "eval", "compile", "super", "self", "Exception", "ValueError",
    "RuntimeError", "KeyError", "IndexError", "AttributeError", "importlib",
    "os", "sys", "ctypes", "time", "hashlib", "base64", "json", "subprocess",
    "threading", "socket", "re", "random", "string", "math", "struct",
}
_BS = chr(92)
_STR_RE = re.compile(
    "(" + r"'(?:[^'" + _BS * 3 + "n]|" + _BS * 2 + ".)*'"
    + '|"(?:[^"' + _BS * 3 + "n]|" + _BS * 2 + '.)*"|#[^' + _BS + "n]*" + ")"
)
_DEF_RE = re.compile(_BS + "b(def|class)" + _BS + "s+([A-Za-z_]" + _BS + "w*)")
_CALL_RE = re.compile("(?<![." + _BS + "w])([A-Za-z_]" + _BS + "w*)(?=" + _BS + "s*" + _BS + "()")



def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _mutate_identifier(match, rng, mapping):
    kind, name = match.group(1), match.group(2)
    if name in _KEYWORDS or name.startswith("__"):
        return match.group(0)
    if name not in mapping:
        mapping[name] = "_%s%s" % (kind[:1], rng.getrandbits(24))
    return "%s %s" % (kind, mapping[name])


def _escape_strings(src: str, rng) -> str:
    """Echappe les chaines courtes imprimables en sequences hexa (brouillage)."""

    def _rep(m):
        s = m.group(0)
        body = s[1:-1]
        if len(body) < 3 or len(body) > 24 or not body.isprintable():
            return s
        if rng.random() < 0.5:
            return s
        enc = "".join((_BS + "x%02x") % b for b in body.encode("utf-8"))
        return '"%s"' % enc

    return re.sub('"[^"' + _BS + 'n]{1,30}"', _rep, src)


_JUNK = [
    "_h = (lambda *a: sum(a))",
    "_x = 0x0", "_y = 0x0",
    "if False: _dead = None",
    "_t = __import__('time').time()",
    "_z = _z + 0 if '_z' in dir() else 0",
    "_pad = b'" + chr(92) + "x00' * 0",
]


def _inject_junk(src: str, rng, count: int) -> str:
    lines = src.splitlines()
    if not lines:
        return src
    for _ in range(count):
        pos = rng.randrange(0, len(lines))
        indent = ""
        stripped = lines[pos].strip()
        if stripped and not stripped.startswith("#") and not stripped.endswith(":"):
            lead = lines[pos][: len(lines[pos]) - len(lines[pos].lstrip())]
            indent = lead
        lines.insert(pos, indent + rng.choice(_JUNK))
    return "\n".join(lines)


def mutate_python(src: str, seed: int) -> dict:
    rng = _rng(seed)
    mapping: dict[str, str] = {}
    parts = _STR_RE.split(src)

    def _map_code(part):
        return _DEF_RE.sub(lambda m: _mutate_identifier(m, rng, mapping), part)

    for i in range(0, len(parts), 2):
        _map_code(parts[i])

    def _rename_code(part):
        if not part:
            return part
        part = _DEF_RE.sub(lambda m: _mutate_identifier(m, rng, mapping), part)

        def _call(m):
            name = m.group(1)
            return mapping.get(name, m.group(0))

        return _CALL_RE.sub(_call, part)

    out = "".join(_rename_code(p) if i % 2 == 0 else p
                   for i, p in enumerate(parts))
    out = _escape_strings(out, rng)
    out = _inject_junk(out, rng, rng.randint(2, 6))
    return {
        "source": out,
        "renamed": mapping,
        "junk_count": len(mapping),
    }

def mutate_tree(src_dir: str, out_dir: str, seed: int) -> dict:
    """Copie src_dir vers out_dir en mutant chaque .py. Retourne un rapport."""
    report = {"renamed_total": 0, "files": []}
    rng = _rng(seed)
    mapping_global: dict[str, str] = {}
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        dst_root = os.path.join(out_dir, rel) if rel != "." else out_dir
        os.makedirs(dst_root, exist_ok=True)
        for name in files:
            src_p = os.path.join(root, name)
            dst_p = os.path.join(dst_root, name)
            if name.endswith(".py"):
                with open(src_p, "r", encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                r = mutate_python(src, seed + rng.randint(0, 999))
                mapping_global.update(r["renamed"])
                with open(dst_p, "w", encoding="utf-8") as fh:
                    fh.write(r["source"])
                report["files"].append({"path": rel + "/" + name, "renamed": len(r["renamed"])})
            else:
                shutil.copy2(src_p, dst_p)
    report["renamed_total"] = len(mapping_global)
    report["identifiers"] = mapping_global
    return report


# --- Passes LLVM (C/C++) --------------------------------------------------
_LLVM_PASSES = {
    "fla": "-mllvm -fla",
    "sub": "-mllvm -sub",
    "bcf": "-mllvm -bcf",
}


def llvm_obfuscate(src: str, out_bin: str, passes: list[str], cc: str) -> dict:
    """Compile un fichier C/C++ avec les passes -mllvm (OLLVM)."""
    flags = []
    for p in passes:
        if p in _LLVM_PASSES:
            flags.extend(_LLVM_PASSES[p].split())
    if not flags:
        return {"status": "skipped", "reason": "aucune passe LLVM demandee"}
    if shutil.which(cc) is None:
        return {"status": "skipped", "reason": "compilateur introuvable: " + cc}
    cmd = [cc, "-O2", *flags, src, "-o", out_bin]
    print("  cc:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"status": "failed", "cmd": " ".join(cmd),
                "error": (r.stderr or r.stdout)[-400:]}
    return {"status": "ok", "cmd": " ".join(cmd), "out": out_bin}


def build_zipapp_dir(src_dir: str, out_path: str) -> str:
    work = src_dir
    if not os.path.isfile(os.path.join(src_dir, "__main__.py")):
        entry = os.path.join(src_dir, "main.py")
        if not os.path.isfile(entry):
            py_files = [f for f in os.listdir(src_dir) if f.endswith(".py")]
            entry = os.path.join(src_dir, py_files[0]) if py_files else None
        if entry is None:
            raise RuntimeError("aucun point d'entree Python pour le zipapp")
        tmp = tempfile.mkdtemp(prefix="lucy_poly_build_")
        shutil.copytree(src_dir, os.path.join(tmp, "pkg"))
        shutil.copy2(entry, os.path.join(tmp, "__main__.py"))
        work = tmp
    zipapp.create_archive(work, out_path, interpreter="/usr/bin/env python3",
                          compressed=True)
    if work != src_dir:
        shutil.rmtree(work, ignore_errors=True)
    return out_path


# --- CLI -------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Polymorph-Engine Lucy (mutation + LLVM + build)")
    p.add_argument("--src", required=True, help="fichier ou dossier source")
    p.add_argument("--seed", type=int, default=42, help="graine deterministe")
    p.add_argument("--out", default=None, help="dossier de sortie (defaut: build_out/)")
    p.add_argument("--build", action="store_true", help="construire un zipapp de la mutation")
    p.add_argument("--llvm-fla", action="store_true", help="passe OLLVM: controle flow flattening")
    p.add_argument("--llvm-sub", action="store_true", help="passe OLLVM: instruction substitution")
    p.add_argument("--llvm-bcf", action="store_true", help="passe OLLVM: bogus control flow")
    p.add_argument("--cc", default="clang", help="compilateur C/C++ (defaut: clang)")
    args = p.parse_args(argv)

    if not os.path.exists(args.src):
        sys.exit("ERREUR: source introuvable: " + args.src)
    out_dir = args.out or os.path.join("build_out", "seed_%d" % args.seed)
    os.makedirs(out_dir, exist_ok=True)

    report = {"seed": args.seed, "src": args.src, "out": out_dir,
              "passes": [n for n, _ in _LLVM_PASSES.items()
                         if getattr(args, "llvm_" + n, False)],
              "mutations": {}, "llvm": {}, "build": None}

    if os.path.isdir(args.src):
        report["mutations"] = mutate_tree(args.src, out_dir, args.seed)
    else:
        with open(args.src, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        m = mutate_python(src, args.seed)
        dst = os.path.join(out_dir, os.path.basename(args.src))
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(m["source"])
        report["mutations"] = {"file": dst, "renamed": m["renamed"]}

    # C/C++: appliquer les passes LLVM
    c_srcs = []
    if os.path.isfile(args.src) and args.src.endswith((".c", ".cpp", ".cc")):
        c_srcs = [args.src]
    elif os.path.isdir(args.src):
        for root, _d, files in os.walk(args.src):
            c_srcs += [os.path.join(root, f) for f in files
                       if f.endswith((".c", ".cpp", ".cc"))]
    if c_srcs:
        for i, c in enumerate(c_srcs):
            report["llvm"][c] = llvm_obfuscate(
                c, os.path.join(out_dir, "bin_%d" % i),
                report["passes"], args.cc)

    if args.build and os.path.isdir(out_dir) and any(
            f.endswith(".py") for _, _, fs in os.walk(out_dir) for f in fs):
        out_pyz = os.path.join(out_dir, "mutated_" + str(args.seed) + ".pyz")
        report["build"] = build_zipapp_dir(out_dir, out_pyz)

    mpath = os.path.join(out_dir, "MANIFEST.json")
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("polymorph_engine:", json.dumps(report, default=str)[:1200])
    return report


if __name__ == "__main__":
    main()
