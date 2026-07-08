"""Dedicated ball tracking module with Kalman filter.

Key design:
- Independent from player tracker (runs at full FPS on a thread)
- HSV color model for ball candidate detection
- Kalman filter with constant-velocity motion model
- Predictive mode when ball disappears (up to 30 frames)
- Size filter: ball = 8-20px diameter at broadcast zoom
- Circularity filter via contour approximation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger("ball_tracker")

# ── Constants ─────────────────────────────────────────────────────
BALL_MIN_RADIUS = 4
BALL_MAX_RADIUS = 12
BALL_CIRCULARITY_MIN = 0.6
WHITE_LOWER = (0, 0, 200)
WHITE_UPPER = (180, 30, 255)
DARK_LOWER = (0, 0, 0)
DARK_UPPER = (180, 255, 50)
MISSED_FRAME_LIMIT = 30
KALMAN_DT = 1.0 / 24.0
CONFIDENCE_VISIBLE = 0.9
CONFIDENCE_PREDICTED = 0.3


@dataclass
class BallDetection:
    frame: int
    timestamp: float
    x: float
    y: float
    conf: float
    is_prediction: bool = False
    radius: float = 0.0


class BallTracker:
    def __init__(self, fps: float = 24.0):
        self.fps = fps
        self.dt = 1.0 / max(fps, 1)
        self.kalman = cv2.KalmanFilter(6, 3)
        self.kalman.measurementMatrix = np.hstack([np.eye(3, 3), np.zeros((3, 3))]).astype(np.float32)
        self.kalman.transitionMatrix = np.array([
            [1, 0, 0, self.dt, 0, 0],
            [0, 1, 0, 0, self.dt, 0],
            [0, 0, 1, 0, 0, self.dt],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1],
        ], dtype=np.float32)
        self.kalman.processNoiseCov = np.eye(6, dtype=np.float32) * 1e-2
        self.kalman.measurementNoiseCov = np.eye(3, dtype=np.float32) * 1e-1
        self.kalman.errorCovPost = np.eye(6, dtype=np.float32)
        self.initialized = False
        self.missed_frames = 0
        self.last_frame = -1
        self.last_timestamp = 0.0
        self.confidence = 0.0
        self.trail: list[BallDetection] = []

    def _find_ball_candidates(self, frame: np.ndarray) -> list[dict]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        candidates = []
        for lower, upper, label in [
            (WHITE_LOWER, WHITE_UPPER, "white"),
            (DARK_LOWER, DARK_UPPER, "dark"),
        ]:
            mask = cv2.inRange(hsv, np.array(lower, dtype=np.uint8), np.array(upper, dtype=np.uint8))
            mask = cv2.erode(mask, None, iterations=1)
            mask = cv2.dilate(mask, None, iterations=2)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                ((x, y), radius) = cv2.minEnclosingCircle(cnt)
                if radius < BALL_MIN_RADIUS or radius > BALL_MAX_RADIUS:
                    continue
                area = cv2.contourArea(cnt)
                if area == 0:
                    continue
                perimeter = cv2.arcLength(cnt, True)
                circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                if circularity < BALL_CIRCULARITY_MIN:
                    continue
                candidates.append({"x": x, "y": y, "radius": radius, "circularity": circularity, "label": label})
        candidates.sort(key=lambda c: c["circularity"], reverse=True)
        return candidates[:3]

    def update(self, frame: np.ndarray, frame_number: int, timestamp: float) -> BallDetection | None:
        candidates = self._find_ball_candidates(frame)
        best = candidates[0] if candidates else None
        if best is not None:
            self.missed_frames = 0
            meas = np.array([[best["x"]], [best["y"]], [best["radius"]]], dtype=np.float32)
            if not self.initialized:
                self.kalman.statePost = np.array([
                    best["x"], best["y"], best["radius"],
                    0, 0, 0,
                ], dtype=np.float32)
                self.kalman.errorCovPost = np.eye(6, dtype=np.float32)
                self.initialized = True
                self.confidence = CONFIDENCE_VISIBLE
            else:
                self.kalman.predict()
                self.kalman.correct(meas)
                self.confidence = CONFIDENCE_VISIBLE
            state = self.kalman.statePost.ravel()
            x, y, r = float(state[0]), float(state[1]), float(state[2])
            det = BallDetection(
                frame=frame_number, timestamp=timestamp,
                x=x, y=y, conf=self.confidence,
                is_prediction=False, radius=r,
            )
        elif self.initialized and self.missed_frames < MISSED_FRAME_LIMIT:
            self.missed_frames += 1
            pred = self.kalman.predict().ravel()
            x, y, r = float(pred[0]), float(pred[1]), float(pred[2])
            decay = max(0.1, 1.0 - self.missed_frames / MISSED_FRAME_LIMIT)
            self.confidence = CONFIDENCE_PREDICTED * decay
            det = BallDetection(
                frame=frame_number, timestamp=timestamp,
                x=x, y=y, conf=self.confidence,
                is_prediction=True, radius=r,
            )
        else:
            self.initialized = False
            self.confidence = 0.0
            return None

        self.last_frame = frame_number
        self.last_timestamp = timestamp
        self.trail.append(det)
        if len(self.trail) > 1000:
            self.trail = self.trail[-500:]
        return det

    def reset(self):
        self.initialized = False
        self.missed_frames = 0
        self.confidence = 0.0
        self.trail.clear()

    def get_trail(self, max_age: float = 5.0) -> list[BallDetection]:
        if not self.trail:
            return []
        cutoff = self.last_timestamp - max_age
        return [b for b in self.trail if b.timestamp >= cutoff]
