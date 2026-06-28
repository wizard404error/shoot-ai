"""Base class for specialised storage classes.

Provides connection management, _ensure_initialized, and _log_error helpers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


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
