"""Audit service for structured event logging.

Provides persistent audit trail for analysis, export, feedback, and
configuration changes. Events are stored in the audit_events table
via StorageService.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any


class AuditService:
    """Structured audit logging backed by StorageService.

    Logs meaningful actions with timestamps so operators can trace
    what happened, when, and by whom.
    """

    VALID_ACTIONS = frozenset({
        "analysis.started", "analysis.completed", "analysis.failed",
        "export.csv", "export.json", "export.pdf", "export.statsbomb",
        "event.created", "event.updated", "event.deleted",
        "match.imported", "match.deleted",
        "feedback.submitted",
        "config.changed",
    })

    def __init__(self, storage_service: Any = None) -> None:
        self._storage = storage_service

    def log_event(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        details: dict | None = None,
        user: str = "local",
    ) -> int:
        """Persist an audit event.

        Returns the row id of the inserted record, or 0 on failure.
        """
        if self._storage is None or self._storage._conn is None:
            return 0
        try:
            cursor = self._storage._conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events (action, entity_type, entity_id, details_json, user)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action, entity_type, entity_id, json.dumps(details or {}), user),
            )
            self._storage._conn.commit()
            return cursor.lastrowid or 0
        except Exception:
            return 0

    def get_events(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit events with optional filters."""
        if self._storage is None or self._storage._conn is None:
            return []
        cursor = self._storage._conn.cursor()
        sql = "SELECT * FROM audit_events WHERE 1=1"
        params: list[Any] = []
        if action:
            sql += " AND action = ?"
            params.append(action)
        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        try:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """Get audit statistics.

        Returns:
            dict with keys: total_events, events_last_24h, by_action, by_type
        """
        if self._storage is None or self._storage._conn is None:
            return {"total_events": 0, "events_last_24h": 0, "by_action": {}, "by_type": {}}
        cursor = self._storage._conn.cursor()
        stats: dict[str, Any] = {}
        try:
            cursor.execute("SELECT COUNT(*) FROM audit_events")
            stats["total_events"] = cursor.fetchone()[0]
        except Exception:
            stats["total_events"] = 0

        try:
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM audit_events WHERE timestamp >= ?", (cutoff,)
            )
            stats["events_last_24h"] = cursor.fetchone()[0]
        except Exception:
            stats["events_last_24h"] = 0

        try:
            cursor.execute(
                "SELECT action, COUNT(*) AS cnt FROM audit_events GROUP BY action ORDER BY cnt DESC"
            )
            stats["by_action"] = {row["action"]: row["cnt"] for row in cursor.fetchall()}
        except Exception:
            stats["by_action"] = {}

        try:
            cursor.execute(
                "SELECT entity_type, COUNT(*) AS cnt FROM audit_events GROUP BY entity_type ORDER BY cnt DESC"
            )
            stats["by_type"] = {row["entity_type"]: row["cnt"] for row in cursor.fetchall()}
        except Exception:
            stats["by_type"] = {}

        return stats
