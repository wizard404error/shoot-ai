"""Tests for pre-match scouting report generator."""

from __future__ import annotations

from conftest import install_kawkab_stubs

install_kawkab_stubs()

from kawkab.services.scouting_service import OpponentProfile, ScoutingService  # noqa: E402


def _make_match(
    formation="4-3-3",
    possession_pct=50.0,
    ppda=10.0,
    set_piece_threat=0.15,
    set_piece_conceded=0.1,
    width_usage=0.5,
    build_up_style="mixed",
    scorers=None,
    assisters=None,
    xg_contributors=None,
) -> dict:
    return {
        "formation": formation,
        "possession_pct": possession_pct,
        "ppda": ppda,
        "set_piece_threat": set_piece_threat,
        "set_piece_conceded": set_piece_conceded,
        "width_usage": width_usage,
        "build_up_style": build_up_style,
        "scorers": scorers or [],
        "assisters": assisters or [],
        "xg_contributors": xg_contributors or [],
    }


class TestEmptyProfile:
    def test_fewer_than_min_matches_returns_empty(self):
        svc = ScoutingService(min_matches=3)
        profile = svc.analyze("FC Test", [])
        assert profile.preferred_formation == "unknown"
        assert profile.matches_analyzed == 0
        assert "Need at least" in profile.recommended_tactics[0]

    def test_one_match_with_min3_returns_empty(self):
        svc = ScoutingService(min_matches=3)
        profile = svc.analyze("FC Test", [_make_match()])
        assert profile.matches_analyzed == 1
        assert profile.preferred_formation == "unknown"


class TestFormationAnalysis:
    def test_detects_preferred_formation(self):
        svc = ScoutingService(min_matches=1)
        matches = [_make_match(formation="4-3-3") for _ in range(3)]
        matches.append(_make_match(formation="4-4-2"))
        profile = svc.analyze("FC Test", matches)
        assert profile.preferred_formation == "4-3-3"

    def test_counts_formation_changes(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(formation="4-3-3"),
            _make_match(formation="4-4-2"),
            _make_match(formation="4-3-3"),
        ]
        profile = svc.analyze("FC Test", matches)
        assert profile.formation_changes == 2


class TestPressClassification:
    def test_high_press_when_ppda_below_8(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(ppda=6.0)])
        assert profile.pressing_intensity == "high"

    def test_medium_press_when_ppda_8_to_13(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(ppda=10.0)])
        assert profile.pressing_intensity == "medium"

    def test_low_press_when_ppda_above_13(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(ppda=15.0)])
        assert profile.pressing_intensity == "low"


class TestBuildUpClassification:
    def test_short_build_up(self):
        svc = ScoutingService(min_matches=1)
        matches = [_make_match(build_up_style="short") for _ in range(3)]
        profile = svc.analyze("FC Test", matches)
        assert profile.build_up_style == "short"

    def test_long_build_up(self):
        svc = ScoutingService(min_matches=1)
        matches = [_make_match(build_up_style="long") for _ in range(2)]
        profile = svc.analyze("FC Test", matches)
        assert profile.build_up_style == "long"

    def test_empty_styles_returns_unknown(self):
        svc = ScoutingService(min_matches=1)
        matches = [_make_match(build_up_style="")]
        profile = svc.analyze("FC Test", matches)
        assert profile.build_up_style in ("", "unknown")


class TestPlayerStatsAggregation:
    def test_aggregates_scorers(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(scorers=[{"player": "A", "goals": 2}, {"player": "B", "goals": 1}]),
            _make_match(scorers=[{"player": "A", "goals": 1}]),
        ]
        profile = svc.analyze("FC Test", matches)
        assert ("A", 3) in profile.top_scorers
        assert ("B", 1) in profile.top_scorers

    def test_aggregates_assisters(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(assisters=[{"player": "X", "assists": 2}]),
        ]
        profile = svc.analyze("FC Test", matches)
        assert ("X", 2) in profile.top_assisters

    def test_aggregates_xg_contributors(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(xg_contributors=[{"player": "P", "xg": 1.5}]),
        ]
        profile = svc.analyze("FC Test", matches)
        assert ("P", 1.5) in profile.top_xg_contributors

    def test_truncates_top_5(self):
        svc = ScoutingService(min_matches=1)
        scorers = [{"player": f"P{i}", "goals": i} for i in range(10)]
        profile = svc.analyze("FC Test", [_make_match(scorers=scorers)])
        assert len(profile.top_scorers) <= 5


class TestVulnerabilityFlags:
    def test_low_press_vulnerability(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(ppda=14.0)])
        assert any("Low press" in f for f in profile.vulnerability_flags)

    def test_set_piece_vulnerability(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(set_piece_conceded=0.3)])
        assert any("set pieces" in f for f in profile.vulnerability_flags)

    def test_wide_play_vulnerability(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(width_usage=0.8)])
        assert any("very wide" in f for f in profile.vulnerability_flags)

    def test_short_build_vulnerability(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(build_up_style="short")])
        assert any("high press" in f for f in profile.vulnerability_flags)


class TestStrengthFlags:
    def test_possession_strength(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(possession_pct=65.0)])
        assert any("Dominant possession" in f for f in profile.strength_flags)

    def test_set_piece_strength(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(set_piece_threat=0.3)])
        assert any("set pieces" in f for f in profile.strength_flags)

    def test_tactical_flexibility_strength(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(formation="4-3-3"),
            _make_match(formation="4-4-2"),
            _make_match(formation="3-5-2"),
            _make_match(formation="4-3-3"),
            _make_match(formation="4-2-3-1"),
        ]
        profile = svc.analyze("FC Test", matches)
        assert any("Tactically flexible" in f for f in profile.strength_flags)


class TestTacticRecommendations:
    def test_recommends_high_press_against_low_press(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(ppda=15.0)])
        assert any("Press high" in r for r in profile.recommended_tactics)

    def test_recommends_set_piece_attack_when_vulnerable(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(set_piece_conceded=0.3)])
        assert any("Attack set pieces" in r for r in profile.recommended_tactics)

    def test_recommends_block_passing_vs_short_build(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(build_up_style="short")])
        assert any("Block passing" in r for r in profile.recommended_tactics)

    def test_flexible_formation_recommendation(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(formation="4-3-3"),
            _make_match(formation="4-4-2"),
            _make_match(formation="3-5-2"),
            _make_match(formation="4-3-3"),
            _make_match(formation="4-4-2"),
        ]
        profile = svc.analyze("FC Test", matches)
        assert any("2 opponent formations" in r for r in profile.recommended_tactics)


class TestFullPipeline:
    def test_analyze_returns_opponent_profile(self):
        svc = ScoutingService(min_matches=1)
        matches = [_make_match()]
        profile = svc.analyze("FC Test", matches)
        assert isinstance(profile, OpponentProfile)
        assert profile.team_name == "FC Test"
        assert profile.matches_analyzed == 1

    def test_averages_are_correct(self):
        svc = ScoutingService(min_matches=1)
        matches = [
            _make_match(possession_pct=60, ppda=8.0, set_piece_threat=0.2, width_usage=0.6),
            _make_match(possession_pct=40, ppda=12.0, set_piece_threat=0.1, width_usage=0.4),
        ]
        profile = svc.analyze("FC Test", matches)
        assert profile.avg_possession_pct == 50.0
        assert profile.avg_ppda == 10.0
        assert profile.set_piece_threat == 0.15
        assert profile.width_usage == 0.5

    def test_default_recommendation_when_no_flags(self):
        svc = ScoutingService(min_matches=1)
        profile = svc.analyze("FC Test", [_make_match(ppda=10.0, set_piece_conceded=0.1)])
        assert any("Standard preparation" in r for r in profile.recommended_tactics)
