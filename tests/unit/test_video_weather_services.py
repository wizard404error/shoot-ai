"""Tests for RaindropDetectionService (TobyBreckon-style) and WeatherImageClassifier."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import install_kawkab_stubs, load_service_module

install_kawkab_stubs()
_rd = load_service_module("rd_test", "raindrop_detection_service.py")
RaindropDetectionService = _rd.RaindropDetectionService

_wc = load_service_module("wc_test", "weather_image_classifier.py")
WeatherImageClassifier = _wc.WeatherImageClassifier
WEATHER_CLASSES = _wc.WEATHER_CLASSES
compute_features = _wc.compute_features

import numpy as np
import pytest


@pytest.fixture
def raindrop_svc() -> RaindropDetectionService:
    return RaindropDetectionService()


@pytest.fixture
def weather_svc() -> WeatherImageClassifier:
    return WeatherImageClassifier()


class TestRaindropService:
    def test_available(self, raindrop_svc: RaindropDetectionService) -> None:
        assert raindrop_svc.available

    def test_default_no_cnn(self, raindrop_svc: RaindropDetectionService) -> None:
        assert not raindrop_svc.has_cnn

    def test_empty_frames(self, raindrop_svc: RaindropDetectionService) -> None:
        result = raindrop_svc.detect([])
        assert result.frame_count == 0
        assert not result.is_rainy

    def test_method_fallback(self, raindrop_svc: RaindropDetectionService) -> None:
        np.random.seed(7)
        frame = np.random.randint(50, 100, (480, 640, 3), dtype=np.uint8)
        result = raindrop_svc.detect([frame])
        assert result.method == "opencv_heuristic"

    def test_video_file_not_found(self, raindrop_svc: RaindropDetectionService) -> None:
        result = raindrop_svc.detect_from_video_file("/nonexistent/video.mp4")
        assert result.frame_count == 0


class TestWeatherImageClassifier:
    def test_available(self, weather_svc: WeatherImageClassifier) -> None:
        assert weather_svc.available

    def test_default_no_cnn(self, weather_svc: WeatherImageClassifier) -> None:
        assert not weather_svc.has_cnn

    def test_clear_frame_sunny(self, weather_svc: WeatherImageClassifier) -> None:
        frame = np.full((480, 640, 3), 200, dtype=np.uint8)
        pred = weather_svc.classify(frame)
        assert pred.predicted_class in WEATHER_CLASSES
        assert pred.method == "feature_based"

    def test_dark_frame(self, weather_svc: WeatherImageClassifier) -> None:
        frame = np.full((480, 640, 3), 30, dtype=np.uint8)
        pred = weather_svc.classify(frame)
        assert pred.predicted_class in {"rainy", "snowy"}

    def test_white_frame(self, weather_svc: WeatherImageClassifier) -> None:
        frame = np.full((480, 640, 3), 220, dtype=np.uint8)
        pred = weather_svc.classify(frame)
        assert pred.predicted_class in {"foggy", "snowy", "sunny"}

    def test_confidence_in_range(self, weather_svc: WeatherImageClassifier) -> None:
        frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        pred = weather_svc.classify(frame)
        assert 0.0 <= pred.confidence <= 1.0

    def test_class_probabilities_sum_to_one(self, weather_svc: WeatherImageClassifier) -> None:
        frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        pred = weather_svc.classify(frame)
        total = sum(pred.class_probabilities.values())
        assert abs(total - 1.0) < 0.01


class TestComputeFeatures:
    def test_returns_tuple(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        brightness, edges, blue = compute_features(frame)
        assert isinstance(brightness, float)
        assert isinstance(edges, float)
        assert isinstance(blue, float)

    def test_white_frame(self) -> None:
        frame = np.full((100, 100, 3), 255, dtype=np.uint8)
        brightness, edges, blue = compute_features(frame)
        assert brightness > 240
        assert edges < 0.05

    def test_black_frame(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        brightness, _, _ = compute_features(frame)
        assert brightness < 5
