"""Tests for Scoreline Probability Distribution module."""

from kawkab.core.scoreline_distribution import ScorelineDistribution


def _make_shot(team: str, xg: float, timestamp: float, is_goal: bool = False) -> dict:
    return {"type": "shot", "team": team, "xg": xg, "timestamp": timestamp, "is_goal": is_goal}


class TestComputeScorelineProbabilities:
    def test_returns_probabilities(self):
        sd = ScorelineDistribution()
        events = [
            _make_shot("home", 0.1, 10),
            _make_shot("away", 0.05, 20),
        ]
        result = sd.compute_scoreline_probabilities(events, n_sims=1000)
        assert "scorelines" in result
        assert result["n_sims"] == 1000
        assert result["remaining_minutes"] > 0

    def test_empty_events(self):
        sd = ScorelineDistribution()
        result = sd.compute_scoreline_probabilities([], n_sims=1000)
        assert result["scorelines"] == {}
        assert result["n_sims"] == 0

    def test_match_over_no_sims(self):
        sd = ScorelineDistribution()
        events = [
            _make_shot("home", 0.1, 5400),
            _make_shot("away", 0.05, 5410),
        ]
        result = sd.compute_scoreline_probabilities(events, n_sims=1000)
        assert result["remaining_minutes"] == 0
        assert len(result["scorelines"]) == 1

    def test_goals_current_are_included(self):
        sd = ScorelineDistribution()
        events = [
            _make_shot("home", 0.3, 30, is_goal=True),
            _make_shot("home", 0.2, 45),
        ]
        result = sd.compute_scoreline_probabilities(events, n_sims=500)
        assert result["goals_current_home"] >= 1

    def test_probabilities_sum_to_one(self):
        sd = ScorelineDistribution()
        events = [
            _make_shot("home", 0.1, 10),
            _make_shot("away", 0.08, 20),
        ]
        result = sd.compute_scoreline_probabilities(events, n_sims=2000)
        total = sum(result["scorelines"].values())
        assert abs(total - 1.0) < 0.05


class TestComputeMatchOutcomeProbs:
    def test_returns_outcomes(self):
        sd = ScorelineDistribution()
        probs = {"1-0": 0.5, "2-0": 0.2, "0-1": 0.2, "1-1": 0.1}
        result = sd.compute_match_outcome_probs(probs)
        assert "win_home" in result
        assert "draw" in result
        assert "win_away" in result
        assert result["win_home"] > result["win_away"]

    def test_empty_probs(self):
        sd = ScorelineDistribution()
        result = sd.compute_match_outcome_probs({})
        assert result["win_home"] == 0.0
        assert result["draw"] == 0.0

    def test_total_matches_one(self):
        sd = ScorelineDistribution()
        probs = {"0-0": 1.0}
        result = sd.compute_match_outcome_probs(probs)
        assert result["draw"] == 1.0


class TestComputeScorelineEntropy:
    def test_entropy_positive(self):
        sd = ScorelineDistribution()
        probs = {"1-0": 0.5, "1-1": 0.3, "0-0": 0.2}
        entropy = sd.compute_scoreline_entropy(probs)
        assert entropy > 0

    def test_certain_match_zero_entropy(self):
        sd = ScorelineDistribution()
        probs = {"1-0": 1.0}
        entropy = sd.compute_scoreline_entropy(probs)
        assert entropy == 0.0
