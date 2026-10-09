PRAGMA foreign_keys = ON;

-- Example table structure
-- Add your database tables here

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
