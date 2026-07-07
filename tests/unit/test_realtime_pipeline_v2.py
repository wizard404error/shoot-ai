from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from kawkab.services.realtime_pipeline_v2 import (
    DualAsyncPipeline,
    WebSocketTelemetryStream,
    OutputTarget,
    PipelineFrame,
    PipelineStats,
)


def dummy_process_fn(frame: np.ndarray) -> dict:
    return {
        "detections": [
            {"bbox": [10, 20, 100, 200], "confidence": 0.95, "class": "player"},
        ],
        "analytics": {"player_count": 1},
    }


class TestDualAsyncPipeline:
    def test_init_sets_defaults(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        assert pipe._max_queue_size == 60
        assert pipe._target_fps == 30.0
        assert pipe._cancel is False

    def test_add_rtmp_output(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        pipe.add_rtmp_output("rtmp://example.com/live/stream")
        assert len(pipe._output_targets) == 1
        assert pipe._output_targets[0][0] == OutputTarget.RTMP
        assert pipe._output_targets[0][1] == "rtmp://example.com/live/stream"

    def test_add_ws_client(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        ws = MagicMock()
        pipe.add_ws_client(ws)
        assert len(pipe._ws_clients) == 1

    def test_remove_ws_client(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        ws1 = MagicMock()
        ws2 = MagicMock()
        pipe.add_ws_client(ws1)
        pipe.add_ws_client(ws2)
        pipe.remove_ws_client(ws1)
        assert len(pipe._ws_clients) == 1
        assert pipe._ws_clients[0] is ws2

    def test_cancel_sets_flag(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        assert pipe._cancel is False
        pipe.cancel()
        assert pipe._cancel is True

    def test_safe_get_returns_none_on_empty(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        result = pipe._safe_get()
        assert result is None

    def test_safe_get_returns_frame(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        pf = PipelineFrame(index=0, timestamp=0.0, data=np.zeros((100, 100, 3), dtype=np.uint8))
        pipe._frame_queue.put(pf)
        result = pipe._safe_get()
        assert result is not None
        assert result.index == 0

    def test_output_to_ws_sends_json(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        ws = MagicMock()
        pipe.add_ws_client(ws)
        pf = PipelineFrame(index=0, timestamp=1.0, detections=[{"bbox": [0, 0, 10, 10]}], analytics={"test": 1})
        pipe._output_to_ws(pf)
        ws.send_text.assert_called_once()
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"] == "frame_analytics"
        assert payload["frame_index"] == 0
        assert payload["detection_count"] == 1

    def test_output_to_ws_removes_dead_client(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        ws = MagicMock()
        ws.send_text.side_effect = Exception("gone")
        pipe.add_ws_client(ws)
        pf = PipelineFrame(index=0, timestamp=0.0)
        pipe._output_to_ws(pf)
        assert len(pipe._ws_clients) == 0

    @patch("subprocess.Popen")
    def test_init_rtmp_output_starts_ffmpeg(self, mock_popen):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        pipe._target_fps = 25.0
        pipe._init_rtmp_output("rtmp://example.com/stream")
        mock_popen.assert_called_once()
        assert pipe._ffmpeg_proc is not None

    def test_cleanup_closes_ffmpeg(self):
        pipe = DualAsyncPipeline(process_fn=dummy_process_fn)
        mock_proc = MagicMock()
        pipe._ffmpeg_proc = mock_proc
        pipe._cleanup()
        mock_proc.stdin.close.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)


class TestWebSocketTelemetryStream:
    def test_add_client(self):
        stream = WebSocketTelemetryStream()
        ws = MagicMock()
        stream.add_client(ws)
        assert ws in stream._clients

    def test_remove_client(self):
        stream = WebSocketTelemetryStream()
        ws1 = MagicMock()
        ws2 = MagicMock()
        stream.add_client(ws1)
        stream.add_client(ws2)
        stream.remove_client(ws1)
        assert ws1 not in stream._clients
        assert ws2 in stream._clients

    def test_push_frame_queues_data(self):
        stream = WebSocketTelemetryStream()
        stream.push_frame({"type": "test", "value": 42})
        assert stream._buffer.qsize() == 1

    def test_push_frame_full_queue_does_not_block(self):
        stream = WebSocketTelemetryStream()
        for i in range(300):
            stream.push_frame({"i": i})
        assert stream._buffer.qsize() <= 200

    def test_client_count(self):
        stream = WebSocketTelemetryStream()
        assert stream.client_count == 0
        stream.add_client(MagicMock())
        assert stream.client_count == 1
        stream.add_client(MagicMock())
        assert stream.client_count == 2

    @pytest.mark.asyncio
    async def test_run_sends_to_clients(self):
        stream = WebSocketTelemetryStream()
        ws = MagicMock()
        stream.add_client(ws)
        stream.push_frame({"type": "test"})

        async def run_and_stop():
            task = asyncio.create_task(stream.run())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_and_stop()
        assert ws.send_text.called

    @pytest.mark.asyncio
    async def test_run_removes_dead_client(self):
        stream = WebSocketTelemetryStream()
        ws = MagicMock()
        ws.send_text.side_effect = Exception("gone")
        stream.add_client(ws)
        stream.push_frame({"type": "test"})

        async def run_and_stop():
            task = asyncio.create_task(stream.run())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_and_stop()
        assert len(stream._clients) == 0
