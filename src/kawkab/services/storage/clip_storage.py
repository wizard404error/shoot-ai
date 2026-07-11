"""Clip storage — video clips and playlists."""

from __future__ import annotations

import json

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
        def sanitize_string(s, max_length=255): return str(s)[:max_length]
        @staticmethod
        def validate_positive_float(v, n="v"): return max(0.0, float(v))
    SecurityValidator = _SecurityValidator()

logger = get_logger(__name__)


class ClipStorage(BaseStorage):
    """CRUD for video clips and playlists."""

    async def save_clip(self, clip: dict) -> int:
        if not self._ensure_initialized("save_clip"):
            return 0
        try:
            SecurityValidator.validate_match_id(clip["match_id"])
            event_type = SecurityValidator.sanitize_string(str(clip["event_type"]), max_length=100)
            start_seconds = SecurityValidator.validate_positive_float(clip["start_seconds"], "start_seconds")
            end_seconds = SecurityValidator.validate_positive_float(clip["end_seconds"], "end_seconds")
            duration_seconds = SecurityValidator.validate_positive_float(clip["duration_seconds"], "duration_seconds")
            source_video_path = SecurityValidator.sanitize_string(str(clip["source_video_path"]), max_length=500)
            output_path = SecurityValidator.sanitize_string(str(clip["output_path"]), max_length=500)
            thumbnail_path = SecurityValidator.sanitize_string(str(clip.get("thumbnail_path", "")), max_length=500) if clip.get("thumbnail_path") else None
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO video_clips (
                    match_id, event_type, start_seconds, end_seconds, duration_seconds,
                    source_video_path, output_path, thumbnail_path, player_id, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clip["match_id"],
                    event_type,
                    start_seconds,
                    end_seconds,
                    duration_seconds,
                    source_video_path,
                    output_path,
                    thumbnail_path,
                    clip.get("player_id"),
                    SecurityValidator.sanitize_string(str(clip.get("description", "")), max_length=500),
                    clip.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_clip", e)
            return 0

    async def get_clips_for_match(self, match_id: int) -> list[dict]:
        if not self._ensure_initialized("get_clips_for_match"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id, match_id, event_type, start_seconds, end_seconds, duration_seconds, source_video_path, output_path, thumbnail_path, player_id, description, created_at FROM video_clips WHERE match_id = ? ORDER BY created_at DESC",
                (match_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_clips_for_match", e)
            return []

    async def save_playlist(self, playlist: dict) -> int:
        if not self._ensure_initialized("save_playlist"):
            return 0
        try:
            name = SecurityValidator.sanitize_string(str(playlist["name"]), max_length=200)
            clip_ids = playlist["clip_ids"]
            if not isinstance(clip_ids, list):
                raise ValueError("clip_ids must be a JSON array (list)")
            description = SecurityValidator.sanitize_string(str(playlist.get("description", "")), max_length=1000)
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO clip_playlists (
                    name, description, clip_ids, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    json.dumps(clip_ids),
                    playlist.get("created_at", ""),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_playlist", e)
            return 0

    async def get_playlists(self) -> list[dict]:
        if not self._ensure_initialized("get_playlists"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT id, name, description, clip_ids, created_at FROM clip_playlists ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_playlists", e)
            return []
