"""Tests for player heatmaps."""

from kawkab.core.heatmap import compute_player_heatmap, compute_team_heatmap


class TestHeatmap:
    def test_empty_positions(self):
        grid = compute_player_heatmap([])
        assert len(grid) == 60
        assert len(grid[0]) == 40
        assert all(v == 0.0 for row in grid for v in row)

    def test_single_position(self):
        positions = [(52.5, 34.0)]
        grid = compute_player_heatmap(positions)
        # Center of pitch should have highest density
        center_r, center_c = 30, 20
        assert grid[center_r][center_c] == 1.0

    def test_value_range(self):
        positions = [(10, 10), (20, 20), (30, 30), (40, 40)]
        grid = compute_player_heatmap(positions)
        assert all(0.0 <= v <= 1.0 for row in grid for v in row)

    def test_higher_density_near_positions(self):
        positions = [(10, 10)]
        grid = compute_player_heatmap(positions, grid_rows=5, grid_cols=5, bandwidth=5.0)
        # Closest cell to (10, 10) should have highest density
        max_val = max(max(row) for row in grid)
        assert max_val == 1.0

    def test_team_heatmap(self):
        positions = {1: [(52.5, 34.0), (50, 30)], 2: [(20, 20)]}
        teams = {1: "home", 2: "home"}
        result = compute_team_heatmap(positions, "home", teams)
        assert 1 in result
        assert 2 in result
        assert result[1].team == "home"

    def test_team_filter(self):
        positions = {1: [(52.5, 34.0)], 3: [(10, 10)]}
        teams = {1: "home", 3: "away"}
        result = compute_team_heatmap(positions, "home", teams)
        assert 1 in result
        assert 3 not in result

    def test_team_heatmap_empty_team_dict(self):
        result = compute_team_heatmap({}, "home", {})
        assert result == {}

    def test_team_heatmap_missing_player_entry(self):
        positions = {1: [(52.5, 34.0)]}
        teams = {2: "home"}
        result = compute_team_heatmap(positions, "home", teams)
        assert 1 not in result  # player has no team entry
