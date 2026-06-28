"""Tests for JerseyNumberService."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from conftest import install_kawkab_stubs

install_kawkab_stubs()

from kawkab.services.jersey_service import JerseyNumberService


class TestJerseyNumberService:
    def test_detect_ocr_success(self, monkeypatch):
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.cvtColor", lambda img, code: img)
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.COLOR_BGR2GRAY", 6)
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.COLOR_GRAY2BGR", 4)
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.resize", lambda img, size: np.zeros((28, 28), dtype=np.uint8) if img.ndim == 2 else np.zeros((*size, 3), dtype=np.uint8))
        fake_reader = MagicMock()
        fake_reader.readtext.return_value = [([[0, 0], [10, 0], [10, 10], [0, 10]], "7", 0.85)]
        service = JerseyNumberService(reader="ocr")
        service._ocr_reader = fake_reader
        result = service.detect(np.zeros((30, 30, 3), dtype=np.uint8))
        assert result["jersey_number"] == 7
        assert result["source"] == "ocr"

    def test_detect_cnn_not_implemented(self, monkeypatch):
        monkeypatch.setattr("kawkab.services.jersey_service.cv2", MagicMock())
        service = JerseyNumberService(reader="cnn")
        result = service.detect(np.zeros((28, 28, 3), dtype=np.uint8))
        assert result["source"] == "none"

    def test_detect_fallback_to_pixel(self, monkeypatch):
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.cvtColor", lambda img, code: img if len(img.shape) == 2 else np.mean(img, axis=2).astype(np.uint8))
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.COLOR_BGR2GRAY", 6)
        monkeypatch.setattr("kawkab.services.jersey_service.cv2.resize", lambda img, size: img[:size[0], :size[1]] if len(img.shape) == 2 else img[:size[0], :size[1], :])
        service = JerseyNumberService(reader="ocr")
        result = service.detect(np.ones((30, 30, 3), dtype=np.uint8) * 255)
        assert isinstance(result, dict)
