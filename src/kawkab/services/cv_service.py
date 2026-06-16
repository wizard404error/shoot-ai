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
        iou_threshold: float = 0.5,
        gpu_enabled: bool = True,
        min_track_lifetime_frames: int = 30,
        min_bbox_area_ratio: float = 0.002,
        max_bbox_area_ratio: float = 0.15,
        expected_player_count: int = 22,
        max_keep_top_n: int = 28,
    ) -> None:
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.gpu_enabled = gpu_enabled
        self.min_track_lifetime = min_track_lifetime_frames
        self.min_bbox_area = min_bbox_area_ratio
        self.max_bbox_area = max_bbox_area_ratio
        self.expected_player_count = expected_player_count
        self.max_keep_top_n = max_keep_top_n
        self._model: Any = None
        self._initialized = False

        logger.info(
            f"CVService v2: model=yolo11{model_size}, "
            f"conf={confidence_threshold}, iou={iou_threshold}, gpu={gpu_enabled}, "
            f"min_track_life={min_track_lifetime_frames}, "
            f"max_keep={max_keep_top_n or 'unlimited'}"
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
        self, frame: np.ndarray, frame_number: int, timestamp: float
    ) -> FrameDetections:
        """Run detection + tracking on a single frame.

        Args:
            frame: Image as numpy array (BGR)
            frame_number: Sequential frame index
            timestamp: Time in seconds from video start

        Returns:
            FrameDetections with all detected objects
        """
        if not self._initialized:
            await self.initialize()

        results = self._model.track(
            frame,
            persist=True,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            classes=[0, 32],  # person, sports ball (COCO)
            tracker="botsort.yaml",
            verbose=False,
        )

        detections: list[Detection] = []
        h, w = frame.shape[:2]
        frame_area = w * h

        pitch_mask = self._compute_pitch_mask(frame)

        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes

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

                    if cls_name == "person" and pitch_mask is not None:
                        foot_x = int((bbox[0] + bbox[2]) / 2)
                        foot_y = int(min(bbox[3] + 5, h - 1))
                        if 0 <= foot_y < h and 0 <= foot_x < w:
                            if not pitch_mask[foot_y, foot_x]:
                                continue

                    detections.append(
                        Detection(
                            bbox=tuple(bbox),
                            confidence=conf,
                            class_id=cls_id,
                            class_name=cls_name,
                            track_id=track_id,
                        )
                    )

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

        frames: list[FrameDetections] = []
        track_appearances: dict[int, int] = defaultdict(int)
        track_first_frame: dict[int, int] = {}
        track_last_frame: dict[int, int] = {}
        track_confidence_sum: dict[int, float] = defaultdict(float)
        track_is_person: dict[int, bool] = defaultdict(lambda: True)
        track_color_samples: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
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
                    frame_det = await self.detect_frame(frame, frame_number, timestamp)
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
                clusters = self._cluster_team_colors(color_data)
                for tid, cluster_id in clusters.items():
                    if tid in color_data:
                        color_data[tid]["cluster_id"] = cluster_id
                cluster_avg_bgr: dict[int, tuple[int, int, int]] = {}
                for cid in set(clusters.values()):
                    members = [
                        color_data[tid]["primary_color"]
                        for tid, c in clusters.items()
                        if c == cid and tid in color_data
                    ]
                    if members:
                        cluster_avg_bgr[cid] = (
                            int(np.mean([m[0] for m in members])),
                            int(np.mean([m[1] for m in members])),
                            int(np.mean([m[2] for m in members])),
                        )
                if cluster_avg_bgr:
                    logger.info(
                        f"Cluster BGR colors: "
                        + ", ".join(
                            f"cluster_{cid}={color}"
                            for cid, color in cluster_avg_bgr.items()
                        )
                    )
                cluster_counts: dict[int, int] = defaultdict(int)
                for r in color_data.values():
                    if "cluster_id" in r:
                        cluster_counts[r["cluster_id"]] += 1
                team_detection_info["n_clusters"] = len(cluster_counts)
                if len(cluster_counts) >= 2:
                    sorted_clusters = sorted(
                        cluster_counts.items(), key=lambda x: -x[1]
                    )
                    home_cluster = sorted_clusters[0][0]
                    away_cluster = sorted_clusters[1][0]
                    for tid, r in color_data.items():
                        if r.get("cluster_id") == home_cluster:
                            player_teams[tid] = "home"
                        elif r.get("cluster_id") == away_cluster:
                            player_teams[tid] = "away"
                    team_detection_info["assigned"] = len(player_teams)
                    team_detection_info["home_cluster_id"] = home_cluster
                    team_detection_info["away_cluster_id"] = away_cluster
                    team_detection_info["home_size"] = cluster_counts[home_cluster]
                    team_detection_info["away_size"] = cluster_counts[away_cluster]
                    team_detection_info["ref_size"] = sum(
                        v for k, v in cluster_counts.items()
                        if k not in (home_cluster, away_cluster)
                    )
                    team_detection_info["home_avg_bgr"] = cluster_avg_bgr.get(home_cluster)
                    team_detection_info["away_avg_bgr"] = cluster_avg_bgr.get(away_cluster)
                    logger.info(
                        f"Team detection: home={cluster_counts[home_cluster]} "
                        f"away={cluster_counts[away_cluster]} "
                        f"ref={team_detection_info['ref_size']} "
                        f"(from {len(player_teams)}/{len(valid_player_tracks)} valid tracks)"
                    )
                else:
                    logger.warning(
                        f"Team clustering found only {len(cluster_counts)} cluster(s) "
                        f"from {len(color_data)} players — jerseys may be similar"
                    )
            except Exception as e:
                logger.warning(f"Team detection failed: {e}", exc_info=True)

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
            },
        )

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

        ocr = None
        try:
            import easyocr
            ocr = easyocr.Reader(["en"], gpu=self.gpu_enabled, verbose=False)
        except ImportError:
            logger.warning("easyocr not installed, using fallback number detection")
        except Exception as e:
            logger.warning(f"Could not initialize EasyOCR: {e}")

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

                                if ocr is not None:
                                    try:
                                        ocr_results = ocr.readtext(torso, allowlist="0123456789")
                                        for (bbox, text, conf) in ocr_results:
                                            digits = "".join(c for c in text if c.isdigit())
                                            if digits:
                                                number = int(digits)
                                                if 0 < number < 100:
                                                    if track_id not in track_jersey_votes:
                                                        track_jersey_votes[track_id] = {}
                                                    track_jersey_votes[track_id][number] = (
                                                        track_jersey_votes[track_id].get(number, 0) + 1
                                                    )
                                    except Exception:
                                        pass
                                else:
                                    h, w = torso.shape[:2]
                                    if h > 20 and w > 10:
                                        gray = cv2.cvtColor(torso, cv2.COLOR_BGR2GRAY)
                                        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
                                        white_pixels = cv2.countNonZero(thresh)
                                        if white_pixels > 50:
                                            estimated_number = self._estimate_jersey_from_pixels(white_pixels, w, h)
                                            if estimated_number:
                                                if track_id not in track_jersey_votes:
                                                    track_jersey_votes[track_id] = {}
                                                track_jersey_votes[track_id][estimated_number] = (
                                                    track_jersey_votes[track_id].get(estimated_number, 0) + 1
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

        clusters = self._cluster_team_colors(result)
        for tid, cluster_id in clusters.items():
            if tid in result:
                result[tid]["cluster_id"] = cluster_id

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
        """Cluster players into teams based on jersey color."""
        if len(color_data) < 2:
            return {tid: 0 for tid in color_data}
        try:
            from sklearn.cluster import KMeans
            tids = list(color_data.keys())
            colors = np.array([color_data[tid]["primary_color"] for tid in tids])
            actual_clusters = min(n_clusters, len(tids))
            kmeans = KMeans(n_clusters=actual_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(colors)
            return {tids[i]: int(labels[i]) for i in range(len(tids))}
        except ImportError:
            tids = list(color_data.keys())
            sorted_by_color = sorted(
                tids, key=lambda t: sum(color_data[t]["primary_color"])
            )
            result = {}
            for i, tid in enumerate(sorted_by_color):
                result[tid] = 0 if i < len(sorted_by_color) / 2 else 1
            return result
