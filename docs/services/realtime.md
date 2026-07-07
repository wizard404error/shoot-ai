# Real-time Pipeline

## V1 — RealtimeService

Sequential frame processing with alert rules and subscribers.

```python
from kawkab.services.realtime_service import RealtimeService
svc = RealtimeService(cv_service)
stats = await svc.run_file("match.mp4")
```

## V2 — DualAsyncPipeline

Producer/consumer pipeline with separate ingest and processing stages.

```python
from kawkab.services.realtime_pipeline_v2 import DualAsyncPipeline

pipe = DualAsyncPipeline(process_fn=my_process_fn)
pipe.add_rtmp_output("rtmp://example.com/live")
pipe.add_ws_client(websocket)
stats = await pipe.run("match.mp4")
```

## WebSocket Telemetry

Stream analytics to browser clients in real time:

```python
from kawkab.services.realtime_pipeline_v2 import WebSocketTelemetryStream

stream = WebSocketTelemetryStream()
stream.add_client(websocket)
stream.push_frame({"type": "frame_analytics", "detections": [...]})
```
