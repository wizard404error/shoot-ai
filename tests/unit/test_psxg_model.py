"""Tests for PSxG model."""

from kawkab.core.psxg_model import compute_psxg, compute_match_psxg, PSxGResult


class TestPSxG:
    def test_off_target_returns_zero(self):
        result = compute_psxg(distance_m=15, angle_deg=30, on_target=False)
        assert result.psxg == 0.0

    def test_on_target_returns_positive(self):
        result = compute_psxg(distance_m=10, angle_deg=15, on_target=True)
        assert result.psxg > 0.0

    def test_closer_higher_psxg(self):
        close = compute_psxg(5, 10, on_target=True)
        far = compute_psxg(35, 10, on_target=True)
        assert close.psxg > far.psxg

    def test_corner_placement_higher_than_center(self):
        corner = compute_psxg(12, 20, placement_x=0.95, placement_y=0.95, on_target=True)
        center = compute_psxg(12, 20, placement_x=0.5, placement_y=0.5, on_target=True)
        assert corner.psxg > center.psxg

    def test_to_dict(self):
        result = compute_psxg(10, 20, on_target=True)
        d = result.to_dict()
        assert "psxg" in d
        assert "save_probability" in d
        assert d["psxg"] + d["save_probability"] == 1.0

    def test_compute_match_psxg(self):
        events = [
            {"type": "shot", "team": "home", "distance_m": 10, "angle_deg": 20,
             "on_target": True, "is_goal": False, "timestamp": 600},
            {"type": "shot", "team": "away", "distance_m": 5, "angle_deg": 10,
             "on_target": True, "is_goal": True, "timestamp": 1200},
        ]
        report = compute_match_psxg(events)
        assert report.home_psxg > 0
        assert report.away_psxg > 0
        assert report.home_goals_conceded == 1

    def test_empty_events(self):
        report = compute_match_psxg([])
        assert report.home_psxg == 0
        assert report.away_psxg == 0
