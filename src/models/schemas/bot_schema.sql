PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('grinder', 'espresso_machine', 'dripper')),
    name TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_equipment_one_default
    ON equipment (user_id, kind) WHERE is_default = 1;

CREATE TABLE IF NOT EXISTS beans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    roaster TEXT,
    origin TEXT,
    process TEXT,
    varietal TEXT,
    roast_level TEXT,
    roast_date TEXT,
    tasting_notes TEXT NOT NULL DEFAULT '[]',
    photo_file_id TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_beans_user ON beans (user_id, archived);

CREATE TABLE IF NOT EXISTS brews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bean_id INTEGER NOT NULL REFERENCES beans (id),
    method TEXT NOT NULL,
    grinder_id INTEGER REFERENCES equipment (id) ON DELETE SET NULL,
    brewer_id INTEGER REFERENCES equipment (id) ON DELETE SET NULL,
    grind_setting REAL,
    dose_g REAL,
    yield_g REAL,
    water_g REAL,
    temp_c REAL,
    time_s REAL,
    extraction TEXT CHECK (extraction IN ('under', 'good', 'over')),
    clarity TEXT,
    tasting_notes TEXT NOT NULL DEFAULT '[]',
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    photo_file_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_brews_user ON brews (user_id, id);
CREATE INDEX IF NOT EXISTS idx_brews_bean_method ON brews (user_id, bean_id, method);
