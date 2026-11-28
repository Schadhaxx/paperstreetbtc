-- PaperStreet page-error reports (Stage 2 analytics, 27 Nov 2026).
-- One row per accepted POST /err. No IP, no User-Agent, no cookies,
-- no query strings. Retention is 30 days, capped at ~5,000 rows
-- (enforced by the Worker on each accepted POST).
CREATE TABLE IF NOT EXISTS errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  path TEXT NOT NULL,
  message TEXT NOT NULL,
  file TEXT NOT NULL DEFAULT '',
  line INTEGER NOT NULL DEFAULT 0,
  browser TEXT NOT NULL DEFAULT 'Other',
  device TEXT NOT NULL DEFAULT 'desktop',
  pin TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'onerror',
  src TEXT
);
CREATE INDEX IF NOT EXISTS idx_errors_ts ON errors (ts);
CREATE INDEX IF NOT EXISTS idx_errors_message ON errors (message);
