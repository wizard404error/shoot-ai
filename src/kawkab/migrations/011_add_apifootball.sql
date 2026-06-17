-- Migration 011: Add API-Football (api-sports.io) reference columns

ALTER TABLE matches ADD COLUMN apifb_home_team_id INTEGER;
ALTER TABLE matches ADD COLUMN apifb_away_team_id INTEGER;
ALTER TABLE matches ADD COLUMN apifb_fixture_id INTEGER;
ALTER TABLE matches ADD COLUMN apifb_league_id INTEGER;
ALTER TABLE matches ADD COLUMN apifb_season INTEGER;

ALTER TABLE player_profiles ADD COLUMN apifb_person_id INTEGER;
ALTER TABLE player_profiles ADD COLUMN apifb_team_id INTEGER;
