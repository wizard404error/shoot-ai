"""Tests for win probability model."""

from kawkab.core.win_probability import compute_win_probability


class TestWinProbability:
    def test_no_events(self):
        report = compute_win_probability([], 1500, 1500)
        assert len(report.timeline) == 1
        assert report.timeline[0]["minute"] == 0
        # Home advantage (50 Elo) makes home slight favorite
        assert report.timeline[0]["home_win"] > report.timeline[0]["away_win"]

    def test_home_goal_increases_home_win(self):
        events = [
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 1800},
        ]
        report = compute_win_probability(events, 1500, 1500)
        assert len(report.timeline) == 2
        home_win = report.timeline[-1]["home_win"]
        draw = report.timeline[-1]["draw"]
        away_win = report.timeline[-1]["away_win"]
        assert home_win > away_win
        assert abs(home_win + draw + away_win - 1.0) < 0.001

    def test_away_goal_increases_away_win(self):
        events = [
            {"type": "shot", "team": "away", "is_goal": True, "timestamp": 2700},
        ]
        report = compute_win_probability(events, 1500, 1500)
        away_win = report.timeline[-1]["away_win"]
        home_win = report.timeline[-1]["home_win"]
        assert away_win > home_win

    def test_multiple_goals(self):
        events = [
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 1200},
            {"type": "shot", "team": "away", "is_goal": True, "timestamp": 2400},
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 4800},
        ]
        report = compute_win_probability(events, 1500, 1500)
        assert len(report.timeline) == 4
        final = report.timeline[-1]
        assert final["home_win"] > final["away_win"]
        assert final["home_score"] == 2
        assert final["away_score"] == 1

    def test_late_goal_has_bigger_impact(self):
        early = [
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 300},
        ]
        late = [
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 5100},
        ]
        r1 = compute_win_probability(early, 1500, 1500)
        r2 = compute_win_probability(late, 1500, 1500)
        assert r2.timeline[-1]["home_win"] > r1.timeline[-1]["home_win"]

    def test_sum_to_one(self):
        events = [
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 900},
            {"type": "shot", "team": "away", "is_goal": True, "timestamp": 1800},
            {"type": "shot", "team": "home", "is_goal": True, "timestamp": 3600},
        ]
        report = compute_win_probability(events, 1500, 1500)
        for pt in report.timeline:
            total = pt["home_win"] + pt["draw"] + pt["away_win"]
            assert abs(total - 1.0) < 0.001
