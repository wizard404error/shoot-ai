"""Computer Vision service - YOLOv11 + BoT-SORT + ReID.

Handles player, ball, and referee detection + tracking.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from kawkab.core.logging import get_logger

try:
    from kawkab.services.norfair_tracker import NorfairTracker
    _NORFAIR_AVAILABLE = True
except ImportError:
    _NORFAIR_AVAILABLE = False
    NorfairTracker = None  # type: ignore

logger = get_logger(__name__)


@dataclass
class Detection:
    """A single object detection."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str
    track_id: int | None = None


@dataclass
class FrameDetections:
    """All detections in a single frame."""

    frame_number: int
    timestamp: float  # seconds
    detections: list[Detection]
    image_width: int
    image_height: int


@dataclass
class MatchTrackData:
    """Complete tracking data for a match."""

    match_id: int
    fps: float
    total_frames: int
    duration_seconds: float
    frames: list[FrameDetections]
    track_registry: dict[int, dict[str, Any]]
    player_teams: dict[int, str] = field(default_factory=dict)
    tracking_metrics: dict[str, Any] = field(default_factory=dict)
    match_type: str = "unknown"

    def swap_teams(self) -> None:
        """Swap home/away assignments for all players.

        Useful when the team color clustering heuristic got the labels wrong.
        After calling this, possession/formation stats will be flipped.
        """
        self.player_teams = {
            tid: ("away" if team == "home" else "home" if team == "away" else team)
            for tid, team in self.player_teams.items()
        }
        if "team_detection" in self.tracking_metrics:
            td = self.tracking_metrics["team_detection"]
            if "home_avg_bgr" in td and "away_avg_bgr" in td:
                td["home_avg_bgr"], td["away_avg_bgr"] = (
                    td["away_avg_bgr"],
                    td["home_avg_bgr"],
                )
            if "home_size" in td and "away_size" in td:
                td["home_size"], td["away_size"] = td["away_size"], td["home_size"]


class CVService:
    """Computer vision pipeline for player/ball detection and tracking.

    v2 improvements:
    - Smart track filtering (min lifetime, bbox area)
    - Bbox area-based filtering for refs/spectators
    - Tracking quality metrics
    - Better noise reduction
    """

    def __init__(
        self,
        model_size: str = "l",
        confidence_threshold: float = 0.4,
        ball_confidence_threshold: float = 0.15,
        iou_threshold: float = 0.5,
        gpu_enabled: bool = True,
        min_track_lifetime_frames: int = 30,
        min_bbox_area_ratio: float = 0.002,
        max_bbox_area_ratio: float = 0.15,
        expected_player_count: int = 22,
        max_keep_top_n: int = 28,
        model_manager=None,
    ) -> None:
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.ball_confidence_threshold = ball_confidence_threshold
        self.iou_threshold = iou_threshold
        self.gpu_enabled = gpu_enabled
        self.min_track_lifetime = min_track_lifetime_frames
        self.min_bbox_area = min_bbox_area_ratio
        self.max_bbox_area = max_bbox_area_ratio
        self.expected_player_count = expected_player_count
        self.max_keep_top_n = max_keep_top_n
        self._model: Any = None
        self._initialized = False
        self._model_manager = model_manager

        logger.info(
            f"CVService v2: model=yolo11{model_size}, "
            f"conf={confidence_threshold} ball_conf={ball_confidence_threshold}, "
            f"iou={iou_threshold}, gpu={gpu_enabled}, "
            f"min_track_life={min_track_lifetime_frames}, "
            f"max_keep={max_keep_top_n or 'unlimited'}, "
            f"lazy_model={model_manager is not None}"
        )

    async def initialize(self, progress_callback=None) -> None:
        """Lazy-load YOLOv11 model and BoT-SORT tracker.

        Args:
            progress_callback: Called with (progress, message) during model download
        """
        if self._initialized:
            return

        try:
            from ultralytics import YOLO
        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise

        model_name = f"yolo11{self.model_size}.pt"
        logger.info(f"Loading {model_name}...")

        # Use ModelManager for lazy loading if available
        if self._model_manager is not None:
            try:
                model_path = self._model_manager.ensure_model(
                    f"yolo11{self.model_size}",
                    progress_callback=progress_callback,
                )
                logger.info(f"Loading model from {model_path}")
                self._model = YOLO(str(model_path))
            except Exception as e:
                logger.warning(f"ModelManager failed ({e}), falling back to direct YOLO load")
                self._model = YOLO(model_name)
        else:
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
        self, frame: np.ndarray, frame_number: int, timestamp: float,
        norfair_tracker: Any | None = None,
    ) -> FrameDetections:
        """Run detection (+ optional Norfair tracking) on a single frame.

        When norfair_tracker is provided, uses YOLO detection + Norfair tracking.
        Otherwise falls back to Ultralytics' built-in BoT-SORT tracker.

        Args:
            frame: Image as numpy array (BGR)
            frame_number: Sequential frame index
            timestamp: Time in seconds from video start
            norfair_tracker: Optional NorfairTracker instance for enhanced tracking

        Returns:
            FrameDetections with all detected objects
        """
        if not self._initialized:
            await self.initialize()

        use_norfair = norfair_tracker is not None and _NORFAIR_AVAILABLE

        if use_norfair:
            results = self._model(
                frame, conf=self.ball_confidence_threshold,
                iou=self.iou_threshold, classes=[0, 32], verbose=False,
            )
        else:
            results = self._model.track(
                frame, persist=True, conf=self.ball_confidence_threshold,
                iou=self.iou_threshold, classes=[0, 32],
                tracker="botsort.yaml", verbose=False,
            )

        h, w = frame.shape[:2]
        frame_area = w * h
        pitch_mask = self._compute_pitch_mask(frame)

        # Collect raw detections
        raw: list[dict[str, Any]] = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                for i in range(len(boxes)):
                    bbox = tuple(boxes.xyxy[i].cpu().numpy())
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())
                    cls_name = self._model.names.get(cls_id, f"class_{cls_id}")
                    tid = (
                        int(boxes.id[i].cpu().numpy())
                        if not use_norfair and boxes.id is not None
                        else None
                    )
                    raw.append({
                        "bbox": bbox, "confidence": conf,
                        "class_id": cls_id, "class_name": cls_name,
                        "track_id": tid,
                    })

        # Filter raw detections
        filtered: list[dict[str, Any]] = []
        for d in raw:
            bbox = d["bbox"]
            conf = d["confidence"]
            cls_name = d["class_name"]
            if cls_name == "person":
                if conf < self.confidence_threshold:
                    continue
                area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / frame_area
                if area_ratio < self.min_bbox_area or area_ratio > self.max_bbox_area:
                    continue
                if pitch_mask is not None:
                    foot_x = int((bbox[0] + bbox[2]) / 2)
                    foot_y = int(min(bbox[3] + 5, h - 1))
                    if 0 <= foot_y < h and 0 <= foot_x < w and not pitch_mask[foot_y, foot_x]:
                        continue
            elif cls_name == "sports ball":
                if conf < self.ball_confidence_threshold:
                    continue
                if pitch_mask is not None:
                    bx = int((bbox[0] + bbox[2]) / 2)
                    by = int((bbox[1] + bbox[3]) / 2)
                    if 0 <= by < h and 0 <= bx < w and not pitch_mask[by, bx]:
                        continue
            filtered.append(d)

        # Apply Norfair tracking if available
        if use_norfair and filtered:
            norfair_input = [
                {"bbox": d["bbox"], "confidence": d["confidence"],
                 "label": d["class_name"]}
                for d in filtered
            ]
            tracked = norfair_tracker.update(frame, norfair_input, period=1)
            # Build track_id lookup by label + best IoU match
            from collections import defaultdict
            track_lookup: dict[str, list[tuple[float, int]]] = defaultdict(list)
            for t in tracked:
                iou = self._bbox_iou(t["bbox"], t["bbox"])  # identity
                track_lookup[t["label"]].append((t["track_id"], t["bbox"]))

            for d in filtered:
                label = d["class_name"]
                best_tid = None
                best_iou = 0.0
                for tid, tbbox in track_lookup.get(label, []):
                    iou = self._bbox_iou(d["bbox"], tbbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_tid = tid
                d["track_id"] = best_tid

        # Build Detection objects
        detections = [
            Detection(
                bbox=d["bbox"], confidence=d["confidence"],
                class_id=d["class_id"], class_name=d["class_name"],
                track_id=d.get("track_id"),
            )
            for d in filtered
        ]

        return FrameDetections(
            frame_number=frame_number, timestamp=timestamp,
            detections=detections, image_width=w, image_height=h,
        )

    async def process_video(
        self,
        video_path: Path,
        progress_callback=None,
        frame_skip: int = 1,
        enable_team_detection: bool = True,
    ) -> MatchTrackData:
        """Process a full video with smart track filtering (v2).

        Key improvements:
        1. Filter refs/spectators by bbox area
        2. Track lifetime filter (drop noise)
        3. Tracking quality metrics
        4. Confidence tracking per track
        5. Frame skipping (v3): process every Nth frame for 2-4x speedup
        6. Team color detection (v3): k-means on jersey colors
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

        frame_skip = max(1, int(frame_skip))
        effective_fps = fps / frame_skip
        logger.info(
            f"Processing video: {video_path.name} "
            f"({total_frames} frames, {fps:.1f} FPS, {duration:.1f}s, "
            f"frame_skip={frame_skip}, effective={effective_fps:.1f} FPS)"
        )

        norfair_tracker: Any | None = None
        if _NORFAIR_AVAILABLE and frame_skip <= 3:
            norfair_tracker = NorfairTracker()
            logger.info("Using Norfair tracker (enhanced ReID + camera motion compensation)")

        frames: list[FrameDetections] = []
        track_appearances: dict[int, int] = defaultdict(int)
        track_first_frame: dict[int, int] = {}
        track_last_frame: dict[int, int] = {}
        track_confidence_sum: dict[int, float] = defaultdict(float)
        track_is_person: dict[int, bool] = defaultdict(lambda: True)
        track_color_samples: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
        track_first_px: dict[int, float] = {}
        frame_number = 0
        h, w = 0, 0
        last_detections: list[Detection] = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                h, w = frame.shape[:2]
                timestamp = frame_number / fps

                if frame_number % frame_skip == 0:
                    frame_det = await self.detect_frame(
                        frame, frame_number, timestamp,
                        norfair_tracker=norfair_tracker,
                    )
                    frames.append(frame_det)
                    last_detections = frame_det.detections
                    if enable_team_detection:
                        sample_interval = max(
                            1, int(fps / 2)
                        )
                        if frame_number % sample_interval == 0:
                            for det in frame_det.detections:
                                if det.class_name != "person" or det.track_id is None:
                                    continue
                                torso = self._extract_torso(frame, det.bbox)
                                if torso is None:
                                    continue
                                color = self._get_dominant_color(torso)
                                if color is not None:
                                    track_color_samples[det.track_id].append(color)
                else:
                    frame_det = FrameDetections(
                        frame_number=frame_number,
                        timestamp=timestamp,
                        detections=last_detections,
                        image_width=w,
                        image_height=h,
                    )
                    frames.append(frame_det)

                for det in frame_det.detections:
                    if det.track_id is None:
                        continue
                    tid = det.track_id
                    if frame_number % frame_skip != 0:
                        continue
                    track_appearances[tid] += 1
                    if tid not in track_first_frame:
                        track_first_frame[tid] = frame_number
                        x1, _, x2, _ = det.bbox
                        track_first_px[tid] = (x1 + x2) / 2
                    track_last_frame[tid] = frame_number
                    track_confidence_sum[tid] += det.confidence
                    if det.class_name != "person":
                        track_is_person[tid] = False

                frame_number += 1

                if progress_callback and frame_number % (30 * frame_skip) == 0:
                    progress = frame_number / total_frames
                    await progress_callback(
                        progress,
                        f"Processed {frame_number}/{total_frames} frames "
                        f"(skip={frame_skip})",
                    )
        finally:
            cap.release()

        raw_tracks = len(track_appearances)
        logger.info(f"Raw tracking: {raw_tracks} unique tracks before filtering")

        valid_player_tracks = set()
        for tid, count in track_appearances.items():
            if not track_is_person.get(tid, True):
                continue
            if count < self.min_track_lifetime:
                continue
            lifetime_pct = (count / total_frames) * 100
            if lifetime_pct < 2.0:
                continue
            valid_player_tracks.add(tid)

        if self.max_keep_top_n and len(valid_player_tracks) > self.max_keep_top_n:
            top_by_lifetime = sorted(
                valid_player_tracks,
                key=lambda tid: track_appearances[tid],
                reverse=True,
            )
            valid_player_tracks = set(top_by_lifetime[:self.max_keep_top_n])
            logger.info(
                f"Truncated to top {self.max_keep_top_n} tracks by lifetime"
            )

        track_registry: dict[int, dict[str, Any]] = {}
        for tid in valid_player_tracks:
            track_registry[tid] = {
                "track_id": tid,
                "class_name": "person",
                "first_seen": track_first_frame.get(tid, 0) / fps,
                "last_seen": track_last_frame.get(tid, 0) / fps,
                "frames_tracked": track_appearances[tid],
                "lifetime_pct": (track_appearances[tid] / total_frames) * 100,
                "confidence_avg": track_confidence_sum[tid] / max(1, track_appearances[tid]),
                "first_pixel_x": track_first_px.get(tid),
            }

        fragmentation_rate = raw_tracks / max(1, len(valid_player_tracks))

        count_ratio = len(valid_player_tracks) / max(1, self.expected_player_count)
        quality = self._assess_tracking_quality(fragmentation_rate, count_ratio)

        logger.info(
            f"After filtering: {len(valid_player_tracks)} validated player tracks "
            f"(raw: {raw_tracks}, fragmentation: {fragmentation_rate:.2f}x, "
            f"count ratio: {count_ratio:.2f}x, quality: {quality})"
        )

        player_teams: dict[int, str] = {}
        team_detection_info: dict[str, Any] = {
            "enabled": enable_team_detection,
            "assigned": 0,
            "n_clusters": 0,
            "color_samples": 0,
        }
        if enable_team_detection and track_color_samples:
            try:
                track_color_samples = {
                    tid: samples
                    for tid, samples in track_color_samples.items()
                    if tid in valid_player_tracks
                }
                if not track_color_samples:
                    logger.warning(
                        "No color samples for valid tracks (all samples were from "
                        "invalid/low-lifetime tracks)"
                    )
                else:
                    logger.info(
                        f"Team color clustering on {len(track_color_samples)} valid tracks "
                        f"with {sum(len(s) for s in track_color_samples.values())} samples"
                    )
                    color_data: dict[int, dict] = {}
                    for tid, samples in track_color_samples.items():
                        if len(samples) < 3:
                            continue
                        avg = (
                            int(np.mean([c[0] for c in samples])),
                            int(np.mean([c[1] for c in samples])),
                            int(np.mean([c[2] for c in samples])),
                        )
                        color_data[tid] = {
                            "primary_color": avg,
                            "color_hex": f"#{avg[2]:02x}{avg[1]:02x}{avg[0]:02x}",
                            "samples": len(samples),
                        }
                    team_detection_info["color_samples"] = sum(
                        r["samples"] for r in color_data.values()
                    )
                clusters = self._cluster_team_colors(color_data, n_clusters=3)
                for tid, label in clusters.items():
                    if tid in color_data:
                        color_data[tid]["team_label"] = label
                cluster_avg_bgr: dict[str, tuple[int, int, int]] = {}
                for label in set(clusters.values()):
                    members = [
                        color_data[tid]["primary_color"]
                        for tid, l in clusters.items()
                        if l == label and tid in color_data
                    ]
                    if members:
                        cluster_avg_bgr[label] = (
                            int(np.mean([m[0] for m in members])),
                            int(np.mean([m[1] for m in members])),
                            int(np.mean([m[2] for m in members])),
                        )
                if cluster_avg_bgr:
                    logger.info(
                        f"Cluster BGR colors: "
                        + ", ".join(
                            f"{label}={color}"
                            for label, color in cluster_avg_bgr.items()
                        )
                    )
                for tid, label in clusters.items():
                    if label in ("home", "away") and tid in color_data:
                        player_teams[tid] = label
                    elif label == "referee":
                        logger.debug(f"Track {tid} classified as referee")
                team_detection_info["assigned"] = len(player_teams)
                team_detection_info["n_clusters"] = len(set(clusters.values()))
                home_members = [tid for tid, l in clusters.items() if l == "home"]
                away_members = [tid for tid, l in clusters.items() if l == "away"]
                ref_members = [tid for tid, l in clusters.items() if l == "referee"]
                team_detection_info["home_size"] = len(home_members)
                team_detection_info["away_size"] = len(away_members)
                team_detection_info["ref_size"] = len(ref_members)
                team_detection_info["home_avg_bgr"] = cluster_avg_bgr.get("home")
                team_detection_info["away_avg_bgr"] = cluster_avg_bgr.get("away")
                logger.info(
                    f"Team detection: home={len(home_members)} away={len(away_members)}"
                    + (f" ref={len(ref_members)}" if ref_members else "")
                    + f" (from {len(player_teams)}/{len(valid_player_tracks)} valid tracks)"
                )
            except Exception as e:
                logger.warning(f"Team detection failed: {e}", exc_info=True)

        # Match type inference
        match_type = "unknown"
        if duration >= 4800:  # 80+ minutes = full match
            match_type = "full_match"
        elif duration < 1200:  # under 20 minutes = highlight
            match_type = "highlight"
        else:
            # Ambiguous: use heuristics
            avg_track_span = 0.0
            if valid_player_tracks:
                spans = [
                    (track_last_frame.get(tid, 0) - track_first_frame.get(tid, 0)) / fps
                    for tid in valid_player_tracks
                ]
                avg_track_span = sum(spans) / len(spans)
            if fragmentation_rate < 2.0 and avg_track_span >= 60:
                match_type = "full_match"
            elif fragmentation_rate >= 3.0 or avg_track_span < 15:
                match_type = "highlight"
        logger.info(
            f"Match type inference: {match_type} "
            f"(duration={duration:.0f}s, fragmentation={fragmentation_rate:.2f}, "
            f"avg_span={avg_track_span:.1f}s)"
        )

        # MOT self-consistency metrics (py-motmetrics intrinsic)
        mot_metrics: dict[str, Any] = {}
        if _NORFAIR_AVAILABLE:
            try:
                from kawkab.services.tracking_metrics import compute_tracking_self_metrics

                mot_metrics = compute_tracking_self_metrics(
                    frames, track_registry, fps
                )
            except Exception as e:
                logger.warning(f"MOT self-metrics failed: {e}")

        return MatchTrackData(
            match_id=0,
            fps=fps,
            total_frames=frame_number,
            duration_seconds=duration,
            frames=frames,
            track_registry=track_registry,
            player_teams=player_teams,
            tracking_metrics={
                "raw_tracks_detected": raw_tracks,
                "validated_player_tracks": len(valid_player_tracks),
                "fragmentation_rate": round(fragmentation_rate, 2),
                "expected_player_count": self.expected_player_count,
                "tracking_quality": quality,
                "frame_skip": frame_skip,
                "effective_fps": round(effective_fps, 1),
                "team_detection": team_detection_info,
                "mot_self_consistency": mot_metrics.get("mot_self_consistency"),
                "mot_details": mot_metrics,
            },
            match_type=match_type,
        )

    @staticmethod
    def _bbox_iou(bbox_a: tuple[float, float, float, float],
                  bbox_b: tuple[float, float, float, float]) -> float:
        """Compute IoU between two bounding boxes (x1, y1, x2, y2)."""
        x1 = max(bbox_a[0], bbox_b[0])
        y1 = max(bbox_a[1], bbox_b[1])
        x2 = min(bbox_a[2], bbox_b[2])
        y2 = min(bbox_a[3], bbox_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
        area_b = (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def _compute_pitch_mask(self, frame):
        """Compute binary mask of pitch (green) area using HSV color.

        Returns boolean array where True = pitch, False = sideline/crowd.
        Used to filter detections of refs/spectators on the sidelines.
        """
        try:
            import cv2
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_green = np.array([25, 40, 40])
            upper_green = np.array([90, 255, 255])
            mask = cv2.inRange(hsv, lower_green, upper_green)
            kernel = np.ones((15, 15), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return None
            largest = max(contours, key=cv2.contourArea)
            filled = np.zeros_like(mask)
            cv2.drawContours(filled, [largest], -1, 255, -1)
            return filled > 0
        except Exception:
            return None

    def _assess_tracking_quality(
        self, fragmentation_rate: float, count_ratio: float = 1.0
    ) -> str:
        """Assess tracking quality based on count ratio (closer to 1.0 = better)."""
        if 0.8 <= count_ratio <= 1.3:
            return "excellent"
        elif count_ratio <= 1.5:
            return "good"
        elif count_ratio <= 2.0:
            return "fair"
        elif count_ratio <= 3.0:
            return "poor"
        else:
            return "very_poor"

    async def shutdown(self) -> None:
        """Release resources."""
        self._model = None
        self._initialized = False
        logger.info("CVService shutdown")

    async def detect_jersey_numbers(
        self,
        video_path: Path,
        track_id_jersey_map: dict[int, int] | None = None,
        sample_every_n_frames: int = 30,
    ) -> dict[int, dict]:
        """Detect jersey numbers for tracked players.

        Uses a combination of:
        1. Torso region detection (top 1/3 of bounding box)
        2. OCR on the torso region
        3. Temporal voting across frames (most common number wins)

        Args:
            video_path: Path to video file
            track_id_jersey_map: Optional map to pre-fill known jerseys
            sample_every_n_frames: Sample every N frames (default 30 = 1/sec at 30fps)

        Returns:
            Dict mapping track_id -> {"jersey_number": int, "confidence": float, "candidates": dict}
        """
        import cv2

        if not self._initialized:
            await self.initialize()

        if track_id_jersey_map is None:
            track_id_jersey_map = {}

        track_jersey_votes: dict[int, dict[int, int]] = {}

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Cannot open video for jersey detection: {video_path}")
            return {}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = 0

        from kawkab.services.jersey_service import JerseyNumberService

        jersey_svc = JerseyNumberService(gpu_enabled=self.gpu_enabled)

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % sample_every_n_frames == 0:
                    results = self._model.track(
                        frame,
                        persist=True,
                        conf=self.confidence_threshold,
                        classes=[0],
                        verbose=False,
                    )
                    if results and len(results) > 0:
                        boxes = results[0].boxes
                        if boxes is not None and len(boxes) > 0:
                            for i in range(len(boxes)):
                                if boxes.id is None:
                                    continue
                                track_id = int(boxes.id[i].cpu().numpy())
                                bbox = boxes.xyxy[i].cpu().numpy()
                                x1, y1, x2, y2 = map(int, bbox)

                                torso_y1 = y1 + int((y2 - y1) * 0.2)
                                torso_y2 = y1 + int((y2 - y1) * 0.6)
                                torso_x1 = x1 + int((x2 - x1) * 0.1)
                                torso_x2 = x2 - int((x2 - x1) * 0.1)

                                torso_y1 = max(0, torso_y1)
                                torso_y2 = min(frame.shape[0], torso_y2)
                                torso_x1 = max(0, torso_x1)
                                torso_x2 = min(frame.shape[1], torso_x2)

                                if torso_x2 <= torso_x1 or torso_y2 <= torso_y1:
                                    continue

                                torso = frame[torso_y1:torso_y2, torso_x1:torso_x2]
                                result = jersey_svc.detect(torso)
                                if result["jersey_number"] is not None:
                                    num = result["jersey_number"]
                                    if track_id not in track_jersey_votes:
                                        track_jersey_votes[track_id] = {}
                                    track_jersey_votes[track_id][num] = (
                                        track_jersey_votes[track_id].get(num, 0) + 1
                                    )

                frame_count += 1
                if frame_count % (sample_every_n_frames * 30) == 0:
                    pct = (frame_count / total_frames) * 100
                    logger.debug(f"Jersey OCR: {pct:.0f}% ({frame_count}/{total_frames})")
        finally:
            cap.release()

        results: dict[int, dict] = {}
        for track_id, votes in track_jersey_votes.items():
            if not votes:
                continue
            total_votes = sum(votes.values())
            best_number = max(votes.items(), key=lambda x: x[1])
            confidence = best_number[1] / total_votes if total_votes > 0 else 0

            if track_id in track_id_jersey_map:
                results[track_id] = {
                    "jersey_number": track_id_jersey_map[track_id],
                    "confidence": 1.0,
                    "candidates": {track_id_jersey_map[track_id]: 1},
                    "source": "manual",
                }
            else:
                results[track_id] = {
                    "jersey_number": best_number[0],
                    "confidence": round(confidence, 2),
                    "candidates": dict(sorted(votes.items(), key=lambda x: -x[1])[:5]),
                    "source": "ocr",
                }

        logger.info(
            f"Jersey detection complete: {len(results)} players, "
            f"avg confidence: {sum(r['confidence'] for r in results.values()) / max(1, len(results)):.1%}"
        )
        return results

    def _estimate_jersey_from_pixels(
        self, white_pixels: int, width: int, height: int
    ) -> int | None:
        """Fallback: estimate jersey number from white pixel count (rough heuristic)."""
        ratio = white_pixels / (width * height) if (width * height) > 0 else 0
        if ratio < 0.05:
            return None
        estimated = int(1 + (ratio * 100) % 99)
        if 0 < estimated < 100:
            return estimated
        return None
    async def detect_team_colors(
        self,
        video_path: Path,
        sample_frames: int = 20,
        known_track_ids: set[int] | None = None,
    ) -> dict[int, dict]:
        """Detect dominant jersey color for each tracked player."""
        import cv2

        if not self._initialized:
            await self.initialize()

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_positions = [
            int(i * (total_frames - 1) / max(1, sample_frames - 1))
            for i in range(sample_frames)
        ]

        track_colors = defaultdict(list)

        for target_frame in frame_positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            if not ret:
                continue

            results = self._model.track(
                frame, persist=True, conf=self.confidence_threshold,
                classes=[0], verbose=False,
            )
            if not results or len(results) == 0:
                continue
            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                if boxes.id is None:
                    continue
                track_id = int(boxes.id[i].cpu().numpy())
                if known_track_ids is not None and track_id not in known_track_ids:
                    continue
                bbox = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = map(int, bbox)
                torso_y1 = max(0, y1 + int((y2 - y1) * 0.25))
                torso_y2 = min(frame.shape[0], y1 + int((y2 - y1) * 0.55))
                torso_x1 = max(0, x1 + int((x2 - x1) * 0.2))
                torso_x2 = min(frame.shape[1], x2 - int((x2 - x1) * 0.2))
                if torso_x2 <= torso_x1 or torso_y2 <= torso_y1:
                    continue
                torso = frame[torso_y1:torso_y2, torso_x1:torso_x2]
                if torso.size == 0:
                    continue
                avg_color = self._get_dominant_color(torso)
                if avg_color:
                    track_colors[track_id].append(avg_color)

        cap.release()

        result = {}
        for tid, colors in track_colors.items():
            if len(colors) < 3:
                continue
            avg = (
                int(np.mean([c[0] for c in colors])),
                int(np.mean([c[1] for c in colors])),
                int(np.mean([c[2] for c in colors])),
            )
            result[tid] = {
                "primary_color": avg,
                "color_hex": f"#{avg[2]:02x}{avg[1]:02x}{avg[0]:02x}",
                "samples": len(colors),
            }

        clusters = self._cluster_team_colors(result, n_clusters=3)
        for tid, label in clusters.items():
            if tid in result:
                result[tid]["team_label"] = label

        n_teams = len(set(clusters.values()))
        logger.info(f"Team color detection: {len(result)} players, {n_teams} clusters")
        return result

    def _extract_torso(self, frame: np.ndarray, bbox: tuple) -> np.ndarray | None:
        """Extract torso region from frame using bbox (x1,y1,x2,y2).

        Returns the upper-middle portion of the bbox (jersey area).
        """
        if frame is None or frame.size == 0:
            return None
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        torso_y1 = max(0, y1 + int((y2 - y1) * 0.25))
        torso_y2 = min(h, y1 + int((y2 - y1) * 0.55))
        torso_x1 = max(0, x1 + int((x2 - x1) * 0.2))
        torso_x2 = min(w, x2 - int((x2 - x1) * 0.2))
        if torso_x2 <= torso_x1 or torso_y2 <= torso_y1:
            return None
        torso = frame[torso_y1:torso_y2, torso_x1:torso_x2]
        if torso.size == 0:
            return None
        return torso

    def _get_dominant_color(self, img_region):
        """Get dominant non-white, non-black color from a region (BGR)."""
        if img_region.size == 0:
            return None
        h, w = img_region.shape[:2]
        if h < 5 or w < 5:
            return None
        pixels = img_region.reshape(-1, 3)
        mask = ~((pixels[:, 0] > 230) & (pixels[:, 1] > 230) & (pixels[:, 2] > 230))
        pixels = pixels[mask]
        mask2 = ~((pixels[:, 0] < 30) & (pixels[:, 1] < 30) & (pixels[:, 2] < 30))
        pixels = pixels[mask2]
        if len(pixels) < 5:
            return None
        return (
            int(np.mean(pixels[:, 0])),
            int(np.mean(pixels[:, 1])),
            int(np.mean(pixels[:, 2])),
        )

    def _cluster_team_colors(self, color_data, n_clusters=2):
        """Cluster players into teams based on jersey color.

        Supports auto-detection of referee (n_clusters=3):
        cluster with darkest/saturation-lowest hue → referee.
        """
        if len(color_data) < 2:
            return {tid: 0 for tid in color_data}

        tids = list(color_data.keys())
        colors_bgr = np.array([color_data[tid]["primary_color"] for tid in tids])

        auto_detect_ref = n_clusters >= 3
        actual_n = min(n_clusters if not auto_detect_ref else 3, len(tids))

        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=actual_n, random_state=42, n_init=10)
            labels = kmeans.fit_predict(colors_bgr)
            label_map: dict[int, str] = {}

            if actual_n >= 3:
                centroids_bgr = kmeans.cluster_centers_.astype(int)
                import cv2
                centroids_hsv = [
                    cv2.cvtColor(
                        np.uint8([[c]]), cv2.COLOR_BGR2HSV
                    )[0, 0]
                    for c in centroids_bgr
                ]
                ref_idx = min(
                    range(len(centroids_hsv)),
                    key=lambda i: (
                        centroids_hsv[i][1],
                        -abs(centroids_hsv[i][0] - 0),
                    ),
                )
                team_indices = [i for i in range(actual_n) if i != ref_idx]
                sorted_teams = sorted(
                    team_indices,
                    key=lambda i: sum(centroids_bgr[i]),
                    reverse=True,
                )
                label_map[ref_idx] = "referee"
                label_map[sorted_teams[0]] = "home"
                label_map[sorted_teams[1]] = "away"
            else:
                sorted_idx = sorted(
                    range(actual_n),
                    key=lambda i: sum(kmeans.cluster_centers_[i].astype(int)),
                    reverse=True,
                )
                label_map[sorted_idx[0]] = "home"
                label_map[sorted_idx[1]] = "away"

            return {tids[i]: label_map.get(int(labels[i]), str(int(labels[i]))) for i in range(len(tids))}
        except ImportError:
            sorted_by_color = sorted(
                tids, key=lambda t: sum(color_data[t]["primary_color"])
            )
            result = {}
            for i, tid in enumerate(sorted_by_color):
                result[tid] = "home" if i < len(sorted_by_color) / 2 else "away"
            return result
