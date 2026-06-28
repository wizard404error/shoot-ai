"""Tests for Game Plan scouting report generation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
from conftest import install_kawkab_stubs  # noqa: E402

install_kawkab_stubs()

from kawkab.core.game_plan import (  # noqa: E402
    OpponentProfile,
    GamePlan,
    generate_game_plan,
    _default_game_plan,
    _compute_formation_probabilities,
    _extract_top_scorers,
    _extract_top_assisters,
    _compute_set_piece_threat,
    _compute_pressing_intensity,
    _compute_transition_speed,
    _identify_key_weaknesses,
    _recommend_formation,
    _recommend_tactics,
    _compute_predicted_scoreline,
    _compute_strength_of_play,
)


def _make_match(overrides: dict = None) -> dict:
    base = {
        "match_id": "m1",
        "formation": "4-3-3",
        "in_possession_formation": "4-3-3",
        "out_possession_formation": "4-5-1",
        "ppda": 8.0,
        "set_piece_threat": 0.15,
        "goals_conceded": 1,
        "goals": 2,
        "goals_from_set_pieces": 0,
        "corners": 5,
        "build_up_score": 0.7,
        "counter_attack_score": 0.4,
        "transition_speed": 0.6,
        "avg_transition_seconds": 4.0,
        "scorers": [{"player": "Player A", "goals": 1}, {"player": "Player B", "goals": 1}],
        "assisters": [{"player": "Player C", "assists": 2}],
    }
    if overrides:
        base.update(overrides)
    return base


class TestGamePlan:
    def test_empty_opponent_data_returns_default_report(self):
        gp = generate_game_plan(
            opponent_team_id="FC Opponent",
            opponent_matches=[],
            own_team_id="FC Home",
            own_matches=[],
        )
        assert gp.opponent.team_name == "FC Opponent"
        assert gp.opponent.formation_probabilities == {}
        assert gp.recommended_formation == "4-4-2"
        assert "insufficient opponent data" in gp.recommended_tactics[0].lower()

    def test_formation_probabilities_from_match_data(self):
        matches = [
            _make_match({"formation": "4-3-3"}),
            _make_match({"formation": "4-3-3"}),
            _make_match({"formation": "4-2-3-1"}),
        ]
        probs = _compute_formation_probabilities(matches)
        assert "4-3-3" in probs
        assert probs["4-3-3"] >= probs.get("4-2-3-1", 0)

    def test_top_scorers_extracted(self):
        matches = [
            _make_match({"scorers": [{"player": "A", "goals": 2}, {"player": "B", "goals": 1}]}),
            _make_match({"scorers": [{"player": "A", "goals": 1}, {"player": "C", "goals": 4}]}),
        ]
        scorers = _extract_top_scorers(matches)
        assert len(scorers) == 3
        assert scorers[0]["player"] == "C"
        assert scorers[0]["goals"] == 4

    def test_top_assisters_extracted(self):
        matches = [
            _make_match({"assisters": [{"player": "X", "assists": 3}]}),
            _make_match({"assisters": [{"player": "Y", "assists": 1}, {"player": "X", "assists": 1}]}),
        ]
        assisters = _extract_top_assisters(matches)
        top = assisters[0]
        assert top["player"] == "X"
        assert top["assists"] == 4

    def test_key_weaknesses_low_ppda_identified(self):
        matches = [_make_match({"ppda": 3.0, "build_up_score": 0.3})]
        weaknesses = _identify_key_weaknesses(
            _compute_pressing_intensity(matches), matches
        )
        has_press_weakness = any("pressing" in w.lower() for w in weaknesses)
        assert has_press_weakness

    def test_set_piece_threat_computed(self):
        matches = [
            _make_match({"set_piece_threat": 0.35}),
            _make_match({"set_piece_threat": 0.25}),
        ]
        threat = _compute_set_piece_threat(matches)
        assert threat == 0.3

    def test_set_piece_threat_fallback_from_goals(self):
        matches = [_make_match({"set_piece_threat": None, "goals": 4, "goals_from_set_pieces": 1})]
        threat = _compute_set_piece_threat(matches)
        assert 0 < threat <= 1.0

    def test_pressing_intensity_normalized(self):
        matches = [_make_match({"ppda": 5.0})]
        intensity = _compute_pressing_intensity(matches)
        assert 0.0 <= intensity <= 1.0

    def test_transition_speed_normalized(self):
        matches = [_make_match({"transition_speed": 2.0})]
        speed = _compute_transition_speed(matches)
        assert 0.0 <= speed <= 1.0

    def test_recommend_formation_returns_counter(self):
        probs = {"4-3-3": 0.7, "4-2-3-1": 0.3}
        formation = _recommend_formation(probs, [])
        assert formation == "4-2-3-1"

    def test_predicted_scoreline_has_required_keys(self):
        opponent = OpponentProfile(
            team_name="Opp",
            formation_probabilities={"4-3-3": 1.0},
            strength_of_play={"build_up": 0.5},
            top_scorers=[{"player": "A", "goals": 5}],
            top_assisters=[{"player": "B", "assists": 3}],
            set_piece_threat=0.2,
            pressing_intensity=0.5,
            transition_speed=0.5,
            key_weaknesses=[],
        )
        scoreline = _compute_predicted_scoreline(opponent, [], home_advantage=True)
        for key in ("most_likely", "home_win_pct", "draw_pct", "away_win_pct"):
            assert key in scoreline

    def test_to_dict_serialization(self):
        opponent = OpponentProfile(
            team_name="FC Test",
            formation_probabilities={"4-3-3": 0.8},
            strength_of_play={"build_up": 0.7},
            top_scorers=[{"player": "A", "goals": 5}],
            top_assisters=[{"player": "B", "assists": 3}],
            set_piece_threat=0.3,
            pressing_intensity=0.6,
            transition_speed=0.4,
            key_weaknesses=["Low press"],
        )
        gp = GamePlan(
            opponent=opponent,
            recommended_formation="4-4-2",
            recommended_tactics=["Press high"],
            key_players_to_neutralize=[{"player": "A", "why": "Scorer", "how": "Mark tight"}],
            set_piece_plan=["Zonal marking"],
            predicted_scoreline={"most_likely": "2-1", "home_win_pct": 55},
            preparation_notes="Test notes",
        )
        d = gp.to_dict()
        assert d["opponent"]["team_name"] == "FC Test"
        assert d["recommended_formation"] == "4-4-2"
        assert d["predicted_scoreline"]["most_likely"] == "2-1"

    def test_to_markdown_generates_readable_output(self):
        opponent = OpponentProfile(
            team_name="FC Markdown",
            formation_probabilities={"4-3-3": 0.7, "4-2-3-1": 0.3},
            strength_of_play={"build_up": 0.6},
            top_scorers=[{"player": "A", "goals": 4}],
            top_assisters=[{"player": "B", "assists": 2}],
            set_piece_threat=0.25,
            pressing_intensity=0.5,
            transition_speed=0.5,
            key_weaknesses=["Concedes from crosses"],
        )
        gp = GamePlan(
            opponent=opponent,
            recommended_formation="4-4-2",
            recommended_tactics=["Press high", "Exploit wide areas"],
            key_players_to_neutralize=[{"player": "A", "why": "Top scorer", "how": "Double team"}],
            set_piece_plan=["Zonal marking"],
            predicted_scoreline={"most_likely": "2-1", "home_win_pct": 50, "draw_pct": 25, "away_win_pct": 25},
            preparation_notes="Focus on defensive transitions.",
        )
        md = gp.to_markdown()
        assert "# Game Plan: vs FC Markdown" in md
        assert "4-3-3" in md
        assert "4-4-2" in md
        assert "press high" in md.lower()
        assert "A" in md

    def test_default_game_plan_structure(self):
        gp = _default_game_plan("Unknown Team")
        assert gp.opponent.team_name == "Unknown Team"
        assert gp.recommended_formation == "4-4-2"
        assert gp.opponent.formation_probabilities == {}

    def test_strength_of_play_computed(self):
        matches = [
            _make_match({"build_up_score": 0.8, "counter_attack_score": 0.3}),
            _make_match({"build_up_score": 0.6, "counter_attack_score": 0.5}),
        ]
        sop = _compute_strength_of_play(matches)
        assert "build_up" in sop
        assert 0.6 <= sop["build_up"] <= 0.8

    def test_recommend_tactics_from_weaknesses(self):
        opponent = OpponentProfile(
            team_name="T",
            formation_probabilities={},
            strength_of_play={},
            top_scorers=[],
            top_assisters=[],
            set_piece_threat=0.3,
            pressing_intensity=0.35,
            transition_speed=0.75,
            key_weaknesses=["Low pressing intensity — can be dominated in midfield"],
        )
        tactics = _recommend_tactics(opponent, opponent.key_weaknesses)
        has_press = any("press" in t.lower() for t in tactics)
        has_transition = any("transition" in t.lower() or "counter" in t.lower() for t in tactics)
        assert has_press
        assert has_transition
