"""Kawkab AI Python Client SDK — REST API client for v1 analytics endpoints.

Usage:
    from kawkab.api.client import KawkabClient
    client = KawkabClient(base_url="http://localhost:8741")
    matches = await client.list_matches()
    shots = await client.get_match_shots(match_id=1)
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class KawkabClient:
    """Async HTTP client for the Kawkab AI REST API."""

    def __init__(self, base_url: str = "http://localhost:8741", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    async def close(self):
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        resp = await self._client.get(
            f"{self.base_url}{path}",
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: dict | None = None) -> Any:
        resp = await self._client.post(
            f"{self.base_url}{path}",
            headers=self._headers,
            json=body or {},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Matches ──

    async def list_matches(self) -> list[dict]:
        return (await self._get("/api/v1/matches")).get("matches", [])

    async def get_match(self, match_id: int) -> dict:
        return await self._get(f"/api/v1/matches/{match_id}")

    async def get_match_events(self, match_id: int, event_type: str | None = None, limit: int = 1000) -> list[dict]:
        params = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        return await self._get(f"/api/v1/matches/{match_id}/events", params=params)

    async def get_match_players(self, match_id: int) -> list[dict]:
        return await self._get(f"/api/v1/matches/{match_id}/players")

    # ── Analysis ──

    async def get_match_shots(self, match_id: int) -> dict:
        return await self._get(f"/api/v1/matches/{match_id}/analysis/shots")

    async def get_tactical_shapes(self, match_id: int) -> dict:
        return await self._get(f"/api/v1/matches/{match_id}/analysis/tactical-shapes")

    async def get_pressing(self, match_id: int) -> dict:
        return await self._get(f"/api/v1/matches/{match_id}/analysis/pressing")

    async def get_match_report(self, match_id: int) -> dict:
        return await self._get(f"/api/v1/matches/{match_id}/analysis/report")

    # ── AI ──

    async def ask_llm(self, match_id: int, question: str) -> str:
        result = await self._post(f"/api/v1/matches/{match_id}/ai/ask", {"match_id": match_id, "question": question})
        return result.get("answer", "")

    # ── Player Ratings ──

    async def get_player_ratings(self, match_id: int) -> list[dict]:
        return await self._get(f"/api/v1/matches/{match_id}/ratings")

    # ── Calibration ──

    async def get_calibration(self, match_id: int) -> dict:
        return await self._get(f"/api/v1/matches/{match_id}/calibration")

    # ── Model Comparison ──

    async def compare_models(self, shots: list[dict], n_folds: int = 5) -> dict:
        return await self._post(f"/api/v1/model-comparison?n_folds={n_folds}", shots)

    # ── Fitness ──

    async def get_player_fitness(self, track_id: int, match_id: int) -> dict:
        return await self._get(f"/api/v1/players/{track_id}/fitness", params={"match_id": match_id})

    # ── Recruitment ──

    async def search_players(self, position: str = "", min_age: int = 16, max_age: int = 40, **kwargs) -> list[dict]:
        body = {"position": position, "min_age": min_age, "max_age": max_age, **kwargs}
        result = await self._post("/api/v1/recruitment/search", body)
        return result.get("results", [])

    async def estimate_transfer_fee(self, player_name: str) -> dict:
        return await self._get(f"/api/v1/recruitment/transfer-fee/{player_name}")

    async def get_shortlist(self) -> list[dict]:
        return await self._get("/api/v1/recruitment/shortlist")

    # ── Game Plan ──

    async def get_game_plan(self, match_id: int, opponent: str) -> dict:
        return await self._get(f"/api/v1/game-plan/{match_id}/vs/{opponent}")

    # ── Monitoring ──

    async def get_monitoring_dashboard(self) -> dict:
        return await self._get("/api/v1/monitoring/dashboard")

    async def get_drift_alerts(self) -> list[dict]:
        result = await self._get("/api/v1/monitoring/drift")
        return result.get("alerts", [])

    # ── Webhooks ──

    async def create_webhook(self, url: str, events: list[str] | None = None, secret: str = "") -> dict:
        return await self._post("/api/v1/webhooks", {"url": url, "events": events or ["*"], "secret": secret})

    async def list_webhooks(self) -> list[dict]:
        return await self._get("/api/v1/webhooks")

    async def delete_webhook(self, webhook_id: int):
        await self._client.delete(f"{self.base_url}/api/v1/webhooks/{webhook_id}", headers=self._headers)
