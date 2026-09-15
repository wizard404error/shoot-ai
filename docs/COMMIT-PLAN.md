# Selective-commit plan (elite-readiness work)

Status: **plan only — nothing has been committed or staged.** This worktree
also contains work from a concurrent xG-retraining session; this file
documents hunk-level ownership so a selective commit can include this
pass's work without sweeping in that session's (failing) files.

## File ownership map (the three mixed files)

### `src/kawkab/__main__.py` — 100% elite-readiness
All 119 added lines are the `validate` + `import` CLI subcommands and their
runners (`_run_validate`, `_run_import`). Stage whole.

### `src/kawkab/api/api_v1.py` — mixed: ONE hunk belongs to the xG session
| Hunk | Location | Owner | Action |
|---|---|---|---|
| 1 | `+from pathlib import Path` | elite-readiness | stage |
| 2 | `_get_audit()` helper | elite-readiness | stage |
| 3 | `analyze_shots`: `compute_xg_from_dict` → `compute_xg_trained_from_dict` (2 lines) | **xG-retraining session** | **SKIP** |
| 4 | pro/season analytics endpoints (`/matches/{id}/analysis/pro`, `/season/pro`) | pre-dates both | stage (harmless, already wired) |
| 5 | trailing 383 lines: tracking/event import + audit endpoints | elite-readiness | stage |

Interactive staging:
```bash
git add -p src/kawkab/api/api_v1.py
#   hunk 1 (Path import)            -> y
#   hunk 2 (_get_audit)             -> y
#   hunk 3 (compute_xg_trained...)  -> n   <-- the only 'n'
#   hunk 4 (pro endpoints)          -> y
#   hunk 5 (import/audit endpoints) -> y
```
Verify nothing foreign got staged:
```bash
git diff --cached src/kawkab/api/api_v1.py | grep -c "xg_trained"   # must print 0
```

### `src/kawkab/migrations/pg_schema.sql` — 100% elite-readiness
All hunks: trigger idempotency (`DROP TRIGGER IF EXISTS` ×4), the RLS
drop-then-create rewrite, `idx_events_dedup` made UNIQUE (mirrors SQLite
migration 015 — required by `save_events_bulk` ON CONFLICT), and the
elite tables (`tracking_imports`, `event_frame_links`, `users`,
`user_sessions`, `audit_events_local`, `gps_*`, `acwr_daily`,
`matches_external_ids`) + indexes. Stage whole.

## Include (per prior decision): validation data

- `data/statsbomb_corpus/*.json` — committed as the project's validation
  corpus (`kawkab validate` reads it).
- `tests/fixtures/tracking/` — real Metrica open-data fixture slices +
  provenance README (`tests/fixtures/tracking/README.md`).

## Exclude at commit time (concurrent session's)

- Anything matching `xg_trained` / retraining in staged diffs — beyond the
  api_v1.py hunk, check:
  ```bash
  git diff --cached | grep -in "xg_trained\|retrain"   # expect empty
  ```
- The xG session's own files (model retrain scripts/tests), if present.
- Generated artifacts: `src/kawkab/web/dist/`, `__pycache__/`, `/tmp` data.

## Suggested staging groups (order preserves a green tree at each step)

1. Schema + storage: `pg_schema.sql`, `migrations/030*.sql`, `migrations/031*.sql`,
   `postgres_storage.py`, `storage_service.py`, `services/storage/`
2. Services: `validation_report_service.py`, `season_import_service.py`,
   `vendor_tracking_import_service.py`, `vendor_event_import_service.py`,
   `analysis/acwr.py`, `core/migration_manager.py`
3. API + CLI: `api/api_v1.py` (per hunk map above), `__main__.py`
4. UI: `ui/bridge.py`, `ui/bridge_handlers/bridge_import.py`,
   `ui/bridge_handlers/__init__.py`
5. Web: `web/index.html`, `web/js/app.js`, `web/js/app-import.js`,
   `web/js/app-search-compare.js`, `sw.js`, `scripts/frontend-manifest.json`
6. Tests: `tests/unit/test_*`, `tests/conftest.py`
7. Data + docs: `data/statsbomb_corpus/`, `tests/fixtures/tracking/`,
   `docs/analyst-guide.md`, `docs/elite-deployment.md`, `docs/INDEX.md`,
   this file
