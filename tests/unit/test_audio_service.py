"""Tests for AudioService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from conftest import install_kawkab_stubs, load_service_module

install_kawkab_stubs()

_mod = load_service_module("kawkab.services.audio_service", "audio_service.py")
AudioService = _mod.AudioService


class TestAudioService:
    @pytest.mark.asyncio
    async def test_initialize_skips_if_disabled(self):
        service = AudioService(enable_transcription=False, enable_whistle_detection=False)
        await service.initialize()
        assert service._model is None

    @pytest.mark.asyncio
    async def test_initialize_loads_whisper(self, monkeypatch):
        fake_model = MagicMock()
        monkeypatch.setattr("kawkab.services.audio_service.WhisperModel", lambda **kw: fake_model)
        service = AudioService(enable_transcription=True, enable_whistle_detection=False)
        await service.initialize()
        assert service._model is not None

    @pytest.mark.asyncio
    async def test_transcribe(self):
        fake_segment = MagicMock()
        fake_segment.text = "hello world"
        fake_segment.start = 0.0
        fake_segment.end = 2.0
        fake_model = MagicMock()
        fake_model.transcribe.return_value = ([fake_segment], None)
        service = AudioService(enable_transcription=True, enable_whistle_detection=False)
        service._model = fake_model
        result = await service.transcribe("test.mp3")
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_transcribe_no_model(self):
        service = AudioService(enable_transcription=False)
        result = await service.transcribe("test.mp3")
        assert result == {}

    @pytest.mark.asyncio
    async def test_detect_whistles(self, monkeypatch):
        monkeypatch.setattr("kawkab.services.audio_service.librosa", MagicMock())
        fake_model = MagicMock()
        service = AudioService(enable_transcription=False, enable_whistle_detection=True)
        service._model = fake_model
        result = await service.detect_whistles("test.mp3")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_analyze_crowd_noise(self, monkeypatch):
        monkeypatch.setattr("kawkab.services.audio_service.librosa", MagicMock())
        service = AudioService(enable_transcription=False, enable_crowd_analysis=True)
        result = await service.analyze_crowd_noise("test.mp3")
        assert "avg_intensity" in result

    @pytest.mark.asyncio
    async def test_initialize_handles_import_error(self, monkeypatch):
        monkeypatch.setattr("kawkab.services.audio_service.WhisperModel", MagicMock(side_effect=ImportError("no whisper")))
        service = AudioService(enable_transcription=True)
        await service.initialize()
        assert service._model is None
