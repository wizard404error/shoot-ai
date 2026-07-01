# Data Card — Kawkab AI

## Tactical Knowledge Base

### Source & Authority

| Category | Files | Author | Authority |
|---|---|---|---|
| Defensive tactics | 13 YAML rules in `knowledge/tactics/defensive/` | Domain expert (football coach) + literature review | Published tactical principles (zonal marking, pressing traps, compactness) |
| Individual tactics | 7 YAML rules in `knowledge/tactics/individual/` | Domain expert | Position-specific responsibilities (CB positioning, FB support, GK distribution) |
| Meta tactics | 3 YAML rules in `knowledge/tactics/meta/` | Domain expert | Fatigue, communication, time management — cross-cutting |
| Offensive tactics | 13 YAML rules in `knowledge/tactics/offensive/` | Domain expert | Build-up patterns, final-third entries, shot quality |
| Transition tactics | 3 YAML rules in `knowledge/tactics/transition/` | Domain expert | Counter-attack, counter-press, defensive transition timing |
| Training drills | 24 YAML files in `knowledge/drills/` | Domain expert + published drill libraries | Small-sided games, positional patterns, set-piece practice |
| Laws of the Game | 1 YAML file in `knowledge/rules/` | IFAB Laws of the Game (official) | Official football rules — unmodified |

### How Rules Are Applied

1. `ReasoningService` loads all YAML rule files at startup
2. For each rule, it checks whether the required metrics exist in the analysis output
3. If a metric is below/above the rule's threshold, the rule fires and generates a diagnosis
4. The diagnoses are assembled into a `DiagnosisReport` and passed to the LLM for narrative generation

### Ground Truth Status

| Metric | Ground Truth Available | Source |
|---|---|---|
| Events (pass, shot, tackle) | Partial | `tests/fixtures/` — manually annotated 5-min clip |
| Ball possession | None | — |
| Player positions | None | — |
| Speed / distance | None | — |
| xG | Heuristic only | No real-shot database |

**Current limitation**: there is no full-match, hand-annotated ground truth dataset. All metrics are evaluated by self-consistency checks (track fragmentation, MOT metrics) rather than against known labels. Backlog item #19 (ground-truth eval set with 3+ amateur matches) is pending to close this gap.

### Analytical Models

| Model | Type | Parameters | Validation |
|---|---|---|---|
| xG (simple) | Logistic regression (distance + angle) | 2 features | Self-consistent (bounds 0.0-1.0) |
| xT (zone) | 20×32 grid with calibrated zone values | 640 cells | Bounded, monotonic toward goal |
| VAEP | Spatiotemporal (player-relative features) | 6+ features | Self-consistent (bounds 0.0-1.0) |
| Pitch control | Voronoi + ball-physics RK4 | Varies | Matches expected qualitative shape |
| Win probability | Monte Carlo (10k Poisson simulations) | Per match | Converges with more simulations |

### Privacy & Data Handling

- **Default: 100% offline.** All processing happens on the user's machine. No data leaves the device.
- **Telemetry**: opt-in only, off by default. Backlog item #63 (telemetry opt-in) covers implementation.
- **Logs**: may contain face crops and player positions. Log redaction is planned but not yet implemented (backlog #60).
- **Model weights**: downloaded from public URLs (ultralytics, boxmot, SoccerNet). No user data is sent to these servers during download.
