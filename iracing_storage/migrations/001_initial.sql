CREATE TABLE recordings (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_uri TEXT,
    import_hash TEXT UNIQUE,
    started_at REAL NOT NULL,
    ended_at REAL,
    status TEXT NOT NULL CHECK(status IN ('recording','completed','interrupted','failed','imported')),
    sample_count INTEGER NOT NULL DEFAULT 0,
    profile_json TEXT NOT NULL CHECK(json_valid(profile_json)),
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json))
);
CREATE INDEX recordings_started ON recordings(started_at, id);
CREATE TABLE channels (
    recording_id TEXT NOT NULL REFERENCES recordings(id),
    name TEXT NOT NULL,
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
    PRIMARY KEY(recording_id, name)
);
CREATE TABLE stints (
    id INTEGER PRIMARY KEY,
    recording_id TEXT NOT NULL REFERENCES recordings(id),
    number INTEGER NOT NULL,
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
    UNIQUE(recording_id, number),
    UNIQUE(recording_id, id)
);
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY,
    recording_id TEXT NOT NULL,
    stint_id INTEGER NOT NULL,
    session_update INTEGER,
    captured_at REAL,
    provenance TEXT NOT NULL,
    raw_session_yaml TEXT NOT NULL,
    raw_setup_yaml TEXT,
    session_json TEXT NOT NULL CHECK(json_valid(session_json)),
    setup_json TEXT NOT NULL CHECK(json_valid(setup_json)),
    parse_error TEXT,
    FOREIGN KEY(recording_id, stint_id) REFERENCES stints(recording_id, id),
    UNIQUE(recording_id, stint_id, id)
);
CREATE INDEX snapshots_recording ON snapshots(recording_id, id);
CREATE TABLE samples (
    recording_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence >= 0),
    stint_id INTEGER NOT NULL,
    snapshot_id INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    captured_at REAL NOT NULL,
    session_num INTEGER,
    session_time REAL,
    lap INTEGER,
    lap_distance REAL,
    values_json TEXT NOT NULL CHECK(json_valid(values_json)),
    FOREIGN KEY(recording_id, stint_id, snapshot_id) REFERENCES snapshots(recording_id, stint_id, id),
    PRIMARY KEY(recording_id, sequence)
) WITHOUT ROWID;
CREATE INDEX samples_lap ON samples(recording_id, stint_id, session_num, lap, sequence);
CREATE INDEX samples_time ON samples(recording_id, session_num, session_time, sequence);
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    recording_id TEXT REFERENCES recordings(id),
    kind TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK(schema_version > 0),
    captured_at REAL NOT NULL,
    source_uri TEXT,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE INDEX documents_kind ON documents(kind, captured_at, id);
CREATE VIEW telemetry_channels AS
SELECT s.recording_id, s.sequence, s.stint_id, s.session_num, s.lap, s.session_time,
       j.key AS channel, j.type AS value_type, j.value AS value
FROM samples AS s, json_each(s.values_json) AS j;
CREATE VIEW setup_fields AS
SELECT s.recording_id, s.stint_id, s.id AS snapshot_id,
       j.fullkey AS path, j.type AS value_type, j.atom AS value
FROM snapshots AS s, json_tree(s.setup_json) AS j
WHERE j.type NOT IN ('object','array');
