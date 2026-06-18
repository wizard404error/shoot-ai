# PositioningService

Analyzes off-ball movement — runs behind defense, width-stretching runs,
decoy movements, drop-offs. Classifies each run by direction and speed
and estimates the xT the run created for teammates.

## Quick start

```python
from kawkab.services.positioning_service import PositioningService
from kawkab.services.cv_service import MatchTrackData

service = PositioningService(min_run_distance_m=5.0)
report = service.analyze(track_data, team="home")
print(f"{report.total_runs} runs, longest {report.longest_run_m}m")
for run in report.runs[:5]:
    print(f"  {run.run_type.value}: {run.distance_m}m at {run.avg_speed_mps:.1f} m/s")
```

## Configuration

| Param | Default | Description |
|---|---|---|
| pitch_length_m | 105.0 | Real pitch length (used to convert pixel deltas to meters) |
| pitch_width_m | 68.0 | Real pitch width |
| min_run_distance_m | 5.0 | Ignore shorter runs as noise |
| sprint_threshold_mps | 5.5 | Speed (m/s) considered a sprint |
| fps | 30.0 | Video frame rate for speed computation |

## RunType enum

- `BEHIND_DEFENSE` — forward run through the middle
- `WIDE` — wide run without significant forward progress
- `DIAGONAL` — wide run with forward progress
- `SUPPORT` — short supporting movement
- `DROP` — backward run (often a defender shifting)
- `DECOY` — false movement to create space (derived from xT effect)
- `UNKNOWN` — could not be classified

## Output

`PositioningReport` contains:

- `total_runs` — number of runs found
- `runs_by_type` — dict mapping RunType -> count
- `total_distance_m`, `avg_run_distance_m`, `longest_run_m`
- `total_xT_created` — sum of xT delta over all runs
- `runs` — list of `Run` records (one per detected run)
- `notes` — coaching observations

Each `Run` has `player_track_id`, `start_frame`/`end_frame`, distance,
speeds, and `created_xT_delta`.

## See also

- `PossessionService` for ball-side analysis
- `ScoutingService` for opponent off-ball tendencies
