# RealtimeService

Processes a live stream (file, webcam, RTSP, HTTP) and emits analytics
events to subscribers. Designed for live coach review during a match.

## Quick start

```python
import asyncio
from kawkab.services.realtime_service import (
    RealtimeService, CallbackSubscriber, LowFpsAlertRule
)
from kawkab.services.cv_service import CVService

async def main():
    cv = CVService()
    await cv.initialize()
    rt = RealtimeService(cv_service=cv, target_fps=15.0)

    rt.subscribe(CallbackSubscriber(lambda e: print(f"  {e.kind.value}: {e.message}")))
    rt.add_alert_rule(LowFpsAlertRule(min_fps=12.0))

    stats = await rt.run_file("match.mp4")
    print(f"Processed {stats.frames_processed} frames at {stats.actual_fps:.1f} FPS")
    print(f"Emitted {stats.events_emitted} events")

asyncio.run(main())
```

## Configuration

| Param | Default | Description |
|---|---|---|
| cv_service | new CVService() | Detection service for frames |
| target_fps | 15.0 | Processing rate. Faster frames are dropped. |
| buffer_size | 300 | How many recent frames to keep in memory |
| stats_interval_s | 1.0 | How often to emit StreamStats |

## Alert rules

Built-in rules:

- `ShotAlertRule` — fire on shot-event frame (cooldown 1.5s)
- `LowFpsAlertRule(min_fps=10.0)` — fire when actual FPS drops below threshold
- `LowConfidenceAlertRule(min_conf=0.4)` — fire when avg detection confidence is low

Custom rules subclass `AlertRule`:

```python
class GoalCelebrationRule(AlertRule):
    kind = AlertKind.GOAL
    cooldown_s = 5.0

    def evaluate(self, frame, prev_frame, ctx):
        if "goal_celebration" in (frame.tags or []):
            return RealtimeEvent(
                kind=self.kind, severity=AlertSeverity.INFO,
                timestamp_s=frame.timestamp, frame_index=frame.frame_number,
                message="Goal celebration detected"
            )
        return None
```

## Subscribers

- `ConsoleSubscriber` — logs to stdout (debug)
- `CallbackSubscriber(cb)` — forwards events to a sync/async callable
- Custom: subclass `RealtimeSubscriber` and implement `on_event`

## StreamStats

Per-second stats contain:
- `actual_fps`, `frames_processed`, `frames_dropped`
- `events_emitted`, `low_confidence_frames`
- `avg_track_count`, `elapsed_s`
