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

    _SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    video_path TEXT DEFAULT '',
    home_team TEXT DEFAULT '',
    away_team TEXT DEFAULT '',
    analysis_json JSONB DEFAULT '{}',
    football_data_json JSONB DEFAULT '{}',
    apifootball_json JSONB DEFAULT '{}',
    bzzoiro_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    event_type TEXT DEFAULT '',
    timestamp DOUBLE PRECISION DEFAULT 0,
    team TEXT DEFAULT '',
    from_track_id INTEGER DEFAULT 0,
    x DOUBLE PRECISION DEFAULT 0,
    y DOUBLE PRECISION DEFAULT 0,
    end_x DOUBLE PRECISION DEFAULT 0,
    end_y DOUBLE PRECISION DEFAULT 0,
    is_goal BOOLEAN DEFAULT FALSE,
    completed BOOLEAN DEFAULT FALSE,
    data JSONB DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    track_id INTEGER DEFAULT 0,
    name TEXT DEFAULT '',
    team TEXT DEFAULT '',
    jersey_number INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS player_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT DEFAULT '',
    team TEXT DEFAULT '',
    position TEXT DEFAULT '',
    jersey_number INTEGER DEFAULT 0,
    photo_path TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS advanced_metrics (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    category TEXT DEFAULT '',
    data_json JSONB DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS corrections (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    event_id INTEGER DEFAULT 0,
    field TEXT DEFAULT '',
    old_value TEXT DEFAULT '',
    new_value TEXT DEFAULT '',
    reason TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    report_text TEXT DEFAULT '',
    language TEXT DEFAULT 'en',
    report_type TEXT DEFAULT 'match',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS benchmark_results (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    total_time DOUBLE PRECISION DEFAULT 0,
    realtime_ratio DOUBLE PRECISION DEFAULT 0,
    fps DOUBLE PRECISION DEFAULT 0,
    peak_memory DOUBLE PRECISION DEFAULT 0,
    peak_gpu_memory DOUBLE PRECISION DEFAULT 0,
    gpu_name TEXT DEFAULT '',
    cpu_name TEXT DEFAULT '',
    model_size TEXT DEFAULT '',
    frame_skip INTEGER DEFAULT 0,
    stages_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS validation_results (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    category TEXT DEFAULT '',
    accuracy DOUBLE PRECISION DEFAULT 0,
    details_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    user_name TEXT DEFAULT '',
    rating INTEGER DEFAULT 0,
    comments TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'low',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS usage_sessions (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    user_name TEXT DEFAULT '',
    action TEXT DEFAULT '',
    duration_s DOUBLE PRECISION DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clips (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    name TEXT DEFAULT '',
    start_time DOUBLE PRECISION DEFAULT 0,
    end_time DOUBLE PRECISION DEFAULT 0,
    video_path TEXT DEFAULT '',
    tags_json JSONB DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS playlists (
    id SERIAL PRIMARY KEY,
    name TEXT DEFAULT '',
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    clips_json JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS coding_tags (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    tag_type TEXT DEFAULT '',
    category TEXT DEFAULT '',
    player_track_id INTEGER DEFAULT 0,
    team TEXT DEFAULT '',
    period INTEGER DEFAULT 0,
    timestamp DOUBLE PRECISION DEFAULT 0,
    notes TEXT DEFAULT '',
    color TEXT DEFAULT '#3498db'
);
"""

    async def initialize(self):
        if not self._dsn:
            return
        try:
            import asyncpg
            self._pool = asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
            await self._pool._initialize()
            self._available = True
            async with self._pool.acquire() as conn:
                await conn.execute(self._SCHEMA_SQL)
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

    # ── Match updates ──

    async def update_match_analysis(self, match_id: int, analysis_data: dict) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                "UPDATE matches SET analysis_json = $1, updated_at = NOW() WHERE id = $2",
                json.dumps(analysis_data, default=str), match_id,
            )
            return r != "UPDATE 0"

    async def update_match_teams(self, match_id: int, home_team: str, away_team: str) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                "UPDATE matches SET home_team = $1, away_team = $2, updated_at = NOW() WHERE id = $3",
                home_team, away_team, match_id,
            )
            return r != "UPDATE 0"

    async def update_match_football_data(self, match_id: int, data: dict) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                "UPDATE matches SET football_data_json = $1, updated_at = NOW() WHERE id = $2",
                json.dumps(data, default=str), match_id,
            )
            return r != "UPDATE 0"

    async def update_match_apifootball(self, match_id: int, data: dict) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                "UPDATE matches SET apifootball_json = $1, updated_at = NOW() WHERE id = $2",
                json.dumps(data, default=str), match_id,
            )
            return r != "UPDATE 0"

    async def update_match_bzzoiro(self, match_id: int, data: dict) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                "UPDATE matches SET bzzoiro_json = $1, updated_at = NOW() WHERE id = $2",
                json.dumps(data, default=str), match_id,
            )
            return r != "UPDATE 0"

    # ── Single event operations ──

    async def save_event(self, match_id: int, event: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO events (match_id, event_type, timestamp, team, from_track_id, x, y, end_x, end_y, is_goal, completed, data)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id""",
                match_id, event.get("type", ""), event.get("timestamp", 0.0),
                event.get("team", ""), event.get("from_track_id", 0),
                event.get("x", 0.0), event.get("y", 0.0),
                event.get("end_x", 0.0), event.get("end_y", 0.0),
                event.get("is_goal", False), event.get("completed", False),
                json.dumps(event, default=str),
            )
            return row["id"] if row else 0

    async def update_event(self, event_id: int, updates: dict) -> bool:
        if not self._pool:
            return False
        sets = []
        args = []
        for k, v in updates.items():
            col = k.replace(" ", "_")
            sets.append(f"{col} = ${len(args) + 1}")
            args.append(v)
        if not sets:
            return False
        args.append(event_id)
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                f"UPDATE events SET {', '.join(sets)} WHERE id = ${len(args)}", *args
            )
            return r != "UPDATE 0"

    async def delete_event(self, event_id: int) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute("DELETE FROM events WHERE id = $1", event_id)
            return r != "DELETE 0"

    # ── Player operations ──

    async def save_player(self, match_id: int, player_data: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO players (match_id, track_id, name, team, jersey_number) VALUES ($1,$2,$3,$4,$5) RETURNING id",
                match_id, player_data.get("track_id", 0), player_data.get("name", ""),
                player_data.get("team", ""), player_data.get("jersey_number", 0),
            )
            return row["id"] if row else 0

    async def save_player_profile(self, profile: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO player_profiles (name, team, position, jersey_number, photo_path, notes) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                profile.get("name", ""), profile.get("team", ""), profile.get("position", ""),
                profile.get("jersey_number", 0), profile.get("photo_path", ""),
                json.dumps(profile.get("notes", {}), default=str),
            )
            return row["id"] if row else 0

    async def get_all_player_profiles(self) -> list[dict]:
        return await self.fetch("SELECT * FROM player_profiles ORDER BY name")

    async def update_player_profile_face(self, profile_id: int, face_path: str) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                "UPDATE player_profiles SET photo_path = $1, updated_at = NOW() WHERE id = $2",
                face_path, profile_id,
            )
            return r != "UPDATE 0"

    # ── Advanced metrics ──

    async def save_advanced_metrics(self, match_id: int, metrics: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO advanced_metrics (match_id, category, data_json) VALUES ($1,$2,$3) RETURNING id",
                match_id, metrics.get("category", "general"), json.dumps(metrics, default=str),
            )
            return row["id"] if row else 0

    async def save_advanced_metrics_bulk(self, match_id: int, metrics_list: list[dict]) -> int:
        if not self._pool:
            return 0
        count = 0
        async with self._pool.acquire() as conn:
            for m in metrics_list:
                await conn.execute(
                    "INSERT INTO advanced_metrics (match_id, category, data_json) VALUES ($1,$2,$3)",
                    match_id, m.get("category", "general"), json.dumps(m, default=str),
                )
                count += 1
        return count

    # ── Corrections / Reports ──

    async def save_correction(self, match_id: int, correction: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO corrections (match_id, event_id, field, old_value, new_value, reason) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                match_id, correction.get("event_id", 0), correction.get("field", ""),
                correction.get("old_value", ""), correction.get("new_value", ""),
                correction.get("reason", ""),
            )
            return row["id"] if row else 0

    async def save_report(self, match_id: int, report_text: str, language: str = "en", report_type: str = "match") -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO reports (match_id, report_text, language, report_type) VALUES ($1,$2,$3,$4) RETURNING id",
                match_id, report_text, language, report_type,
            )
            return row["id"] if row else 0

    async def get_reports(self, match_id: int, language: str = "") -> list[dict]:
        if language:
            return await self.fetch("SELECT * FROM reports WHERE match_id = $1 AND language = $2 ORDER BY created_at DESC", match_id, language)
        return await self.fetch("SELECT * FROM reports WHERE match_id = $1 ORDER BY created_at DESC", match_id)

    # ── Benchmarks ──

    async def save_benchmark(self, result: Any) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO benchmark_results (match_id, total_time, realtime_ratio, fps, peak_memory, peak_gpu_memory, gpu_name, cpu_name, model_size, frame_skip, stages_json) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id",
                getattr(result, "match_id", 0), getattr(result, "total_time", 0.0),
                getattr(result, "realtime_ratio", 0.0), getattr(result, "fps", 0.0),
                getattr(result, "peak_memory", 0), getattr(result, "peak_gpu_memory", 0),
                getattr(result, "gpu_name", ""), getattr(result, "cpu_name", ""),
                getattr(result, "model_size", ""), getattr(result, "frame_skip", 2),
                json.dumps(getattr(result, "stages", {}), default=str),
            )
            return row["id"] if row else 0

    async def get_recent_benchmarks(self, limit: int = 10) -> list[dict]:
        return await self.fetch("SELECT * FROM benchmark_results ORDER BY created_at DESC LIMIT $1", limit)

    # ── Validation ──

    async def save_validation_result(self, report: Any) -> list[int]:
        if not self._pool:
            return []
        ids = []
        async with self._pool.acquire() as conn:
            for cat in ["events", "possession", "team_assignment", "speed"]:
                score = getattr(report, f"{cat}_accuracy", 0.0) if hasattr(report, f"{cat}_accuracy") else 0.0
                row = await conn.fetchrow(
                    "INSERT INTO validation_results (match_id, category, accuracy, details_json) VALUES ($1,$2,$3,$4) RETURNING id",
                    getattr(report, "match_id", 0), cat, score,
                    json.dumps(getattr(report, "to_dict", lambda: {})() if callable(getattr(report, "to_dict", None)) else {}, default=str),
                )
                if row:
                    ids.append(row["id"])
        return ids

    async def get_validation_results(self, match_id: int) -> list[dict]:
        return await self.fetch("SELECT * FROM validation_results WHERE match_id = $1 ORDER BY created_at DESC", match_id)

    # ── Feedback / Issues ──

    async def save_feedback(self, feedback: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO feedback (match_id, user_name, rating, comments) VALUES ($1,$2,$3,$4) RETURNING id",
                feedback.get("match_id", 0), feedback.get("user_name", ""),
                feedback.get("rating", 0), feedback.get("comments", ""),
            )
            return row["id"] if row else 0

    async def get_all_feedback(self) -> list[dict]:
        return await self.fetch("SELECT * FROM feedback ORDER BY created_at DESC")

    async def save_issue(self, issue: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO issues (match_id, description, severity, status) VALUES ($1,$2,$3,$4) RETURNING id",
                issue.get("match_id", 0), issue.get("description", ""),
                issue.get("severity", "info"), issue.get("status", "open"),
            )
            return row["id"] if row else 0

    async def get_all_issues(self) -> list[dict]:
        return await self.fetch("SELECT * FROM issues ORDER BY created_at DESC")

    # ── Usage sessions ──

    async def save_usage_session(self, session: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO usage_sessions (match_id, user_name, action, duration_s) VALUES ($1,$2,$3,$4) RETURNING id",
                session.get("match_id", 0), session.get("user_name", ""),
                session.get("action", ""), session.get("duration_s", 0),
            )
            return row["id"] if row else 0

    # ── Clips / Playlists ──

    async def save_clip(self, clip: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO clips (match_id, name, start_time, end_time, video_path, tags_json) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                clip.get("match_id", 0), clip.get("name", ""),
                clip.get("start_time", 0.0), clip.get("end_time", 0.0),
                clip.get("video_path", ""), json.dumps(clip.get("tags", []), default=str),
            )
            return row["id"] if row else 0

    async def get_clips_for_match(self, match_id: int) -> list[dict]:
        return await self.fetch("SELECT * FROM clips WHERE match_id = $1 ORDER BY start_time", match_id)

    async def save_playlist(self, playlist: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO playlists (name, match_id, clips_json) VALUES ($1,$2,$3) RETURNING id",
                playlist.get("name", ""), playlist.get("match_id", 0),
                json.dumps(playlist.get("clips", []), default=str),
            )
            return row["id"] if row else 0

    async def get_playlists(self) -> list[dict]:
        return await self.fetch("SELECT * FROM playlists ORDER BY created_at DESC")

    # ── Coding tags ──

    async def save_coding_tag(self, match_id: int, tag: dict) -> int:
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO coding_tags (match_id, tag_type, category, player_track_id, team, period, timestamp, notes, color) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id",
                match_id, tag.get("tag_type", ""), tag.get("category", ""),
                tag.get("player_track_id", 0), tag.get("team", ""),
                tag.get("period", ""), tag.get("timestamp", 0.0),
                tag.get("notes", ""), tag.get("color", ""),
            )
            return row["id"] if row else 0

    async def get_coding_tags(self, match_id: int) -> list[dict]:
        return await self.fetch("SELECT * FROM coding_tags WHERE match_id = $1 ORDER BY timestamp", match_id)

    async def get_coding_tags_by_type(self, match_id: int, tag_type: str) -> list[dict]:
        return await self.fetch("SELECT * FROM coding_tags WHERE match_id = $1 AND tag_type = $2 ORDER BY timestamp", match_id, tag_type)

    async def get_coding_tags_by_player(self, match_id: int, player_track_id: int) -> list[dict]:
        return await self.fetch("SELECT * FROM coding_tags WHERE match_id = $1 AND player_track_id = $2 ORDER BY timestamp", match_id, player_track_id)

    async def update_coding_tag(self, tag_id: int, updates: dict) -> bool:
        if not self._pool:
            return False
        sets = []
        args = []
        for k, v in updates.items():
            col = k.replace(" ", "_")
            sets.append(f"{col} = ${len(args) + 1}")
            args.append(v)
        if not sets:
            return False
        args.append(tag_id)
        async with self._pool.acquire() as conn:
            r = await conn.execute(
                f"UPDATE coding_tags SET {', '.join(sets)} WHERE id = ${len(args)}", *args
            )
            return r != "UPDATE 0"

    async def delete_coding_tag(self, tag_id: int) -> bool:
        if not self._pool:
            return False
        async with self._pool.acquire() as conn:
            r = await conn.execute("DELETE FROM coding_tags WHERE id = $1", tag_id)
            return r != "DELETE 0"

    async def get_coding_tag_stats(self, match_id: int) -> dict:
        rows = await self.fetch(
            "SELECT category, tag_type, COUNT(*) as count FROM coding_tags WHERE match_id = $1 GROUP BY category, tag_type ORDER BY category, tag_type",
            match_id,
        )
        total = sum(r["count"] for r in rows)
        return {
            "total_tags": total,
            "by_category": {r["category"]: r["count"] for r in rows},
            "by_type": {r["tag_type"]: r["count"] for r in rows},
        }
