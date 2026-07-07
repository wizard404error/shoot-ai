from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing import Queue, Process
from queue import Empty as QueueEmpty
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    INGEST = "ingest"
    PROCESS = "process"
    ANALYZE = "analyze"
    OUTPUT = "output"


@dataclass
class PipelineFrame:
    index: int
    timestamp: float
    data: Optional[np.ndarray] = None
    detections: Optional[list[dict]] = None
    analytics: Optional[dict] = None


@dataclass
class PipelineStats:
    ingest_fps: float = 0.0
    process_fps: float = 0.0
    queue_depth: int = 0
    frames_ingested: int = 0
    frames_processed: int = 0
    dropped_frames: int = 0
    avg_latency_ms: float = 0.0


class OutputTarget(str, Enum):
    NONE = "none"
    WINDOW = "window"
    RTMP = "rtmp"
    WEBSOCKET = "websocket"


class DualAsyncPipeline:
    """Producer-consumer pipeline for real-time video analysis.

    Stage 1 (Ingest): reads frames from source into a bounded queue.
    Stage 2 (Process): pops frames from queue, runs detection/analytics.
    Stage 3 (Output): sends processed frames to target (window, RTMP, WS).
    """

    def __init__(
        self,
        process_fn: Callable[[np.ndarray], dict],
        max_queue_size: int = 60,
        target_fps: float = 30.0,
    ) -> None:
        self._process_fn = process_fn
        self._max_queue_size = max_queue_size
        self._target_fps = target_fps
        self._frame_queue: Queue = Queue(maxsize=max_queue_size)
        self._stats_queue: Queue = Queue(maxsize=10)
        self._cancel = False
        self._ingest_process: Optional[Process] = None
        self._process_process: Optional[Process] = None
        self._output_targets: list[tuple[OutputTarget, str]] = []
        self._ws_clients: list[Any] = []
        self._ffmpeg_proc: Optional[subprocess.Popen] = None

    # ── Public API ──

    def add_rtmp_output(self, rtmp_url: str) -> None:
        self._output_targets.append((OutputTarget.RTMP, rtmp_url))

    def add_ws_client(self, websocket: Any) -> None:
        self._ws_clients.append(websocket)

    def remove_ws_client(self, websocket: Any) -> None:
        self._ws_clients = [c for c in self._ws_clients if c is not websocket]

    async def run(self, source: str) -> PipelineStats:
        self._cancel = False
        ingest_task = asyncio.create_task(self._ingest_loop(source))
        process_task = asyncio.create_task(self._process_loop())
        output_task = asyncio.create_task(self._output_loop())
        stats_task = asyncio.create_task(self._stats_collector())
        try:
            await asyncio.gather(ingest_task, process_task, output_task)
        except asyncio.CancelledError:
            self.cancel()
        finally:
            stats_task.cancel()
            self._cleanup()
        return await self._collect_final_stats()

    def cancel(self) -> None:
        self._cancel = True

    # ── Stage 1: Ingest ──

    async def _ingest_loop(self, source: str) -> None:
        import cv2

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise ValueError(f"Cannot open source: {source}")
        fps = cap.get(cv2.CAP_PROP_FPS) or self._target_fps
        frame_skip = max(1, int(fps / self._target_fps))
        frame_idx = 0
        ingest_start = time.monotonic()
        frames_ingested = 0
        while not self._cancel:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx += 1
            if frame_idx % frame_skip != 0:
                continue
            pf = PipelineFrame(
                index=frames_ingested,
                timestamp=time.monotonic() - ingest_start,
                data=frame,
            )
            try:
                self._frame_queue.put(pf, timeout=1.0)
                frames_ingested += 1
            except Exception:
                logger.warning("Ingest queue full, dropping frame %d", frame_idx)
        cap.release()
        self._frame_queue.put(None)  # sentinel

    # ── Stage 2: Process ──

    async def _process_loop(self) -> None:
        loop = asyncio.get_running_loop()
        process_count = 0
        while not self._cancel:
            try:
                pf = await loop.run_in_executor(None, lambda: self._safe_get())
            except StopIteration:
                break
            if pf is None:
                self._frame_queue.put(None)
                break
            start = time.monotonic()
            result = await loop.run_in_executor(None, self._process_fn, pf.data)
            latency = (time.monotonic() - start) * 1000
            pf.detections = result.get("detections", [])
            pf.analytics = result.get("analytics", {})
            pf.analytics["latency_ms"] = round(latency, 1)
            process_count += 1
            try:
                self._stats_queue.put({
                    "latency_ms": latency,
                    "processed": process_count,
                    "ingested": pf.index + 1,
                }, timeout=0.1)
            except Exception:
                pass

    def _safe_get(self) -> Optional[PipelineFrame]:
        try:
            item = self._frame_queue.get(timeout=0.5)
            return item
        except QueueEmpty:
            return None

    # ── Stage 3: Output ──

    async def _output_loop(self) -> None:
        import cv2

        for target, url in self._output_targets:
            if target == OutputTarget.RTMP:
                self._init_rtmp_output(url)

        while not self._cancel:
            try:
                pf = self._safe_get()
            except StopIteration:
                break
            if pf is None:
                break
            self._output_to_ws(pf)
            self._output_to_rtmp(pf)
            for target, url in self._output_targets:
                if target == OutputTarget.WINDOW:
                    self._output_to_window(pf)

    def _init_rtmp_output(self, rtmp_url: str) -> None:
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", "1280x720",
            "-r", str(self._target_fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-f", "flv",
            rtmp_url,
        ]
        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error("Failed to start RTMP output: %s", e)

    def _output_to_rtmp(self, pf: PipelineFrame) -> None:
        if self._ffmpeg_proc is not None and pf.data is not None:
            try:
                self._ffmpeg_proc.stdin.write(pf.data.tobytes())  # type: ignore
            except Exception:
                pass

    def _output_to_window(self, pf: PipelineFrame) -> None:
        import cv2

        if pf.data is not None:
            display = pf.data.copy()
            if pf.detections:
                for d in pf.detections:
                    bbox = d.get("bbox", [])
                    if len(bbox) == 4:
                        x1, y1, x2, y2 = map(int, bbox)
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imshow("Kawkab AI Live", display)
            cv2.waitKey(1)

    def _output_to_ws(self, pf: PipelineFrame) -> None:
        payload = json.dumps({
            "type": "frame_analytics",
            "frame_index": pf.index,
            "timestamp": pf.timestamp,
            "detection_count": len(pf.detections or []),
            "analytics": pf.analytics or {},
        })
        for ws in list(self._ws_clients):
            try:
                asyncio.ensure_future(ws.send_text(payload))
            except Exception:
                self._ws_clients.remove(ws)

    # ── Stats ──

    async def _stats_collector(self) -> None:
        latencies: list[float] = []
        while not self._cancel:
            try:
                item = self._stats_queue.get(timeout=0.5)
                if item:
                    latencies.append(item["latency_ms"])
                    if len(latencies) > 100:
                        latencies = latencies[-100:]
            except QueueEmpty:
                pass
            await asyncio.sleep(0.5)

    async def _collect_final_stats(self) -> PipelineStats:
        latencies = []
        frames_processed = 0
        while not self._stats_queue.empty():
            try:
                item = self._stats_queue.get_nowait()
                latencies.append(item["latency_ms"])
                frames_processed = max(frames_processed, item["processed"])
            except QueueEmpty:
                break
        avg_lat = float(np.mean(latencies)) if latencies else 0.0
        return PipelineStats(
            frames_processed=frames_processed,
            avg_latency_ms=round(avg_lat, 1),
        )

    def _cleanup(self) -> None:
        if self._ffmpeg_proc is not None:
            try:
                self._ffmpeg_proc.stdin.close()
                self._ffmpeg_proc.wait(timeout=5)
            except Exception:
                self._ffmpeg_proc.kill()
            self._ffmpeg_proc = None


class WebSocketTelemetryStream:
    """Streams analytics telemetry over WebSocket connections.

    Attaches to an existing RealtimeService or DualAsyncPipeline
    and forwards detections, track positions, and stats to connected
    browser clients.
    """

    def __init__(self) -> None:
        self._clients: list[Any] = []
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=200)

    def add_client(self, ws: Any) -> None:
        self._clients.append(ws)

    def remove_client(self, ws: Any) -> None:
        self._clients = [c for c in self._clients if c is not ws]

    def push_frame(self, frame_data: dict) -> None:
        try:
            self._buffer.put_nowait(frame_data)
        except asyncio.QueueFull:
            pass

    async def run(self) -> None:
        while True:
            try:
                data = await asyncio.wait_for(self._buffer.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            payload = json.dumps(data)
            for ws in list(self._clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    self._clients.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)
