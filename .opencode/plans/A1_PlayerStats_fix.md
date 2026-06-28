# A1: Populate PlayerStats pass statistics

## Problem
`PlayerStats.passes_attempted` and `PlayerStats.passes_completed` are never populated — they remain 0 always. This causes:
- `pass_accuracy` property returns 0.0
- Player ratings get `pass_acc_score=0` and `pass_vol_score=0` 
- Database saves zeros to storage_service
- Frontend displays 0 passes for every player

## Fix 1: Back-populate PlayerStats from typed events
**File**: `src/kawkab/services/analysis_service.py`
**Location**: After line 186 (end of typed_events loop), before "# --- Phase 1: Carry detection ---"

Insert:
```python
# --- Populate PlayerStats from typed events ---
for ev in typed_events:
    if isinstance(ev, PassEvent) and ev.track_id is not None:
        player = players.get(ev.track_id)
        if player:
            player.passes_attempted += 1
            if ev.completed:
                player.passes_completed += 1
```

## Fix 2: Use estats for pass counts in _compute_player_ratings
**File**: `src/kawkab/services/analysis_service.py`
**Lines**: 710-713

Change:
```python
rating = compute_rating(
    pass_accuracy=player.pass_accuracy,
    passes_completed=player.passes_completed,
    passes_attempted=player.passes_attempted,
```
To:
```python
rating = compute_rating(
    pass_accuracy=estats.get("passes", 0) / max(estats.get("passes", 0), 1) if estats.get("passes", 0) > 0 else 0.0,
    passes_completed=estats.get("passes", 0),  # approximate — needs completed tracking
    passes_attempted=estats.get("passes", 0),
```

Actually, a cleaner approach: just read from player.pass_accuracy after Fix 1 populates it.

## Verification
- Run existing tests: `$env:PYTHONPATH="src"; python -m pytest tests/unit/test_core_events.py tests/unit/test_player_rating.py -v`
- All current tests should still pass (they mock the rating inputs directly)
