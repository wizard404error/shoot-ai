"""Analysis service - statistics, patterns, formations, xG/xT.

Thin re-export wrapper around analysis/ subpackage.
Ensures parent package stubs exist so submodule imports resolve.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_SELF_DIR = Path(__file__).resolve().parent
_ANALYSIS_DIR = _SELF_DIR / "analysis"
_SRC_KAWKAB = _SELF_DIR.parent  # src/kawkab

# Ensure parent packages are registered with __path__ so sub-package
# imports (e.g. from kawakab.core.game_constants) can resolve.
# The conftest stubs for kawakab.core and kawakab.services do NOT set
# __path__, so we add it here when the conftest stubs are present.
_PACKAGE_PATHS = {
    "kawkab": str(_SRC_KAWKAB),
    "kawkab.services": str(_SELF_DIR),
    "kawkab.core": str(_SRC_KAWKAB / "core"),
}
for _pkg, _path in _PACKAGE_PATHS.items():
    _mod = sys.modules.get(_pkg)
    if _mod is None:
        _mod = types.ModuleType(_pkg)
        sys.modules[_pkg] = _mod
    if not hasattr(_mod, "__path__") or not _mod.__path__:
        _mod.__path__ = [_path]

# Load each analysis submodule individually
_submodules = {
    "core": "AnalysisServiceCore, PlayerStats, TeamStats, MatchAnalysis",
    "xg_xt": "XgXtMixin",
    "passing": "PassingMixin",
    "tracking": "TrackingMixin",
}

_mods = {}
for _name in _submodules:
    _path = _ANALYSIS_DIR / f"{_name}.py"
    _spec = importlib.util.spec_from_file_location(
        f"kawkab.services.analysis.{_name}",
        str(_path),
    )
    assert _spec is not None and _spec.loader is not None
    _mod = importlib.util.module_from_spec(_spec)
    _mod.__package__ = "kawkab.services.analysis"
    sys.modules[_spec.name] = _mod
    _spec.loader.exec_module(_mod)
    _mods[_name] = _mod

AnalysisServiceCore = _mods["core"].AnalysisServiceCore
PlayerStats = _mods["core"].PlayerStats
TeamStats = _mods["core"].TeamStats
MatchAnalysis = _mods["core"].MatchAnalysis
XgXtMixin = _mods["xg_xt"].XgXtMixin
PassingMixin = _mods["passing"].PassingMixin
TrackingMixin = _mods["tracking"].TrackingMixin


class AnalysisService(AnalysisServiceCore, XgXtMixin, PassingMixin, TrackingMixin):
    pass


__all__ = ["AnalysisService", "MatchAnalysis", "PlayerStats", "TeamStats"]
