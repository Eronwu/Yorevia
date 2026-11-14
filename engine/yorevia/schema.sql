PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources(
 id TEXT PRIMARY KEY, root TEXT NOT NULL UNIQUE, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
 captured_at TEXT, date_source TEXT NOT NULL DEFAULT 'unknown', date_manual INTEGER NOT NULL DEFAULT 0,
 width INTEGER, height INTEGER, latitude REAL, longitude REAL,
 thumb TEXT, note_text TEXT NOT NULL DEFAULT '', face_status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS locations(
 source_id TEXT NOT NULL REFERENCES sources(id), relative_path TEXT NOT NULL,
 asset_id TEXT NOT NULL REFERENCES assets(id), size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
 available INTEGER NOT NULL DEFAULT 1, scan_id TEXT NOT NULL,
 PRIMARY KEY(source_id,relative_path)
);
CREATE TABLE IF NOT EXISTS people(
 id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS faces(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
 person_id TEXT NOT NULL REFERENCES people(id), box TEXT NOT NULL,
 embedding BLOB NOT NULL, thumb TEXT NOT NULL, confidence REAL NOT NULL,
 locked INTEGER NOT NULL DEFAULT 0, ignored INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS relationships(
 id TEXT PRIMARY KEY, a TEXT NOT NULL REFERENCES people(id), b TEXT NOT NULL REFERENCES people(id),
 label TEXT NOT NULL, start_date TEXT, end_date TEXT, CHECK(a<>b)
);
CREATE TABLE IF NOT EXISTS stories(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 happened_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS story_assets(
 story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
 asset_id TEXT NOT NULL REFERENCES assets(id), PRIMARY KEY(story_id,asset_id)
);
CREATE TABLE IF NOT EXISTS story_people(
 story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
 person_id TEXT NOT NULL REFERENCES people(id), PRIMARY KEY(story_id,person_id)
);
CREATE INDEX IF NOT EXISTS ix_assets_date ON assets(captured_at);
CREATE INDEX IF NOT EXISTS ix_locations_asset ON locations(asset_id);
CREATE INDEX IF NOT EXISTS ix_faces_person ON faces(person_id,ignored);
CREATE INDEX IF NOT EXISTS ix_faces_asset ON faces(asset_id,ignored);
PRAGMA user_version=1;
