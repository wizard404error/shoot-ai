"""Shared test helpers and loguru stub."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path


# Get project root robustly: parent of tests/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def install_loguru_stub() -> None:
    """Install a no-op loguru stub if loguru is not available."""
    if "loguru" in sys.modules:
        return
    try:
        import loguru  # noqa: F401
        return
    except ImportError:
        pass
    loguru_stub = types.ModuleType("loguru")

    class _Logger:
        def __init__(self, name: str = "") -> None:
            self.name = name

        def info(self, *a, **k) -> None: pass
        def warning(self, *a, **k) -> None: pass
        def error(self, *a, **k) -> None: pass
        def debug(self, *a, **k) -> None: pass
        def bind(self, name: str = "") -> "_Logger":
            return _Logger(name)
        def remove(self, *a, **k) -> None: pass
        def add(self, *a, **k) -> None: pass

    loguru_stub.logger = _Logger()
    sys.modules["loguru"] = loguru_stub


def install_kawkab_stubs() -> None:
    """Install stubs for kawkab.* modules that services depend on.

    This lets us load individual service modules without triggering
    the full kawkab package initialization.
    """
    install_loguru_stub()
    install_httpx_stub()

    if "kawkab" not in sys.modules:
        sys.modules["kawkab"] = types.ModuleType("kawkab")

    if "kawkab.core" not in sys.modules:
        core_mod = types.ModuleType("kawkab.core")
        sys.modules["kawkab.core"] = core_mod

    if "kawkab.core.logging" not in sys.modules:
        log_mod = types.ModuleType("kawkab.core.logging")
        class _ServiceLogger:
            def __init__(self, name: str = "") -> None:
                self.name = name
            def info(self, *a, **k) -> None: pass
            def warning(self, *a, **k) -> None: pass
            def error(self, *a, **k) -> None: pass
            def debug(self, *a, **k) -> None: pass
        def _get_logger(name: str = "") -> _ServiceLogger:
            return _ServiceLogger(name)
        log_mod.get_logger = _get_logger
        log_mod.setup_logging = lambda debug=False: None
        sys.modules["kawkab.core.logging"] = log_mod


def install_httpx_stub() -> None:
    """Install a no-op httpx stub if httpx is not available."""
    if "httpx" in sys.modules:
        return
    try:
        import httpx  # noqa: F401
        return
    except ImportError:
        pass
    httpx_stub = types.ModuleType("httpx")

    class _AsyncClient:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self) -> "_AsyncClient":
            return self

        async def __aexit__(self, *a) -> bool:
            return False

        async def get(self, *a, **k):
            return None

        async def aclose(self) -> None:
            pass

    httpx_stub.AsyncClient = _AsyncClient
    sys.modules["httpx"] = httpx_stub


def load_service_module(module_name: str, file_basename: str, subdir: str = "services"):
    """Load a service module directly without going through __init__.

    This avoids the cascading import of services/__init__.py which
    requires all dependencies to be installed (loguru, ultralytics, etc).
    """
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
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
