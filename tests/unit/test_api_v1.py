"""Tests for REST API v1 endpoints."""

from __future__ import annotations

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Use isolated temp DB for testing
os.environ.setdefault("KAWKAB_JWT_SECRET", "test-secret-for-testing-purposes-only")
os.environ["KAWKAB_CLOUD_DB"] = os.path.join(tempfile.gettempdir(), f"kawkab_test_api_v1.db")
os.environ["KAWKAB_RATE_LIMIT_DISABLE"] = "1"

from kawkab.cloud.auth import create_access_token
from kawkab.cloud.database import get_cloud_db
from kawkab.cloud.server import app


client = TestClient(app)


def _ensure_user(email, username, role):
    """Get or create a test user, return auth headers."""
    db = get_cloud_db()
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        db.execute(
            "INSERT OR IGNORE INTO users (username, email, password_hash, display_name, role) VALUES (?, ?, ?, ?, ?)",
            (username, email, "hash", f"{role.title()} Tester", role),
        )
        db.commit()
        row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        return {}
    token = create_access_token(row["id"], role=role)
    return {"Authorization": f"Bearer {token}"}


def _admin_headers():
    return _ensure_user("admin@test.com", "admintest", "admin")


def _analyst_headers():
    return _ensure_user("analyst@test.com", "analysttest", "analyst")


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
        resp = client.get("/api/v1/matches", headers=_analyst_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or "matches" in data
        assert "total" in data

    def test_get_match_not_found(self):
        resp = client.get("/api/v1/matches/999999", headers=_analyst_headers())
        assert resp.status_code == 404

    def test_get_match_players_not_found(self):
        resp = client.get("/api/v1/matches/999999/players", headers=_analyst_headers())
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
        resp = client.post("/api/v1/webhooks", headers=_admin_headers(), json={
            "url": "https://example.com/hook",
            "events": ["match.analyzed"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://example.com/hook"

    def test_list_webhooks(self):
        resp = client.get("/api/v1/webhooks", headers=_admin_headers())
        assert resp.status_code == 200

    def test_delete_webhook(self):
        resp = client.delete("/api/v1/webhooks/1", headers=_admin_headers())
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
        resp = client.post("/api/v1/recruitment/search", headers=_analyst_headers(), json={
            "position": "forward",
            "min_age": 20,
            "max_age": 30,
        })
        assert resp.status_code == 200

    def test_transfer_fee(self):
        resp = client.get("/api/v1/recruitment/transfer-fee/Mbappe", headers=_analyst_headers())
        assert resp.status_code == 200
        assert "estimated_fee" in resp.json()

    def test_shortlist(self):
        resp = client.get("/api/v1/recruitment/shortlist", headers=_analyst_headers())
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
