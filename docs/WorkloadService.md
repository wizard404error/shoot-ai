# WorkloadService

Computes the Acute:Chronic Workload Ratio (ACWR) and related injury-risk
indicators from training and match load over a 28-day window. Used by
sports scientists to flag fatigue and over-training.

## Quick start

```python
from datetime import date
from kawkab.services.workload_service import WorkloadService, WorkloadRecord, WorkloadSource

records = [
    WorkloadRecord("2024-01-22", WorkloadSource.MATCH, 90, rpe=7.0, distance_m=10000),
    WorkloadRecord("2024-01-23", WorkloadSource.TRAINING, 60, rpe=4.0, distance_m=4000),
    # ... more records
]
service = WorkloadService()
report = service.analyze(player_id=7, player_name="X", history=records)
print(f"ACWR: {report.acwr:.2f} ({report.risk_level.value})")
for rec in report.recommendations:
    print(f"  - {rec}")
```

## ACWR thresholds

| ACWR | Risk |
|---|---|
| < 0.8 | MODERATE (under-trained) |
| 0.8 - 1.3 | LOW (sweet spot) |
| 1.3 - 1.5 | MODERATE-HIGH |
| 1.5 - 2.0 | HIGH |
| ≥ 2.0 | VERY HIGH |

## Monotony & Strain

- **Monotony** = mean daily load / stdev. > 2.0 indicates repetitive training
- **Strain** = weekly total × monotony

## WorkloadRecord fields

- `date` — ISO date string
- `source` — `WorkloadSource.MATCH` or `WorkloadSource.TRAINING`
- `duration_min` — session length
- `rpe` — session rating of perceived exertion (0-10)
- `distance_m` — total distance covered
- `sprints` — number of sprint efforts
- `high_intensity_m` — distance > 5.5 m/s

Session load is computed as `rpe * duration_min` (Foster sRPE) when
rpe is given; otherwise defaults are 7 (match) or 4 (training) per minute.

## References

- Hulin et al. (2014) — ACWR > 1.5 = elevated injury risk
- Gabbett (2016) — the 0.8 - 1.3 "sweet spot"
- Foster's sRPE method
