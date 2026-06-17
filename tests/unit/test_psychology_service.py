"""Tests for PsychologyService."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import install_kawkab_stubs, load_service_module

install_kawkab_stubs()
_svc = load_service_module("psy_test", "psychology_service.py")
PsychologyService = _svc.PsychologyService
ScoreState = _svc.ScoreState
PsychologyEventType = _svc.PsychologyEventType

import pytest


@pytest.fixture
def psy() -> PsychologyService:
    return PsychologyService()


def make_match_events() -> list[dict]:
    return [
        {"type": "goal", "team": "home", "minute": 12, "second": 0},
        {"type": "goal", "team": "away", "minute": 28, "second": 0},
        {"type": "goal", "team": "home", "minute": 60, "second": 0},
        {"type": "pass", "team": "home", "minute": 5, "second": 0, "completed": True},
        {"type": "pass", "team": "home", "minute": 10, "second": 0, "completed": True},
        {"type": "pass", "team": "home", "minute": 15, "second": 0, "completed": True},
        {"type": "pass", "team": "home", "minute": 20, "second": 0, "completed": True},
        {"type": "pass", "team": "home", "minute": 80, "second": 0, "completed": False},
        {"type": "pass", "team": "home", "minute": 82, "second": 0, "completed": False},
        {"type": "pass", "team": "home", "minute": 85, "second": 0, "completed": False},
        {"type": "foul", "team": "home", "minute": 80, "second": 0},
        {"type": "foul", "team": "home", "minute": 85, "second": 0},
        {"type": "foul", "team": "home", "minute": 88, "second": 0},
    ]


class TestScoreStates:
    def test_initial_state(self) -> None:
        assert PsychologyService._score_state(0, 0) == ScoreState.DRAWING

    def test_winning_by_1(self) -> None:
        assert PsychologyService._score_state(2, 1) == ScoreState.WINNING_BY_1

    def test_winning_by_2_plus(self) -> None:
        assert PsychologyService._score_state(3, 0) == ScoreState.WINNING_BY_2_PLUS

    def test_losing_by_1(self) -> None:
        assert PsychologyService._score_state(0, 1) == ScoreState.LOSING_BY_1

    def test_losing_by_2_plus(self) -> None:
        assert PsychologyService._score_state(1, 4) == ScoreState.LOSING_BY_2_PLUS


class TestAnalyzeBasic:
    def test_analyze_runs(self, psy: PsychologyService) -> None:
        report = psy.analyze(1, "Home", "Away", make_match_events())
        assert report.match_id == 1
        assert isinstance(report.score_state_transitions, list)
        assert isinstance(report.momentum_timeline, list)
        assert isinstance(report.psychology_events, list)

    def test_empty_events(self, psy: PsychologyService) -> None:
        report = psy.analyze(1, "H", "A", [])
        assert len(report.score_state_transitions) == 0


class TestScoreStateTransitions:
    def test_home_goal_changes_state(self, psy: PsychologyService) -> None:
        events = [{"type": "goal", "team": "home", "minute": 10, "second": 0}]
        report = psy.analyze(1, "H", "A", events)
        assert len(report.score_state_transitions) >= 1
        first = report.score_state_transitions[0]
        assert first.from_state == ScoreState.DRAWING
        assert first.to_state == ScoreState.WINNING_BY_1
        assert first.team == "home"

    def test_two_goals_return_to_drawing(self, psy: PsychologyService) -> None:
        events = [
            {"type": "goal", "team": "home", "minute": 10, "second": 0},
            {"type": "goal", "team": "away", "minute": 20, "second": 0},
        ]
        report = psy.analyze(1, "H", "A", events)
        assert report.score_state_transitions[-1].to_state == ScoreState.DRAWING


class TestMomentumTimeline:
    def test_timeline_length(self, psy: PsychologyService) -> None:
        report = psy.analyze(1, "H", "A", make_match_events())
        assert len(report.momentum_timeline) >= 80

    def test_momentum_bounded(self, psy: PsychologyService) -> None:
        report = psy.analyze(1, "H", "A", make_match_events())
        for m in report.momentum_timeline:
            assert -1.0 <= m.home_momentum <= 1.0
            assert -1.0 <= m.away_momentum <= 1.0


class TestNotes:
    def test_notes_generated(self, psy: PsychologyService) -> None:
        report = psy.analyze(1, "H", "A", make_match_events())
        assert len(report.notes) > 0

    def test_notes_for_empty_match(self, psy: PsychologyService) -> None:
        report = psy.analyze(1, "H", "A", [])
        assert any("no significant" in n.lower() for n in report.notes)
