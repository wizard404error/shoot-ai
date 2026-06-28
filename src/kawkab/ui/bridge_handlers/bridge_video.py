"""Handler for video/realtime bridge methods, including multi-angle sync, trimming, and highlight reel."""

from __future__ import annotations

import json

from kawkab.core.logging import get_logger
from kawkab.core.security import ErrorSanitizer, SecurityValidator
from kawkab.services.video_sync_service import MultiAngleSyncService
from kawkab.services.highlight_reel_service import HighlightReelService

logger = get_logger(__name__)


class VideoHandler:
    """Handles video / real-time streaming operations for Bridge."""

    def __init__(self, bridge, services):
        self._bridge = bridge
        self._services = services
        self._sync_service = MultiAngleSyncService()
        reel_output = getattr(bridge, "_reel_output_dir", None)
        self._highlight_reel = HighlightReelService(output_dir=reel_output)

    @property
    def realtime_service(self):
        return self._services.get("realtime_service")

    # --- Multi-Angle Sync ---

    def sync_load(self, videos_json: str) -> str:
        try:
            paths = json.loads(videos_json)
            return self._sync_service.load_videos(paths)
        except Exception as e:
            logger.error(f"sync_load failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def sync_set_offset(self, source_index: int, offset_seconds: float) -> str:
        try:
            return self._sync_service.set_offset(source_index, offset_seconds)
        except Exception as e:
            logger.error(f"sync_set_offset failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def sync_positions(self, master_time: float) -> str:
        try:
            return self._sync_service.get_sync_positions(master_time)
        except Exception as e:
            logger.error(f"sync_positions failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def sync_state(self) -> str:
        try:
            return self._sync_service.get_state()
        except Exception as e:
            logger.error(f"sync_state failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def sync_clear(self) -> str:
        try:
            return self._sync_service.clear()
        except Exception as e:
            logger.error(f"sync_clear failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- Video Trimming ---

    def trim_video(self, video_path: str, start_seconds: float, end_seconds: float, output_name: str = "") -> str:
        try:
            path = SecurityValidator.validate_video_path(video_path)
            if not path:
                return json.dumps({"error": "Invalid video path"})
            import asyncio
            from kawkab.services.clip_service import ClipExtractionService
            svc = ClipExtractionService()
            name = output_name or f"trim_{int(start_seconds)}_{int(end_seconds)}.mp4"
            result = asyncio.run(svc.extract_clip(path, start_seconds, end_seconds, name, quality="high"))
            return json.dumps({"output": result, "ok": True})
        except Exception as e:
            logger.error(f"trim_video failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- Highlight Reel ---

    def reel_compose(self, clips_json: str, output_filename: str) -> str:
        try:
            import asyncio
            from kawkab.services.highlight_reel_service import ReelClip
            clips_data = json.loads(clips_json)
            clips = [
                ReelClip(video_path=c["video_path"], start_seconds=c["start_s"], end_seconds=c["end_s"], label=c.get("label", ""))
                for c in clips_data
            ]
            result = asyncio.run(self._highlight_reel.compose_reel(clips, output_filename))
            return result
        except Exception as e:
            logger.error(f"reel_compose failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def reel_from_events(self, match_id: int, events_json: str, video_path: str) -> str:
        try:
            events = json.loads(events_json)
            result = self._highlight_reel.make_reel_from_events(match_id, events, video_path)
            return result
        except Exception as e:
            logger.error(f"reel_from_events failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    # --- Realtime ---

    def realtime_status(self):
        if self.realtime_service is None:
            return json.dumps({"available": False, "error": "RealtimeService not initialized"})
        try:
            return json.dumps({
                "available": True,
                "target_fps": self.realtime_service.target_fps,
                "buffer_size": self.realtime_service.buffer_size,
                "alert_rule_count": len(self.realtime_service._alert_rules),
                "subscriber_count": len(self.realtime_service._subscribers),
            })
        except Exception as e:
            logger.error(f"realtime_status failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def realtime_cancel(self):
        if self.realtime_service is None:
            return json.dumps({"error": "RealtimeService not initialized"})
        try:
            self.realtime_service.cancel()
            return json.dumps({"ok": True, "message": "Realtime stream cancelled"})
        except Exception as e:
            logger.error(f"realtime_cancel failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def realtime_subscribe_console(self):
        if self.realtime_service is None:
            return json.dumps({"error": "RealtimeService not initialized"})
        try:
            from kawkab.services.realtime_service import ConsoleSubscriber
            sub = ConsoleSubscriber()
            self.realtime_service.subscribe(sub)
            return json.dumps({"ok": True, "message": "Console subscriber added"})
        except Exception as e:
            logger.error(f"realtime_subscribe_console failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})
