"""Back-compat shim — wearables ingestion has moved to ``kawkab.services.wearables``.

This module re-exports the new :class:`WearableImportService` so that any
out-of-tree caller using the old import path keeps working. New code should
import from :mod:`kawkab.services.wearables` directly.

Kept as a thin file (rather than deleted) because the original had zero
in-tree consumers but may be referenced by external scripts, tutorials, or
plugins that load services by dotted path.
"""

from __future__ import annotations

from kawkab.services.wearables.models import WearableDataPoint, WearableSession
from kawkab.services.wearables.service import WearableImportService

__all__ = ["WearableImportService", "WearableDataPoint", "WearableSession"]
