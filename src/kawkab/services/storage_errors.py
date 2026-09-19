"""Typed storage errors — A1 of the elite plan ("nothing lies").

History: storage methods swallowed every DB failure into 0/[]/False.
The proven damage: save_coding_tag's FK violation surfaced to the UI as
"Tag rejected: event_type/tag_type required" — the user was told their
input was wrong when the real cause was a missing match row (CI failure,
2026-09-19), and a Postgres deployment once returned empty data for every
call because the adapter's no-pool fallback silently fed [] to all reads.

Contract (applied cluster-by-cluster, coding tags first):

- "Not initialized / not connected" raises StorageNotInitialized — the
  caller must know the operation never ran.
- "The database refused / failed the operation" raises StorageWriteError
  or StorageReadError with the method name as context. Writes raise;
  reads raise too — an empty list is reserved for legitimate no-rows.
- "Rejected input" (invalid tag dict, no-op update) keeps the legacy
  falsy return so existing callers distinguish it from failure —
  rejection is a *contract*, failure is an *exception*.
"""

from __future__ import annotations


class StorageError(Exception):
    """Base class for all storage honesty errors."""


class StorageNotInitializedError(StorageError):
    """The storage backend has no usable connection (initialize/close)."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(
            f"storage not initialized: {operation} called with no open connection "
            "(service not initialized, already closed, or pool never came up)"
        )


class StorageWriteError(StorageError):
    """A write operation failed at the database level."""

    def __init__(self, operation: str, cause: Exception | str) -> None:
        self.operation = operation
        self.cause = cause
        super().__init__(f"{operation} failed: {cause}")


class StorageReadError(StorageError):
    """A read operation failed at the database level."""

    def __init__(self, operation: str, cause: Exception | str) -> None:
        self.operation = operation
        self.cause = cause
        super().__init__(f"{operation} failed: {cause}")
