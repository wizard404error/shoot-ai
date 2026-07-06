"""Tests for REST API v1 endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kawkab.cloud.server import app


client = TestClient(app)


class TestApiHealth:
    def test_api_health(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_api_version(self):
        resp = client.get("/api/v1/health")
        assert resp.json()["api_version"] == "v1"

    def test_server_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestApiMatches:
    def test_list_matches(self):
        resp = client.get("/api/v1/matches")
        assert resp.status_code == 200
        data = resp.json()
        assert "matches" in data
        assert "total" in data

    def test_get_match_not_found(self):
        resp = client.get("/api/v1/matches/999999")
        assert resp.status_code == 404

    def test_get_match_players_not_found(self):
        resp = client.get("/api/v1/matches/999999/players")
        assert resp.status_code == 200


class TestApiModelComparison:
    def test_compare_models_empty(self):
        resp = client.post("/api/v1/model-comparison?n_folds=0", json=[])
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data

    def test_compare_models_with_shots(self):
        shots = [
            {"xg_heuristic": 0.5, "is_goal": True, "distance_m": 5.0, "angle_deg": 0.0},
            {"xg_heuristic": 0.1, "is_goal": False, "distance_m": 20.0, "angle_deg": 30.0},
            {"xg_heuristic": 0.05, "is_goal": False, "distance_m": 30.0, "angle_deg": 45.0},
            {"xg_heuristic": 0.3, "is_goal": True, "distance_m": 12.0, "angle_deg": 10.0},
        ]
        resp = client.post("/api/v1/model-comparison?n_folds=2", json=shots)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) >= 1


class TestApiWebhooks:
    def test_create_webhook(self):
        resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/hook",
            "events": ["match.analyzed"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://example.com/hook"

    def test_list_webhooks(self):
        resp = client.get("/api/v1/webhooks")
        assert resp.status_code == 200

    def test_delete_webhook(self):
        resp = client.delete("/api/v1/webhooks/1")
        assert resp.status_code == 200


class TestApiMonitoring:
    def test_monitoring_dashboard(self):
        resp = client.get("/api/v1/monitoring/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "total_evaluations" in data

    def test_drift_alerts(self):
        resp = client.get("/api/v1/monitoring/drift")
        assert resp.status_code == 200
        assert "alerts" in resp.json()


class TestApiRecruitment:
    def test_search_players(self):
        resp = client.post("/api/v1/recruitment/search", json={
            "position": "forward",
            "min_age": 20,
            "max_age": 30,
        })
        assert resp.status_code == 200

    def test_transfer_fee(self):
        resp = client.get("/api/v1/recruitment/transfer-fee/Mbappe")
        assert resp.status_code == 200
        assert "estimated_fee" in resp.json()

    def test_shortlist(self):
        resp = client.get("/api/v1/recruitment/shortlist")
        assert resp.status_code == 200


class TestApiGamePlan:
    def test_game_plan(self):
        resp = client.get("/api/v1/game-plan/1/vs/Barcelona")
        assert resp.status_code == 200
        data = resp.json()
        assert "opponent" in data
        assert data["opponent"] == "Barcelona"


class TestApiSeason:
    def test_season_summary(self):
        resp = client.get("/api/v1/season/summary")
        assert resp.status_code == 200
