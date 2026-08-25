"""
Module Manager — backend plugin registry.
Handles registration, HMAC signing, version management, and serving code to agents.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from config import settings
from database import database
from db.models import Module

logger = logging.getLogger(__name__)

_HMAC_KEY_ENV = "MODULE_HMAC_KEY"


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
    ) -> Module:
        """Register or update a module. Signs the code automatically."""
        signature = self.sign_code(code)

        with database:
            existing = Module.get_or_none(Module.name == name)
            if existing:
                Module.update(
                    version=version,
                    code=code,
                    description=description,
                    author=author,
                    dependencies=json.dumps(dependencies or []),
                    os_compat=json.dumps(os_compat or ["windows", "linux", "darwin"]),
                    signature=signature,
                    updated_at=datetime.now(timezone.utc),
                ).where(Module.name == name).execute()
                mod = Module.get(Module.name == name)
                logger.info("Module '%s' updated to v%s.", name, version)
            else:
                mod = Module.create(
                    name=name,
                    version=version,
                    code=code,
                    description=description,
                    author=author,
                    dependencies=json.dumps(dependencies or []),
                    os_compat=json.dumps(os_compat or ["windows", "linux", "darwin"]),
                    signature=signature,
                    enabled=True,
                )
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

    # --- Seed built-in modules from /modules/ directory ---

    def seed_from_directory(self, modules_dir: str) -> int:
        """
        Load all .py files from a directory as modules.
        Each file must define: NAME, VERSION, DESCRIPTION, AUTHOR,
        DEPENDENCIES, OS_COMPAT at module level.
        Returns number of modules seeded.
        """
        import os

        seeded = 0
        if not os.path.isdir(modules_dir):
            return 0

        for fname in os.listdir(modules_dir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            fpath = os.path.join(modules_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    code = f.read()

                ns: dict = {}
                exec(compile(code, fpath, "exec"), ns)

                self.register(
                    name=ns.get("NAME", fname[:-3]),
                    version=ns.get("VERSION", "1.0.0"),
                    code=code,
                    description=ns.get("DESCRIPTION", ""),
                    author=ns.get("AUTHOR", "lucy"),
                    dependencies=ns.get("DEPENDENCIES", []),
                    os_compat=ns.get("OS_COMPAT", ["windows", "linux", "darwin"]),
                )
                seeded += 1
            except Exception as exc:
                logger.warning("Failed to seed module '%s': %s", fname, exc)

        logger.info("Seeded %d modules from %s.", seeded, modules_dir)
        return seeded
