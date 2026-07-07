# StatsBomb

StatsBomb Open Data provides free match event data for major competitions.

## Usage

```python
from kawkab.services.statsbomb_service import (
    get_competitions, get_matches, get_events, get_shots
)

comps = await get_competitions()
matches = await get_matches(competition_id=43, season_id=106)
events = await get_events(match_id=3788741)
shots = await get_shots(match_id=3788741)
```

## Supported Competitions

- FIFA World Cup 2018, 2022
- UEFA Euro 2020, 2024
- FA Women's Super League
- La Liga
- Premier League (selected seasons)
