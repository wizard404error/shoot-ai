from __future__ import annotations

import csv
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WearableDataPoint:
    timestamp_s: float = 0.0
    heart_rate_bpm: Optional[float] = None
    speed_ms: Optional[float] = None
    distance_m: Optional[float] = None
    acceleration_ms2: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    cadence_rpm: Optional[float] = None
    power_w: Optional[float] = None


@dataclass
class WearableSession:
    device_type: str = ""
    device_serial: str = ""
    start_time: Optional[datetime] = None
    duration_s: float = 0.0
    data: list[WearableDataPoint] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "device_type": self.device_type,
            "device_serial": self.device_serial,
            "start_time": self.start_time.isoformat() if self.start_time else "",
            "duration_s": round(self.duration_s, 1),
            "point_count": len(self.data),
            "avg_hr": round(np.mean([d.heart_rate_bpm for d in self.data if d.heart_rate_bpm is not None]), 1) if self.data else 0,
            "max_hr": round(np.max([d.heart_rate_bpm for d in self.data if d.heart_rate_bpm is not None]), 1) if self.data else 0,
            "total_distance_m": round(np.sum([d.distance_m for d in self.data if d.distance_m is not None]), 1) if self.data else 0,
            "max_speed_ms": round(np.max([d.speed_ms for d in self.data if d.speed_ms is not None]), 2) if self.data else 0,
        }


class WearableImportService:
    def import_catapult_csv(self, file_path: str) -> str:
        try:
            session = WearableSession(device_type="catapult")
            with open(file_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dp = WearableDataPoint()
                    dp.timestamp_s = float(row.get("Timestamp (s)", row.get("time", 0)))
                    dp.speed_ms = self._parse_float(row.get("Speed (m/s)", row.get("speed", "")))
                    dp.heart_rate_bpm = self._parse_float(row.get("Heart Rate (bpm)", row.get("heart_rate", "")))
                    dp.distance_m = self._parse_float(row.get("Distance (m)", row.get("distance", "")))
                    dp.acceleration_ms2 = self._parse_float(row.get("Acceleration (m/s²)", row.get("acceleration", "")))
                    dp.cadence_rpm = self._parse_float(row.get("Cadence (rpm)", row.get("cadence", "")))
                    session.data.append(dp)
            if session.data:
                session.duration_s = session.data[-1].timestamp_s - session.data[0].timestamp_s
            return json.dumps({"session": session.to_dict(), "ok": True})
        except Exception as e:
            logger.error(f"import_catapult_csv failed: {e}")
            return json.dumps({"error": str(e)})

    def import_statsports_gpx(self, file_path: str) -> str:
        try:
            session = WearableSession(device_type="statsports")
            ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
            tree = ET.parse(file_path)
            root = tree.getroot()
            for trkpt in root.iter("{http://www.topografix.com/GPX/1/1}trkpt"):
                dp = WearableDataPoint()
                dp.latitude = self._parse_float(trkpt.get("lat"))
                dp.longitude = self._parse_float(trkpt.get("lon"))
                ele = trkpt.find("gpx:ele", ns) or trkpt.find("ele")
                if ele is not None and ele.text:
                    dp.altitude_m = self._parse_float(ele.text)
                time_el = trkpt.find("gpx:time", ns) or trkpt.find("time")
                if time_el is not None and time_el.text:
                    try:
                        dt = datetime.fromisoformat(time_el.text.replace("Z", "+00:00"))
                        dp.timestamp_s = dt.timestamp()
                        if session.start_time is None:
                            session.start_time = dt
                    except ValueError:
                        pass
                ext = trkpt.find("gpx:extensions", ns) or trkpt.find("extensions")
                if ext is not None:
                    hr = ext.find("{http://www.garmin.com/xmlschemas/TrackPointExtension/v1}hr") or ext.find("hr")
                    if hr is not None and hr.text:
                        dp.heart_rate_bpm = self._parse_float(hr.text)
                    spd = ext.find("{http://www.garmin.com/xmlschemas/SpeedExtension/v1}speed") or ext.find("speed")
                    if spd is not None and spd.text:
                        dp.speed_ms = self._parse_float(spd.text)
                session.data.append(dp)
            if session.data:
                session.duration_s = session.data[-1].timestamp_s - session.data[0].timestamp_s
            return json.dumps({"session": session.to_dict(), "ok": True})
        except Exception as e:
            logger.error(f"import_statsports_gpx failed: {e}")
            return json.dumps({"error": str(e)})

    def import_polar_hr_csv(self, file_path: str) -> str:
        try:
            session = WearableSession(device_type="polar")
            with open(file_path, "r") as f:
                content = f.read()
            lines = content.strip().split("\n")
            data_start = 0
            for i, line in enumerate(lines):
                if line.startswith("---") or line.startswith("Time"):
                    data_start = i + 1
                    break
            for line in lines[data_start:]:
                parts = line.split(",")
                if len(parts) < 2:
                    continue
                dp = WearableDataPoint()
                try:
                    time_parts = parts[0].strip().split(":")
                    if len(time_parts) == 3:
                        dp.timestamp_s = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
                    else:
                        dp.timestamp_s = float(parts[0].strip())
                except ValueError:
                    continue
                dp.heart_rate_bpm = self._parse_float(parts[1].strip())
                if len(parts) > 2:
                    dp.speed_ms = self._parse_float(parts[2].strip())
                session.data.append(dp)
            if session.data:
                session.duration_s = session.data[-1].timestamp_s - session.data[0].timestamp_s
            return json.dumps({"session": session.to_dict(), "ok": True})
        except Exception as e:
            logger.error(f"import_polar_hr_csv failed: {e}")
            return json.dumps({"error": str(e)})

    def import_auto(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            with open(file_path, "r") as f:
                header = f.readline().lower()
            if "heart rate" in header or "hr" in header:
                return self.import_polar_hr_csv(file_path)
            return self.import_catapult_csv(file_path)
        elif ext == ".gpx":
            return self.import_statsports_gpx(file_path)
        return json.dumps({"error": f"Unsupported file format: {ext}"})

    @staticmethod
    def _parse_float(val) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
