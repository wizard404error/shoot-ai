-- Migration 019: Collaboration tables (users persistence, mentions)

CREATE TABLE IF NOT EXISTS collab_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    role TEXT DEFAULT 'analyst',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS collab_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    event_id INTEGER DEFAULT 0,
    user_id INTEGER DEFAULT 0,
    username TEXT DEFAULT '',
    text TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS collab_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    from_user TEXT NOT NULL,
    text TEXT NOT NULL,
    match_id INTEGER DEFAULT 0,
    event_id INTEGER DEFAULT 0,
    read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_collab_mentions_username ON collab_mentions(username);
CREATE INDEX IF NOT EXISTS idx_collab_comments_match ON collab_comments(match_id);
