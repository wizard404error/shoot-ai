"""Tests for influence maps."""

from kawkab.core.influence_map import (
    compute_player_influence,
    compute_team_influence_map,
)


class TestInfluenceMap:
    def test_empty_positions(self):
        grid = compute_player_influence([])
        assert len(grid) == 40
        assert all(v == 0.0 for row in grid for v in row)

    def test_single_position_center(self):
        grid = compute_player_influence([(52.5, 34.0)])
        assert len(grid) == 40
        assert len(grid[0]) == 60
        max_val = max(max(row) for row in grid)
        assert max_val > 0.0  # density around center

    def test_multiple_positions(self):
        positions = [(10, 10), (20, 20), (30, 30), (80, 50), (90, 30)]
        grid = compute_player_influence(positions)
        assert len(grid) == 40
        assert any(max(row) > 0 for row in grid)

    def test_team_influence_map_empty(self):
        result = compute_team_influence_map({}, {})
        assert "home" in result
        assert "away" in result

    def test_team_influence_map_with_data(self):
        home = {1: [(10, 10), (20, 20)], 2: [(50, 34), (60, 40)]}
        away = {5: [(80, 30), (90, 34)]}
        result = compute_team_influence_map(home, away)
        assert max(max(row) for row in result["home"]) > 0
        assert max(max(row) for row in result["away"]) > 0

    def test_normalized_grid_values(self):
        positions = [(52.5, 34.0), (53, 33), (51, 35), (52, 34)]
        grid = compute_player_influence(positions)
        for row in grid:
            for v in row:
                assert 0.0 <= v <= 1.0
