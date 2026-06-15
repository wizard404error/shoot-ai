"""Tests for core configuration module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kawkab.core.config import AppSettings, get_settings


def test_default_settings() -> None:
    """Test default settings values."""
    settings = AppSettings()

    assert settings.app_name == "Kawkab AI"
    assert settings.app_version == "0.1.0"
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


def test_language_validation() -> None:
    """Test language accepts only 'en' or 'ar'."""
    settings_en = AppSettings(language="en")
    assert settings_en.language == "en"

    settings_ar = AppSettings(language="ar")
    assert settings_ar.language == "ar"

    with pytest.raises(ValidationError):
        AppSettings(language="fr")
