"""Bridge import handler — vendor data import from the desktop UI.

Follows the thin-dispatcher convention: async methods return JSON-serializable
dicts, the Bridge exposes them as @Slot delegators, and the frontend calls
them via QWebChannel (kawkab.import_season_directory(...)).

Delegates to the existing import services (SeasonImportService,
VendorTrackingImportService, VendorEventImportService) — one owner per
capability, no logic duplicated here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from kawkab.core.security import ErrorSanitizer
from kawkab.ui.bridge_handlers.base import BridgeHandlerBase

logger = logging.getLogger(__name__)


class ImportHandler(BridgeHandlerBase):
    """Vendor data import: season directories, tracking feeds, event files."""

    def __init__(self, bridge, services: dict[str, Any], rate_limiter=None) -> None:
        super().__init__(bridge, services, rate_limiter)

    @property
    def storage_service(self):
        return self._services.get("storage_service")

    def _err(self, exc: Exception) -> str:
        return ErrorSanitizer.sanitize_error(exc)

    # ── Season (bulk StatsBomb directory) ───────────────────────────────

    async def import_season_directory(
        self,
        directory: str,
        competition: str = "",
        season_id: int | None = None,
        max_matches: int | None = None,
    ) -> str:
        """Import every StatsBomb event file in a directory as one season.

        Progress is emitted on the bridge's importProgress signal after
        each file so the UI panel can show a live counter.
        """
        self._check_rate_limit()
        try:
            from kawkab.services.season_import_service import SeasonImportService

            svc = SeasonImportService(self.storage_service)
            done = {"n": 0}

            def _on_file(row: dict) -> None:
                done["n"] += 1
                self._bridge.importProgress.emit(float(done["n"]), str(row.get("file", "")))

            result = await svc.import_statsbomb_directory(
                directory,
                competition=competition or None,
                season_id=season_id,
                max_matches=max_matches,
                on_file_done=_on_file,
            )
            return json.dumps({"success": True, **result})
        except Exception as exc:
            logger.warning("season import failed: %s", exc)
            return json.dumps({"success": False, "error": self._err(exc)})

    # ── Vendor tracking feed (SkillCorner / EPTS / Metrica) ─────────────

    async def import_tracking_file(
        self,
        path: str,
        vendor: str = "",
        away_csv: str = "",
        match_name: str = "",
        home_team: str = "",
        away_team: str = "",
    ) -> str:
        self._check_rate_limit()
        try:
            from kawkab.core.security import SecurityValidator

            # Extension allowlist + allowlist-directory check before the
            # file is handed to any parser.
            SecurityValidator.validate_data_file_path(path)
            if away_csv:
                SecurityValidator.validate_data_file_path(away_csv)
            from kawkab.services.vendor_tracking_import_service import (
                VendorTrackingImportService,
            )

            svc = VendorTrackingImportService(self.storage_service)
            result = await svc.import_tracking_file(
                path,
                vendor=vendor or None,
                away_csv=away_csv or None,
                match_name=match_name or None,
                home_team=home_team or None,
                away_team=away_team or None,
            )
            return json.dumps({"success": True, **result})
        except Exception as exc:
            logger.warning("tracking import failed: %s", exc)
            return json.dumps({"success": False, "error": self._err(exc)})

    # ── Vendor events (Opta F24 / Wyscout) ──────────────────────────────

    async def import_event_file(
        self,
        path: str,
        f7_path: str = "",
        match_name: str = "",
        home_team: str = "",
        away_team: str = "",
    ) -> str:
        """Import an Opta F24 (with optional F7) or Wyscout event file."""
        self._check_rate_limit()
        try:
            from kawkab.core.security import SecurityValidator

            SecurityValidator.validate_data_file_path(path)
            if f7_path:
                SecurityValidator.validate_data_file_path(f7_path)
            from kawkab.services.vendor_event_import_service import (
                VendorEventImportService,
            )

            svc = VendorEventImportService(self.storage_service)
            p = Path(path)
            if p.suffix.lower() in (".f24", ".xml") or "f24" in p.name.lower():
                result = await svc.import_opta_f24(
                    path,
                    f7_path or None,
                    match_name=match_name or None,
                    home_team=home_team or None,
                    away_team=away_team or None,
                )
                result.setdefault("provider", "opta")
            else:
                result = await svc.import_wyscout(
                    path,
                    match_name=match_name or None,
                    home_team=home_team or None,
                    away_team=away_team or None,
                )
                result.setdefault("provider", "wyscout")
            return json.dumps({"success": True, **result})
        except Exception as exc:
            logger.warning("event import failed: %s", exc)
            return json.dumps({"success": False, "error": self._err(exc)})
