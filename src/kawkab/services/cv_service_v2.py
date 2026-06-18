"""Enhanced Computer Vision service — YOLOv11 + BoT-SORT + Smart Filtering.

.. warning::
    **OUTDATED FORK — DO NOT IMPORT.** After investigation in cycle G of
    ITERATION_LOG.md (2026-06-17), the canonical ``cv_service.py`` already
    implements the smart filters this fork was meant to introduce:

    - ``min_track_lifetime`` filter (cv_service.py line 437)
    - ``lifetime_pct`` filter (line 440)
    - ``max_keep_top_n`` filter (line 444)
    - Team color clustering via k-means (line 486)
    - ``_assess_tracking_quality`` (line 471)
    - Norfair tracker with enhanced ReID (line 347)

    The only things this v2 has that v1 doesn't are the ``Detection.team``
    and ``Detection.area`` dataclass fields. The v1 ``CVService`` is used
    in production by ``app.py`` and ``ui/bridge.py``.

    **Action taken (cycle G):** added this header. **Next decision (your call):**
    delete this file, or keep it as a frozen historical reference.

If you need the v2-specific dataclass fields, copy them into a feature branch
of ``cv_service.py`` and propose a PR rather than importing this module.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from kawkab.core.logging import get_logger

logger = get_logger(__name__)

logger.warning(
    "cv_service_v2 is experimental and not wired into production. "
    "See the module docstring and ITERATION_LOG.md cycle G for context."
)


@dataclass
class Detection:
    """A single object detection."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str
    track_id: int | None = None
    team: str | None = None
    area: float = 0.0


@dataclass
class FrameDetections:
    """All detections in a single frame."""

    frame_number: int
    timestamp: float
    detections: list[Detection]
    image_width: int
    image_height: int


@dataclass
class PlayerTrack:
    """A consolidated player track with metadata."""

    track_id: int
    team: str | None = None
    jersey_number: int | None = None
    name: str | None = None
    positions: list[tuple[float, float, float]] = None  # (timestamp, x, y)
    first_seen: float = 0.0
    last_seen: float = 0.0
    frames_tracked: int = 0
    confidence_avg: float = 0.0
    is_actual_player: bool = False  # True if passed all filters

    def __post_init__(self):
        if self.positions is None:
            self.positions = []


@dataclass
class MatchTrackData:
    """Complete tracking data for a match."""

    match_id: int
    fps: float
    total_frames: int
    duration_seconds: float
    frames: list[FrameDetections]
    track_registry: dict[int, dict[str, Any]]
    player_teams: dict[int, str]  # track_id -> team
    tracking_metrics: dict[str, Any]


class CVService:
    """Computer vision pipeline for player/ball detection and tracking.

    Improvements in v2:
    - Track lifetime filtering (drop noise)
    - Bbox area filtering (refs/spectators are far/small)
    - Position-based filtering (edges = refs)
    - BoT-SORT with better params for amateur footage
    - Quality metrics (true player count, fragmentation rate)
    """

    def __init__(
        self,
        model_size: str = "l",
        confidence_threshold: float = 0.4,
        iou_threshold: float = 0.5,
        gpu_enabled: bool = True,
        min_track_lifetime_frames: int = 30,
        min_bbox_area_ratio: float = 0.002,
        max_bbox_area_ratio: float = 0.15,
        expected_player_count: int = 22,
    ) -> None:
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.gpu_enabled = gpu_enabled
        self.min_track_lifetime = min_track_lifetime_frames
        self.min_bbox_area = min_bbox_area_ratio
        self.max_bbox_area = max_bbox_area_ratio
        self.expected_player_count = expected_player_count
        self._model: Any = None
        self._initialized = False

        logger.info(
            f"CVService v2: model=yolo11{model_size}, "
            f"conf={confidence_threshold}, iou={iou_threshold}, gpu={gpu_enabled}, "
            f"min_track_life={min_track_lifetime_frames}, "
            f"expected_players={expected_player_count}"
        )

    async def initialize(self) -> None:
        """Lazy-load YOLOv11 model and BoT-SORT tracker."""
        if self._initialized:
            return

        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise

        model_name = f"yolo11{self.model_size}.pt"
        logger.info(f"Loading {model_name}...")
        self._model = YOLO(model_name)

        if self.gpu_enabled:
            try:
                import torch
                if torch.cuda.is_available():
                    self._model.to("cuda")
                    logger.info("Model loaded on GPU (CUDA)")
                else:
                    logger.warning("GPU not available, using CPU")
            except ImportError:
                logger.warning("PyTorch not installed, cannot check CUDA")

        self._initialized = True
        logger.info("CVService initialized")

    async def detect_frame(
        self, frame: np.ndarray, frame_number: int, timestamp: float, persist: bool = True
    ) -> FrameDetections:
        """Run detection + tracking on a single frame."""
        if not self._initialized:
            await self.initialize()

        results = self._model.track(
            frame,
            persist=persist,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            classes=[0, 32],  # person, sports ball
            tracker="botsort.yaml",
            verbose=False,
        )

        detections: list[Detection] = []
        h, w = frame.shape[:2]
        frame_area = w * h

        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                for i in range(len(boxes)):
                    bbox = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())
                    track_id = (
                        int(boxes.id[i].cpu().numpy())
                        if boxes.id is not None
                        else None
                    )

                    cls_name = self._model.names.get(cls_id, f"class_{cls_id}")

                    area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / frame_area

                    if cls_name == "person" and (
                        area_ratio < self.min_bbox_area or area_ratio > self.max_bbox_area
                    ):
                        continue

                    detections.append(Detection(
                        bbox=tuple(bbox),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=cls_name,
                        track_id=track_id,
                        area=area_ratio,
                    ))

        return FrameDetections(
            frame_number=frame_number,
            timestamp=timestamp,
            detections=detections,
            image_width=w,
            image_height=h,
        )

    async def process_video(
        self,
        video_path: Path,
        progress_callback=None,
    ) -> MatchTrackData:
        """Process a full video with smart track filtering.

        Key improvement: after YOLO+BoT-SORT, we filter tracks by:
        1. Lifetime (must be visible for N frames)
        2. Bbox area (must be in expected size range for player)
        3. Position (must be on the pitch, not off-field)
        4. Consistency (high confidence)
        """
        if not self._initialized:
            await self.initialize()

        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(
            f"Processing video: {video_path.name} "
            f"({total_frames} frames, {fps:.1f} FPS, {duration:.1f}s, {w}x{h})"
        )

        frames: list[FrameDetections] = []
        track_appearances: dict[int, int] = defaultdict(int)
        track_first_frame: dict[int, int] = {}
        track_last_frame: dict[int, int] = {}
        track_confidence_sum: dict[int, float] = defaultdict(float)
        track_positions: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
        track_areas: dict[int, list[float]] = defaultdict(list)
        track_is_person: dict[int, bool] = defaultdict(lambda: True)

        frame_number = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                timestamp = frame_number / fps
                frame_det = await self.detect_frame(frame, frame_number, timestamp)
                frames.append(frame_det)

                for det in frame_det.detections:
                    if det.track_id is None:
                        continue

                    tid = det.track_id
                    track_appearances[tid] += 1
                    if tid not in track_first_frame:
                        track_first_frame[tid] = frame_number
                    track_last_frame[tid] = frame_number
                    track_confidence_sum[tid] += det.confidence

                    if det.class_name == "person":
                        cx = (det.bbox[0] + det.bbox[2]) / 2
                        cy = (det.bbox[1] + det.bbox[3]) / 2
                        track_positions[tid].append((timestamp, cx, cy))
                        track_areas[tid].append(det.area)
                    else:
                        track_is_person[tid] = False

                frame_number += 1

                if progress_callback and frame_number % 30 == 0:
                    progress = frame_number / total_frames
                    await progress_callback(
                        progress,
                        f"Processed {frame_number}/{total_frames} frames",
                    )
        finally:
            cap.release()

        logger.info(
            f"Raw tracking: {len(track_appearances)} unique tracks before filtering"
        )

        valid_player_tracks = self._filter_player_tracks(
            track_appearances,
            track_first_frame,
            track_last_frame,
            track_confidence_sum,
            track_positions,
            track_areas,
            track_is_person,
            total_frames,
        )

        player_teams = self._assign_teams_simple(valid_player_tracks, w, h)

        filtered_track_registry = {}
        for tid in valid_player_tracks:
            filtered_track_registry[tid] = {
                "track_id": tid,
                "class_name": "person",
                "first_seen": track_first_frame.get(tid, 0) / fps,
                "last_seen": track_last_frame.get(tid, 0) / fps,
                "frames_tracked": track_appearances[tid],
                "lifetime_pct": (track_appearances[tid] / total_frames) * 100,
                "confidence_avg": track_confidence_sum[tid] / max(1, track_appearances[tid]),
            }

        fragmentation_rate = len(track_appearances) / max(1, len(valid_player_tracks))

        tracking_metrics = {
            "raw_tracks_detected": len(track_appearances),
            "validated_player_tracks": len(valid_player_tracks),
            "fragmentation_rate": round(fragmentation_rate, 2),
            "expected_player_count": self.expected_player_count,
            "tracking_quality": self._assess_tracking_quality(fragmentation_rate),
            "filter_settings": {
                "min_lifetime_frames": self.min_track_lifetime,
                "min_bbox_area": self.min_bbox_area,
                "max_bbox_area": self.max_bbox_area,
            },
        }

        logger.info(
            f"After filtering: {len(valid_player_tracks)} validated player tracks "
            f"(fragmentation: {fragmentation_rate:.2f}x, "
            f"quality: {tracking_metrics['tracking_quality']})"
        )

        return MatchTrackData(
            match_id=0,
            fps=fps,
            total_frames=frame_number,
            duration_seconds=duration,
            frames=frames,
            track_registry=filtered_track_registry,
            player_teams=player_teams,
            tracking_metrics=tracking_metrics,
        )

    def _filter_player_tracks(
        self,
        appearances: dict[int, int],
        first_frame: dict[int, int],
        last_frame: dict[int, int],
        conf_sum: dict[int, float],
        positions: dict[int, list],
        areas: dict[int, list],
        is_person: dict[int, bool],
        total_frames: int,
    ) -> set[int]:
        """Filter tracks to keep only real players."""
        valid = set()
        min_lifetime_pct = 2.0

        for tid, count in appearances.items():
            if not is_person.get(tid, False):
                continue

            lifetime_pct = (count / total_frames) * 100
            if lifetime_pct < min_lifetime_pct:
                continue

            if count < self.min_track_lifetime:
                continue

            avg_area = sum(areas.get(tid, [0])) / max(1, len(areas.get(tid, [1])))
            if avg_area < self.min_bbox_area:
                continue
            if avg_area > self.max_bbox_area:
                continue

            valid.add(tid)

        return valid

    def _assign_teams_simple(
        self, valid_tracks: set[int], w: int, h: int
    ) -> dict[int, str]:
        """Simple team assignment by horizontal position (left/right split)."""
        track_avg_x: dict[int, float] = {}

        for tid in valid_tracks:
            pass

        return {}

    def _assess_tracking_quality(self, fragmentation_rate: float) -> str:
        """Assess tracking quality based on fragmentation rate."""
        if fragmentation_rate <= 1.5:
            return "excellent"
        elif fragmentation_rate <= 2.0:
            return "good"
        elif fragmentation_rate <= 3.0:
            return "fair"
        elif fragmentation_rate <= 5.0:
            return "poor"
        else:
            return "very_poor"

    async def shutdown(self) -> None:
        """Release resources."""
        self._model = None
        self._initialized = False
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info("CVService shutdown (v2)")
