PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, channel TEXT NOT NULL CHECK(channel IN ('media','portal','community','sns','broadcast','official')),
 name TEXT NOT NULL, access_mode TEXT NOT NULL, expected_minutes INTEGER, last_success TEXT, status TEXT NOT NULL DEFAULT 'not_connected',
 rights_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), external_id TEXT,
 url TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, published_at TEXT NOT NULL, collected_at TEXT NOT NULL,
 time_basis TEXT NOT NULL DEFAULT 'source', content_scope TEXT NOT NULL CHECK(content_scope IN ('full','snippet','title','transcript','comment')),
 content_hash TEXT NOT NULL, cluster_id TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1)),
 parent_id TEXT REFERENCES documents(id), sample_method TEXT, revision INTEGER NOT NULL DEFAULT 1,
 UNIQUE(source_id,external_id)
);
CREATE INDEX IF NOT EXISTS document_time ON documents(published_at);
CREATE INDEX IF NOT EXISTS document_cluster ON documents(cluster_id);
CREATE TABLE IF NOT EXISTS fact_baselines (
 id TEXT PRIMARY KEY, statement TEXT NOT NULL, procedural_status TEXT NOT NULL,
 source_uri TEXT NOT NULL, source_hash TEXT NOT NULL, locator TEXT NOT NULL, evidence_quote TEXT NOT NULL,
 verification TEXT NOT NULL CHECK(verification IN ('pending','verified','superseded')),
 version INTEGER NOT NULL, approved_by TEXT, approved_at TEXT, valid_from TEXT NOT NULL, valid_to TEXT,
 CHECK(verification != 'verified' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND length(evidence_quote)>0))
);
CREATE TABLE IF NOT EXISTS analyses (
 document_id TEXT PRIMARY KEY REFERENCES documents(id), status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
 primary_frame TEXT NOT NULL, secondary_json TEXT NOT NULL, frames_json TEXT NOT NULL,
 targets_json TEXT NOT NULL, tone TEXT NOT NULL CHECK(tone IN ('negative','neutral','positive','unknown')),
 emotion TEXT NOT NULL, argument TEXT NOT NULL, evidence_json TEXT NOT NULL, exposure_json TEXT NOT NULL,
 fact_gap TEXT NOT NULL, confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 model TEXT NOT NULL, prompt_version TEXT NOT NULL, fact_version INTEGER NOT NULL, reviewed_by TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS amplifications (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id), kind TEXT NOT NULL CHECK(kind IN ('portal_main','broadcast_top','broadcast_general')),
 observed_at TEXT NOT NULL, ended_at TEXT, evidence_uri TEXT NOT NULL, verified INTEGER NOT NULL CHECK(verified IN (0,1)),
 duration_basis TEXT NOT NULL DEFAULT 'point_observation'
);
CREATE TABLE IF NOT EXISTS alerts (
 id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, window_end TEXT NOT NULL, severity TEXT NOT NULL,
 payload_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, UNIQUE(rule_id,window_end)
);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, scheduled_at TEXT NOT NULL UNIQUE, cutoff_at TEXT NOT NULL, status TEXT NOT NULL,
 body TEXT NOT NULL, snapshot_json TEXT NOT NULL, generated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL, object_id TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL REFERENCES sources(id), started_at TEXT NOT NULL,
 finished_at TEXT, status TEXT NOT NULL, items INTEGER NOT NULL DEFAULT 0, cursor TEXT, error_code TEXT
);
