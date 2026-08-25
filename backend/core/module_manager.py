"""
Module Manager — backend plugin registry.
Handles registration, HMAC signing, version management, and serving code to agents.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from config import settings
from database import database
from db.models import Module

logger = logging.getLogger(__name__)

_HMAC_KEY_ENV = "MODULE_HMAC_KEY"

# Restricted builtins for safe execution of module source during seeding.
# We never execute raw user-provided strings; this namespace is only used
# for fallback parsing of local, known module files in modules_dir.
_SAFE_MODULE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "dir": dir,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hasattr": hasattr,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "object": object,
    "pow": pow,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "__build_class__": __build_class__,
    # Needed by `import` statements in compiled module source.
    "__import__": __import__,
    # Self-reference so modules can access builtin namespace if needed.
    "__builtins__": __builtins__,
    # Common exceptions used by module code.
    "Exception": Exception,
    "BaseException": BaseException,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "RuntimeError": RuntimeError,
    "OSError": OSError,
    "AttributeError": AttributeError,
    "ImportError": ImportError,
    "ModuleNotFoundError": ModuleNotFoundError,
}


def _get_hmac_key() -> bytes:
    """Derive a stable HMAC key from the master key."""
    import hmac as _hmac
    return hashlib.sha256(settings.MASTER_KEY.encode() + b":module-signing").digest()


# ---------------------------------------------------------------------------
# BaseModule interface (server-side reference)
# ---------------------------------------------------------------------------


class ModuleError(Exception):
    pass


class BaseModule:
    name: str = ""
    version: str = "1.0.0"
    dependencies: list[str] = []
    os_compat: list[str] = ["windows", "linux", "darwin"]

    async def run(self, params: dict) -> dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Module Manager
# ---------------------------------------------------------------------------


class ModuleManager:
    """Singleton registry for all Lucy modules."""

    _instance: Optional["ModuleManager"] = None

    def __new__(cls) -> "ModuleManager":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._cache: dict[str, dict] = {}
            cls._instance = inst
        return cls._instance

    # --- HMAC signing ---

    def sign_code(self, code: str) -> str:
        import hmac as _hmac
        key = _get_hmac_key()
        return _hmac.new(key, code.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_code_signature(self, code: str, signature: str) -> bool:
        import hmac as _hmac
        expected = self.sign_code(code)
        return _hmac.compare_digest(expected, signature)

    # --- Registration ---

    def register(
        self,
        name: str,
        version: str,
        code: str,
        description: str = "",
        author: str = "",
        dependencies: list[str] | None = None,
        os_compat: list[str] | None = None,
        actions: list[str] | None = None,
        params_schema: dict | None = None,
        category: str | None = None,
        mitre_techniques: list[str] | None = None,
        tags: list[str] | None = None,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        expected_duration: int | None = None,
    ) -> Module:
        """Register or update a module. Signs the code automatically."""
        signature = self.sign_code(code)

        def _j(value: Any | None) -> str:
            return json.dumps(value) if value is not None else None

        with database:
            existing = Module.get_or_none(Module.name == name)
            update_kwargs = {
                "version": version,
                "code": code,
                "description": description,
                "author": author,
                "dependencies": _j(dependencies or []),
                "os_compat": _j(os_compat or ["windows", "linux", "darwin"]),
                "actions": _j(actions or []),
                "params_schema": _j(params_schema or {}),
                "category": category,
                "mitre_techniques": _j(mitre_techniques or []),
                "tags": _j(tags or []),
                "inputs": _j(inputs or []),
                "outputs": _j(outputs or []),
                "expected_duration": expected_duration,
                "signature": signature,
                "updated_at": datetime.now(timezone.utc),
            }
            create_kwargs = {**update_kwargs, "enabled": True}
            if existing:
                Module.update(**update_kwargs).where(Module.name == name).execute()
                mod = Module.get(Module.name == name)
                logger.info("Module '%s' updated to v%s.", name, version)
            else:
                mod = Module.create(name=name, **create_kwargs)
                logger.info("Module '%s' v%s registered.", name, version)

        self._cache.pop(name, None)
        return mod

    # --- Retrieval ---

    def get(self, name: str) -> Optional[Module]:
        if name in self._cache:
            return self._cache[name]
        mod = Module.get_or_none((Module.name == name) & (Module.enabled == True))
        if mod:
            self._cache[name] = mod
        return mod

    def get_by_id(self, module_id: str) -> Optional[Module]:
        return Module.get_or_none(Module.id == module_id)

    def list_all(
        self,
        enabled_only: bool = True,
        os_filter: str | None = None,
    ) -> list[Module]:
        q = Module.select()
        if enabled_only:
            q = q.where(Module.enabled == True)
        modules = list(q.order_by(Module.name))
        if os_filter:
            modules = [
                m for m in modules
                if os_filter.lower() in (json.loads(m.os_compat or "[]"))
            ]
        return modules

    # --- Download (for agent) ---

    def get_for_agent(self, name: str) -> Optional[dict]:
        """Return signed module payload for agent download."""
        mod = self.get(name)
        if not mod:
            return None
        return {
            "name": mod.name,
            "version": mod.version,
            "code": mod.code,
            "signature": mod.signature,
            "dependencies": mod.dependencies_list,
            "os_compat": mod.os_compat_list,
        }

    # --- Delete ---

    def delete(self, name: str) -> bool:
        self._cache.pop(name, None)
        deleted = Module.delete().where(Module.name == name).execute()
        return bool(deleted)

    # --- Enable / disable ---

    def set_enabled(self, name: str, enabled: bool) -> None:
        self._cache.pop(name, None)
        Module.update(enabled=enabled).where(Module.name == name).execute()

    # --- Stats ---

    def increment_install_count(self, name: str) -> None:
        Module.update(install_count=Module.install_count + 1).where(
            Module.name == name
        ).execute()

    # --- Descriptor helpers ---

    def _load_manifest(self, manifest_path: str) -> dict:
        """Load a module manifest from JSON (or YAML if PyYAML is installed)."""
        import os
        with open(manifest_path, "r", encoding="utf-8") as f:
            if manifest_path.lower().endswith((".yaml", ".yml")):
                try:
                    import yaml
                    return yaml.safe_load(f) or {}
                except ImportError:
                    logger.warning("PyYAML not installed; cannot load YAML manifest %s", manifest_path)
                    return {}
            return json.load(f) or {}

    # --- Seed built-in modules from /modules/ directory ---

    def _extract_constants_ast(self, code: str) -> dict:
        """Extract top-level string/list constants from module source without executing it."""
        import ast

        constants: dict = {}
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return constants

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, (ast.Constant, ast.List, ast.Tuple)):
                        constants[target.id] = ast.literal_eval(node.value)
        return constants

    def seed_from_directory(self, modules_dir: str) -> int:
        """
        Load all .py files from a directory as modules.
        Optional manifest (.json) beside the .py file supplies descriptor metadata.
        A central `descriptors.json` in the directory can also map module names to
        descriptor metadata (actions, category, schemas, tags, ...).
        Each file should define: NAME, VERSION, DESCRIPTION, AUTHOR,
        DEPENDENCIES, OS_COMPAT at module level (fallback if manifest absent).
        Returns number of modules seeded.
        """
        import os

        seeded = 0
        if not os.path.isdir(modules_dir):
            return 0

        central_descriptors: dict = {}
        central_path = os.path.join(modules_dir, "descriptors.json")
        if os.path.isfile(central_path):
            try:
                central_descriptors = self._load_manifest(central_path)
            except Exception as exc:
                logger.warning("Failed to load central descriptors %s: %s", central_path, exc)

        for fname in os.listdir(modules_dir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            fpath = os.path.join(modules_dir, fname)
            manifest_path = os.path.splitext(fpath)[0] + ".json"
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    code = f.read()

                # Try AST extraction first (safe for modules with unevaluated type hints).
                ns = self._extract_constants_ast(code)

                # If AST didn't find the metadata, fall back to exec with a forgiving namespace.
                if not ns.get("NAME") and not ns.get("name"):
                    exec_ns: dict = {
                        "__name__": fname[:-3],
                        "__file__": fpath,
                        "__builtins__": _SAFE_MODULE_BUILTINS,
                    }
                    try:
                        import typing
                        exec_ns["Any"] = typing.Any
                        exec_ns["Optional"] = typing.Optional
                        exec_ns["Dict"] = typing.Dict
                        exec_ns["List"] = typing.List
                        exec_ns["Union"] = typing.Union
                    except Exception:
                        pass
                    # Use PEP 563 so type annotations are not evaluated at definition time.
                    future_code = "from __future__ import annotations\n" + code
                    try:
                        exec(compile(future_code, fpath, "exec"), exec_ns)
                    except Exception:
                        # Last-ditch: try compiling the original code as-is.
                        exec(compile(code, fpath, "exec"), exec_ns)
                    ns = exec_ns

                manifest = {}
                if os.path.isfile(manifest_path):
                    try:
                        manifest = self._load_manifest(manifest_path)
                    except Exception as exc:
                        logger.warning("Failed to load manifest '%s': %s", manifest_path, exc)

                # Merge central descriptor for this module (lowest priority after module constants)
                central = central_descriptors.get(fname[:-3], {}) or {}

                def _get(key: str, default: Any) -> Any:
                    return manifest.get(key) or ns.get(key) or ns.get(key.lower()) or central.get(key) or default

                self.register(
                    name=_get("NAME", fname[:-3]),
                    version=_get("VERSION", "1.0.0"),
                    code=code,
                    description=_get("DESCRIPTION", ""),
                    author=_get("AUTHOR", "lucy"),
                    dependencies=_get("DEPENDENCIES", []),
                    os_compat=_get("OS_COMPAT", ["windows", "linux", "darwin"]),
                    actions=_get("actions", []),
                    params_schema=_get("params_schema", {}),
                    category=_get("category", ""),
                    mitre_techniques=_get("mitre_techniques", []),
                    tags=_get("tags", []),
                    inputs=_get("inputs", []),
                    outputs=_get("outputs", []),
                    expected_duration=_get("expected_duration", None),
                )
                seeded += 1
            except Exception as exc:
                logger.warning("Failed to seed module '%s': %s", fname, exc)

        logger.info("Seeded %d modules from %s.", seeded, modules_dir)
        return seeded
