"""Core configuration and settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="KAWKAB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Kawkab AI"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, description="Enable debug mode")

    language: Literal["en", "ar"] = Field(
        default="en", description="Default UI language"
    )

    gpu_enabled: bool = Field(default=True, description="Use GPU for inference")
    model_size: Literal["n", "s", "m", "l", "x"] = Field(
        default="l", description="YOLOv11 model size (n=nano, l=large)"
    )
    confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Detection confidence threshold"
    )
    iou_threshold: float = Field(
        default=0.45, ge=0.0, le=1.0, description="IoU threshold for NMS"
    )

    enhancement_enabled: bool = Field(
        default=True, description="Enable video enhancement"
    )
    enable_upscaling: bool = Field(
        default=False, description="Enable Real-ESRGAN upscaling"
    )
    enable_interpolation: bool = Field(
        default=False, description="Enable RIFE frame interpolation"
    )

    llm_provider: Literal["ollama", "groq", "google", "openrouter"] = Field(
        default="ollama", description="LLM provider for reports"
    )
    ollama_model: str = Field(
        default="ministral-3:14b", description="Ollama model name"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama API URL"
    )

    crash_reporting_enabled: bool = Field(
        default=False, description="Enable Sentry crash reporting"
    )
    analytics_enabled: bool = Field(
        default=False, description="Enable Plausible analytics"
    )

    max_video_size_gb: float = Field(
        default=4.0, gt=0, description="Maximum video file size in GB"
    )
    analysis_timeout_min: int = Field(
        default=60, gt=0, description="Analysis timeout in minutes"
    )


_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Get or create application settings singleton."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    """Force reload settings (useful for tests)."""
    global _settings
    _settings = AppSettings()
    return _settings
