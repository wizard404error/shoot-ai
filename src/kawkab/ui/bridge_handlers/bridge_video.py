"""Handler for video/realtime bridge methods (realtimeStatus, realtimeCancel, realtimeSubscribe)."""

from __future__ import annotations

import json

from kawkab.core.logging import get_logger
from kawkab.core.security import ErrorSanitizer

logger = get_logger(__name__)


class VideoHandler:
    """Handles video / real-time streaming operations for Bridge."""

    def __init__(self, bridge, services):
        self._bridge = bridge
        self._services = services

    @property
    def realtime_service(self):
        return self._services.get("realtime_service")

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
