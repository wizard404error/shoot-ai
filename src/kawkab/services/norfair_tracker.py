"""Norfair-based tracking wrapper for football player + ball tracking.

Replaces Ultralytics' built-in BoT-SORT tracker with Norfair for:
- Customizable distance functions (IoU + centroid fusion)
- Built-in ReID for camera-cut recovery (color histogram embeddings)
- Camera motion compensation via MotionEstimator
- Greedy matching (less erratic ID switching than Hungarian)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from norfair import Detection, Tracker
from norfair.camera_motion import MotionEstimator
from norfair.tracker import TrackedObject

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants tuned for amateur football broadcast footage
# ---------------------------------------------------------------------------
PERSON_HIT_COUNTER_MAX = 30       # frames before losing a player track
BALL_HIT_COUNTER_MAX = 15         # ball disappears faster (occlusion, blur)
INITIALIZATION_DELAY = 3          # frames before a new track is "confirmed"
IOU_DISTANCE_THRESHOLD = 0.6      # max IoU distance for person matching
CENTROID_DISTANCE_THRESHOLD = 40  # max pixel distance for ball matching
REID_DISTANCE_THRESHOLD = 0.35    # max cosine distance for ReID match
REID_HIT_COUNTER_MAX = 60         # extra longevity for ReID-matched tracks
N_HIST_BINS = 32                  # HSV histogram bins for ReID embedding


def _bbox_corners(bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Convert (x1, y1, x2, y2) bbox to 4-corner point array for IoU."""
    x1, y1, x2, y2 = bbox
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)


def _bbox_center(bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Return (cx, cy) centroid as a single-point array."""
    return np.array([[(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]], dtype=np.float32)


def _hsv_histogram(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Compute normalized HSV histogram for the torso region of a bbox.

    Used as a lightweight ReID embedding (invariant to brightness changes).
    """
    import cv2
    x1, y1, x2, y2 = [int(v) for v in bbox]
    h, w = frame.shape[:2]
    # Torso region: 25%-55% vertical, 20%-80% horizontal (jersey area)
    ty1 = max(0, y1 + int((y2 - y1) * 0.25))
    ty2 = min(h, y1 + int((y2 - y1) * 0.55))
    tx1 = max(0, x1 + int((x2 - x1) * 0.2))
    tx2 = min(w, x2 - int((x2 - x1) * 0.2))
    if ty2 <= ty1 or tx2 <= tx1:
        return np.zeros(N_HIST_BINS, dtype=np.float32)
    torso = frame[ty1:ty2, tx1:tx2]
    if torso.size == 0:
        return np.zeros(N_HIST_BINS, dtype=np.float32)
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [N_HIST_BINS, N_HIST_BINS], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten().astype(np.float32)


# ---------------------------------------------------------------------------
# ReID distance function for Norfair
# ---------------------------------------------------------------------------

def _reid_distance(obj_a: TrackedObject, obj_b: TrackedObject) -> float:
    """Cosine distance between HSV histogram embeddings.

    Called by Norfair when reconnecting tracks after camera cuts or occlusion.
    Returns float('inf') if either object has no embedding.
    """
    emb_a = getattr(obj_a.last_detection, "embedding", None) if obj_a.last_detection else None
    emb_b = getattr(obj_b.last_detection, "embedding", None) if obj_b.last_detection else None
    if emb_a is None or emb_b is None:
        return float("inf")
    # Cosine distance
    norm_a = np.linalg.norm(emb_a)
    norm_b = np.linalg.norm(emb_b)
    if norm_a < 1e-8 or norm_b < 1e-8:
        return float("inf")
    return float(1.0 - np.dot(emb_a, emb_b) / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# NorfairTracker wrapper
# ---------------------------------------------------------------------------

class NorfairTracker:
    """Wraps Norfair Tracker + MotionEstimator for football video.

    Usage:
        tracker = NorfairTracker()
        for frame in video:
            # Get YOLO detections as list of dicts
            raw_dets = [{"bbox": (x1,y1,x2,y2), "confidence": 0.9, "label": "person"}, ...]
            # Update tracker
            tracked = tracker.update(frame, raw_dets)
            # tracked is a list of dicts with track_id, bbox, confidence, label
    """

    def __init__(self) -> None:
        self._motion_estimator = MotionEstimator()
        self._person_tracker = Tracker(
            distance_function="iou",
            distance_threshold=IOU_DISTANCE_THRESHOLD,
            hit_counter_max=PERSON_HIT_COUNTER_MAX,
            initialization_delay=INITIALIZATION_DELAY,
            reid_distance_function=_reid_distance,
            reid_distance_threshold=REID_DISTANCE_THRESHOLD,
            reid_hit_counter_max=REID_HIT_COUNTER_MAX,
        )
        self._ball_tracker = Tracker(
            distance_function="euclidean",
            distance_threshold=CENTROID_DISTANCE_THRESHOLD,
            hit_counter_max=BALL_HIT_COUNTER_MAX,
            initialization_delay=1,
        )
        self._initialized = False

    def reset(self) -> None:
        """Reset tracker state (call between videos)."""
        self._motion_estimator = MotionEstimator()
        self._person_tracker = Tracker(
            distance_function="iou",
            distance_threshold=IOU_DISTANCE_THRESHOLD,
            hit_counter_max=PERSON_HIT_COUNTER_MAX,
            initialization_delay=INITIALIZATION_DELAY,
            reid_distance_function=_reid_distance,
            reid_distance_threshold=REID_DISTANCE_THRESHOLD,
            reid_hit_counter_max=REID_HIT_COUNTER_MAX,
        )
        self._ball_tracker = Tracker(
            distance_function="euclidean",
            distance_threshold=CENTROID_DISTANCE_THRESHOLD,
            hit_counter_max=BALL_HIT_COUNTER_MAX,
            initialization_delay=1,
        )

    def update(
        self,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        period: int = 1,
    ) -> list[dict[str, Any]]:
        """Update tracker with new frame and detections.

        Args:
            frame: Full-resolution video frame (BGR numpy array).
            detections: List of dicts with keys:
                - "bbox": (x1, y1, x2, y2) tuple
                - "confidence": float
                - "label": "person" or "sports ball"
            period: Frame skip factor (1 = every frame, 3 = every 3rd frame).

        Returns:
            List of dicts with keys:
                - "track_id": int (Norfair-assigned)
                - "bbox": (x1, y1, x2, y2) tuple
                - "confidence": float
                - "label": "person" or "sports ball"
        """
        # Camera motion estimation
        coord_transformations = self._motion_estimator.update(frame)

        # Split detections into persons + ball
        person_dets = []
        ball_dets = []
        for d in detections:
            if d["label"] == "person":
                emb = _hsv_histogram(frame, d["bbox"])
                person_dets.append(
                    Detection(
                        points=_bbox_corners(d["bbox"]),
                        scores=np.array([d["confidence"]] * 4),
                        label="person",
                        data={"bbox": d["bbox"], "confidence": d["confidence"]},
                        embedding=emb,
                    )
                )
            elif d["label"] == "sports ball":
                ball_dets.append(
                    Detection(
                        points=_bbox_center(d["bbox"]),
                        scores=np.array([d["confidence"]]),
                        label="sports ball",
                        data={"bbox": d["bbox"], "confidence": d["confidence"]},
                    )
                )

        # Update trackers
        person_tracked = self._person_tracker.update(
            detections=person_dets,
            coord_transformations=coord_transformations,
            period=period,
        )
        ball_tracked = self._ball_tracker.update(
            detections=ball_dets,
            coord_transformations=coord_transformations,
            period=period,
        )

        # Merge results
        result: list[dict[str, Any]] = []
        for obj in person_tracked:
            if obj.last_detection is None:
                continue
            data = obj.last_detection.data
            result.append({
                "track_id": obj.global_id,
                "bbox": data["bbox"],
                "confidence": data["confidence"],
                "label": "person",
            })
        for obj in ball_tracked:
            if obj.last_detection is None:
                continue
            data = obj.last_detection.data
            result.append({
                "track_id": obj.global_id,
                "bbox": data["bbox"],
                "confidence": data["confidence"],
                "label": "sports ball",
            })

        return result
