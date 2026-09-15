"""Base class for specialised storage classes.

Provides connection management, _ensure_initialized, and _log_error helpers,
plus shared row-parsing helpers used by both storage backends.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


def parse_metadata_json(row: dict) -> dict:
    """Move a row's raw ``metadata_json`` string into ``metadata`` (dict).

    Used by every tracking-import read on both backends; malformed JSON
    degrades to an empty dict rather than raising (an unreadable provenance
    annotation must not kill the record it describes).
    """
    if isinstance(row.get("metadata_json"), str):
        try:
            row["metadata"] = json.loads(row["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            row["metadata"] = {}
    return row


class BaseStorage:
    """Base storage class with connection management helpers."""

    def __init__(self, storage: Any = None) -> None:
        self._storage = storage

    @property
    def _conn(self) -> sqlite3.Connection | None:
        if self._storage is not None:
            return self._storage._conn
        return getattr(self, "_conn_local", None)

    @_conn.setter
    def _conn(self, value: sqlite3.Connection | None) -> None:
        self._conn_local = value

    @property
    def _db_path(self) -> Path | None:
        if self._storage is not None:
            return self._storage._db_path
        return getattr(self, "_db_path_local", None)

    @_db_path.setter
    def _db_path(self, value: Path | None) -> None:
        self._db_path_local = value

    def _ensure_initialized(self, method_name: str) -> bool:
        if self._conn is None:
            logger.error(f"{method_name}: database not initialized")
            return False
        return True

    def _log_error(self, method_name: str, error: Exception) -> None:
        logger.error(f"{method_name}: {error}")
