# CLAUDE.md — Kawkab AI

Source of truth for working on this codebase. Supersedes AGENTS.md and every
other root-level markdown file (all archived under `docs/archive/` — kept for
history, not maintained). If something here conflicts with an archived file,
this file is right; the archived one was a snapshot in time.

## What this is

Kawkab AI is a football (soccer) analytics platform for amateur-through-elite
coaches: a PySide6 desktop app that runs YOLO11 player/ball tracking on match
video, detects events, computes 117 analytical models (xG, xT, VAEP, pitch
control, pressing, set pieces, ...), and surfaces them through a vanilla-JS
SPA served inside a `QWebEngineView` over `QWebChannel`. SQLite by default;
optional PostgreSQL backend and a separate multi-user FastAPI cloud server for
team collaboration. Bilingual (English/Arabic, full RTL).

The analytical depth is real and the test suite is real. The layers *between*
the models and the coach had multiple breaks — this file exists so they don't
come back.

## Correct commands (read this before running anything)

```powershell
# Desktop app
$env:PYTHONPATH="src"; python -m kawkab
# or explicitly:
$env:PYTHONPATH="src"; python -m kawkab gui

# Full unit suite (4,886 tests as of 2026-07-30, should be 0 failures)
$env:PYTHONPATH="src"; python -m pytest tests/unit/ -q

# Lint / types (installed as of 2026-07-30 -- see "Correct commands" note below)
python -m ruff check src/ tests/
python -m mypy src/kawkab --ignore-missing-imports

# Root-level suite (includes tests/test_load.py, tests/e2e/, tests/integration/)
$env:PYTHONPATH="src"; python -m pytest tests/ -q

# Frontend build (run after touching any src/kawkab/web/js/*.js file)
node scripts/bundle-js.mjs

# Frontend tests
cd src/kawkab/web && npm test

# Coverage
$env:PYTHONPATH="src"; python -m pytest tests/unit/ --cov=src/kawkab --cov-report=term
```

**Why `PYTHONPATH=src` in every command above:** `kawkab` is not installed
(editable or otherwise) into the system Python on this machine — every
dependency was installed directly, but the project itself never went
through `pip install -e .` / `uv sync`. A fresh clone following the README's
own `uv sync` install flow gets a real editable install and doesn't need
`PYTHONPATH` at all (`uv run python -m kawkab` just works). Both are fine;
this file documents what actually works on the machine this audit ran on.

**Use the system `python`, not `.venv\Scripts\python.exe`.** This repo has two
Python installs: a `.venv` at 3.12 (has almost nothing installed in it) and
the system `python` at 3.11.9 (has every real dependency — PySide6, torch,
opencv, ultralytics, pytest, everything). The system one is what actually
works on this machine; `.venv` looks "correct" by version number but is
functionally empty. `requires-python` was `">=3.12"` — which made the
*correct* interpreter look unsupported by the project's own metadata, despite
demonstrably running the full suite clean. Nothing in `src/` uses 3.12-only
syntax (checked: no PEP 695 `type X = ...` / `class Foo[T]`), so relaxed to
`">=3.11"` (also updated `[tool.ruff] target-version` and `[tool.mypy]
python_version` to match). If you're setting up a fresh clone, `pip install
-e ".[test,cloud]"` into whatever interpreter you use (see the packaging note
below — that command was broken until this session's fixes).

**`ruff`/`mypy`/`pytest-xdist` were added to `pyproject.toml`'s `dev`/`test`
extras this session but never actually installed** — they were configured,
not verified, until the final verification pass caught it (`python -m ruff`
→ `No module named ruff`). `pip install -e ".[dev,test]"` also currently
fails on this machine's system Python (3.11.9) for an unrelated reason: pip
re-resolves the full dependency graph and *that* re-triggers `requires-python`
enforcement against whatever it was at the time — which is exactly the
metadata mismatch fixed above, but if you hit an install error that looks
like it again, run `pip install ruff mypy pytest-xdist` directly (bypasses
the project's own metadata resolution entirely) rather than fighting it.

**`KAWKAB_TEST_MODE` does nothing.** It's referenced only in a doc file
(`CLEANUP_PROMPT.md`), never read by any source file. Harmless to set, but
don't treat it as meaningful — the AGENTS.md-documented test commands that
included it were following a convention that was never implemented.

## Architecture map

```
src/kawkab/
  core/            117 analytical modules (pure functions/classes: xg_model,
                   xt_model, vaep, pitch_control, pass_network, ...). No I/O,
                   no bridge/service knowledge — importable and testable in
                   isolation. 59 of 117 are wired into services/bridge; 58 are
                   built + tested but not reachable from the UI (see below).
  services/        Business logic + I/O: cv_service (YOLO+tracking),
                   analysis/ (AnalysisService, split into mixins: core.py,
                   passing.py, ...), storage_service.py (SQLite),
                   postgres_storage.py (Postgres — NOT a drop-in twin of
                   storage_service, see "Storage backend divergence" below),
                   116 total service classes.
  ui/bridge.py     QWebChannel bridge exposed to JS as `kawkab.<method>()`.
                   Thin dispatcher only — every @Slot is a 2-line delegator
                   into ui/bridge_handlers/*.py. 325+ slots.
  ui/bridge_handlers/  AnalysisHandler (4,100+ lines, the biggest one),
                   AuthHandler, CodingHandler, ExportHandler, ExternalHandler,
                   LifecycleHandler, ProviderHandler, StorageHandler,
                   VideoHandler. Real implementations live here, not in
                   bridge.py.
  web/             Vanilla JS SPA. index.html (3000+ lines) + css/main.css
                   (5000+ lines) + js/*.js (28 IIFE files, concatenated by
                   scripts/bundle-js.mjs into dist/app.bundle.min.js, which
                   is what index.html actually loads).
  cloud/           Separate FastAPI multi-user server (auth, teams, sync) —
                   optional, desktop app never needs it.
  migrations/      27 numbered SQLite migration files, applied in order by
                   core/migration_manager.py. pg_schema.sql (no number
                   prefix, correctly skipped by the numeric-migration
                   scanner) is the separate Postgres schema.
```

## Invariants (why each of these exists — don't undo them without reading the reason)

- **Every `bridge.X(...)` / `kawkab.X(...)` call in `web/js/*.js` needs a
  matching `@Slot` in `ui/bridge.py`.** Enforced by
  `tests/unit/test_bridge_contract.py` — it fails the build if this drifts.
  6 calls were silently broken this way (Dashboard, Player Compare, 3D pitch,
  Scout search) before this session; the JS caught the resulting exception
  and degraded quietly, so nothing crashed loudly and nobody noticed.
- **Frontend load order lives in `scripts/frontend-manifest.json`, never in
  index.html's `<script>` tags.** `scripts/bundle-js.mjs` used to parse the
  file list out of index.html's script tags, bundle them, then *delete those
  tags from index.html*. The next run had nothing left to parse and would
  have silently emitted a near-empty bundle. The manifest is now the single,
  version-controlled source of truth; index.html's bundle `<script>` tag is
  permanent, hand-maintained markup. If you add a new IIFE file to
  `web/js/`, add it to the manifest, not to index.html.
- **`services/` delegates metrics to `core/`, never re-implements them.**
  `services/analysis/passing.py::_compute_pass_network` used to be its own,
  cruder pass-network builder (no betweenness, no eigenvector centrality)
  that happened to share a name with the real, richer `core/pass_network.py`.
  Same pattern in `advanced_event_detection_service.py::_detect_progressive_actions`
  vs `core/progressive_actions.py` (flat 10m-distance threshold vs the real
  ratio-of-remaining-distance + attacking-third + zone-aware logic driven by
  `game_constants.py`). Both now delegate. If you're about to write threshold
  logic in a `services/` file for something that sounds like an existing
  `core/` concept, check `core/` first.
- **norfair `Detection.points` must be `(N, 2)` for the `"iou"` distance
  function** (`services/norfair_tracker.py`). An older norfair accepted
  4-corner points; norfair>=2.3 validates strictly and raises
  `AssertionError: Bounding boxes must be defined as np.array with (N, 4)
  shape` (the "4" there means 4 *numbers* — 2 points × 2 coords — not 4
  points). `tests/unit/test_norfair_tracker.py` stubs the real package
  unconditionally now (it used to skip stubbing if norfair was *already*
  imported by something upstream, which meant the test's own isolation
  silently depended on import order and which norfair version happened to be
  installed).
- **`playwright` is a required dependency despite no kawkab code importing
  it.** `EasySoccerData` (import name `esd`)'s Sofascore client does `import
  playwright` internally without declaring it as *its own* dependency. A
  bare `grep -r playwright` across `src/` finds nothing and looks safe to
  remove — it isn't. Confirmed by installing into a clean venv and running
  `test_easy_soccer_service.py`.
- **CSS custom properties: map new names onto existing tokens, don't invent
  literals.** `--accent`, `--accent-color`, and `--primary-color` were three
  independently-invented names (in three different features, at different
  times) for the same "this is the active/selected one" semantic, each with
  a different undefined-elsewhere fallback color (teal, dark green, medium
  green) that didn't match the app's real primary blue. All three now alias
  `var(--primary)`. See `:root` in `main.css` for the full list and why each
  exists.
- **`KAWKAB_JWT_SECRET` must be ≥32 characters.** `cloud/auth.py` enforces
  this now (`MIN_JWT_SECRET_LENGTH`). HS256 with a short key is a real
  forgery risk, not just a lint warning — PyJWT already warns about it
  (`InsecureKeyLengthWarning`), this makes it a hard failure instead.
- **`tool.hatch.metadata.allow-direct-references = true` is required and
  load-bearing.** The `sports` extra pins `sports @ git+https://...`
  (a VCS dependency). Hatchling validates *every* `optional-dependencies`
  group at metadata-generation time regardless of which extra you're
  actually installing — without this flag, `pip install -e ".[anything]"`
  fails immediately, before pytest ever runs a single test. This is not
  about the `sports` extra specifically; removing this flag breaks
  installing the project at all.
- **`core/security.py`'s `SecurityValidator` is the one, real, actually-used
  validator. If a `services/storage/*.py` file's `try: from
  kawkab.core.security import SecurityValidator / except ImportError: class
  _SecurityValidator: ...` fallback defines a method the real class
  doesn't have, that is not a harmless backup — it is proof the real class
  is missing something callers depend on.** The `except ImportError` branch
  never runs (the import always succeeds), so whatever the fallback defines
  and the real class lacks was *always* calling a nonexistent method,
  caught by the caller's own broad `except Exception`, silently returning a
  failure value forever. Found via mypy (`attr-defined` on
  `"type[SecurityValidator]"`), confirmed via `test_storage_submodules.py`,
  which had monkey-patched 5 of these methods onto the real class at
  *module import time* to make its own tests pass — meaning the test
  suite's green status was actively hiding this, not catching it. All 6
  missing methods (`validate_track_id`, `validate_positive_float`,
  `validate_float_range`, `validate_event_type`, `validate_event_dict`,
  `validate_int`) are now on the real class; the monkey-patch is deleted.
  See "What was fixed this session" for the full blast radius. If you add a
  new fallback stub method to any `services/storage/*.py` file, add it to
  the real `SecurityValidator` in the same change, or don't add the
  fallback at all — an unreachable branch that *looks* like a safety net is
  worse than no safety net.
- **mypy `strict = true` was configured in `pyproject.toml` months before
  anyone actually ran `mypy` against it.** It produces 2,885 errors across
  203 of 299 files — 82% of them pure annotation-completeness noise
  (`type-arg`, `no-untyped-def`, `no-untyped-call`, `no-any-return`) on a
  125k-LOC codebase that was never written with complete type coverage.
  Config alone proves nothing; a gate has to actually run before you know
  if it's honest or aspirational. Dialed back to non-strict (820 errors,
  mostly the same annotation-completeness category) — the real bugs mypy
  is good at (`name-defined`, `attr-defined` on nonexistent methods) surface
  either way. See Known Gaps for the current count and how to use it.

## What was fixed this session (2026-07-30 audit)

Verified against a **clean `pip install -e ".[test,cloud]"` into an isolated
venv**, not just the ambient dev environment — the dev environment had extra
packages already installed (real `norfair`, `email_validator`, `playwright`)
that masked several of these until tested in isolation.

**P0 — the product was unreachable:**
- `python -m kawkab` (and the packaged `.exe`, and the `kawkab` console
  script) launched nothing — no subcommand fell through to `print_help()` +
  `sys.exit(1)` instead of the desktop app. Fixed in `__main__.py`; added
  `tests/unit/test_entrypoints.py`.
- `kawkab/app.py` itself failed to import — `from kawkab.core.config import
  get_settings`, but `core/config.py` had been fully repurposed for the CV
  tracking-pipeline's `TrackingConfig` dataclasses (Sprint F work) and no
  longer had an app-level `Settings`/`get_settings` at all. Reconstructed as
  a `pydantic-settings`-based `Settings` class matching every field
  `app.py`/`.env.example` need, backed by env vars.
- Verified past both fixes: constructed the full `MainWindow()` under
  `QT_QPA_PLATFORM=offscreen` — all ~45 services initialize, the bridge
  initializes, the UI loads. **I could not click through the actual native
  Qt window from this environment (no tool drives a real desktop GUI here,
  only the embedded web browser pane) — do one manual launch-and-click-
  through yourself before calling this fully proven.**
- 6 frontend↔bridge calls were broken (`get_dashboard_stats`,
  `compare_players`/`comparePlayers`, `get_player_stats`, `get_match_players`,
  plus 2 typo'd provider-search calls). Fixed; all now have dedicated tests
  in `tests/unit/test_new_analysis_handlers.py`.
- `scripts/bundle-js.mjs` was destructive (see Invariants above). Rewritten
  around `scripts/frontend-manifest.json`; verified idempotent (byte-identical
  output across repeated runs).
- `pip install -e ".[test,cloud]"` — what every CI job runs — failed before
  pytest ever started (hatchling metadata validation, see Invariants). This
  likely means CI has been red at the install step for a while independent
  of anything test-related.
- `email-validator` was missing from the `cloud` extra (pydantic `EmailStr`
  in `cloud/models.py` needs it); added.

**Quality gates were hollow, now honest:**
- `pytest tests/` (root, not just `tests/unit/`) failed collection outright —
  `tests/test_load.py` used unregistered `load`/`benchmark` markers under
  `--strict-markers`. Registered.
- `[tool.coverage.report] exclude_lines` excluded any line matching
  `logger\.(debug|info|warning|error)` or bare `return` — i.e. most
  executable lines in the codebase. Removed. Real measured coverage:
  **69.53%** (2026-07-30, full `tests/unit/` run, branch coverage,
  re-measured after this session's bug fixes). Set `fail_under = 65`.
- `ci.yml`'s `unit` job `--ignore`d 20 files. Investigated each against the
  clean-venv environment rather than trusting local pass/fail: `
  test_audio_service.py` was genuinely failing (stale test file — source had
  moved from module-level `faster_whisper`/`librosa` imports + a dict-shaped
  `transcribe()` to lazy imports + a list-shaped `transcribe_video()`, and
  `analyze_crowd_noise()` didn't exist despite the constructor's
  `enable_crowd_analysis` flag; both fixed — see git history for the
  full before/after). `test_easy_soccer_service.py` and
  `test_norfair_tracker.py` needed the playwright/norfair fixes above. The
  other 16 had no discernible reason for the ignore. Down to 1 legitimate
  exclusion (`test_health_endpoints.py`, already covered by the `server` job
  with real Postgres+JWT env configured — ignored in `unit` purely to avoid
  running it twice, not because it fails).
- `test.yml` (a second, separate CI workflow) used `uv sync --only-dev`,
  which refers to `[tool.uv.dev-dependencies]`/`[dependency-groups]` — this
  project uses PEP 621 `[project.optional-dependencies]` instead, so that
  command installed nothing and every job in the workflow failed at its
  first tool invocation. Fixed to `uv sync --extra dev` (lint/typecheck
  jobs) or `--extra test --extra cloud` (jobs that run pytest).
- `.pre-commit-config.yaml` ran both `ruff-format` and `black` — both
  reformat code, in different ways, so every commit got reformatted twice
  and the hook loop never settled. Dropped `black`; `[tool.ruff.format]`
  matches its defaults to keep the diff small.
- Two flaky, pre-existing tests found and fixed while chasing full-suite
  reliability: `test_match_scripting.py`'s `home_dominant` test used
  unseeded `random`, so a 5:1-weighted statistical assertion failed by
  chance on an unlucky draw — now seeded (autouse fixture). `norfair`/`cv2`
  stub installers in `test_norfair_tracker.py` only applied if the real
  package wasn't *already* imported — see Invariants.
- README's Tests badge pointed at a random pasted image attachment, not a
  real CI badge; fixed to a real GitHub Actions status badge. Coverage badge
  was a hardcoded, never-updated "50%"; removed rather than leave another
  fake number (see the real, measured number above instead).
- The repo's actual GitHub remote is `wizard404error/shoot-ai` — README's
  clone instructions, `pyproject.toml`'s `[project.urls]`, `mkdocs.yml`,
  `installer.iss`, and two doc files all said
  `github.com/{yourusername,jraya106}/kawkab-ai` (a placeholder that was
  never filled in, and a stale username). Fixed everywhere.

**Data layer:**
- Added a fresh-DB migration test (`test_migration_manager.py`): applies the
  *real* `001` → `027` chain from `src/kawkab/migrations/` to a genuinely
  empty database (every existing migration test used a synthetic, hand-
  written migrations dir — none of them ever ran the real chain end to end).
  It currently passes cleanly; this is the regression test that would have
  caught it if it hadn't.
- `shortlist_service.py`, `injury_tracker.py`, `contract_tracker.py`:
  `SELECT *` → explicit columns (11 sites). `postgres_storage.py` still has
  `SELECT *` in ~8 places — not fixed this session (see Known gaps).
- `.env.example` documented `FLUIDX3D_PATH`; the code reads
  `KAWKAB_FLUIDX3D_PATH`. Following the example file literally meant your
  physics-engine path was silently never picked up. Fixed, and the whole
  undocumented `cloud/` env var surface
  (`KAWKAB_DB_URL`, `KAWKAB_CLOUD_DB`, `KAWKAB_CLOUD_URL`,
  `KAWKAB_CORS_ORIGINS`, `KAWKAB_RATE_LIMIT_DISABLE`, the 3 OAuth provider
  pairs, `KAWKAB_CKPT_SECRET`) is now documented too.
- **Storage backend divergence (audited, not reconciled — see Known gaps).**

**Bugs found by actually running the quality gates this session added (ruff/mypy were configured but never executed until the final verification pass — see the two new Invariants above):**
- **The entire `services/storage/` save path was silently broken**:
  `PlayerStorage.save_player`/`save_players_bulk`, `ProfileStorage
  .save_player_profile`, `EventStorage.save_event`/`save_events_bulk`,
  `ClipStorage.save_clip`, `FeedbackStorage.save_feedback` all called
  `SecurityValidator` methods that didn't exist
  (`validate_track_id`/`validate_positive_float`/`validate_float_range`/
  `validate_event_type`/`validate_event_dict`), raising `AttributeError`
  on every call, caught by each method's own broad `except Exception` and
  turned into a quiet `return 0`/`return False`. Fixed by adding all 6
  methods (plus a 7th, `validate_int`, found the same way — see next item)
  to the real `SecurityValidator`. `tests/unit/test_storage_submodules.py`
  no longer needs (or has) its own copy of these methods monkey-patched
  onto the class.
- **The entire GPS/ACWR bridge feature was silently broken** the same way:
  `AnalysisHandler.import_gps_file`/`get_gps_sessions`/`get_gps_samples`/
  `get_player_gps_summary`/`get_player_acwr` (`bridge_handlers/
  bridge_analysis.py`) all called `SecurityValidator.validate_int`, which
  didn't exist anywhere, unconditionally, on every call — no fallback stub
  this time, so nothing was hiding it, it just had zero test coverage.
  New tests in `test_new_analysis_handlers.py::TestGpsAcwrHandlers`.
- **`ai_v2_list_convs` (AI chat conversation history, called from
  `app-ai.js:44` on every match load) had no backing method at all** —
  its body had been orphaned onto the tail of the unrelated
  `transfermarkt_squad` method at some point in history (git blame shows
  the method's own `async def` line was deleted in the same change that
  added the "Phase 13" section after it), referencing an undefined
  `match_id`. `bridge.py`'s `@Slot` called `self._analysis
  .ai_v2_list_convs(...)`, which didn't exist as a method →
  `AttributeError` on every call. `test_bridge_contract.py` didn't catch
  this because it only checks that a `@Slot` exists in `bridge.py`, not
  that the handler method it delegates to actually exists one layer down
  — a real gap in that guard, noted but not yet closed (would need
  parsing `self._analysis.X`/`self._X.Y` call sites the same way). Fixed;
  regression tests in `test_new_analysis_handlers.py::TestAiV2Conversations`.
- **`quality_scoring_service.py`'s `save_scores` used `json.dumps` without
  importing `json`.** Only reachable when `issues`/`warnings` is non-empty
  (falsy short-circuits to `None` first) — the existing test only ever
  called it with no issues, so this shipped unnoticed. Fixed; regression
  test passes a non-empty issue list.
- **`card_detection_service.py`'s whistle detector indexed
  `Sxx[whistle_mask_mask]`** (an always-undefined typo of `whistle_mask`,
  defined one line above) — `NameError` whenever the audio actually has
  energy in the 1–3.5kHz whistle band, i.e. whenever there's a whistle.
  Zero test coverage on `detect_cards_audio` before this session. Fixed;
  new `TestDetectCardsAudio` tests with a real synthetic 2kHz tone.
- **`arabic_glossary.py`'s `get_glossary()` singleton relied on catching
  `NameError` on an undeclared global** — works, but is exactly the kind
  of pattern that looks like a bug (and is flagged as one by every static
  checker) even though it isn't. Rewritten to the conventional
  `_singleton: T | None = None` + `if _singleton is None` form. No
  behavior change, just no longer indistinguishable from the real bugs
  above at a glance.
- `storage_service.py`'s `save_benchmark`/`save_validation_result` type
  hints referenced `BenchmarkResult`/`ValidationReport` without importing
  them — harmless at runtime (`from __future__ import annotations` defers
  evaluation) but wrong for any type-checker or IDE. Fixed via a
  `TYPE_CHECKING`-guarded import (avoids a real circular-import risk with
  `benchmark_service.py`/`validation_service.py`).
- **`pytest tests/ -n auto` (root, full execution — one level past what the
  original verification plan committed to, which was collection-only for
  the root tree) surfaced 3 more real, fixable bugs**, found via the same
  root-cause-first process (confirmed each in isolation before touching
  anything, per `superpowers:systematic-debugging`):
  - `Bridge.__init__` accepted `frame_skip` and threaded it into the
    handler services dict, but never did `self.frame_skip = frame_skip` —
    so `bridge.frame_skip` (read directly by `get_gpu_info()`'s test and
    by any other future caller expecting it as a plain attribute) raised
    `AttributeError`. One-line fix.
  - `tests/conftest.py`'s `_ServiceLogger` test stub (stands in for the
    real loguru-backed logger under `install_kawkab_stubs()`) was missing
    `.exception()` — present on every real logger (stdlib `logging` and
    loguru both have it), so any code path that hits an exception handler
    calling `logger.exception(...)` under stubbed tests raised
    `AttributeError` on top of whatever it was actually handling, masking
    the real error. Added the missing no-op method to the stub.
  - `tests/test_load.py` defined its own `pytest_addoption(parser)` to
    register `--run-load` — but pytest only discovers that hook in
    `conftest.py` (or a plugin), never in a regular test module, so
    `--run-load` was never actually registered and
    `config.getoption('--run-load')` raised `ValueError: no option named
    '--run-load'` on every load test's `skipif` check, erroring instead of
    skipping. Moved the hook to `tests/conftest.py`; load tests now skip
    cleanly by default and would run under `--run-load` (untested end to
    end — `pyproject.toml`'s `test` extra doesn't include whatever these
    benchmarks need to actually execute meaningfully; that's a separate,
    unopened question).

**Frontend:**
- 8 CSS custom properties were referenced but never defined anywhere
  (`--accent`, `--accent-color`, `--bg-primary`, `--border-color`,
  `--primary-color`, `--radius-sm`, `--radius-md`, `--surface`) — every
  declaration using them without an explicit fallback was silently
  discarded by the browser. Auditing them turned up 2 more with a
  different, worse problem: `--bg-hover` and `--bg-secondary` *were*
  defined, but only inside the `[data-theme="light"]` block — meaning
  button hover states and several component backgrounds (telestrate
  toolbar, highlight reel, training drills, scout icons, collab badges,
  live tagging, physio metrics) rendered with an unset/transparent
  background in the default **dark** theme specifically. All 10 now alias
  real tokens in `:root` (see `main.css` top of file).
- **A calibration-state trust banner** (Task 9): without homography
  calibration, xG/xT/distance/formation numbers are computed from raw pixel
  positions and presented as if they were real meters — README already
  admits this ("all spatial stats are in pixel space... coach must
  calibrate first") but the UI gave no indication either way. The Results
  page now calls the already-existing (but previously never-called from
  JS) `get_homography(match_id)` slot and shows a clear ✅ Calibrated /
  ⚠️ Not Calibrated banner with a one-click "Calibrate Now" action.
- **Season Form** (Task 8): wired `core/form_analysis.py`'s `FormAnalyzer`
  into the Dashboard — a "Recent Form" card showing streak, last-5 W/D/L,
  and points-per-game. `FormAnalyzer.compute_form_streak()` matches teams by
  the match's free-text `home_team`/`away_team` name, which isn't reliable
  for identifying "our team" across a season (a coach might enter their own
  team's actual name inconsistently); the handler instead builds synthetic
  matches using the event-level `team == "home"` convention (the same
  reliable convention `get_dashboard_stats`'s win/loss counting already
  uses), reusing FormAnalyzer's calculation without inheriting its
  name-matching fragility. `get_all_matches()` returns newest-first; the
  handler reverses it before computing streaks (FormAnalyzer reads
  oldest-first) — this exact ordering bug is what
  `test_win_streak_uses_chronological_order` guards.
- **xA (expected assists)** (2026-07-30, follow-up pass): wired
  `core/xa_model.py`'s `ExpectedAssistModel` into the match Results view —
  a new `get_xa_report(match_id)` handler/slot, an xA line appended to the
  existing home/away team-stats panels (`#home-stats`/`#away-stats`).
  Deliberately placed there rather than under the dead `#xg-section` nav
  link (one of the 22 dead-nav-link items — being fixed in a separate,
  concurrently-running session; avoided touching `app-router.js`/nav
  markup to not collide with it). `xa_split` (per-player, per-event-type
  breakdown) is not wired yet — this pass only did the match-level
  home/away total.
  - **Found and fixed a real, separate bug while wiring this**:
    `get_match_quality_score` (the data-quality shield/badge shown on the
    Results page) was declared as a plain `def`, not `async def`, but
    called `self.storage_service.get_match_events(mid)` — which *is*
    async — without `await`. That returned an un-awaited coroutine object
    instead of the events list, which the anomaly-detection functions
    couldn't process; the handler's own broad `except Exception` caught
    the resulting failure and silently returned `{"level": "error"}`
    forever. The feature has been silently broken on every single call.
    Caught by a `RuntimeWarning: coroutine ... was never awaited` that
    had been appearing in this session's own test output from the start
    (visible in every `tests/unit/` run's warnings summary) but was only
    traced back to its source now. Fixed by making the handler
    `async def` + `await`ing the call; `bridge.py`'s slot was already
    correctly `async`. The 4 tests in `TestBridgeQualitySlot`
    (`tests/unit/test_phase5_quality.py`) previously called the handler
    without `await` (matching its old sync signature) and — worse —
    explicitly accepted `"error"` as a valid outcome alongside
    `"good"`/`"fair"`/`"poor"` in their assertions, which is exactly how a
    permanently-broken feature kept passing its own tests. Fixed to
    `async def` + `await` and tightened the assertions to reject the
    error state for scenarios that should succeed.
- **Pressing efficiency** (2026-07-30, follow-up pass): wired
  `core/pressing_efficiency.py`'s `PressingEfficiencyAnalyzer` — a
  `get_pressing_report(match_id)` handler/slot exposing trap-to-shot
  conversion rate, appended to the same home/away stats panels as xA
  above. Only `compute_trap_to_shot_rate` (conversion %) is rendered in
  the UI; `high_press_index` is included in the JSON response but not
  displayed yet (kept the card simple); `compute_trap_to_goal_rate` and
  `compute_press_recovery_attack` from the same analyzer class aren't
  wired at all. `core/pressing_clusters.py` (spatial zone clustering) was
  deliberately left alone this pass — its output is a list of pitch zones
  meant for a heatmap/pitch-map overlay, not a stat card, which is a
  bigger, separate UI task.
- audio_service.py's `analyze_crowd_noise()` was declared via a constructor
  flag (`enable_crowd_analysis`) that did nothing — no method used it.
  Implemented (librosa RMS-intensity over time), matching the pattern
  `detect_whistles()` already uses (lazy import, safe-shape return on
  failure).
- Mojibake sweep: repo-wide scan (not just the ~8 sequences originally
  estimated) found double-encoded UTF-8 (saved-as-cp1252-then-reencoded)
  across `app-ai.js`, `app-marketplace.js`, `app-opponent.js`, `main.css`,
  `core/physical_metrics.py` — decorative box-drawing banners, emoji,
  em-dashes, €, ². All repaired via a byte-level round-trip script (WHATWG
  windows-1252 table, since Python's own `cp1252` codec leaves 5 byte slots
  undefined that browsers/Node don't). Also stripped a stray UTF-8 BOM from
  `__main__.py` and 3 JS files.
- **CSS design tokens: white/black primitives + two real light-theme bugs**
  (2026-08-07, follow-up pass): added `--color-white`/`--color-black`
  theme-invariant primitives to `main.css` and migrated the ~99
  component-level literal `#fff`/`#ffffff`/`#000` usages onto them (zero
  visual change, same values — one place to retune from for the
  accessibility pass next). Found and fixed a real bug in the same pass:
  `.nav-item.active` set `color: #000` against a background that resolves
  to `var(--accent-color)` → `var(--primary)` (`#2563eb` blue) —
  black-on-blue is ~4.06:1 contrast, below WCAG AA's 4.5:1 for normal text
  and worse than white's ~5.17:1; also dropped the rule's fallback
  `#4ecdc4`, a stale teal that predates this session's earlier
  --accent-color → --primary aliasing fix and could never trigger anyway
  (--accent-color is unconditionally defined).
  **Two much bigger real bugs turned up while auditing which of the
  remaining hex values were safe to fold into existing tokens** (not part
  of the white/black migration itself): `--text` (the primary body-text
  token, set directly via `color: var(--text)` at 40+ sites across nearly
  every section — headers, tabs, tables, cards, chat, tooltips, timeline,
  benchmark, comparison, collaboration) and `--bg-elevated` (background
  for ~48 button/input/list-row/chat-bubble sites, several pairing
  directly with `color: var(--text)`) were each defined **only** in the
  base dark `:root`, with no `[data-theme="light"]` override — the mirror
  image of the already-documented `--bg-hover`/`--bg-secondary` bug
  (defined only in light, broken in dark). Before this fix the two
  tokens' unfixed dark values happened to drift together (light text on a
  dark "elevated" surface — still readable, just visually stuck in dark
  mode even when light theme was active); fixing `--text` alone first
  would have made it *worse* for every `--bg-elevated` pairing
  (dark-on-dark). Fixed both together: added `--text-primary:
  var(--text)` to the dark base (the handful of call sites already
  defensively falling back to a hardcoded `#e0e0e0` now get a real
  definition instead — those fallbacks were dead code and removed), and
  `--text: var(--text-primary)` / `--bg-elevated: var(--bg-hover)` to
  both light-theme-activation blocks (`[data-theme="light"]` and the
  `prefers-color-scheme` media query). Verified with a fresh
  `fetch()`-injected copy of the stylesheet against `getComputedStyle` in
  the browser preview, both themes — the page's own `<link>` tag kept
  serving a stale cached copy across edits in this preview environment
  (not a real bug, just meant live-page verification needed the
  cache-bypassing fetch instead of trusting the rendered page directly).
  Net effect: any plain-text-colored element that doesn't rely on
  inheriting `body`'s color should now actually be readable under light
  theme, not just the ones that already had their own dedicated
  `[data-theme="light"]` override. The remaining ~195 hardcoded hex values
  and 204 inline `style=` attributes are still open — see Known Gaps.
- **Accessibility audit** (2026-08-07): first real pass beyond what
  `accessibility.css` (168 lines) already had. Found a stale, actively
  misleading `src/kawkab/web/a11y-report.md` first — dated June 2026,
  it claimed `@media (prefers-reduced-motion: reduce)` and the skip link
  were both *missing* (both are present, and predate this session), cited
  `--text-muted: #7e8ea8`/`--danger: #ef4444`/`--success: #22c55e` as
  current values (none match `main.css` — current are `#94a3b8`/
  `#dc2626`/`#16a34a`), and claimed "13+ canvases have `aria-label`"
  against a codebase with 14 `<canvas>` elements and only 5
  `setAttribute('aria-label', ...)` calls total, none confirmed to target
  a canvas. Likely describes a divergent or reverted branch, not this
  codebase at any real point in time. Archived to
  `docs/archive/a11y-report-stale-2026-06.md` rather than trusted or
  updated in place — every claim below was independently re-verified
  against current source, not against that report.
  - **Coding-matrix event buttons are real `<button>` elements** with
    visible text labels (`btn.label`) and a visible shortcut hint —
    already keyboard-focusable and screen-reader-nameable for free, no
    fix needed there. But `renderCodingMatrix()` in `app-coding.js` set
    each button's background to an arbitrary per-event hex from the
    backend's template JSON (`bridge_coding.py`) while `.coding-matrix-btn`
    CSS hardcoded `color: var(--color-white)` regardless — computed
    against the actual shipped default palette, several are severe WCAG
    failures, not edge cases: white-on-`#a5f3fc` (goal_kick) is **1.25:1**,
    white-on-`#fca5a5` (bad_pass) **1.90:1**, white-on-`#a3e635` (key_pass)
    **1.51:1** — all far under even the 3:1 floor for bold UI text. Fixed
    with a WCAG-relative-luminance `contrastTextColor()` helper that picks
    black or white per-button at render time instead of assuming white
    always works; safe for coach-customized palettes too, not just the
    shipped defaults.
  - **`--text-muted` in light theme was flatly wrong, not just
    suboptimal**: it reused the dark theme's `#94a3b8` verbatim (tuned for
    dark surfaces, 5.7-7.0:1 there) instead of getting its own light-theme
    value — on light theme's actual backgrounds that same literal measures
    **2.34-2.56:1**, nowhere near WCAG AA's 4.5:1 floor. Since this token
    is the muted/secondary-label color used across nearly every section
    (KPI labels, timestamps, hints), this made a large fraction of
    secondary text hard to read under light theme specifically. Fixed with
    a light-theme-specific `#5b6b82` (same blue-gray family, darkened for
    a light background — 4.95-5.43:1 across `--bg`/`--bg-card`/
    `--bg-elevated`). Dark theme's own `#94a3b8` vs `--bg-elevated`
    specifically measures 4.04:1, a smaller shortfall against a less-common
    pairing — understood, not changed this pass (would mean re-tuning the
    color used everywhere in dark theme for one marginal surface
    combination); see Known Gaps.
  - **The keyboard focus ring was invisible in light theme**:
    `accessibility.css`'s `:focus-visible`/`.skip-link:focus` outlines were
    a hardcoded `#ffd700` gold — excellent against dark surfaces
    (10.4-12.7:1) but **1.34-1.40:1** against light theme's white/
    near-white ones, i.e. keyboard users tabbing through the app in light
    mode couldn't see what was focused at all. The exact
    one-color-for-one-theme-only bug class as `--bg-hover`/`--text`/
    `--bg-elevated` above, just discovered in a different file. Tokenized
    as `--focus-ring` in `main.css` (dark: `#ffd700`; light:
    `var(--primary-dark)`, `#1d4ed8`, 6.41-6.70:1) and pointed
    `accessibility.css`'s 4 outline-color declarations at it instead of
    the literal.
  - **Dashboard KPIs, recent-matches list, and recent-form card had no
    `aria-live`** despite populating asynchronously after the initial
    page load (`get_dashboard_stats` et al.) — a screen reader user would
    never be told the numbers changed from the static "0" placeholders.
    Added `aria-live="polite"` to `#dashboard-kpis`, `#dashboard-recent-list`,
    and `#dashboard-form-content`. Did not add it to the whole
    `#dashboard-section` (would announce every minor chart/canvas mutation
    inside it too, likely noisy) — `#results-section` already had a
    section-level `aria-live="polite"` from earlier work, which is why the
    xA/pressing-efficiency stats appended to `#home-stats`/`#away-stats`
    this session didn't need their own.
  - **Verified present already, contrary to what the stale report
    claimed**: skip-to-content link (`index.html:27`,
    `<a class="skip-link" href="#main-content">`), `role="banner"` /
    `role="main"` / `role="navigation"` landmarks, `@media
    (prefers-reduced-motion: reduce)`, and a toast system with
    `aria-live="polite"` + `textContent` (not `innerHTML`) for the message.
  - **Not fixed, judgment call flagged rather than silently changed**:
    white text on `--success`/`--warning` badges (risk levels, confidence
    badges, ratings) measures 3.30:1 / 3.19:1 — passes the 3:1 floor for
    large/bold UI text but fails the 4.5:1 normal-text floor, and several
    of these badges are small (~0.72rem). Fixing it means darkening two
    recognizable brand/status colors used far beyond just these badges
    (buttons, icons, borders) — `#15803d`/`#b45309` would each clear
    4.5:1 with white text if this gets revisited, but changing "the app's
    green/amber" is a more visible design call than the other fixes in
    this pass and wasn't made unilaterally.
  - **Not audited this pass**: the 22-coding-matrix-button *keyboard
    shortcut* system itself (are the actual keydown handlers correct,
    not just the buttons' native focusability), full-page keyboard
    walkthrough, screen-reader walkthrough with a real AT, target-size
    audit (WCAG 2.2's 24x24px minimum) beyond the existing 44px
    touch-device media query, and the `[data-focus-trap]` CSS marker in
    `accessibility.css` which has zero matching `data-focus-trap`
    attribute or JS behavior anywhere in the codebase — styled but never
    actually applied to a real modal; unclear if any modal has a real
    keyboard focus trap at all.
- **XSS sweep of `innerHTML` sites** (2026-08-09): first full pass, not
  just sampling. Found real bugs, not just missing escaping.
  - **`app-opponent.js`, `app-marketplace.js`, and `app-ai.js` are not
    wrapped in their own IIFE**, unlike every other `web/js/*.js` file —
    they were split out of `app.js` without one (4-space-indented top-level
    code is the tell). `scripts/bundle-js.mjs` does plain string
    concatenation with no per-file wrapper, so correctness depends
    entirely on each file being self-contained. These three call bare
    `escapeHtml(...)` a combined 52 times with no definition in scope, no
    import, and no global exposure anywhere — `window.escapeHtml` doesn't
    exist; the real implementation lives at `window.__kawkab.escapeHtml`
    (set by `utils.js`). `app-data-providers.js` already had the fix
    (`var escapeHtml = window.__kawkab.escapeHtml;` at the top) — these
    three were just missing the same line. Fixed identically. Confirmed
    with a new regression test
    (`tests/split-files-global-scope.test.js`) using `eval` to replicate
    the bundler's actual concatenation behavior — `require()` alone
    would NOT have caught this, since Node's CommonJS wrapper
    accidentally gives each required file its own scope, masking exactly
    the isolation these files lack in the real bundle.
  - **`app.js` defined `escapeHtml` twice** (a DOM-based version using
    `textContent`/`innerHTML` round-trip, and a manual regex-replace
    version added later) — both plain `function` declarations in the same
    IIFE, so the second silently won for every caller in the file
    regardless of which one a reader would assume from context. The
    losing (correct) one escaped `&<>"`; the winning one additionally
    missed `'` (single quote) — a real gap for any call site whose output
    lands inside a single-quoted attribute. Deleted the weaker duplicate;
    every caller in `app.js` now gets the safer DOM-based version, a
    strict superset of protection (no behavior change for existing
    correct usages).
  - **`app-ai.js`'s cloud-team-list renderer interpolated `t.name`/`t.role`
    into `innerHTML` unescaped** (`bridge.cloud_list_teams()` — the
    multi-user collaboration feature). Team names are coach-entered and
    this list renders for every teammate on that cloud team, not just the
    creator — the one genuinely cross-user-reachable finding in this
    sweep, not just self-XSS. Also unescaped in the same file: live-tag
    `notes` (coach free-text typed during live tagging) and `type`/`team`
    on the same tag object, plus an SVG marker's `ev.type`. All fixed.
  - **`calibration.js` had zero `escapeHtml` usage at all** despite
    rendering `seg.label` (camera-segment label) directly into
    `innerHTML` at two sites. Can't import the shared
    `window.__kawkab.escapeHtml` here — `calibration.js` loads at
    manifest position 4, before `utils.js` at position 6 — so it got its
    own small local copy instead, matching the pattern already used by
    `app-highlight.js`/`app-coding.js`/etc.
  - **`app-ai.js` line ~1055 called
    `document.getElementById('match-video').addEventListener(...)` at
    the file's top level with no null-check** — not an XSS bug, but
    found while tracing why the regression test above failed for this
    file specifically. Currently harmless only because `index.html` has
    a static `<video id="match-video">` and the bundle loads via
    `<script defer>` (guaranteeing full DOM parse first) — but an
    uncaught error here would abort the rest of that single concatenated
    bundle, silently preventing `app.js` and everything after it in load
    order from ever initializing. Added a null-guard; trivial fix for a
    disproportionately large blast radius.
  - **Smaller inconsistencies fixed for defense-in-depth**, not because a
    live exploit path was confirmed: `app-data-providers.js`'s
    `image_b64` (base64 can't structurally contain HTML-special chars,
    but costs nothing to escape anyway), `app.js`'s external-provider
    match-badge tooltips (`api_match_id`/`bzzoiro_event_id`/
    `apifb_fixture_id`) and one `stats.error` site that was inconsistent
    with two identical, already-escaped sibling sites in the same file,
    and `app-coding.js`'s category-label `cat.color` (interpolated into
    a `style="color:...">` attribute string, not a `.style.background =`
    assignment — the latter is a DOM property set and can't be broken out
    of regardless of content, the former is string concatenation and can).
  - **Spot-checked and confirmed safe, not fixed**: `app-hud.js`'s
    keyboard-shortcut list (author-written string literals only),
    `app-tooltips.js`'s `data-tooltip` reader (confirmed the only dynamic
    setter anywhere is in its own test fixture — real usage is always
    static HTML markup), `app-sparklines.js`'s SVG builder (numeric
    chart data and CSS color options only), `app-charts.js` and most of
    `calibration.js`/`app-coding.js`/`app.js` (i18n keys, `.toFixed()`
    output, and other numeric/fixed-vocabulary values). `showEmptyState`
    (`app-ux.js`) and `KawkabErrorBoundary.wrap` (`app-error-boundary.js`)
    both have unescaped-parameter risk in their signatures but are never
    actually called anywhere in the codebase — dead code, not a live gap.
  - **Not swept**: the remaining ~280 of ~334 total `innerHTML`/
    `insertAdjacentHTML` sites, concentrated in `app-tactics.js`,
    `app-scout.js`, `app-squad.js`, `app-highlight.js`, `app-briefing.js`,
    and `events.js` — all confirmed to already define and use their own
    local `escapeHtml`, and every site checked via the same heuristic
    search in this pass came back correctly escaped, but not every
    individual site in these files was read by hand.
- **6 broken API v1 endpoints + `compute_goals_added` fixed** (2026-08-19):
  the mypy `attr-defined` sweep (see "820 mypy errors remain" below) had
  already found these calling nonexistent classes/methods — an instant
  500/`AttributeError` on every call, never caught by
  `test_bridge_contract.py` (JS-call-vs-slot-name only, doesn't check the
  handler method one layer down actually exists — see that gap below) or
  `test_api_v1.py` (14 of 39 routes covered, none of these six). Fixed
  each by tracing the real API instead of guessing a rename:
  - `get_tactical_shapes`: `TacticalShapeAnalyzer.analyze` doesn't exist;
    real method is `analyze_shapes(events, team=...)`, called once per side.
  - `get_pressing`: `PressingClassifier` class doesn't exist; real API is
    the module-level `classify_pressing_system(events, team=...)`.
  - `get_match_report`: `TacticalReportGenerator` class doesn't exist;
    real API is `generate_tactical_report(events, match_id, home_team,
    away_team)`, which already populates `key_tactical_observations`
    internally.
  - `get_player_fitness`/`get_player_injury_risk`: `PhysicalLoadService
    .compute_load`/`WorkloadService.compute_acwr`/`InjuryRiskPredictor
    .predict_risk` don't exist. The first two classes are real but need
    data these endpoints don't have (raw per-frame tracking, season-long
    day-by-day load history) — neither is derivable from match events.
    Rewired both onto the real, GPS-import-backed `gps_sessions`/
    `acwr_daily` tables (`StorageService.get_gps_sessions`/
    `get_player_acwr`, already fixed earlier this session's GPS/ACWR
    bridge work) instead. A player with no GPS import gets
    `data_available: False` / an honest zero, not a fabricated number —
    same principle as the `possession_service.py` 50/50 fallback this
    tier flags elsewhere.
  - `get_squad/{team_id}/injury-report`: called a `StorageService` method
    that never existed (and constructed a bare, un-singletoned
    `StorageService()`, bypassing the file's own `_get_storage()`). The
    real logic lives on `InjuryTrackerService.get_squad_injury_report
    (team_player_ids)`, keyed by `player_profiles` ids, not a match-local
    `track_id` — and no team_id → player-roster resolution existed
    anywhere. Added `StorageService.get_squad_injury_report(team_id)`,
    resolving via `matches.home_team_id`/`away_team_id` (migration 022) +
    `player_match_links` (migration 002, already joined the same way by
    `player_profile_service.py`) before delegating to
    `InjuryTrackerService`. An empty resolved player list returns an
    honest empty report rather than falling through to
    `InjuryTrackerService.get_active_injuries`'s own
    falsy-list-means-"no filter" branch, which would otherwise leak every
    other team's injuries under a team that has none of its own.
  - `compute_goals_added` (`bridge_analysis.py`): imported a nonexistent
    `core.goals_added.compute_g_plus` (real: `compute_goals_added
    (player_id, match_stats, position)`) and was a plain `def` calling
    `self.storage_service.get_match_events(...)` — an async method —
    without `await`, so fixing only the import would have left it
    aggregating over a coroutine object. Made `async def`; `bridge.py`'s
    slot needed `await` added too (the same sync-calls-async-without-await
    shape as the `get_match_quality_score` bug documented above).
    Computes real per-player xG (`core.xg_model.compute_xg_from_dict` over
    each player's shot events) and a defensive-actions count; `xa`/`xt`/
    `obv` components are left absent from `match_stats` (the function's
    own `.get(key, 0.0)` convention for "not measured") rather than
    fabricated, since none are derivable from raw events without their
    own dedicated pipelines — `obv` specifically needs the same per-frame
    tracking data the OBV/EPV gap below already documents as generally
    unavailable.

  **Found while verifying the above, all fixed in the same pass:**
  - **`StorageService.get_match_players()` has been broken on every real
    SQLite deployment**: its `SELECT` includes a `confidence` column that
    `001_initial.sql`'s `players` table never had, and no later migration
    ever added — `sqlite3.OperationalError: no such column: confidence`
    on every call, for every match with players. Postgres was never
    affected (`pg_schema.sql`'s `players` table already declares it).
    Invisible to every existing test because the 4 test files with their
    own hand-written synthetic `players` schema (see the storage-
    divergence entries above) all happened to already include
    `confidence` in their own copy — the bug only surfaces against the
    real migration chain, which is why `test_game_plan` (the one existing
    test that already runs the real chain) never called
    `get_match_players` and never tripped it. Added migration 029.
    Nothing populates the column yet (`save_player`/`save_players_bulk`
    don't set it) — it stays `NULL` until a real per-player
    detection-confidence source exists; this migration only stops the
    crash, it doesn't fabricate a value.
  - **`core/tactical_shape_analyzer.py`'s `_analyze_window` crashed on any
    event without spatial metadata**: `ev.get("x", 0.5) * PITCH_LENGTH` —
    but `get_match_events()` always includes the `"x"` key (via
    `json_extract` on `metadata`), `None` whenever an event has no
    spatial data, and `dict.get(key, default)` only uses `default` when
    the key is *absent* — the same Pydantic-v2-semantics gap already
    fixed once this session for `MatchOut.fps`. `None * PITCH_LENGTH`
    raised on every event without pixel coordinates, i.e. any event whose
    `metadata` wasn't populated with `x`/`y`. Fixed with an explicit
    `is None` check before multiplying, for both `x` and `y`.
  - **`AnalysisHandler.get_squad_injury_report` was defined twice** in
    `bridge_analysis.py` — Python keeps only the second same-named method
    in a class body, so the first (whose `risk_category`/`key_factors`
    field names `app-squad.js`'s `renderSquadHealthPlayers` actually
    reads) was dead code, and the second — fabricating ACWR from a
    synthetic `100 + (i % 20 - 10)` sawtooth formula, and returning
    differently-named `risk_level`/`factors` fields the frontend doesn't
    read — was the one that actually ran. The squad health view has
    likely shown "low" risk and blank factors for every player since
    whichever commit introduced the second definition. Merged into one
    method using the same real `get_player_acwr` GPS data as the
    `get_player_fitness` fix above, with the frontend's actual field
    names. Ruff (`--select F811`, run for the first time against this
    file as part of verifying this fix) found two more instances of the
    identical duplicate-method pattern in the same class
    (`get_injury_risk`, `generate_training_plan`) — flagged as a
    follow-up task rather than fixed in this pass; see Known Gaps.

## What was fixed this session (2026-09-07 — elite-readiness pass)

**Environment note:** this session ran on a Linux machine (the repo's
history is Windows-first); a `.venv-linux` (Python 3.12, uv-managed) was
created with the analysis-surface deps (numpy/scipy/loguru/pydantic/pytest/
fastapi/opencv-headless/ultralytics/PySide6). The documented Windows
`.venv` remains untouched. Tests that import the full CV stack need those
packages; pure-core tests (validation package, xG/xT/PSxG models) don't.

**P1 — Models trained on real data (the elite-readiness unlock):**
- `src/kawkab/core/validation/` — new package: StatsBomb loader (corpus →
  Kawkab schema, freeze-frame GK distance, 120×80→105×68m conversion),
  Metrica tracking loader (→ OBV/EPV frame schema), strict-validated metric
  suite (Brier, BSS, reliability, tie-aware AUC, log loss, ECE, bootstrap
  CI — NaN/out-of-range inputs raise, never silently propagate into a
  report), and three trainers (`train_xg`, `train_psxg`, `train_xt`).
- **xG trained**: 5,905 shots from 297 StatsBomb matches → fitted logistic
  weights (`trained_xg_coefficients.json`, auto-loaded, heuristic kept as
  fallback). Held-out 1,449 shots: **Brier 0.0707 vs StatsBomb's own
  0.0667**, AUC 0.772 vs 0.780, ECE 0.0143 (heuristic was ECE 0.068 and
  underestimated mean xG 5×). Provenance API:
  `EnhancedXgModel().coeffs_source`, `trained_model_available()`;
  `compute_xg_trained_from_dict()` is the function new call sites must
  use (legacy `compute_xg_from_dict` kept for compat).
- **PSxG trained + 3-implementation unification started**: fitted from
  2,768 on-target shots (Brier 0.167, AUC 0.753). The empirical zone
  table (top corners 0.34, top-center 0.156) caught the first feature
  set conflating lateral/vertical into one center-distance radius —
  redesigned as lateral×height interaction. `psxg_model.py` keeps its
  legacy signature (goalkeeper_analytics depends on it) but loads
  fitted coefficients; `psxg_improved.py`/`psxg_model_trained.py` remain
  as compat heuristics (full deletion still open — see Known Gaps).
- **xT reference grid**: league-wide 20×32 grid from 534,927 actions
  (`trained_xt_grid.json`), monotonic (own-half 0.025 < final-third
  0.897). `ExpectedThreatModel.build_transition_matrix` now falls back
  to a reference-grid blend when a match has <200 actions (cold-start
  matches previously got an all-zero grid).
- `scripts/validate_models.py` — reproducible CLI emitting
  `docs/validation/validation_report.json` + `REPORT.md` covering all
  three models with bootstrap CIs. `MODEL_CARD.md` updated with the
  measured tables and honest caveats (GK-distance features come from
  SB freeze frames — not yet extracted from live video).

**P2 — Trust debt cleared:**
- `test_bridge_contract.py` grew a second contract layer: every
  `self._X.method(...)` delegation in bridge.py must exist in the
  matching `bridge_handlers/*.py` (the `ai_v2_list_convs` bug class).
  Verified by planting a fake broken delegation — the test caught it.
- Shadowed-duplicate methods merged: `get_injury_risk` (both old versions
  were wrong — one read never-populated workload_d1..28 fields, the other
  FABRICATED ACWR from a `100 + (i%20-10)` sawtooth; canonical version
  uses real GPS `get_player_acwr` data with honest `insufficient_data`
  when absent, response carries BOTH field-name conventions) and
  `generate_training_plan` (kept the event-driven version; deleted the
  mock-diagnosis dead copy). `ruff --select F811` on bridge_handlers/ is
  now clean. `tests/unit/test_phase6_sprint1.py`'s unknown-player test
  now pins the honest "Player not found" contract (it previously
  asserted fabricated scores for nonexistent players).
- `tests/integration/test_bridge_advanced_metrics.py`'s FakeCVService
  signature was stale (missing `match_id`/`storage_service` params the
  real `CVService.process_video` takes) — every analyze_match call
  TypeError'd into error-payload asserts. Stub mirrors the real
  signature now; 4/4 pass. (The CLAUDE.md note blaming the tempdir
  path policy for these failures was wrong — the real cause was the
  stale stub, found by actually reading the error.)
- `pg_schema.sql` duplicate `seasons` table: second (silently no-op)
  definition commented out with an explanatory note — canonical is the
  first, narrower one.
- `pressing_efficiency.py::compute_trap_to_shot_rate` had the same
  None-vs-default `dict.get` bug class as tactical_shape_analyzer (fixed
  there 2026-08-19 but not here): storage's json_extract emits `x: None`
  for events without spatial data → `float(None)` TypeError. Fixed with
  the same explicit None-check. Found via the interop tests below
  running real imported data through it.

**P4b — StatsBomb interop (the elite-club wedge):**
- `services/statsbomb_import_service.py`: imports a StatsBomb events
  file into the Kawkab DB (match + events + players + cached headline
  metrics, xG computed by the trained model at import time). Clubs run
  the full 117-model stack on their existing event data with zero video
  capture. Handles the migration-015 dedup index (same-type/same-second
  events by one player = true duplicates, skipped + counted).
- `POST /api/v1/matches/import/statsbomb` — RBAC-gated (analysis:run),
  accepts file_path (SecurityValidator-validated) or inline events_json.
- `tests/unit/test_statsbomb_import_service.py` (7 tests, all against a
  REAL migration-chained SQLite DB + real corpus files) — includes a
  downstream-models smoke test proving pass-network, pressing, and
  tactical-shape analyzers run on imported data unchanged.

**New-test totals this session:** 41 (validation package) + 7 (import
service) + 3 test files repaired (phase6: 18, bridge_advanced_metrics: 4,
phase5 collection now works with cv2 installed). All green.

**P4a — Pro Analytics suite wired (the 57-orphaned-modules gap, first tranche):**
- `ui/bridge_handlers/bridge_pro_analytics.py` (new handler): one
  `get_pro_analytics_report(match_id)` aggregating 12 elite modules —
  OBV, EPV, pass flow, pressing clusters, duels, ball recovery, box
  entries, switches of play, crossing, set pieces, through balls,
  off-ball — each block with an honest `data_available` flag + reason.
  Delegates to core/ exclusively; storage rows normalized ONCE centrally
  (`_normalize_event`: event_type→type, metadata JSON → top-level
  x/y/is_goal) instead of per-module adaptation.
- Bridge slot `get_pro_analytics_report` + API endpoint
  `GET /api/v1/matches/{id}/analysis/pro` (RBAC analysis:read) +
  frontend section (`app-proanalytics.js`, nav "Pro Analytics", route
  `proanalytics`, manifest entry, bundle rebuilt). Frontend cards render
  per-block availability — never fabricated zeros.
- **3 real core-module crashes fixed via real-imported-data testing**
  (all the same None-vs-default bug class): `epv._to_zone` and
  `epv.compute_possession_epv` (None/ZONE_WIDTH TypeError; end_x-start_x
  on None), `ball_recovery._to_zone` + `classify_recovery`
  (`math.isfinite(None)` TypeError). Each guarded with pitch-center
  fallback.
- `statsbomb_import_service._SB_TYPE_MAP` completed with the full
  open-data type census (Ball Recovery→interception so core/ recovery
  modules count it, Pressure, Block, Dribbled Past, Shield, 50/50→duel,
  Error→miscontrol, Bad Behaviour, Player On/Off, Own Goal variants).
- **`analyze_match` now passes `storage_service` to `process_video`** —
  tracking-frame persistence (the documented non-default path that made
  OBV/EPV/off-ball silently empty) is now the default for every video
  analysis. Event-data imports still have no frames; those blocks report
  data_available:False with the reason, per the honest-empty principle.
- **Frontend test gate repaired** (was: jest-circus missing /
  "Module not found" — the CLAUDE.md-documented flaky Node/jest combo
  finally broken by a stale node_modules): `npm install` in
  `src/kawkab/web` restored 118/118 tests passing. The bundler needed
  `esbuild` resolvable from repo root (`npm install --no-save esbuild`
  at root — web/node_modules has it but scripts/bundle-js.mjs resolves
  from its own location).
- `tests/unit/test_pro_analytics_handler.py` (6 tests): report shape,
  event-blocks-compute on a real import, tracking-blocks honest-when-
  absent, OBV/off-ball compute with synthetic frames, empty-store honest
  failure, and the None-coordinate regression tests for EPV/ball_recovery.

**P4a tranche 2 + season analytics (2026-09-07, second build pass):**
- **Trained-model migration complete**: the last two live call sites on
  the legacy heuristic migrated — `api_v1.get_shots_analysis` (the
  `/analysis/shots` endpoint) and `vaep.py`'s frame-based scoring-prob
  term (legacy heuristic underestimated xG ~5x, deflating every VAEP
  value with it). `model_comparison.py`'s heuristic-vs-enhanced calls are
  deliberate (that module's purpose is comparing them) — untouched.
- **Pro Analytics tranche 2 (13 new blocks)**: carry_xt, xg_chain,
  game_state, flank_analysis, defensive_xt, corner_xg, crossing_xg,
  expected_pass, passing_triangles, scoreline + honest-empty velocity /
  influence_map / lineup_optimizer (need calibrated tracking or season
  history — reasons say so). 17 of 25 blocks compute live on a plain
  StatsBomb import. Frontend ORDER/BLOCK_META extended; bundle rebuilt.
- **3 more real core-module crashes fixed** (the None-coordinate bug
  class, found by feeding real imported data through): `defensive_xt`
  (zone math on None — unlocated defensive events are now SKIPPED, not
  center-fallback: an xT-prevented value needs a real location);
  `passing_triangles` (sorted() over a set containing None track_ids);
  `scoreline_distribution` (sum over xg=None feeding Poisson rate).
  Plus handler-side: scoreline's nested return shape was flattened
  wrongly (reads result["scorelines"] now).
- **PSxG trio unified**: `psxg_improved.py` and `psxg_model_trained.py`
  DELETED (hand-tuned zone heuristics, zero product consumers — only
  their own tests imported them). Their behavioral contracts (header <
  foot, distance decay, bounds) were ported to `test_psxg_model.py`'s
  new `TestTrainedModelBehavior`. Canonical: `psxg_model.py` with fitted
  coefficients. The docstring history note in train_psxg.py updated.
- **Season analytics handler** (`bridge_season_analytics.py` +
  `get_season_pro_report` slot + `GET /api/v1/season/pro` + frontend
  "Season Report" button): formation trends across matches (honestly
  labeled approximation from event x-distributions — the true formation
  detector needs tracking data and there is no formation column in the
  schema), discipline/suspension risk from accumulated card events,
  fixture difficulty with opponent strengths inferred from stored
  results. 4 tests; single-match stores get an honest "needs ≥ 2
  matches" response.
- **Known-gaps count**: orphaned core/ modules down to ~30 (25 wired
  across the two Pro Analytics tranches + season handler; the rest need
  tracking-frame team assignment, season history, or are deliberately
  dormant).

## What was fixed this session (2026-09-16 — commit-integrity + xG angle-convention pass)

**P0 — HEAD (907798a) was a broken commit.** The 2026-09-15 commit applied
COMMIT-PLAN.md's "exclude the concurrent xG session's files" rule at
whole-file granularity instead of hunk granularity, so the committed tree
referenced files that were never committed:
- `ui/bridge_handlers/__init__.py` imported `bridge_pro_analytics.py` /
  `bridge_season_analytics.py` → `import kawkab.ui.bridge` crashed on a
  fresh checkout of HEAD.
- `core/xg_model.py` loaded `trained_xg_coefficients.json` (masked at
  runtime by the heuristic fallback) and `__main__.py` wired a `validate`
  CLI whose `scripts/validate_models.py` + `core/validation/train_*.py`
  were also untracked.
Fixed by committing the working tree in thematic groups (analytics
handlers first — that alone repairs the import crash; then models; then
the 2026-09-02 accuracy-audit fixes; then docs), with a scripted
tracked→untracked reference audit run before staging.

**P1 — the trained xG fit was built on the wrong angle convention (real
bug, caught by the committed sanity guard shipping in the same commit):**
- `validation/statsbomb_loader.shot_distance_angle` returns the
  goal-OPENING angle (posts subtended from the shot; central ≈ 36°,
  goal-line-wide ≈ 90°+). `EnhancedXgModel` (and the CV pipeline via
  `atan2(|dy|,|dx|)`) consumes the DEVIATION-from-central convention
  (0° = central; `1 − cos(angle)` with a negative coefficient). Training
  on opening angle taught the model that WIDE shots score MORE —
  `TestTrainedXgCoefficientsSanity` failed with 11m-central = 0.057 and
  11m-wide = 0.49 — and distance decay collapsed onto the angle term
  (fitted `angle_sin` = +5.89 on `1 − cos`). Same disease the 56-shot
  fit had; scripts/train_xg_from_statsbomb.py's `_get_angle` had already
  been fixed for exactly this and its docstring documents the history.
- Fix: added `shot_deviation_angle` to the loader (opening angle KEPT —
  PSxG's serving model is calibrated for it and its tests pin it) +
  `StatsBombShot.angle_deviation_deg` (appended LAST so positional
  constructions keep their meaning). `train_xg.py` feeds the deviation
  on both the fit and predict boundaries; `statsbomb_import_service`
  stores `angle_deviation_deg` alongside `angle_deg` (metadata key
  `angle_deg` stays OPENING — the PSxG serving path reads it with a
  positive-coefficient convention; live-CV events already emit
  deviation-style `angle_to_goal_deg`, so imports are now consistent
  with them).
- Retrained from the committed 297-match corpus (offline, no network):
  Brier 0.0707 / AUC **0.7724** (was 0.7667) / ECE 0.0143 / mean xG
  0.0999 vs true 0.10 — wide < central now holds, distance decays.
  `docs/validation/REPORT.md` + `MODEL_CARD.md` regenerated with the
  corrected numbers.
- Convention table (put this near any angle-eating model): xG →
  deviation (0 = central); PSxG → opening (posts subtended). The
  DB/event metadata `angle_deg` key holds OPENING for imports and the
  CV pipeline stores `angle_to_goal_deg` (deviation) — a known wart,
  documented rather than silently renamed.

**P0.1 — first measured tracking benchmark (mot_metrics finally exercised
in anger).** `mot_metrics` was complete and tested but nothing ever ran the
*production* tracker through it. New
`scripts/benchmark_production_tracking.py`: drives the real
`NorfairTracker` (norfair installed into `.venv-linux` via uv — declared
dependency) over GT player positions from the committed Metrica fixture,
converted to a 20 px/m pixel grid, scored with the project's own
`compute_mot_metrics`. Two rows: *ceiling* (GT as perfect detections —
MOTA 0.9903, IDF1 0.9954: association is near-perfect, the detector is the
ceiling) and *degraded* (3 px jitter σ, 10% drop, 2% FPs — MOTA 0.9155,
IDF1 0.9620, 268 swaps / 43,978 positions ≈ 0.6%). Deterministic (same
seed → byte-identical metrics). Numbers + honest scope caveats published in
MODEL_CARD.md ("Player Tracking — association benchmark"). Regression test
`tests/unit/test_tracking_benchmark.py` (9 tests): pins ceiling > degraded
on MOTA + IDF1, pins degraded against collapse (the first degraded config
used 10 px jitter on ~20 px boxes — consecutive-frame IoU fell below the
tracker's 0.6 match threshold so no track ever initialized: physically
unrealistic, caught by the test, calibrated to 3 px), and pops/restores
norfair stubs around the real-norfair e2e test so it neither depends on
import order nor leaks real norfair into stubbed tests (the leak direction
that bit test_cv_service). E2E window sized at 120 frames deliberately:
the tracker's 3-frame init costs a fixed ~66 FN, which is 3.75% of an
80-frame window (ceiling MOTA 0.899 there) but amortized at 120. Still
open, honestly scoped: end-to-end camera→detection→tracking MOTA on
labeled video, and ball tracking (fixture is players only).

**Environment note:** this session ran in `.venv-linux` (Python 3.12).
5 `test_raindrop_detection_service.py` failures are env-only (this venv's
opencv build lacks `groupRectangles`; Windows CI has it) and 1
`test_easy_soccer_service.py::test_get_event` failure likewise (the
service does `import esd` inside the method; esd isn't installed here —
CLAUDE.md documents playwright as esd's undeclared dependency). Not code
bugs; not chased further.

## Known gaps (found, understood, deliberately not fixed this session — read before assuming any of these "just work")

- **Storage backend divergence.** `StorageService` (SQLite) and
  `PostgresStorageAdapter` (Postgres) are not the same interface with two
  implementations — they've drifted into genuinely different feature
  sets. The rough "20/57/10" counts from the original audit turned out to
  be very close, but were estimates; here's the exact, code-introspected
  breakdown (2026-07-30, via `inspect.signature` over both classes, not
  manual reading — see method for reproducing this if the classes change):
  **88 SQLite public methods, 124 Postgres, 68 shared by name, 20
  SQLite-only, 56 Postgres-only, 10 shared-name-but-different-signature.**
  - **SQLite-only (20)**: `audit_log`, `change_password`, `create_user`,
    `delete_session`, `get_all_users`, `get_audit_log`, `get_gps_samples`,
    `get_gps_sessions`, `get_player_acwr`, `get_player_gps_summary`,
    `get_user_by_id`, `get_user_by_username`, `record_failed_login`,
    `save_acwr`, `save_gps_samples_bulk`, `save_gps_session`,
    `save_session`, `update_gps_session_stats`, `update_user_login`,
    `validate_session` — local user auth/sessions/audit log, plus all
    GPS/ACWR tracking. A Postgres/cloud deployment has no GPS import or
    local-auth-session feature at all.
  - **Postgres-only (56)**, minus 4 that are generic query primitives
    (`execute`, `executemany`, `fetch`, `fetchrow` — a different API
    style, not really "missing SQLite features") = **52 real gaps**.
    **Confirmed NOT safe to delete as "duplicates"**: 10 of them
    (`save_shortlist_entry`/`get_shortlist`/`update_shortlist_entry`/
    `delete_shortlist_entry`, `save_injury`/`get_injuries`/
    `update_injury`, `save_contract`/`get_contracts`/
    `get_contracts_expiring_soon`) look like duplicates of
    `shortlist_service.py`/`injury_tracker.py`/`contract_tracker.py`, but
    those three dedicated services are hardcoded to `sqlite3.Connection`
    (checked directly) — meaning for Postgres deployments, the
    "duplicate" methods on `PostgresStorageAdapter` are the *only*
    implementation of shortlist/injury/contract tracking that exists.
    Deleting them would remove a real feature, not dead code. The
    remaining ~42 Postgres-only methods (seasons, match comparisons,
    analysis quality, batch jobs, cache, card/psychology events, collab
    comments/mentions/users, wearable sessions, medical history, audit
    events, settings, schema version) genuinely have no SQLite
    equivalent, or SQLite gets the same feature through a different,
    dedicated service instead (same shortlist/injury/contract pattern).
  - **10 signature mismatches (exact params)**: `get_coding_tags_by_type`
    (`event_type` vs `tag_type`), `save_advanced_metrics` (Postgres adds
    `metrics`/`category` params SQLite doesn't have),
    `save_advanced_metrics_bulk` (`metrics` vs `metrics_list`),
    `save_correction` (SQLite: `event_id, correction_type,
    original_value, corrected_value`; Postgres: a much wider, looser
    `match_id_or_event_id, correction, correction_type, original_value,
    corrected_value, event_id, match_id, field, old_value, new_value,
    reason` — accepts several overlapping calling conventions at once),
    `save_report` (`report_text_or_language` overload param on Postgres
    only), `update_match_analysis` (`analysis_data` param Postgres-only),
    `update_match_apifootball`/`update_match_bzzoiro`/
    `update_match_football_data` (all three: `data` param Postgres-only),
    `update_player_profile_face` (`face_embedding_json` vs
    `face_embedding_or_path`). Any code path calling one of these 10 by
    positional args instead of keywords would silently call the wrong
    parameter across backends.
  - Fixing this properly still needs either the ~52 real-gap methods
    written and verified against a live Postgres instance, or a real
    architectural unification (e.g. making `shortlist_service.py` etc.
    backend-agnostic so `PostgresStorageAdapter` can delegate to them
    too) — both bigger than what this pass attempted. What changed this
    session is that the exact list now exists, so that work no longer
    has to start with re-deriving it.
  - If you switch a deployment to `KAWKAB_DB_URL` (Postgres), do not
    assume feature parity with SQLite — check the specific methods above.
- ~~**22 dead nav links** in the left sidebar~~ — **fixed 2026-09-16, and
  the original diagnosis understated the severity**: the links did NOT
  "do nothing". Sidebar navigation is handled by an inline
  `syncSidebarClicks` handler in index.html that toggles `hidden` on
  every `.section` whose id doesn't match the clicked link's
  `data-section` — so clicking any of the 23 links whose target id had
  never existed (Timeline, xG, xT, VAEP, Charts, Heatmap, Pass Network,
  Momentum, Transitions, Finishing, Set Pieces, Phases, Tactics Report,
  Game Plan, Compare, Shortlist, Contracts, Recruitment, Settings,
  Search, Import, Data Export, plus a 24th, Sandbox, never counted)
  **hid every section and blanked the whole app**. The mobile bottom
  nav's Settings button had the same bug. Resolution per link: the 14
  Analysis/Tactics links whose views are panels INSIDE the Results page
  (xG/xT cards, charts, timeline sidebar, heatmap, pass network,
  momentum, set pieces, phases, report, transitions/finishing panels)
  now route to `results-section`; Compare → `professional-section`
  (where the pc-* compare panel actually lives); Sandbox →
  `results-section` (its `tactical-sandbox-section` div is embedded
  there — it was never a `.section`); Import → `results-section`
  (vendor-import panel); Data Export → `results-section` (export
  buttons); Search link **removed** (global search is the always-visible
  header box); Shortlist/Contracts/Recruitment and Settings and Game
  Plan **removed** (no UI exists anywhere — Settings had no section, no
  modal, no JS at all; Game Plan is backend-only
  `generate_game_plan`); bottom-nav Settings → Calibration (a real
  section that was previously unreachable from mobile nav).
  `calibration-section` was wrongly on the original dead list — it is a
  real `<section>` and worked. Regression gate:
  `src/kawkab/web/tests/nav-integrity.test.js` fails the frontend build
  if any `data-section` target (sidebar or bottom nav) stops resolving
  to a real `.section`. Remaining true gaps (no UI yet, link removed
  rather than faked): Shortlist, Contracts, Recruitment, Settings,
  Game Plan.
- ~~**34 frontend Jest failures**~~ — fixed (2026-07-30, same session as the
  harness fix below). All three were exactly "stale assertions against
  DOM/JS that moved on," confirmed via root-cause investigation rather than
  patched blind: `ui.test.js` (21) loaded `ui.js` with a regex expecting
  ES-module `export function` syntax that hasn't existed since `ui.js` was
  refactored to the IIFE-attaches-to-`window` convention every other
  `web/js/*.js` file uses — fixed by loading it the same way
  `js/__tests__/router.test.js` already does (`require()` + read the
  resulting `window.*` properties) rather than reinventing a loader.
  `app-charts.test.js` (12) mocked `Chart` without a `.register` static
  method; real Chart.js v3+ needs it and `app-charts.js` calls it at load
  time — added `MockChart.register = jest.fn()`. `analytics.test.js` (1)
  expected error output wrapped in a `.error`-class element; the actual
  (dead, see next bullet) code just does `container.textContent =
  data.error` — fixed the assertion to match.
- ~~**`web/js/analytics.js` was dead code with its own test suite**~~ —
  investigated and deleted (2026-07-30, follow-up pass), along with
  `tests/analytics.test.js`. Confirmed safe to delete, not "wire it up":
  it `import`s from `./core.js`, which doesn't exist anywhere in
  `web/js/`, and `import { showToast, ... } from './ui.js'` against a
  `ui.js` that is a plain IIFE with no `export` at all (ES-module syntax
  against a non-module file — this could never have worked, bundled or
  not). Its 9 backend calls (`get_xa_report`, `get_vaep_report`,
  `get_xt_report`, `get_momentum_index`, `get_set_piece_report`,
  `get_pass_flow`, `get_match_narrative`, `get_progressive_report`,
  `get_defensive_report`) don't exist anywhere in `bridge.py` either —
  unlike the 113 unreachable-but-real slots below, these were never
  implemented on the backend at all. Most of its own render functions
  were empty stubs (`function renderX(data) {}`). Net effect of deleting:
  zero working functionality lost; Jest suite unaffected (114/114 still
  pass). The underlying feature gap this abandoned prototype was reaching
  for (xA/VAEP/xT/momentum/set-piece/progressive/defensive report views)
  is still real and now folds into the existing "58 orphaned `core/`
  modules" gap below rather than being tracked twice.
- **Jest's parallel worker mode crashes** (`StackOverflowException`) on this
  Node/`jest-environment-jsdom` combination — `--runInBand` (sequential)
  works fine. Fixed via `maxWorkers: 1` in `jest.config.cjs`, so `npm test`
  is usable again, but the underlying version-compat crash itself wasn't
  root-caused.
- ~~**~8 remaining `SELECT *` sites in `postgres_storage.py`**~~ — fixed
  (2026-07-30, follow-up pass). Actually 21 sites across 15 tables, not ~8.
  `src/kawkab/migrations/pg_schema.sql` turned out to be a complete,
  authoritative column source (43 tables, matches every `INSERT` in the
  same file) — no live Postgres connection was needed after all, just
  cross-referencing against it. Verified via `ast.parse` (syntax) and the
  14 non-integration tests in `test_postgres_storage.py`; the 20
  integration tests still require a real `KAWKAB_DB_URL` connection to
  exercise, same as before. Note: `pg_schema.sql` itself has a latent bug
  found in the process — `seasons` is `CREATE TABLE IF NOT EXISTS`'d
  *twice* with two different column sets (line ~30 and line ~186); since
  `IF NOT EXISTS` makes the second a no-op against a fresh DB, only the
  first (narrower) definition ever actually applies. Not fixed — flagged
  here since it means the second definition's extra columns
  (`team_name`, `competition`) don't exist in any real deployment, despite
  looking like part of the schema.
- ~~**91 `except ... : pass` blocks**~~ — the 4 flagged-as-highest-risk
  files audited per-site (2026-07-30, follow-up pass); the rest (spread
  thin across the remaining files) intentionally not swept, see below.
  - **`cv_service.py` and `advanced_event_detection_service.py` had 2 real
    bugs, not just silence** — both follow the identical shape: on
    `homography_matrix.pixel_to_pitch()` failure, the code fell back to
    the *raw pixel* coordinates and kept going as if they were pitch-space
    meters. `_detect_dribbles`: the resulting "distance_m" (compared
    against a 1.0m threshold) would be the raw pixel distance --
    trivially over threshold, so any homography hiccup mid-match produced
    a false-positive dribble event with a nonsense distance. `_detect_clearances`:
    same mechanism, but for `"speed_mps"` against an 8 m/s threshold --
    guaranteed false-positive clearance the instant homography failed once.
    Both fixed: reset the tracking window instead of mixing pixel- and
    pitch-space points in it. Regression tests in
    `test_advanced_event_detection_service.py` use a `_FailingHomography`
    that always raises, confirming no false positives now.
  - **`_detect_corners`/`_detect_free_kicks`/`_detect_throw_ins` in the
    same file already used a `-1` sentinel + explicit `>= 0` guards before
    using pitch coordinates** — i.e. the same class of bug the two above
    had, but already correctly handled. Only missing diagnostic logging
    on the swallowed exception, added for consistency.
  - **`audit_service.py`'s except-blocks are correctly designed as-is** --
    every one already returns a safe, honest sentinel (`""`, `0`, `[]`,
    `{}`) rather than fabricating data; this file is audit-log
    bookkeeping, not match analytics, so a swallowed exception here means
    "lost a log entry," never "silently wrong stat." Also found and fixed
    an additional `SELECT *` in `get_events()` missed by the earlier
    SQLite `SELECT *` cleanup (columns: `id, timestamp, action,
    entity_type, entity_id, details_json, user, prev_hash` -- matches the
    explicit-column style `_get_last_hash()` in the same file already used).
  - **`gpu_acceleration.py`'s except-blocks are also correctly designed**
    -- this file is hardware-capability probing (which GPU backend,
    which VRAM tier), not analytics; most blocks already narrow to
    specific exception types (`FileNotFoundError`, `subprocess
    .TimeoutExpired`, `ImportError`, `ValueError`/`IndexError`) rather
    than bare `Exception`, and every fallback is an honest degraded mode
    ("no GPU backend detected -- using CPU"), not a fabricated result.
    Not logging every miss is correct here, not a gap -- most machines
    legitimately lack `nvidia-smi`/CUDA, and logging that as a warning on
    every single run would be noise, not signal.
  - **Remaining `except: pass` sites outside these 4 files** were not
    swept this session -- the 91 count was concentrated enough in these 4
    that auditing them covered the highest-risk surface; a full repo-wide
    sweep is still open if you want it.
- **~195 hardcoded hex colors + 204 inline `style=` attributes** remain in
  the frontend (down from the original ~295/310 estimate — see the CSS
  design-tokens entry above for the white/black primitive migration, the
  `.nav-item.active` contrast fix, and the two real `--text`/
  `--bg-elevated` light-theme bugs already fixed). What's left is mostly
  semantic status colors (`#dc2626`/`#16a34a`/`#d97706`/`#2563eb`, etc.)
  needing per-site judgment, not a blanket regex: some are already
  `var(--token, #stale-fallback)` (safe, mechanical cleanup — the fallback
  is dead since the token is unconditionally defined), but others, like
  `.pitch3d-legend-item .home-dot/.away-dot` and
  `.btn-pitch3d-home/away`, are "team side" colors that coincidentally
  match `--primary`/`--danger`'s current values and should map onto the
  already-existing but under-used `--team-home`/`--team-away` tokens
  instead — not the brand/status ones, or a future retune of "danger red"
  would unintentionally repaint the away-team markers too. A few (the
  `.fs-btn-*` fullscreen-tagging gradient family — goal/shot/pass/tackle/
  foul/corner/save/card, each its own two-stop gradient) are deliberately
  decorative, self-consistent one-offs not worth forcing onto unrelated
  tokens. A real token layer (spacing scale, type scale) still hasn't been
  built — these two passes fixed what was *broken* and what was safely
  mechanical, not a full design-system migration.
- **57 of 117 `core/` analytical modules are built and tested but not
  wired into the UI** (down ~12 as of 2026-09-07 — the Pro Analytics
  handler surfaces EPV, OBV, pass_flow, pressing_clusters, duels,
  ball_recovery, box_entries, switch_of_play, crossing, set_pieces,
  through_balls, offball_metrics; Season Form/xA/pressing-efficiency
  wired earlier). Remaining by area (full list shrunk accordingly):
  - Attacking: `xa_split` (xA itself now wired, see below), `expected_pass`, `through_ball`,
    `crossing_analysis`, `crossing_xg`, `corner_xg`, `box_entries`,
    `packing`, `switch_of_play`
  - Build-up/possession: `pass_network` (delegated-to but not surfaced as
    its own view), `passing_lanes`, `passing_triangles`, `pass_flow`,
    `carry_xt`
  - Defending: `defensive_actions`, `defensive_xt`, `pressing_efficiency`
    (trap-to-shot conversion now wired, see below; trap-to-goal rate and
    press-recovery-attack from the same module still aren't),
    `pressing_clusters` (spatial zone data — needs a pitch-map
    visualization, not a stat card; not attempted), `ball_recovery`, `duel_analysis`
  - Set pieces: `set_piece_analysis`, `set_piece_xt`
  - Player/squad: `obv`, `epv` (both need per-frame tracking data that
    isn't reliably persisted for most matches — see below), `offball_metrics`,
    `velocity_analysis`, `lineup_optimizer`
  - Season/admin: `fixture_difficulty`, `referee_analysis`,
    `suspension_tracker`, `formation_effectiveness`, `confidence_intervals`,
    `uncertainty`
  - Also fully untouched: `ball_physics_pitch_control`, `match_scripting`,
    `match_timeline`, `model_comparison_service`, `model_manager`,
    `pattern_detection`, `scoreline_distribution`, `scout_report_upgrade`, `xg_chain`,
    `xt_confidence`, `game_state`, `event_schema`, `export_converters`,
    `config` (the *tracking-pipeline* config, unrelated to the
    `Settings` class reconstructed this session), `fatigue_model`,
    `flank_analysis`, `form_analysis` (partially wired — see Season Form
    above), `influence_map`
  - **`OBV`/`EPV` specifically need full per-frame tracking data**
    (`frames: [{timestamp, possession, ball_pos, home_positions,
    away_positions}, ...]`), which the `tracking_frames` table only
    persists when `CVService.process_video()` is called with a
    `storage_service` param — not the default path. Wiring these without
    checking for that data first would silently show an empty/misleading
    report for most matches.
  - **PSxG unification completed 2026-09-16 (earlier pass):** the two
    hand-tuned alternate implementations (`core/psxg_improved.py`,
    `core/psxg_model_trained.py`) were DELETED; their behavioral contracts
    were ported into `tests/unit/test_psxg_contracts.py`. `core/psxg_model.py`
    (fitted coefficients, kept legacy API for `goalkeeper_analytics`) is
    now the single PSxG implementation. Still open: none of the PSxG path
    is used by the live CV pipeline's event path yet
    (goalkeeper_analytics is the only consumer of psxg_model).
- **113 of 325+ `@Slot` methods are never called from any JS file**
  (down from the original audit's count as this session wired a few more
  in) — includes the entire tactical whiteboard feature (19 slots, 45
  passing tests, zero UI). `tests/unit/test_bridge_contract.py`'s
  `test_unreachable_slots_inventory` prints the current live list — run it
  with `-s` rather than trusting this document, since the exact list will
  drift as more gets wired in.
- **Accessibility: real gaps found, some fixed, some flagged** — see the
  dated entry above for the full detail. Fixed: coding-matrix button
  text contrast, light-theme `--text-muted`, light-theme focus ring,
  dashboard `aria-live` coverage. Still open: dark-theme `--text-muted`
  vs `--bg-elevated` (4.04:1, marginal), white-on-`--success`/`--warning`
  badge text at small sizes (a brand-color judgment call, not made
  unilaterally), a full keyboard/screen-reader walkthrough, a WCAG 2.2
  target-size (24×24px) audit, and confirming whether the
  `[data-focus-trap]` CSS marker is backed by any real JS focus trap
  (found zero call sites setting the attribute).
- **XSS sweep: real bugs fixed, most sites spot-checked not hand-read.**
  See the dated entry above. Fixed: 3 files silently missing `escapeHtml`
  entirely (broken reference, not just unescaped output), a shadowed
  duplicate `escapeHtml` in `app.js` missing quote-escaping, a
  cross-user-reachable gap in the cloud-team-list renderer, and
  `calibration.js` having no escaping at all. ~280 of ~334 total
  `innerHTML` sites (concentrated in `app-tactics.js`/`app-scout.js`/
  `app-squad.js`/`app-highlight.js`/`app-briefing.js`/`events.js`) were
  confirmed via heuristic search to already use their own correctly-scoped
  `escapeHtml`, not read site-by-site by hand.
- **820 mypy errors remain** (non-strict; see the mypy Invariant above for
  why strict mode isn't the baseline) across ~130 files. Triaged by
  category, not by file: `attr-defined` (optional-attribute-without-a-
  None-check in `mujoco_ball_service.py`, cv2 stub incompleteness,
  mixin-composition false positives in `services/analysis/*.py` where
  `self.pitch_length` etc. really is set — just on the composed class, not
  the mixin mypy is checking in isolation) and `object has no attribute
  append` in `reasoning_service.py` (a heterogeneous `dict` literal mixing
  `int` and `list` values, inferred too broadly — runs fine) were sampled
  and are noise, not bugs. The two categories that *were* bugs
  (`name-defined`, `attr-defined` on `"type[X]"` i.e. calling a
  classmethod/staticmethod that doesn't exist) were mined exhaustively
  this session — see the SecurityValidator/ai_v2_list_convs/
  quality_scoring/card_detection/arabic_glossary fixes above. Re-run
  `mypy src/kawkab --ignore-missing-imports` and grep for those two error
  codes before assuming any *new* mypy error is noise.
  - **Follow-up sweep (2026-07-30) of `union-attr` and `return-value`,
    the two next-most-plausible-for-real-bugs categories**: mostly the
    same "mypy can't trace a guard through a separate method/function
    call" false positive already documented above (`self._conn`
    Optional-narrowed by `_ensure_initialized()`, `AsyncClient | None`
    narrowed by a lazy `_ensure_client()`-style setup, `_fernet` narrowed
    by `init_fernet()` in `core/encryption.py`) — confirmed, not fixed,
    since "fixing" would mean threading `assert`/inline-`if` everywhere
    mypy needs to see the narrowing, for zero behavior change. Found 2
    genuine issues in the same sweep: `bzzoiro_service.py::get_match_detail`
    called `.get()` on a value that could be a bare `list` (not just a
    `dict`) if the API ever responds unusually for a single-match-detail
    endpoint — added an `isinstance` guard. `player_profile_service
    .py::create_profile` is typed to return a non-Optional `PlayerProfile`
    but its last line delegated to `get_profile()`, which *is* Optional;
    callers (`bridge_analysis.py:950` among others) index straight into
    `profile.id` with no None-check. Fixed by raising a clear
    `RuntimeError` if the post-insert re-fetch is ever empty, instead of
    letting `None` silently satisfy a non-Optional return type. Also
    cleaned up `multi_camera_service.py::_merge_tracks`, which had a
    pointless `return track_groups` inside a `-> None` function (the one
    caller never used the return value) — cosmetic, zero behavior change.
- **115 ruff errors remain on the ~93 files touched this session** (of an
  original 590 before autofix + per-file-ignores; 2,073 across the whole,
  never-linted-before codebase). Dominated by `F841` unused-variable (38,
  spread across a dozen files, all pre-existing, none in code added this
  session — checked `test_health_endpoints.py`'s specifically since it's
  the one this session had already touched for an unrelated reason; it
  was genuine dead code with a misleading comment, fixed). Not chased
  further — mass-editing pre-existing unused-variable sites in files
  touched only incidentally is exactly the kind of scope creep this audit
  was trying to avoid elsewhere.
- **`pytest tests/ -n auto` (full root tree, all of it) is not clean —
  found 3 more issues while running it for the first time as part of the
  final verification pass, past this two fixed above:
  1. ~~**`test_bridge_advanced_metrics_wiring` and
     `test_bridge_frame_skip_parameter`**~~ — **fixed 2026-09-07, and
     the original diagnosis was wrong**: the failures were NOT the
     tempdir-path policy — they were a stale `FakeCVService
     .process_video` stub missing the `match_id`/`storage_service`
     parameters the real method takes (every analyze_match call
     TypeError'd into error-payload asserts). The stub now mirrors the
     real signature; 4/4 pass.
  2. **Tests that pass individually can fail when the *entire* `tests/`
     tree runs together** (confirmed: `test_cv_service_model_manager.py`
     and all of `tests/e2e/test_e2e_video_pipeline.py` pass 100% clean in
     isolation, but showed `TypeError: CVService() takes no arguments`
     when run as part of the full tree under `-n auto`). This is
     `pytest-xdist` worker-process co-scheduling exposing some
     `sys.modules` stub leaking from one test file into another's process
     — the same *species* of bug as the `test_norfair_tracker.py` leakage
     already fixed this session (see the norfair Invariant above), just a
     different pair of files, and distribution/order-dependent so it may
     not reproduce the same way every run. Not root-caused to the specific
     leaking file — would need the same kind of `sys.modules` save/restore
     audit across the stub-installing test files that
     `test_norfair_tracker.py` got.
  3. **`test_e2e_pipeline.py::TestCoverageConfig::test_coverage_fail_under_is_50`**
     ~~fixed before 2026-09-07~~ — now asserts pyproject's
     `fail_under = 65` (passes; see `tests/e2e/test_e2e_pipeline.py`
     line ~227 for the current assertion).
- **`test_bridge_contract.py` only checks that `bridge.py` has a `@Slot`
  for every JS call — not that the handler method the slot delegates to
  (`self._analysis.X(...)`, `self._auth.Y(...)`, etc.) actually exists.**
  ~~Closed 2026-09-07~~: `test_every_slot_delegation_targets_a_real_handler_method`
  parses bridge.py's `self._X.method(...)` delegations and verifies each
  against the real handler modules' method sets. Verified fail-positive
  by planting a fake broken delegation.
- **2 more shadowed-duplicate methods in `bridge_analysis.py`** — ~~fixed
  2026-09-07~~: both merged (see "What was fixed" above); `ruff
  --select F811` against `ui/bridge_handlers/` is clean as of this
  session. The live-video xG event path still calls the legacy heuristic
  `compute_xg_from_dict` in several places other than the fixed
  `compute_goals_added` — migrating every call site to
  `compute_xg_trained_from_dict` is open (grep
  `compute_xg_from_dict` in services/ + bridge_handlers/).

## Graphify

This project has a knowledge graph at `graphify-out/` with god nodes,
community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `Skill` tool with
`skill: "graphify"` before doing anything else.

- For codebase questions, first run `graphify query "<question>"` when
  `graphify-out/graph.json` exists. Use `graphify path "<A>" "<B>"` for
  relationships and `graphify explain "<concept>"` for focused concepts.
  These return a scoped subgraph, usually much smaller than
  `GRAPH_REPORT.md` or raw grep output.
- Dirty `graphify-out/` files are expected after hooks or incremental
  updates; dirty graph files are not a reason to skip graphify. Only skip
  graphify if the task is about stale/incorrect graph output, or the user
  explicitly says not to use it.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation
  instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or
  when query/path/explain don't surface enough context.
- After modifying code, run `graphify update .` to keep the graph current
  (AST-only, no API cost).
