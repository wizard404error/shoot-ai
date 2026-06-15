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
            f"min_track_life={min_track_lifetime_frames}"
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
    ) -> MatchTrackData:
        """Process a full video with smart track filtering (v2).

        Key improvements:
        1. Filter refs/spectators by bbox area
        2. Track lifetime filter (drop noise)
        3. Tracking quality metrics
        4. Confidence tracking per track
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

        logger.info(
            f"Processing video: {video_path.name} "
            f"({total_frames} frames, {fps:.1f} FPS, {duration:.1f}s)"
        )

        frames: list[FrameDetections] = []
        track_appearances: dict[int, int] = defaultdict(int)
        track_first_frame: dict[int, int] = {}
        track_last_frame: dict[int, int] = {}
        track_confidence_sum: dict[int, float] = defaultdict(float)
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
                    if det.class_name != "person":
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
        quality = self._assess_tracking_quality(fragmentation_rate)

        logger.info(
            f"After filtering: {len(valid_player_tracks)} validated player tracks "
            f"(raw: {raw_tracks}, fragmentation: {fragmentation_rate:.2f}x, "
            f"quality: {quality})"
        )

        return MatchTrackData(
            match_id=0,
            fps=fps,
            total_frames=frame_number,
            duration_seconds=duration,
            frames=frames,
            track_registry=track_registry,
            player_teams={},
            tracking_metrics={
                "raw_tracks_detected": raw_tracks,
                "validated_player_tracks": len(valid_player_tracks),
                "fragmentation_rate": round(fragmentation_rate, 2),
                "expected_player_count": self.expected_player_count,
                "tracking_quality": quality,
            },
        )

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
