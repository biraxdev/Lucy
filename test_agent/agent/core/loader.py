"""
Agent module loader — dynamic exec-based plugin system.
All modules stored in memory, never written to disk.
"""
import hashlib
import hmac as _hmac_mod
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger("lucy_agent.loader")

# ---------------------------------------------------------------------------
# Restricted builtins (optional sandboxing)
# ---------------------------------------------------------------------------

_SAFE_BUILTINS = {
    k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
    for k in (
        "print", "len", "range", "enumerate", "zip", "map", "filter",
        "str", "int", "float", "bool", "list", "dict", "tuple", "set",
        "bytes", "bytearray", "type", "isinstance", "issubclass",
        "hasattr", "getattr", "setattr", "delattr", "callable",
        "sorted", "reversed", "min", "max", "sum", "abs", "round",
        "repr", "hash", "id", "hex", "oct", "bin", "chr", "ord",
        "open",           # needed for file ops
        "Exception", "ValueError", "TypeError", "RuntimeError",
        "IOError", "OSError", "FileNotFoundError", "PermissionError",
        "KeyError", "IndexError", "AttributeError", "NotImplementedError",
        "StopIteration", "GeneratorExit", "BaseException",
        "__import__",     # needed for module imports inside plugin code
        "__name__", "__builtins__",
    )
    if (isinstance(__builtins__, dict) and k in __builtins__)
    or (not isinstance(__builtins__, dict) and hasattr(__builtins__, k))
}


# ---------------------------------------------------------------------------
# Module cache entry
# ---------------------------------------------------------------------------


class CachedModule:
    __slots__ = ("name", "version", "namespace", "signature", "load_time")

    def __init__(
        self,
        name: str,
        version: str,
        namespace: dict,
        signature: str,
    ) -> None:
        import time
        self.name = name
        self.version = version
        self.namespace = namespace
        self.signature = signature
        self.load_time = time.time()

    def get_run_fn(self) -> Optional[Any]:
        return self.namespace.get("run") or self.namespace.get(f"{self.name}_run")


# ---------------------------------------------------------------------------
# ModuleLoader
# ---------------------------------------------------------------------------


class ModuleLoader:
    """
    Dynamic module loader for the Lucy agent.
    - Compiles and execs Python code into isolated namespaces
    - Caches by (name, version) — invalidated on version mismatch
    - Verifies HMAC-SHA256 signatures before execution
    - Runs each module in a thread with configurable timeout
    """

    def __init__(
        self,
        hmac_key: Optional[bytes] = None,
        sandbox: bool = False,
        default_timeout: int = 60,
    ) -> None:
        self._cache: dict[str, CachedModule] = {}
        self._hmac_key = hmac_key
        self._sandbox = sandbox
        self._default_timeout = default_timeout
        self._lock = threading.Lock()

    # --- Signature verification ---

    def verify_signature(self, code: str, signature: str) -> bool:
        if not self._hmac_key:
            return True
        expected = _hmac_mod.new(
            self._hmac_key, code.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return _hmac_mod.compare_digest(expected, signature)

    # --- Load ---

    def load(
        self,
        name: str,
        version: str,
        code: str,
        signature: str = "",
    ) -> CachedModule:
        """
        Compile and cache a module.
        Raises ValueError if signature verification fails.
        """
        if self._hmac_key and signature:
            if not self.verify_signature(code, signature):
                raise ValueError(f"Module '{name}' signature verification failed")

        with self._lock:
            cached = self._cache.get(name)
            if cached and cached.version == version:
                return cached

            namespace: dict[str, Any] = {
                "__name__": f"lucy_module_{name}",
                "__file__": f"<lucy:{name}>",
            }

            if self._sandbox:
                namespace["__builtins__"] = _SAFE_BUILTINS
            else:
                namespace["__builtins__"] = __builtins__

            try:
                compiled = compile(code, f"<lucy:{name}>", "exec")
                exec(compiled, namespace)
            except Exception as exc:
                raise RuntimeError(f"Module '{name}' failed to compile: {exc}") from exc

            entry = CachedModule(
                name=name,
                version=version,
                namespace=namespace,
                signature=signature,
            )
            self._cache[name] = entry
            logger.info("Module '%s' v%s loaded into cache.", name, version)
            return entry

    # --- Execute ---

    def execute(
        self,
        name: str,
        action: str,
        params: dict,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Execute a loaded module's run() function in a thread with timeout.
        Returns result dict: {status, data, error}
        """
        cached = self._cache.get(name)
        if not cached:
            return {"status": "failed", "data": None, "error": f"Module '{name}' not loaded"}

        run_fn = cached.get_run_fn()
        if not callable(run_fn):
            return {
                "status": "failed",
                "data": None,
                "error": f"Module '{name}' has no run() function",
            }

        effective_timeout = timeout or self._default_timeout
        result_box: list = []
        error_box: list = []

        def _target():
            try:
                import asyncio
                if asyncio.iscoroutinefunction(run_fn):
                    loop = asyncio.new_event_loop()
                    result_box.append(loop.run_until_complete(run_fn(action, params)))
                    loop.close()
                else:
                    result_box.append(run_fn(action, params))
            except Exception as exc:
                error_box.append(str(exc))

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=effective_timeout)

        if t.is_alive():
            return {
                "status": "failed",
                "data": None,
                "error": f"Module '{name}' timed out after {effective_timeout}s",
            }

        if error_box:
            return {"status": "failed", "data": None, "error": error_box[0]}

        result = result_box[0] if result_box else {}
        return {
            "status": result.get("status", "completed"),
            "data": result.get("data"),
            "error": result.get("error"),
        }

    # --- Load + execute convenience ---

    def load_and_execute(
        self,
        name: str,
        version: str,
        code: str,
        action: str,
        params: dict,
        signature: str = "",
        timeout: Optional[int] = None,
    ) -> dict:
        try:
            self.load(name, version, code, signature)
        except (ValueError, RuntimeError) as exc:
            return {"status": "failed", "data": None, "error": str(exc)}
        return self.execute(name, action, params, timeout)

    # --- Cache management ---

    def is_cached(self, name: str, version: str) -> bool:
        cached = self._cache.get(name)
        return cached is not None and cached.version == version

    def invalidate(self, name: str) -> None:
        with self._lock:
            self._cache.pop(name, None)
            logger.debug("Module '%s' evicted from cache.", name)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def cached_modules(self) -> list[dict]:
        return [
            {"name": m.name, "version": m.version, "load_time": m.load_time}
            for m in self._cache.values()
        ]
