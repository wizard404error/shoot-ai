"""Profile storage — player profiles and face embeddings."""

from __future__ import annotations

from kawkab.core.logging import get_logger
from kawkab.services.storage.base import BaseStorage

try:
    from kawkab.core.security import SecurityValidator as _SecVal
    SecurityValidator = _SecVal
except ImportError:
    class _SecurityValidator:
        @staticmethod
        def sanitize_string(s, max_length=255): return str(s)[:max_length]
        @staticmethod
        def validate_jersey_number(j): return int(j)
        @staticmethod
        def validate_positive_float(v, n="v"): return max(0.0, float(v))
    SecurityValidator = _SecurityValidator()

logger = get_logger(__name__)


class ProfileStorage(BaseStorage):
    """CRUD for player profiles."""

    async def save_player_profile(self, profile: dict) -> int:
        if not self._ensure_initialized("save_player_profile"):
            return 0
        try:
            display_name = SecurityValidator.sanitize_string(str(profile.get("display_name", "")), max_length=100)
            team = SecurityValidator.sanitize_string(str(profile.get("team", "home")), max_length=50)
            preferred_position = SecurityValidator.sanitize_string(str(profile.get("preferred_position", "")), max_length=30)
            jersey_number = SecurityValidator.validate_jersey_number(profile.get("jersey_number", 0)) if profile.get("jersey_number") is not None else None
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO player_profiles (
                    global_id, display_name, jersey_number, preferred_position,
                    team, is_active, face_embedding, face_confidence
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    profile.get("global_id", ""),
                    display_name,
                    jersey_number,
                    preferred_position,
                    team,
                    profile.get("face_embedding"),
                    SecurityValidator.validate_positive_float(profile.get("face_confidence", 0.0), "face_confidence"),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_player_profile", e)
            return 0

    async def get_all_player_profiles(self) -> list[dict]:
        if not self._ensure_initialized("get_all_player_profiles"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT id, global_id, display_name, jersey_number, preferred_position, height_cm, weight_kg, dominant_foot, date_of_birth, nationality, photo_path, team, is_active, face_embedding, face_confidence, created_at, updated_at FROM player_profiles WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_all_player_profiles", e)
            return []

    async def update_player_profile_face(
        self, profile_id: int, face_embedding_json: str, face_confidence: float
    ) -> None:
        if not self._ensure_initialized("update_player_profile_face"):
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE player_profiles
                SET face_embedding = ?, face_confidence = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (face_embedding_json, face_confidence, profile_id),
            )
            self._conn.commit()
        except Exception as e:
            self._log_error("update_player_profile_face", e)
