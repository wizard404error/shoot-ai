"""Wearables ingestion sub-package for Kawkab AI.

Vendor parsers convert proprietary wearable exports (Catapult, STATSports,
Polar, FIT, TCX, GPX) into a unified :class:`WearableSession`. The
:class:`WearableImportService` facade auto-detects the format and dispatches
to the right parser.

Architecture::

    file ─► detect_parser() ─► VendorParser.parse() ─► WearableSession
                                                          │
                                  ┌───────────────────────┴────────────┐
                                  ▼                                    ▼
                          metrics.py (PlayerLoad,            storage (cycle C10)
                          HSR, sprint, ACWR, ...)
                                  │
                                  ▼
                          fusion/ (cycle C8-C9, time-sync with video)

Currently implemented parsers:
- CatapultCsvParser (OpenField 10Hz sensor export)
- StatsportsGpxParser (Sonra GPX)
- PolarHrCsvParser (Polar HR CSV)
- FitParser (FIT binary, via fitdecode — Catapult/Polar/Garmin)
- TcxParser (TCX XML — Polar/Garmin/older devices)

Pending (cycles C4–C5):
- statsports_csv.py    (Sonra CSV/XML aggregate export)
- statsports_xml.py
- polar_pro.py         (Polar Team Pro full export)
- wimu.py              (RealTrack WIMU)

Public API re-exported below; import from ``kawkab.services.wearables``.
"""

from kawkab.services.wearables.auto import detect_parser  # noqa: E402
from kawkab.services.wearables.base import BaseWearableParser
from kawkab.services.wearables.catapult_csv import CatapultCsvParser
from kawkab.services.wearables.fit_parser import FitParser
from kawkab.services.wearables.models import WearableDataPoint, WearableSession
from kawkab.services.wearables.polar_hr import PolarHrCsvParser
from kawkab.services.wearables.service import WearableImportService
from kawkab.services.wearables.statsports_csv import StatsportsCsvParser
from kawkab.services.wearables.statsports_gpx import StatsportsGpxParser
from kawkab.services.wearables.tcx_parser import TcxParser

__all__ = [
    "BaseWearableParser",
    "CatapultCsvParser",
    "StatsportsGpxParser",
    "StatsportsCsvParser",
    "PolarHrCsvParser",
    "FitParser",
    "TcxParser",
    "WearableImportService",
    "WearableDataPoint",
    "WearableSession",
    "detect_parser",
]
