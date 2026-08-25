NAME = "file_manager"
VERSION = "1.1.0"
DESCRIPTION = "Full file management — explore, read, write, upload, download, delete, hash, search."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


import base64
import hashlib
import os
import platform
import stat
import time


class ModuleError(Exception):
    pass


def run(action: str, params: dict) -> dict:
    dispatch = {
        "list": _list,
        "read": _read,
        "write": _write,
        "delete": _delete,
        "stat": _stat,
        "tree": _tree,
        "search": _search,
        "hash": _hash_file,
        "copy": _copy,
        "move": _move,
        "mkdir": _mkdir,
        "drives": _drives,
    }
    handler = dispatch.get(action)
    if not handler:
        return {"status": "failed", "data": None, "error": f"Unknown action: {action}"}
    try:
        return handler(params)
    except PermissionError as exc:
        return {"status": "failed", "data": None, "error": f"Permission denied: {exc}"}
    except Exception as exc:
        return {"status": "failed", "data": None, "error": str(exc)}


def _list(params: dict) -> dict:
    path = params.get("path", ".")
    show_hidden = params.get("hidden", True)
    entries = []
    try:
        for name in os.listdir(path):
            if not show_hidden and name.startswith("."):
                continue
            full = os.path.join(path, name)
            try:
                s = os.stat(full)
                entries.append({
                    "name": name,
                    "path": full,
                    "is_dir": os.path.isdir(full),
                    "size": s.st_size,
                    "modified": s.st_mtime,
                    "permissions": oct(stat.S_IMODE(s.st_mode)),
                })
            except OSError:
                entries.append({"name": name, "path": full, "error": "stat failed"})
    except PermissionError as exc:
        return {"status": "failed", "data": None, "error": str(exc)}

    entries.sort(key=lambda x: (not x.get("is_dir", False), x.get("name", "")))
    return {"status": "completed", "data": {"path": path, "entries": entries, "count": len(entries)}}


def _read(params: dict) -> dict:
    path = params.get("path", "")
    offset = int(params.get("offset", 0))
    length = params.get("length")

    with open(path, "rb") as f:
        if offset:
            f.seek(offset)
        content = f.read(int(length)) if length else f.read()

    sha256 = hashlib.sha256(content).hexdigest()
    return {"status": "completed", "data": {
        "path": path,
        "content_b64": base64.b64encode(content).decode(),
        "size": len(content),
        "sha256": sha256,
        "offset": offset,
    }}


def _write(params: dict) -> dict:
    path = params.get("path", "")
    content_b64 = params.get("content_b64", "")
    append = params.get("append", False)

    content = base64.b64decode(content_b64)
    mode = "ab" if append else "wb"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, mode) as f:
        f.write(content)

    return {"status": "completed", "data": {
        "path": path,
        "size": len(content),
        "written": True,
        "appended": append,
    }}


def _delete(params: dict) -> dict:
    path = params.get("path", "")
    recursive = params.get("recursive", False)

    if os.path.isdir(path):
        if recursive:
            import shutil
            shutil.rmtree(path)
        else:
            os.rmdir(path)
    else:
        os.remove(path)

    return {"status": "completed", "data": {"path": path, "deleted": True}}


def _stat(params: dict) -> dict:
    path = params.get("path", "")
    s = os.stat(path)
    return {"status": "completed", "data": {
        "path": path,
        "size": s.st_size,
        "modified": s.st_mtime,
        "accessed": s.st_atime,
        "created": s.st_ctime,
        "is_dir": os.path.isdir(path),
        "is_file": os.path.isfile(path),
        "permissions": oct(stat.S_IMODE(s.st_mode)),
        "owner_uid": s.st_uid if hasattr(s, "st_uid") else None,
    }}


def _tree(params: dict) -> dict:
    root = params.get("path", ".")
    max_depth = int(params.get("depth", 3))
    max_files = int(params.get("max_files", 500))
    tree = []

    def _walk(base: str, depth: int) -> None:
        if depth > max_depth or len(tree) >= max_files:
            return
        try:
            for name in os.listdir(base):
                if len(tree) >= max_files:
                    break
                full = os.path.join(base, name)
                is_dir = os.path.isdir(full)
                tree.append({"path": full, "name": name, "is_dir": is_dir, "depth": depth})
                if is_dir:
                    _walk(full, depth + 1)
        except (PermissionError, OSError):
            pass

    _walk(root, 0)
    return {"status": "completed", "data": {"root": root, "tree": tree, "count": len(tree)}}


def _search(params: dict) -> dict:
    root = params.get("path", ".")
    pattern = params.get("pattern", "").lower()
    content_search = params.get("content", "").lower()
    max_results = int(params.get("max_results", 200))
    matches = []

    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if len(matches) >= max_results:
                break
            full = os.path.join(dirpath, fname)
            if pattern and pattern not in fname.lower():
                continue
            if content_search:
                try:
                    with open(full, "rb") as f:
                        if content_search.encode() not in f.read(1_000_000):
                            continue
                except Exception:
                    continue
            try:
                s = os.stat(full)
                matches.append({"path": full, "name": fname, "size": s.st_size})
            except OSError:
                matches.append({"path": full, "name": fname})

    return {"status": "completed", "data": {"matches": matches, "count": len(matches)}}


def _hash_file(params: dict) -> dict:
    path = params.get("path", "")
    algos = params.get("algos", ["sha256", "md5"])
    results: dict = {"path": path}
    with open(path, "rb") as f:
        data = f.read()
    for algo in algos:
        try:
            results[algo] = hashlib.new(algo, data).hexdigest()
        except ValueError:
            results[algo] = f"unsupported: {algo}"
    return {"status": "completed", "data": results}


def _copy(params: dict) -> dict:
    import shutil
    src = params.get("src", "")
    dst = params.get("dst", "")
    shutil.copy2(src, dst)
    return {"status": "completed", "data": {"src": src, "dst": dst, "copied": True}}


def _move(params: dict) -> dict:
    import shutil
    src = params.get("src", "")
    dst = params.get("dst", "")
    shutil.move(src, dst)
    return {"status": "completed", "data": {"src": src, "dst": dst, "moved": True}}


def _mkdir(params: dict) -> dict:
    path = params.get("path", "")
    os.makedirs(path, exist_ok=True)
    return {"status": "completed", "data": {"path": path, "created": True}}


def _drives(params: dict) -> dict:
    drives = []
    if platform.system() == "Windows":
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                letter = f"{chr(65 + i)}:\\"
                try:
                    total, free = ctypes.c_ulonglong(0), ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(letter, None, ctypes.byref(total), ctypes.byref(free))
                    drives.append({"drive": letter, "total": total.value, "free": free.value})
                except Exception:
                    drives.append({"drive": letter})
    else:
        import shutil
        for mount in ["/", "/home", "/tmp", "/var"]:
            if os.path.exists(mount):
                try:
                    usage = shutil.disk_usage(mount)
                    drives.append({"mount": mount, "total": usage.total, "free": usage.free})
                except Exception:
                    pass
    return {"status": "completed", "data": {"drives": drives}}
