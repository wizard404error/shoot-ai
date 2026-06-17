"""Tests for core configuration module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kawkab.core.config import AppSettings, get_settings


def test_default_settings() -> None:
    """Test default settings values."""
    settings = AppSettings()

    assert settings.app_name == "Kawkab AI"
    assert settings.app_version == "0.8.0"
    assert settings.gpu_enabled is True
    assert settings.model_size == "l"
    assert settings.confidence_threshold == 0.5
    assert settings.language == "en"


def test_model_size_validation() -> None:
    """Test model_size accepts only valid values."""
    with pytest.raises(ValidationError):
        AppSettings(model_size="invalid")


def test_confidence_threshold_bounds() -> None:
    """Test confidence_threshold is between 0 and 1."""
    with pytest.raises(ValidationError):
        AppSettings(confidence_threshold=-0.1)

    with pytest.raises(ValidationError):
        AppSettings(confidence_threshold=1.5)


def test_settings_singleton() -> None:
    """Test get_settings returns same instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_frame_skip_bounds() -> None:
    """Test frame_skip is between 1 and 10."""
    with pytest.raises(ValidationError):
        AppSettings(frame_skip=0)
    with pytest.raises(ValidationError):
        AppSettings(frame_skip=15)
    settings = AppSettings(frame_skip=5)
    assert settings.frame_skip == 5


def test_auto_detect_gpu_tier_default() -> None:
    """Test auto_detect_gpu_tier defaults to True."""
    settings = AppSettings()
    assert settings.auto_detect_gpu_tier is True
    settings_off = AppSettings(auto_detect_gpu_tier=False)
    assert settings_off.auto_detect_gpu_tier is False
