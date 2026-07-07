"""Audit service for structured event logging.

Provides persistent audit trail for analysis, export, feedback, and
configuration changes. Events are stored in the audit_events table
via StorageService.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


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
        "read", "data.erased", "data.archived",
    })

    def __init__(self, storage_service: Any = None) -> None:
        self._storage = storage_service
        if self._storage is not None:
            self._ensure_schema()

    # ── Hash chain ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(event_dict: dict) -> str:
        """Compute SHA-256 hash of a canonical event string.

        The canonical form concatenates the seven core fields with pipe
        separators. Missing keys default to empty string.
        """
        canon = "|".join([
            str(event_dict.get("action", "")),
            str(event_dict.get("entity_type", "")),
            str(event_dict.get("entity_id", "")),
            json.dumps(
                event_dict.get("details", event_dict.get("details_json", {})),
                sort_keys=True,
                default=str,
            ),
            str(event_dict.get("user", "")),
            str(event_dict.get("timestamp", "")),
            str(event_dict.get("prev_hash", "")),
        ])
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def _get_last_hash(self) -> str:
        """Return the SHA-256 hash of the most recent audit event.

        Returns an empty string when the table is empty or unreachable.
        """
        if self._storage is None or self._storage._conn is None:
            return ""
        try:
            cursor = self._storage._conn.cursor()
            cursor.execute(
                "SELECT id, action, entity_type, entity_id, "
                "details_json, user, timestamp, prev_hash "
                "FROM audit_events ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row is None:
                return ""
            return self._compute_hash(dict(row))
        except Exception:
            return ""

    def _ensure_schema(self) -> None:
        """Add ``prev_hash`` column if it does not already exist."""
        if self._storage is None or self._storage._conn is None:
            return
        try:
            cursor = self._storage._conn.cursor()
            cursor.execute(
                "ALTER TABLE audit_events ADD COLUMN prev_hash TEXT DEFAULT ''"
            )
            self._storage._conn.commit()
            logger.info("Added prev_hash column to audit_events")
        except Exception:
            pass

    # ── Core logging ────────────────────────────────────────────────────

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
            prev_hash = self._get_last_hash()
            cursor = self._storage._conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events
                    (action, entity_type, entity_id, details_json, user, prev_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (action, entity_type, entity_id, json.dumps(details or {}), user, prev_hash),
            )
            self._storage._conn.commit()
            return cursor.lastrowid or 0
        except Exception:
            return 0

    def log_read(
        self,
        entity_type: str,
        entity_id: str | None = None,
        user: str = "local",
    ) -> int:
        """Log a read / view action on an entity."""
        return self.log_event("read", entity_type, entity_id, user=user)

    # ── Queries ─────────────────────────────────────────────────────────

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

    # ── DSAR (Data Subject Access Request) ──────────────────────────────

    def get_user_data(self, user_id: str) -> dict:
        """Return all data associated with a user across known tables.

        This is intended for Data Subject Access Requests (GDPR Art. 15).
        Returns a dictionary of table_name -> list of rows.
        """
        result: dict[str, list[dict]] = {}

        if self._storage is None or self._storage._conn is None:
            return result

        cursor = self._storage._conn.cursor()

        # Primary: audit_events
        try:
            cursor.execute(
                "SELECT * FROM audit_events WHERE user = ? ORDER BY id DESC",
                (user_id,),
            )
            rows = [dict(r) for r in cursor.fetchall()]
            if rows:
                result["audit_events"] = rows
        except Exception:
            pass

        # Known user-related tables (safe-fail if table / column missing)
        _queries: list[tuple[str, str, list[Any]]] = [
            ("coach_feedback", "SELECT * FROM coach_feedback WHERE coach_id = ?", [user_id]),
            ("collab_comments", "SELECT * FROM collab_comments WHERE username = ?", [user_id]),
            ("collab_mentions", "SELECT * FROM collab_mentions WHERE username = ? OR from_user = ?", [user_id, user_id]),
            ("collab_users", "SELECT * FROM collab_users WHERE username = ?", [user_id]),
        ]

        for table, sql, params in _queries:
            try:
                cursor.execute(sql, params)
                rows = [dict(r) for r in cursor.fetchall()]
                if rows:
                    result[table] = rows
            except Exception:
                pass

        return result

    # ── Retention policy ───────────────────────────────────────────────

    def apply_retention_policy(self, retention_days: int = 365) -> int:
        """Archive events older than *retention_days* and delete from active table.

        Archived events are written to a JSON file under
        ``<db_parent>/audit_archive_<date>.json``.

        Returns the number of archived events, or 0 on failure.
        """
        if self._storage is None or self._storage._conn is None:
            return 0

        try:
            cursor = self._storage._conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()

            cursor.execute(
                "SELECT * FROM audit_events WHERE timestamp < ? ORDER BY id",
                (cutoff,),
            )
            old_rows = [dict(r) for r in cursor.fetchall()]
            if not old_rows:
                return 0

            # Lazy paths import to avoid circular / eager deps
            from kawkab.core.paths import get_paths

            archive_dir = get_paths().database.parent if get_paths().database else Path(".")
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_name = f"audit_archive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            archive_path = archive_dir / archive_name

            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(old_rows, f, default=str, indent=2)

            count = len(old_rows)
            min_id = old_rows[0]["id"]
            max_id = old_rows[-1]["id"]

            cursor.execute(
                "DELETE FROM audit_events WHERE id BETWEEN ? AND ?",
                (min_id, max_id),
            )
            self._storage._conn.commit()

            logger.info(
                "Archived %d audit event(s) to %s", count, archive_path
            )
            return count
        except Exception:
            return 0

    # ── Right to erasure ───────────────────────────────────────────────

    def erase_user_data(self, user_id: str) -> bool:
        """Anonymise all references to *user_id* across the audit trail.

        Replaces the ``user`` field with ``"erased_user"`` in every matching
        audit event.  The events themselves are preserved so the integrity of
        the audit log is maintained (GDPR Art. 17 — right to erasure
        compatible with Art. 5(1)(e) retention requirements).

        Returns ``True`` if at least one row was updated, ``False`` otherwise.
        """
        if self._storage is None or self._storage._conn is None:
            return False

        try:
            cursor = self._storage._conn.cursor()
            cursor.execute(
                "UPDATE audit_events SET user = 'erased_user' WHERE user = ?",
                (user_id,),
            )
            self._storage._conn.commit()
            updated = cursor.rowcount

            # Also try known collab tables so the erasure is thorough
            try:
                cursor.execute(
                    "UPDATE collab_comments SET username = 'erased_user' WHERE username = ?",
                    (user_id,),
                )
                self._storage._conn.commit()
            except Exception:
                pass

            try:
                cursor.execute(
                    "UPDATE collab_mentions SET username = 'erased_user' WHERE username = ?",
                    (user_id,),
                )
                self._storage._conn.commit()
            except Exception:
                pass

            try:
                cursor.execute(
                    "UPDATE collab_mentions SET from_user = 'erased_user' WHERE from_user = ?",
                    (user_id,),
                )
                self._storage._conn.commit()
            except Exception:
                pass

            try:
                cursor.execute(
                    "UPDATE coach_feedback SET coach_id = 'erased_user' WHERE coach_id = ?",
                    (user_id,),
                )
                self._storage._conn.commit()
            except Exception:
                pass

            if updated > 0:
                logger.info("Erased user data for '%s' (%d audit row(s))", user_id, updated)

            return updated > 0
        except Exception:
            return False
