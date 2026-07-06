"""PostgreSQL adapter for StorageService — asyncpg-based parallel to SQLite.

Enables dual-mode operation: SQLite for local single-user, PostgreSQL for club deployment.
"""

from __future__ import annotations

import json
from typing import Any


class PostgresStorageAdapter:
    """PostgreSQL adapter mirroring StorageService's async interface.

    Falls back to SQLite if PostgreSQL is unavailable or not configured.
    """

    def __init__(self, dsn: str | None = None):
        self._dsn = dsn
        self._pool = None
        self._available = False

    async def initialize(self):
        if not self._dsn:
            return
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
            self._available = True
        except Exception:
            self._available = False

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def available(self) -> bool:
        return self._available

    async def fetch(self, query: str, *args) -> list[dict]:
        if not self._pool:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args) -> dict | None:
        if not self._pool:
            return None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def execute(self, query: str, *args) -> str:
        if not self._pool:
            return "0"
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def executemany(self, query: str, args: list[tuple]) -> None:
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(query, args)

    # ── Match operations ──

    async def save_match(self, name: str, video_path: str, home_team: str = "", away_team: str = "") -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO matches (name, video_path, home_team, away_team) VALUES ($1, $2, $3, $4) RETURNING id",
                name, video_path, home_team, away_team,
            )
            return row["id"] if row else 0

    async def get_all_matches(self) -> list[dict]:
        return await self.fetch("SELECT * FROM matches ORDER BY created_at DESC")

    async def get_match(self, match_id: int) -> dict | None:
        return await self.fetchrow("SELECT * FROM matches WHERE id = $1", match_id)

    # ── Event operations ──

    async def save_events_bulk(self, match_id: int, events: list[dict]) -> int:
        if not self._pool or not events:
            return 0
        async with self._pool.acquire() as conn:
            count = 0
            for ev in events:
                await conn.execute(
                    """INSERT INTO events (match_id, event_type, timestamp, team, from_track_id, x, y, end_x, end_y, is_goal, completed, data)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                       ON CONFLICT DO NOTHING""",
                    match_id, ev.get("type", ""), ev.get("timestamp", 0.0),
                    ev.get("team", ""), ev.get("from_track_id", 0),
                    ev.get("x", 0.0), ev.get("y", 0.0),
                    ev.get("end_x", 0.0), ev.get("end_y", 0.0),
                    ev.get("is_goal", False), ev.get("completed", False),
                    json.dumps(ev, default=str),
                )
                count += 1
            return count

    async def get_match_events(self, match_id: int) -> list[dict]:
        rows = await self.fetch("SELECT * FROM events WHERE match_id = $1 ORDER BY timestamp", match_id)
        result = []
        for r in rows:
            ev = dict(r)
            try:
                extra = json.loads(ev.pop("data", "{}"))
                ev.update(extra)
            except Exception:
                pass
            result.append(ev)
        return result

    # ── Player operations ──

    async def save_players_bulk(self, match_id: int, players: list[dict]) -> int:
        if not self._pool:
            return 0
        tuples = [
            (match_id, p.get("track_id", 0), p.get("name", ""), p.get("team", ""), p.get("jersey_number", 0))
            for p in players
        ]
        await self.executemany(
            """INSERT INTO players (match_id, track_id, name, team, jersey_number)
               VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING""",
            tuples,
        )
        return len(tuples)

    async def get_match_players(self, match_id: int) -> list[dict]:
        return await self.fetch("SELECT * FROM players WHERE match_id = $1 ORDER BY track_id", match_id)
