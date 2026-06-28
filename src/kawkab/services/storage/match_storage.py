"""Match storage — CRUD for match records and their metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
        def validate_team_name(n): return str(n)
        @staticmethod
        def sanitize_string(s, max_length=255): return str(s)[:max_length]
    SecurityValidator = _SecurityValidator()

logger = get_logger(__name__)


class MatchStorage(BaseStorage):
    """CRUD for match records."""

    async def save_match(
        self,
        name: str,
        video_path: str,
        home_team: str | None = None,
        away_team: str | None = None,
    ) -> int:
        if not self._ensure_initialized("save_match"):
            return 0
        try:
            name = SecurityValidator.sanitize_string(name, max_length=255)
            if home_team:
                home_team = SecurityValidator.validate_team_name(home_team)
            if away_team:
                away_team = SecurityValidator.validate_team_name(away_team)
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO matches (name, video_path, home_team, away_team)
                VALUES (?, ?, ?, ?)
                """,
                (name, video_path, home_team, away_team),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_match", e)
            return 0

    async def get_all_matches(self) -> list[dict]:
        if not self._ensure_initialized("get_all_matches"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT id, name, video_path, home_team, away_team, match_date,
                       duration_seconds, analyzed_at, created_at,
                       api_match_id, competition_code,
                       bzzoiro_home_team_id, bzzoiro_away_team_id, bzzoiro_event_id, bzzoiro_league_id,
                       apifb_home_team_id, apifb_away_team_id, apifb_fixture_id, apifb_league_id
                FROM matches
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_all_matches", e)
            return []

    async def get_match(self, match_id: int) -> dict | None:
        if not self._ensure_initialized("get_match"):
            return None
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            self._log_error("get_match", e)
            return None

    async def update_match_analysis(
        self,
        match_id: int,
        duration: float,
        fps: float,
        total_frames: int,
    ) -> None:
        if not self._ensure_initialized("update_match_analysis"):
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE matches
                SET duration_seconds = ?, fps = ?, total_frames = ?,
                    analyzed_at = ?
                WHERE id = ?
                """,
                (duration, fps, total_frames, datetime.now(), match_id),
            )
            self._conn.commit()
        except Exception as e:
            self._log_error("update_match_analysis", e)

    async def update_match_teams(
        self, match_id: int, home_team: str, away_team: str
    ) -> None:
        if not self._ensure_initialized("update_match_teams"):
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "UPDATE matches SET home_team = ?, away_team = ? WHERE id = ?",
                (home_team, away_team, match_id),
            )
            self._conn.commit()
        except Exception as e:
            self._log_error("update_match_teams", e)

    async def update_match_football_data(
        self,
        match_id: int,
        api_match_id: int | None = None,
        competition_code: str | None = None,
        football_data_home_team_id: int | None = None,
        football_data_away_team_id: int | None = None,
    ) -> None:
        if not self._ensure_initialized("update_match_football_data"):
            return
        try:
            sets = []
            vals = []
            if api_match_id is not None:
                sets.append("api_match_id = ?")
                vals.append(api_match_id)
            if competition_code is not None:
                sets.append("competition_code = ?")
                vals.append(competition_code)
            if football_data_home_team_id is not None:
                sets.append("football_data_home_team_id = ?")
                vals.append(football_data_home_team_id)
            if football_data_away_team_id is not None:
                sets.append("football_data_away_team_id = ?")
                vals.append(football_data_away_team_id)
            if not sets:
                return
            vals.append(match_id)
            cursor = self._conn.cursor()
            cursor.execute(
                f"UPDATE matches SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()
        except Exception as e:
            self._log_error("update_match_football_data", e)

    async def update_match_apifootball(
        self,
        match_id: int,
        apifb_home_team_id: int | None = None,
        apifb_away_team_id: int | None = None,
        apifb_fixture_id: int | None = None,
        apifb_league_id: int | None = None,
        apifb_season: int | None = None,
    ) -> None:
        if not self._ensure_initialized("update_match_apifootball"):
            return
        try:
            sets = []
            vals = []
            if apifb_home_team_id is not None:
                sets.append("apifb_home_team_id = ?")
                vals.append(apifb_home_team_id)
            if apifb_away_team_id is not None:
                sets.append("apifb_away_team_id = ?")
                vals.append(apifb_away_team_id)
            if apifb_fixture_id is not None:
                sets.append("apifb_fixture_id = ?")
                vals.append(apifb_fixture_id)
            if apifb_league_id is not None:
                sets.append("apifb_league_id = ?")
                vals.append(apifb_league_id)
            if apifb_season is not None:
                sets.append("apifb_season = ?")
                vals.append(apifb_season)
            if not sets:
                return
            vals.append(match_id)
            cursor = self._conn.cursor()
            cursor.execute(
                f"UPDATE matches SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()
        except Exception as e:
            self._log_error("update_match_apifootball", e)

    async def update_match_bzzoiro(
        self,
        match_id: int,
        bzzoiro_home_team_id: int | None = None,
        bzzoiro_away_team_id: int | None = None,
        bzzoiro_event_id: int | None = None,
        bzzoiro_league_id: int | None = None,
        bzzoiro_competition_code: str | None = None,
        prediction_data: str | None = None,
    ) -> None:
        if not self._ensure_initialized("update_match_bzzoiro"):
            return
        try:
            sets = []
            vals = []
            if bzzoiro_home_team_id is not None:
                sets.append("bzzoiro_home_team_id = ?")
                vals.append(bzzoiro_home_team_id)
            if bzzoiro_away_team_id is not None:
                sets.append("bzzoiro_away_team_id = ?")
                vals.append(bzzoiro_away_team_id)
            if bzzoiro_event_id is not None:
                sets.append("bzzoiro_event_id = ?")
                vals.append(bzzoiro_event_id)
            if bzzoiro_league_id is not None:
                sets.append("bzzoiro_league_id = ?")
                vals.append(bzzoiro_league_id)
            if bzzoiro_competition_code is not None:
                sets.append("bzzoiro_competition_code = ?")
                vals.append(bzzoiro_competition_code)
            if prediction_data is not None:
                sets.append("prediction_data = ?")
                vals.append(prediction_data)
            if not sets:
                return
            vals.append(match_id)
            cursor = self._conn.cursor()
            cursor.execute(
                f"UPDATE matches SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()
        except Exception as e:
            self._log_error("update_match_bzzoiro", e)
