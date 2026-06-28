"""Event storage — CRUD for match events, advanced metrics, corrections."""

from __future__ import annotations

import json
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
        def validate_event_type(e): return str(e)
        @staticmethod
        def validate_event_dict(e): return e
        @staticmethod
        def validate_track_id(t): return int(t)
        @staticmethod
        def sanitize_string(s, max_length=255): return str(s)[:max_length]
        @staticmethod
        def validate_positive_float(v, n="v"): return max(0.0, float(v))
    SecurityValidator = _SecurityValidator()

logger = get_logger(__name__)


class EventStorage(BaseStorage):
    """CRUD for match events, advanced metrics, and corrections."""

    async def save_event(self, match_id: int, event: dict) -> int:
        if not self._ensure_initialized("save_event"):
            return 0
        try:
            SecurityValidator.validate_match_id(match_id)
            SecurityValidator.validate_event_dict(event)
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (
                    match_id, event_type, timestamp, from_track_id, to_track_id,
                    team, completed, confidence, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    event["type"],
                    event["timestamp"],
                    event.get("from_track_id"),
                    event.get("to_track_id"),
                    event.get("team"),
                    event.get("completed", False),
                    event.get("confidence", 0.0),
                    json.dumps(event.get("metadata", {})),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_event", e)
            return 0

    async def save_events_bulk(self, match_id: int, events: list[dict]) -> int:
        if not self._ensure_initialized("save_events_bulk"):
            return 0
        try:
            SecurityValidator.validate_match_id(match_id)
            cursor = self._conn.cursor()
            rows = []
            for event in events:
                SecurityValidator.validate_event_dict(event)
                rows.append((
                    match_id,
                    event["type"],
                    event["timestamp"],
                    event.get("from_track_id"),
                    event.get("to_track_id"),
                    event.get("team"),
                    event.get("completed", False),
                    event.get("confidence", 0.0),
                    json.dumps(event.get("metadata", {})),
                ))
            cursor.executemany(
                """
                INSERT INTO events (
                    match_id, event_type, timestamp, from_track_id, to_track_id,
                    team, completed, confidence, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._conn.commit()
            return len(rows)
        except Exception as e:
            self._log_error("save_events_bulk", e)
            return 0

    async def get_match_events(self, match_id: int) -> list[dict]:
        if not self._ensure_initialized("get_match_events"):
            return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE match_id = ? ORDER BY timestamp",
                (match_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self._log_error("get_match_events", e)
            return []

    async def update_event(self, event_id: int, updates: dict) -> bool:
        if not self._ensure_initialized("update_event"):
            return False
        allowed = {"event_type", "team", "from_track_id", "to_track_id",
                    "completed", "confidence", "metadata"}
        try:
            SecurityValidator.validate_match_id(event_id)
            sets = []
            vals = []
            for key, val in updates.items():
                if key in allowed:
                    col = key
                    if key == "event_type":
                        SecurityValidator.validate_event_type(val)
                    elif key == "team":
                        val = SecurityValidator.sanitize_string(str(val), max_length=50)
                    elif key in ("from_track_id", "to_track_id"):
                        if val is not None:
                            SecurityValidator.validate_track_id(val)
                    elif key == "completed":
                        val = bool(val)
                    elif key == "confidence":
                        SecurityValidator.validate_positive_float(val, "confidence")
                    elif key == "metadata" and isinstance(val, dict):
                        val = json.dumps(val)
                    sets.append(f"{col} = ?")
                    vals.append(val)
            if not sets:
                return False
            sets.append("user_corrected = 1")
            vals.append(event_id)
            cursor = self._conn.cursor()
            cursor.execute(
                f"UPDATE events SET {', '.join(sets)} WHERE id = ?", vals
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            self._log_error("update_event", e)
            return False

    async def delete_event(self, event_id: int) -> bool:
        if not self._ensure_initialized("delete_event"):
            return False
        try:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            self._log_error("delete_event", e)
            return False

    async def save_advanced_metrics(
        self,
        match_id: int,
        metric_name: str,
        metric_value: float,
        metric_category: str = "",
        player_id: int | None = None,
        pitch_zone: str = "",
        timestamp: float | None = None,
        metadata: dict | None = None,
    ) -> int:
        if not self._ensure_initialized("save_advanced_metrics"):
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO advanced_metrics (
                    match_id, player_id, metric_name, metric_value,
                    metric_category, pitch_zone, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    player_id,
                    metric_name,
                    metric_value,
                    metric_category,
                    pitch_zone,
                    timestamp,
                    json.dumps(metadata or {}),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_advanced_metrics", e)
            return 0

    async def save_advanced_metrics_bulk(
        self, match_id: int, metrics: list[dict]
    ) -> int:
        if not self._ensure_initialized("save_advanced_metrics_bulk"):
            return 0
        try:
            cursor = self._conn.cursor()
            rows = []
            for m in metrics:
                rows.append((
                    match_id,
                    m.get("player_id"),
                    m["metric_name"],
                    m["metric_value"],
                    m.get("metric_category", ""),
                    m.get("pitch_zone", ""),
                    m.get("timestamp"),
                    json.dumps(m.get("metadata", {})),
                ))
            cursor.executemany(
                """
                INSERT INTO advanced_metrics (
                    match_id, player_id, metric_name, metric_value,
                    metric_category, pitch_zone, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._conn.commit()
            return len(rows)
        except Exception as e:
            self._log_error("save_advanced_metrics_bulk", e)
            return 0

    async def save_correction(
        self,
        event_id: int,
        correction_type: str,
        original_value: Any,
        corrected_value: Any,
    ) -> int:
        if not self._ensure_initialized("save_correction"):
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_corrections (
                    event_id, correction_type, original_value, corrected_value
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    event_id,
                    correction_type,
                    json.dumps(original_value),
                    json.dumps(corrected_value),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid or 0
        except Exception as e:
            self._log_error("save_correction", e)
            return 0
