# Tests

## Test Structure

```
tests/
├── unit/          # Fast, isolated unit tests (3700+)
├── e2e/           # End-to-end pipeline tests
└── conftest.py    # Shared fixtures
```

## Running Tests

```bash
# All unit tests (excluding infrastructure-dependent)
$env:PYTHONPATH="src"; python -m pytest tests/unit/ \
    --ignore=tests/unit/test_audio_service.py -q

# Named test files
python -m pytest tests/unit/test_xg_model.py tests/unit/test_vaep.py -v

# With JWT secret for cloud tests
$env:KAWKAB_JWT_SECRET="test-secret"; python -m pytest tests/unit/test_oauth_api.py -v
```

## Regression Tests

Requires StatsBomb ground truth data:

```bash
python scripts/download_ground_truth.py --statsbomb --output data/ground_truth
python -m pytest tests/unit/test_regression_xg_models.py -v
```

## Load Tests

```bash
python -m pytest tests/unit/test_performance_benchmarks.py --run-load -v
```

## CI Pipeline

- `lint` — Ruff + mypy
- `unit` — Core analytical tests
- `regression` — Ground truth validation
- `server` — Cloud/OAuth/health tests
- `benchmark` — Load tests (nightly)
