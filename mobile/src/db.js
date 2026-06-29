import * as SQLite from 'expo-sqlite';

let db = null;

export async function getDb() {
  if (!db) {
    db = await SQLite.openDatabaseAsync('kawkab_mobile.db');
    await initDb();
  }
  return db;
}

async function initDb() {
  const d = await getDb();
  await d.execAsync(`
    CREATE TABLE IF NOT EXISTS matches (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      home_team TEXT,
      away_team TEXT,
      home_score INTEGER DEFAULT 0,
      away_score INTEGER DEFAULT 0,
      date TEXT,
      data TEXT DEFAULT '{}',
      synced INTEGER DEFAULT 0,
      updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS scout_reports (
      id TEXT PRIMARY KEY,
      player_name TEXT NOT NULL,
      team TEXT,
      position TEXT,
      rating INTEGER DEFAULT 0,
      notes TEXT,
      photo_uri TEXT,
      synced INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS sync_queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      operation TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      data TEXT DEFAULT '{}',
      created_at TEXT DEFAULT (datetime('now'))
    );
  `);
}

export async function saveMatch(match) {
  const d = await getDb();
  await d.runAsync(
    `INSERT OR REPLACE INTO matches (id, name, home_team, away_team, home_score, away_score, date, data, synced, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))`,
    [match.id, match.name, match.home_team, match.away_team,
     match.home_score || 0, match.away_score || 0, match.date,
     JSON.stringify(match), match.synced || 0]
  );
  await d.runAsync(
    `INSERT INTO sync_queue (operation, entity_type, entity_id, data) VALUES ('upsert', 'match', ?, ?)`,
    [match.id, JSON.stringify(match)]
  );
}

export async function getMatches() {
  const d = await getDb();
  const rows = await d.getAllAsync('SELECT * FROM matches ORDER BY date DESC');
  return rows;
}

export async function saveScoutReport(report) {
  const d = await getDb();
  await d.runAsync(
    `INSERT OR REPLACE INTO scout_reports (id, player_name, team, position, rating, notes, photo_uri, synced)
     VALUES (?, ?, ?, ?, ?, ?, ?, 0)`,
    [report.id, report.player_name, report.team, report.position,
     report.rating, report.notes, report.photo_uri]
  );
  await d.runAsync(
    `INSERT INTO sync_queue (operation, entity_type, entity_id, data) VALUES ('upsert', 'scout_report', ?, ?)`,
    [report.id, JSON.stringify(report)]
  );
}

export async function getScoutReports() {
  const d = await getDb();
  return await d.getAllAsync('SELECT * FROM scout_reports ORDER BY created_at DESC');
}

export async function getUnsynced() {
  const d = await getDb();
  return await d.getAllAsync('SELECT * FROM sync_queue ORDER BY created_at ASC LIMIT 50');
}

export async function clearSyncQueue() {
  const d = await getDb();
  await d.runAsync('DELETE FROM sync_queue');
}
