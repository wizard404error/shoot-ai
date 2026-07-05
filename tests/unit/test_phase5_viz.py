"""Tests for Sprint 2 (frontend visualization depth) bridge methods."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from conftest import install_kawkab_stubs

install_kawkab_stubs()

from kawkab.ui.bridge_handlers.bridge_analysis import AnalysisHandler


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture
def mock_bridge():
    return MagicMock()


@pytest.fixture
def mock_storage():
    svc = MagicMock()
    svc.get_match_events = MagicMock(return_value=[
        {"id": 1, "type": "pass", "team": "home", "track_id": 10, "completed": True,
         "start_x": 30.0, "start_y": 20.0, "end_x": 50.0, "end_y": 25.0},
        {"id": 2, "type": "pass", "team": "home", "track_id": 10, "completed": True,
         "start_x": 40.0, "start_y": 30.0, "end_x": 70.0, "end_y": 35.0},
        {"id": 3, "type": "pass", "team": "home", "track_id": 10, "completed": False,
         "start_x": 50.0, "start_y": 34.0, "end_x": 80.0, "end_y": 40.0},
        {"id": 4, "type": "shot", "team": "home", "track_id": 10, "xG": 0.45,
         "start_x": 80.0, "start_y": 34.0, "end_x": 100.0, "end_y": 34.0},
        {"id": 5, "type": "tackle", "team": "home", "track_id": 10,
         "start_x": 40.0, "start_y": 34.0},
        {"id": 6, "type": "pass", "team": "away", "track_id": 20, "completed": True,
         "start_x": 70.0, "start_y": 34.0, "end_x": 50.0, "end_y": 34.0},
        {"id": 7, "type": "shot", "team": "away", "track_id": 20, "xG": 0.12,
         "start_x": 20.0, "start_y": 34.0, "end_x": 10.0, "end_y": 34.0},
        {"id": 8, "type": "cross", "team": "home", "track_id": 10, "completed": True,
         "start_x": 60.0, "start_y": 10.0, "end_x": 90.0, "end_y": 30.0},
    ])
    return svc


@pytest.fixture
def empty_storage():
    svc = MagicMock()
    svc.get_match_events = MagicMock(return_value=[])
    return svc


@pytest.fixture
def error_storage():
    svc = MagicMock()
    svc.get_match_events = MagicMock(side_effect=RuntimeError("DB error"))
    return svc


@pytest.fixture
def analysis_handler(mock_bridge, mock_storage):
    services = {"storage_service": mock_storage}
    return AnalysisHandler(mock_bridge, services)


@pytest.fixture
def empty_handler(mock_bridge, empty_storage):
    services = {"storage_service": empty_storage}
    return AnalysisHandler(mock_bridge, services)


@pytest.fixture
def error_handler(mock_bridge, error_storage):
    services = {"storage_service": error_storage}
    return AnalysisHandler(mock_bridge, services)


# ========================================================================
# Pitch Control Overlay — 5 tests
# ========================================================================

class TestPitchControlOverlay:
    def test_grid_shape(self, analysis_handler):
        r = json.loads(analysis_handler.get_pitch_control_overlay("1"))
        assert "home_grid" in r
        assert "away_grid" in r
        assert isinstance(r["home_grid"], list)
        assert len(r["home_grid"]) > 0

    def test_control_percentages(self, analysis_handler):
        r = json.loads(analysis_handler.get_pitch_control_overlay("1"))
        assert "ball_control_pct" in r
        assert 0.0 <= r["ball_control_pct"] <= 100.0

    def test_hot_zones_present(self, analysis_handler):
        r = json.loads(analysis_handler.get_pitch_control_overlay("1"))
        assert "hot_zones" in r
        assert isinstance(r["hot_zones"], list)

    def test_empty_match(self, empty_handler):
        r = json.loads(empty_handler.get_pitch_control_overlay("1"))
        assert r.get("ball_control_pct") == 50.0

    def test_error_handling(self, error_handler):
        r = json.loads(error_handler.get_pitch_control_overlay("1"))
        assert "error" in r


# ========================================================================
# Pass Sonar — 5 tests
# ========================================================================

class TestPlayerPassSonar:
    def test_eight_directions(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_pass_sonar("1", "10"))
        assert "directions" in r
        assert len(r["directions"]) == 8

    def test_accuracy_percentages(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_pass_sonar("1", "10"))
        assert "accuracy_pct" in r
        assert len(r["accuracy_pct"]) == 8
        for acc in r["accuracy_pct"]:
            assert 0.0 <= acc <= 100.0

    def test_missing_player(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_pass_sonar("1", "999"))
        assert r.get("total_passes") == 0
        assert "error" in r

    def test_empty_match(self, empty_handler):
        r = json.loads(empty_handler.get_player_pass_sonar("1", "10"))
        assert r.get("total_passes") == 0
        assert "error" in r

    def test_error_handling(self, error_handler):
        r = json.loads(error_handler.get_player_pass_sonar("1", "10"))
        assert "error" in r


# ========================================================================
# Space Control Heatmap — 5 tests
# ========================================================================

class TestSpaceControlHeatmap:
    def test_grid_present(self, analysis_handler):
        r = json.loads(analysis_handler.get_space_control_heatmap("1"))
        assert "grid" in r
        assert isinstance(r["grid"], list)

    def test_team_control_pcts(self, analysis_handler):
        r = json.loads(analysis_handler.get_space_control_heatmap("1"))
        assert "team_control_pcts" in r
        assert isinstance(r["team_control_pcts"], dict)

    def test_hot_zones(self, analysis_handler):
        r = json.loads(analysis_handler.get_space_control_heatmap("1"))
        assert "hot_zones" in r
        assert isinstance(r["hot_zones"], list)

    def test_space_gained(self, analysis_handler):
        r = json.loads(analysis_handler.get_space_control_heatmap("1"))
        assert "space_gained" in r
        assert isinstance(r["space_gained"], (int, float))

    def test_empty_match(self, empty_handler):
        r = json.loads(empty_handler.get_space_control_heatmap("1"))
        assert r.get("space_gained") == 0.0
        assert r.get("grid") == []


# ========================================================================
# Role Classifier Bridge — 5 tests
# ========================================================================

class TestPlayerRole:
    def test_valid_role(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_role("1", "10"))
        assert "primary_role" in r
        assert isinstance(r["primary_role"], str)
        assert r["primary_role"] != ""

    def test_confidence(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_role("1", "10"))
        assert "confidence" in r
        assert 0.0 <= r["confidence"] <= 1.0

    def test_secondary_role(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_role("1", "10"))
        assert "secondary_role" in r

    def test_missing_player(self, analysis_handler):
        r = json.loads(analysis_handler.get_player_role("1", "999"))
        assert r.get("primary_role") == "unknown"
        assert r.get("confidence") == 0.0

    def test_error_handling(self, error_handler):
        r = json.loads(error_handler.get_player_role("1", "10"))
        assert "error" in r


# ========================================================================
# Dominance Index Bridge — 5 tests
# ========================================================================

class TestDominanceIndex:
    def test_index_range(self, analysis_handler):
        r = json.loads(analysis_handler.get_dominance_index("1"))
        assert "index" in r
        assert 0.0 <= r["index"] <= 100.0

    def test_sub_scores(self, analysis_handler):
        r = json.loads(analysis_handler.get_dominance_index("1"))
        assert "sub_scores" in r
        assert isinstance(r["sub_scores"], dict)
        expected = {"possession", "xg_diff", "territory", "pressing", "pass_completion"}
        assert expected.issubset(r["sub_scores"].keys())

    def test_phases(self, analysis_handler):
        r = json.loads(analysis_handler.get_dominance_index("1"))
        assert "phases" in r
        assert isinstance(r["phases"], dict)

    def test_empty_match(self, empty_handler):
        r = json.loads(empty_handler.get_dominance_index("1"))
        assert r.get("index") == 50.0

    def test_error_handling(self, error_handler):
        r = json.loads(error_handler.get_dominance_index("1"))
        assert "error" in r


# ========================================================================
# Bridge Integration — verify methods registered
# ========================================================================

class TestBridgeRegistration:
    def test_handler_has_all_methods(self, analysis_handler):
        assert hasattr(analysis_handler, "get_pitch_control_overlay")
        assert hasattr(analysis_handler, "get_player_pass_sonar")
        assert hasattr(analysis_handler, "get_space_control_heatmap")
        assert hasattr(analysis_handler, "get_player_role")
        assert hasattr(analysis_handler, "get_dominance_index")

    def test_methods_return_json(self, analysis_handler):
        for method_name in ("get_pitch_control_overlay", "get_space_control_heatmap", "get_dominance_index"):
            r = getattr(analysis_handler, method_name)("1")
            d = json.loads(r)
            assert isinstance(d, dict)

    def test_player_methods_return_json(self, analysis_handler):
        for method_name in ("get_player_pass_sonar", "get_player_role"):
            r = getattr(analysis_handler, method_name)("1", "10")
            d = json.loads(r)
            assert isinstance(d, dict)
