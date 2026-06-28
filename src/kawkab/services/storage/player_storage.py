"""Player storage — CRUD for player records."""

from __future__ import annotations

from kawkab.core.logging import get_logger
from kawkab.services.storage.base import BaseStorage

try:
    from kawkab.core.security import SecurityValidator as _SecVal
    SecurityValidator = _SecVal
except ImportError:
    class _SecurityValidator:
        @staticmethod
        def validate_match_id(mid): return int(mid)
        @staticmethod
        def validate_track_id(t): return int(t)
        @staticmethod
        def validate_jersey_number(j): return int(j)
        @staticmethod
        def sanitize_string(s, max_length=255): return str(s)[:max_length]
        @staticmethod
        def validate_positive_float(v, n="v"): return max(0.0, float(v))
    SecurityValidator = _SecurityValidator()

logger = get_logger(__name__)


class PlayerStorage(BaseStorage):
    """CRUD for player records."""

    async def save_player(self, match_id: int, player_data: dict) -> int:
        if not self._ensure_initialized("save_player"):
            return 0
        try:
            SecurityValidator.validate_match_id(match_id)
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO players (
                    match_id, track_id, jersey_number, name, team, position,
                    distance_covered_m, max_speed_kmh, avg_speed_kmh,
                    passes_attempted, passes_completed, shots, tackles
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    SecurityValidator.validate_track_id(player_data["track_id"]),
                    SecurityValidator.validate_jersey_number(player_data.get("jersey_number", 0)),
                    SecurityValidator.sanitize_string(str(player_data.get("name", "")), max_length=100),
                    SecurityValidator.sanitize_string(str(player_data.get("team", "")), max_length=50),
                    SecurityValidator.sanitize_string(str(player_data.get("position", "")), max_length=30),
                    SecurityValidator.validate_positive_float(player_data.get("distance_covered_m", 0), "distance"),
                    SecurityValidator.validate_positive_float(player_data.get("max_speed_kmh", 0), "max_speed"),
                    SecurityValidator.validate_positive_float(player_data.get("avg_speed_kmh", 0), "avg_speed"),
                    max(0, int(player_data.get("passes_attempted", 0))),
                    max(0, int(player_data.get("passes_completed", 0))),
                    max(0, int(player_data.get("shots", 0))),
                    max(0, int(player_data.get("tackles", 0))),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_player", e)
            return 0

    async def save_players_bulk(self, match_id: int, players: list[dict]) -> int:
        if not self._ensure_initialized("save_players_bulk"):
            return 0
        try:
            SecurityValidator.validate_match_id(match_id)
            cursor = self._conn.cursor()
            rows = []
            for p in players:
                rows.append((
                    match_id,
                    SecurityValidator.validate_track_id(p.get("track_id", 0)),
                    SecurityValidator.validate_jersey_number(p.get("jersey_number", 0)) if p.get("jersey_number") is not None else None,
                    SecurityValidator.sanitize_string(str(p.get("name", "")), max_length=100),
                    SecurityValidator.sanitize_string(str(p.get("team", "")), max_length=50),
                    SecurityValidator.sanitize_string(str(p.get("position", "")), max_length=30),
                    SecurityValidator.validate_positive_float(p.get("distance_covered_m", 0), "distance"),
                    SecurityValidator.validate_positive_float(p.get("max_speed_kmh", 0), "max_speed"),
                    SecurityValidator.validate_positive_float(p.get("avg_speed_kmh", 0), "avg_speed"),
                    int(SecurityValidator.validate_positive_float(p.get("passes_attempted", 0), "passes_attempted")),
                    int(SecurityValidator.validate_positive_float(p.get("passes_completed", 0), "passes_completed")),
                    int(SecurityValidator.validate_positive_float(p.get("shots", 0), "shots")),
                    int(SecurityValidator.validate_positive_float(p.get("tackles", 0), "tackles")),
                ))
            cursor.executemany(
                """
                INSERT INTO players (
                    match_id, track_id, jersey_number, name, team, position,
                    distance_covered_m, max_speed_kmh, avg_speed_kmh,
                    passes_attempted, passes_completed, shots, tackles
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._conn.commit()
            return len(rows)
        except Exception as e:
            self._log_error("save_players_bulk", e)
            return 0

    async def get_match_players(self, match_id: int) -> list[dict]:
        if not self._ensure_initialized("get_match_players"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM players WHERE match_id = ? ORDER BY track_id",
                (match_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_match_players", e)
            return []
