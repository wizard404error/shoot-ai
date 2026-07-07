# Model Monitoring

## Snapshot Recording

```python
from kawkab.services.model_monitor_service import ModelMonitor

monitor = ModelMonitor()
monitor.record_snapshot("xg_model", predictions, actuals)
```

## Drift Detection

Monitors Brier score and log-loss against configurable thresholds:

- Brier drift threshold: 0.05
- Log-loss drift threshold: 0.10

## Dashboard

```python
from kawkab.services.model_monitor_service import ModelMonitoringService

svc = ModelMonitoringService()
dashboard = svc.dashboard()
```

## Auto-Retrain Check

```python
needs_retrain = svc.check_retrain_needed()
```
