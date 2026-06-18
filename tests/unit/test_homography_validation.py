"""Tests for homography 4-corner validation."""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import install_kawkab_stubs, load_service_module

install_kawkab_stubs()


def _install_stubs() -> None:
    if "kawkab.core" in sys.modules and "kawkab.services" in sys.modules:
        return
    if "kawkab" not in sys.modules:
        sys.modules["kawkab"] = types.ModuleType("kawkab")
    core_mod = types.ModuleType("kawkab.core")
    sys.modules["kawkab.core"] = core_mod
    paths_mod = types.ModuleType("kawkab.core.paths")
    class _Paths:
        def __init__(self):
            self.calibration_dir = Path("/tmp/cal")
            self.data_dir = Path("/tmp/data")
    paths_mod.get_paths = lambda: _Paths()
    sys.modules["kawkab.core.paths"] = paths_mod
    services_mod = types.ModuleType("kawkab.services")
    sys.modules["kawkab.services"] = services_mod
    cv_mod = types.ModuleType("kawkab.services.cv_service")
    class FrameDetections:
        pass
    class MatchTrackData:
        pass
    cv_mod.FrameDetections = FrameDetections
    cv_mod.MatchTrackData = MatchTrackData
    sys.modules["kawkab.services.cv_service"] = cv_mod
    services_mod.cv_service = cv_mod


_install_stubs()
_h = load_service_module("h_test", "homography_service.py")
HomographyService = _h.HomographyService

import pytest


class TestValidate4Corner:
    def test_valid_corners(self) -> None:
        svc = HomographyService()
        corners = [(100, 50), (1800, 50), (1800, 1000), (100, 1000)]
        result = svc.validate_4corner_calibration(corners)
        assert result["is_valid"] is True
        assert result["score"] > 0.5
        assert result["issues"] == []

    def test_wrong_number_of_corners(self) -> None:
        svc = HomographyService()
        result = svc.validate_4corner_calibration([(0, 0), (1, 1), (2, 2)])
        assert result["is_valid"] is False
        assert "exactly 4 corners" in result["issues"][0]
        assert result["score"] == 0.0

    def test_skewed_corners_low_score(self) -> None:
        svc = HomographyService()
        corners = [(100, 50), (1800, 50), (1800, 500), (100, 1000)]
        result = svc.validate_4corner_calibration(corners)
        assert result["score"] < 1.0
        assert any("aspect" in i or "height" in i for i in result["issues"])

    def test_self_intersecting_polygon(self) -> None:
        svc = HomographyService()
        corners = [(100, 50), (100, 1000), (1800, 50), (1800, 1000)]
        result = svc.validate_4corner_calibration(corners)
        assert any("convex" in i.lower() for i in result["issues"])

    def test_metrics_included(self) -> None:
        svc = HomographyService()
        corners = [(100, 50), (1800, 50), (1800, 1000), (100, 1000)]
        result = svc.validate_4corner_calibration(corners)
        m = result["metrics"]
        assert "aspect_ratio" in m
        assert "expected_aspect_ratio" in m
        assert "reprojection_error_px" in m
        assert m["expected_aspect_ratio"] == pytest.approx(105 / 68, 0.01)

    def test_degenerate_corner_rejected(self) -> None:
        svc = HomographyService()
        corners = [(0, 0), (0, 0), (100, 100), (0, 100)]
        result = svc.validate_4corner_calibration(corners)
        assert result["is_valid"] is False
        assert result["score"] == 0.0

    def test_convex_check_simple(self) -> None:
        assert HomographyService._is_convex([(0, 0), (1, 0), (1, 1), (0, 1)]) is True
        assert HomographyService._is_convex([(0, 0), (1, 0), (0, 1), (1, 1)]) is False

    def test_convex_check_triangle(self) -> None:
        assert HomographyService._is_convex([(0, 0), (1, 0), (0, 1)]) is True
