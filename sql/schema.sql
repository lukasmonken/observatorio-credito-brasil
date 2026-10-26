CREATE TABLE IF NOT EXISTS series (
 code INTEGER PRIMARY KEY, name TEXT NOT NULL, unit TEXT NOT NULL,
 frequency TEXT NOT NULL CHECK (frequency IN ('D','M')), measure_type TEXT NOT NULL,
 segment TEXT NOT NULL, classification TEXT NOT NULL, metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT,
 status TEXT NOT NULL CHECK (status IN ('running','success','partial','failed')),
 mode TEXT NOT NULL, summary_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
 code INTEGER NOT NULL REFERENCES series(code), date TEXT NOT NULL,
 value DOUBLE PRECISION, run_id TEXT NOT NULL REFERENCES runs(run_id),
 PRIMARY KEY (code,date)
);
CREATE INDEX IF NOT EXISTS observations_date_idx ON observations(date);
CREATE TABLE IF NOT EXISTS monthly_observations (
 code INTEGER NOT NULL REFERENCES series(code), date TEXT NOT NULL,
 value DOUBLE PRECISION, run_id TEXT NOT NULL REFERENCES runs(run_id),
 PRIMARY KEY (code,date)
);
CREATE TABLE IF NOT EXISTS revisions (
 revision_id TEXT PRIMARY KEY, code INTEGER NOT NULL REFERENCES series(code),
 date TEXT NOT NULL, old_value DOUBLE PRECISION, new_value DOUBLE PRECISION,
 run_id TEXT NOT NULL REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS quality (
 check_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
 code INTEGER REFERENCES series(code), check_name TEXT NOT NULL,
 severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
 message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS derived_indicators (
 code INTEGER NOT NULL REFERENCES series(code), date TEXT NOT NULL,
 metric TEXT NOT NULL, value DOUBLE PRECISION, base_month TEXT,
 run_id TEXT NOT NULL REFERENCES runs(run_id),
 PRIMARY KEY (code,date,metric)
);
