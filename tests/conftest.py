"""Shared test helpers and stubs."""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


# ── Stub helpers ────────────────────────────────────────────────────────────


def _make_module(name: str, path: str | None = None) -> types.ModuleType:
    m = types.ModuleType(name)
    if path is not None:
        m.__path__ = [path]
    return m


def install_loguru_stub() -> None:
    if "loguru" in sys.modules:
        return
    try:
        import loguru  # noqa: F401
        return
    except ImportError:
        pass
    loguru_stub = types.ModuleType("loguru")
    class _Logger:
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def error(self, *a, **k): pass
        def debug(self, *a, **k): pass
        def bind(self, name=""): return _Logger()
        def remove(self, *a, **k): pass
        def add(self, *a, **k): pass
    loguru_stub.logger = _Logger()
    sys.modules["loguru"] = loguru_stub


def install_httpx_stub() -> None:
    if "httpx" in sys.modules:
        return
    try:
        import httpx  # noqa: F401
        return
    except ImportError:
        pass
    httpx_stub = types.ModuleType("httpx")
    class _AsyncClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): return None
        async def aclose(self): pass
    httpx_stub.AsyncClient = _AsyncClient
    sys.modules["httpx"] = httpx_stub


def install_kawkab_stubs() -> None:
    """Install stubs for kawkab.* packages that services depend on.
    Every stub gets __path__ so sub-package resolution works.
    """
    install_loguru_stub()
    install_httpx_stub()

    _stubs: dict[str, str | None] = {
        "kawkab": str(SRC_DIR / "kawkab"),
        "kawkab.core": str(SRC_DIR / "kawkab" / "core"),
        "kawkab.services": str(SRC_DIR / "kawkab" / "services"),
        "kawkab.core.paths": None,
        "kawkab.core.migration_manager": None,
    }
    for _pkg, _path in _stubs.items():
        if _pkg not in sys.modules:
            sys.modules[_pkg] = _make_module(_pkg, _path)

    # Wire up parent→child attributes so importlib._set_parent_attr works
    _kawkab = sys.modules["kawkab"]
    _kawkab.core = sys.modules["kawkab.core"]
    _kawkab.services = sys.modules["kawkab.services"]
    _kawkab.core.paths = sys.modules.get("kawkab.core.paths")
    _kawkab.core.migration_manager = sys.modules.get("kawkab.core.migration_manager")

    if "kawkab.core.logging" not in sys.modules:
        log_mod = _make_module("kawkab.core.logging")
        class _ServiceLogger:
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass
            def debug(self, *a, **k): pass
            def bind(self, name=""): return _ServiceLogger()
        def _get_logger(name=""): return _ServiceLogger()
        log_mod.get_logger = _get_logger
        log_mod.setup_logging = lambda debug=False: None
        sys.modules["kawkab.core.logging"] = log_mod

    # Always overwrite paths and migration_manager stubs to ensure
    # attributes like get_paths survive _ensure_package_loaded restores.
    paths_mod = _make_module("kawkab.core.paths")
    class _Paths:
        def __init__(self):
            tmp = Path(tempfile.gettempdir()) / "kawkab_test"
            self.appdata = tmp
            self.localappdata = tmp
            self.documents = tmp
            self.videos = tmp / "videos"
            self.exports = tmp / "exports"
            self.cache = tmp / "cache"
            self.logs = tmp / "logs"
            self.models = tmp / "models"
            self.migrations = tmp / "migrations"
            self.database = tmp / "kawkab.db"
            self.config_file = tmp / "config.json"
    paths_mod.Paths = _Paths
    # Return a singleton so callers don't fight over state per-test;
    # note: knowledge_base is NOT in __init__ — the knowledge_service
    # test fixture sets it dynamically.
    paths_mod._default_paths = _Paths()
    paths_mod.get_paths = lambda: paths_mod._default_paths
    sys.modules["kawkab.core.paths"] = paths_mod

    mm_mod = _make_module("kawkab.core.migration_manager")
    class _MigrationManager:
        def __init__(self, db_path, migrations_dir): pass
        def migrate(self): pass
    mm_mod.MigrationManager = _MigrationManager
    sys.modules["kawkab.core.migration_manager"] = mm_mod

    # Pre-load storage sub-modules into sys.modules
    _stg_dir = SRC_DIR / "kawkab" / "services" / "storage"
    if _stg_dir.exists() and "kawkab.services.storage" not in sys.modules:
        stg_pkg = _make_module(
            "kawkab.services.storage",
            str(SRC_DIR / "kawkab" / "services" / "storage"),
        )
        sys.modules["kawkab.services.storage"] = stg_pkg
        for _sf in sorted(_stg_dir.glob("*.py")):
            if _sf.name == "__init__.py":
                continue
            _smn = f"kawkab.services.storage.{_sf.stem}"
            if _smn not in sys.modules:
                _spec = importlib.util.spec_from_file_location(_smn, str(_sf))
                if _spec and _spec.loader:
                    _mod = importlib.util.module_from_spec(_spec)
                    sys.modules[_smn] = _mod
                    _spec.loader.exec_module(_mod)


# ── Package loading helpers ─────────────────────────────────────────────────


def _ensure_package_loaded(
    package_name: str,
    skip_import: frozenset[str] = frozenset(),
) -> None:
    """Replace stub with real package import if possible; restore stub on failure.
    
    skip_import: set of fully-qualified module names that should NOT be
                 re-imported (remain as stubs). Useful for packages whose
                 __init__.py imports trigger missing-dependency cascades.
    """
    parts = package_name.split(".")
    for i in range(1, len(parts) + 1):
        prefix = ".".join(parts[:i])
        if prefix in skip_import:
            # Ensure stub exists with __path__
            if prefix not in sys.modules:
                sys.modules[prefix] = _make_module(
                    prefix,
                    str(SRC_DIR / prefix.replace(".", "/")),
                )
            continue
        mod = sys.modules.get(prefix)
        if mod is not None:
            if not hasattr(mod, "__file__") or mod.__file__ is None:
                del sys.modules[prefix]
                try:
                    importlib.import_module(prefix)
                except ImportError:
                    if prefix not in sys.modules:
                        sys.modules[prefix] = _make_module(
                            prefix,
                            str(SRC_DIR / prefix.replace(".", "/")),
                        )
        else:
            try:
                importlib.import_module(prefix)
            except ImportError:
                if prefix not in sys.modules:
                    sys.modules[prefix] = _make_module(
                        prefix,
                        str(SRC_DIR / prefix.replace(".", "/")),
                    )


# ── Service module loader ───────────────────────────────────────────────────


def load_service_module(
    module_name: str,
    file_basename: str,
    subdir: str = "services",
) -> types.ModuleType:
    """Load a service module directly, bypassing __init__.py."""
    _ensure_package_loaded("kawkab")
    _ensure_package_loaded("kawkab.core")
    # kawakab.core.paths has read-only @property knowledge_base that breaks
    # when tests try to set it. Keep the conftest stub (__path__ + get_paths)
    # so tests can freely set attributes.
    _ensure_package_loaded("kawkab.core.paths", skip_import=frozenset({"kawkab.core.paths"}))
    # kawakab.services __init__.py imports norfair_tracker → needs norfair.
    # Keep the stub (with __path__) to avoid cascade failures.
    _ensure_package_loaded("kawkab.services", skip_import=frozenset({"kawkab.services"}))
    _ensure_package_loaded("kawkab.services.storage", skip_import=frozenset({"kawkab.services"}))

    if subdir == "services":
        file_path = SRC_DIR / "kawkab" / "services" / file_basename
    elif subdir == "utils":
        file_path = SRC_DIR / "kawkab" / "utils" / file_basename
    elif subdir == "i18n":
        file_path = SRC_DIR / "kawkab" / "i18n" / file_basename
    elif subdir == "core":
        file_path = SRC_DIR / "kawkab" / "core" / file_basename
    else:
        raise ValueError(f"Unknown subdir: {subdir}")
    if not file_path.exists():
        raise FileNotFoundError(f"Module file not found: {file_path}")

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
