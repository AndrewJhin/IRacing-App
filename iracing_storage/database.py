"""SQLite persistence. Write methods participate in the caller's transaction."""

from __future__ import annotations

import json
import math
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1


def default_database() -> Path:
    override = os.environ.get('IRACING_DATABASE')
    if override:
        return Path(override).expanduser()
    # Windows packaged hosts can virtualize AppData file access into their cache,
    # even when the path is absolute. Keep this database outside that redirected tree.
    return Path.home() / '.iracing-app' / 'storage' / 'iracing.sqlite3'


def json_safe(value: Any) -> Any:
    """Keep types and unavailable markers; label nonfinite numbers for strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return {'_nonfinite': str(value)}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # YAML may contain dates. Preserve their text without interpreting car units.
    return str(value)


def encode(value: Any) -> str:
    return json.dumps(json_safe(value), ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def numeric(value: Any, *, integer: bool = False) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if integer:
        return int(value) if value == int(value) and -(2**63) <= value < 2**63 else None
    return value


def decode_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in list(result):
        if key.endswith('_json'):
            result[key[:-5]] = json.loads(result.pop(key))
    return result


def page_limit(limit: int) -> int:
    if not 1 <= limit <= 5000:
        raise ValueError('limit must be between 1 and 5000')
    return limit


class Store:
    def __init__(self, path: Path | str | None = None, *, readonly: bool = False):
        self.path = (Path(path) if path is not None else default_database()).expanduser().resolve()
        if readonly:
            self.connection = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.path, timeout=5)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute('PRAGMA foreign_keys=ON')
            if readonly:
                self.connection.execute('PRAGMA query_only=ON')
                if self.connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
                    raise ValueError('Unsupported database schema; run init with the matching application version')
            else:
                self._migrate()
                self.connection.execute('PRAGMA journal_mode=WAL')
                self.connection.execute('PRAGMA synchronous=FULL')
        except BaseException:
            self.connection.close()
            raise

    def _migrate(self) -> None:
        # Serialize initialization and make each upgrade transactional.
        with self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError(f'Database schema {version} is newer than supported version {SCHEMA_VERSION}')
            if version == 0:
                if self.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                    raise ValueError('Refusing to initialize an unrelated database')
                migration = Path(__file__).parent / 'migrations' / '001_initial.sql'
                statement = ''
                for line in migration.read_text(encoding='utf-8').splitlines(True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        self.connection.execute(statement)
                        statement = ''
                self.connection.execute('PRAGMA user_version=1')

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def create_recording(self, *, profile: dict, catalog: list[dict], source_kind: str,
                         source_uri: str | None = None, metadata: dict | None = None,
                         started_at: float | None = None, recording_id: str | None = None) -> str:
        recording_id = recording_id or str(uuid.uuid4())
        self.connection.execute(
            'INSERT INTO recordings(id,source_kind,source_uri,started_at,status,profile_json,metadata_json) '
            "VALUES(?,?,?,?,'recording',?,?)",
            (recording_id, source_kind, source_uri, time.time() if started_at is None else started_at,
             encode(profile), encode(metadata or {})))
        self.connection.executemany('INSERT INTO channels VALUES(?,?,?)',
                                    [(recording_id, item['name'], encode(item)) for item in catalog])
        return recording_id

    def add_stint(self, recording_id: str, number: int, metadata: dict) -> int:
        return self.connection.execute('INSERT INTO stints(recording_id,number,metadata_json) VALUES(?,?,?)',
                                       (recording_id, number, encode(metadata))).lastrowid

    def add_snapshot(self, recording_id: str, stint_id: int, raw_yaml: str, *, update: int | None = None,
                     captured_at: float | None = None, provenance: str = 'observed_before_sample',
                     setup_override: Any = None, use_setup_override: bool = False,
                     raw_setup_override: str | None = None) -> int:
        error = None
        try:
            info = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            info, error = None, str(exc)
        setup = info.get('CarSetup') if isinstance(info, dict) else None
        # Retain the exact setup text even when the full session YAML cannot be parsed.
        lines = raw_yaml.splitlines(keepends=True)
        start = next((i for i, line in enumerate(lines) if line.rstrip('\r\n') == 'CarSetup:'), None)
        raw_setup = None
        if start is not None:
            end = next((i for i in range(start + 1, len(lines))
                        if lines[i].strip() and not lines[i][0].isspace() and ':' in lines[i]), len(lines))
            raw_setup = ''.join(lines[start:end])
        if error and raw_setup:
            try:
                parsed_setup = yaml.safe_load(raw_setup)
                setup = parsed_setup.get('CarSetup') if isinstance(parsed_setup, dict) else None
            except yaml.YAMLError:
                pass
        if use_setup_override:
            setup, raw_setup = setup_override, raw_setup_override
        return self.connection.execute(
            'INSERT INTO snapshots(recording_id,stint_id,session_update,captured_at,provenance,'
            'raw_session_yaml,raw_setup_yaml,session_json,setup_json,parse_error) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (recording_id, stint_id, update, captured_at, provenance, raw_yaml, raw_setup,
             encode(info), encode(setup), error)).lastrowid

    def add_samples(self, recording_id: str, rows: list[tuple]) -> None:
        self.connection.executemany('INSERT INTO samples VALUES(?,?,?,?,?,?,?,?,?,?,?)', rows)
        self.connection.execute('UPDATE recordings SET sample_count=sample_count+? WHERE id=?',
                                (len(rows), recording_id))

    def finish_recording(self, recording_id: str, status: str, *, ended_at: float | None = None) -> None:
        if status not in ('completed', 'interrupted', 'failed', 'imported'):
            raise ValueError('Invalid final recording status')
        self.connection.execute('UPDATE recordings SET status=?,ended_at=? WHERE id=?',
                                (status, time.time() if ended_at is None else ended_at, recording_id))

    def add_document(self, kind: str, payload: Any, *, recording_id: str | None = None,
                     schema_version: int = 1, source_uri: str | None = None) -> str:
        document_id = str(uuid.uuid4())
        self.connection.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',
                                (document_id, recording_id, kind, schema_version, time.time(), source_uri, encode(payload)))
        return document_id

    def list_recordings(self, *, limit: int = 100, offset: int = 0,
                        started_from: float | None = None, started_until: float | None = None) -> list[dict]:
        if offset < 0:
            raise ValueError('offset must be nonnegative')
        clauses, params = [], []
        for value, operator in ((started_from, '>='), (started_until, '<')):
            if value is not None:
                if not math.isfinite(value):
                    raise ValueError('Invalid date boundary')
                clauses.append('started_at' + operator + '?')
                params.append(value)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        return [decode_row(row) for row in self.connection.execute(
            'SELECT * FROM recordings' + where + ' ORDER BY started_at DESC,id LIMIT ? OFFSET ?',
            (*params, page_limit(limit), offset))]

    def recording(self, recording_id: str) -> dict:
        row = self.connection.execute('SELECT * FROM recordings WHERE id=?', (recording_id,)).fetchone()
        if row is None:
            raise KeyError(recording_id)
        result = decode_row(row)
        result['stints'] = [decode_row(row) for row in self.connection.execute(
            'SELECT * FROM stints WHERE recording_id=? ORDER BY number', (recording_id,))]
        return result

    def catalog(self, recording_id: str) -> list[dict]:
        return [json.loads(row[0]) for row in self.connection.execute(
            'SELECT metadata_json FROM channels WHERE recording_id=? ORDER BY name', (recording_id,))]

    def samples(self, recording_id: str, *, after: int = -1, limit: int = 1000,
                channels: list[str] | None = None, stint_id: int | None = None,
                session_num: int | None = None, lap: int | None = None,
                time_min: float | None = None, time_max: float | None = None) -> dict:
        if after < -1:
            raise ValueError('after must be at least -1')
        if channels is not None and (len(channels) > 256 or any(not name for name in channels)):
            raise ValueError('Provide 1 to 256 nonempty channel names, or omit channels')
        clauses = ['recording_id=?', 'sequence>?']
        params: list[Any] = [recording_id, after]
        for column, value, operator in [('stint_id', stint_id, '='), ('session_num', session_num, '='),
                                         ('lap', lap, '='), ('session_time', time_min, '>='),
                                         ('session_time', time_max, '<=')]:
            if value is not None:
                if not math.isfinite(value):
                    raise ValueError('Filters must be finite numbers')
                clauses.append(f'{column}{operator}?')
                params.append(value)
        if time_min is not None and time_max is not None and time_min > time_max:
            raise ValueError('time_min must not exceed time_max')
        rows = self.connection.execute('SELECT * FROM samples WHERE ' + ' AND '.join(clauses) +
                                       ' ORDER BY sequence LIMIT ?', [*params, page_limit(limit) + 1]).fetchall()
        more = len(rows) > limit
        items = [decode_row(row) for row in rows[:limit]]
        if channels is not None:
            for item in items:
                item['values'] = {name: item['values'].get(name, {'_unavailable': True, 'reason': 'not_recorded'})
                                  for name in channels}
        return {'items': items, 'has_more': more, 'next_after': items[-1]['sequence'] if items else after}

    def snapshots(self, recording_id: str, *, after: int = 0, limit: int = 100) -> list[dict]:
        return [decode_row(row) for row in self.connection.execute(
            'SELECT * FROM snapshots WHERE recording_id=? AND id>? ORDER BY id LIMIT ?',
            (recording_id, after, page_limit(limit)))]

    def documents(self, *, kind: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
        if offset < 0:
            raise ValueError('offset must be nonnegative')
        return [decode_row(row) for row in self.connection.execute(
            'SELECT * FROM documents WHERE (? IS NULL OR kind=?) ORDER BY captured_at,id LIMIT ? OFFSET ?',
            (kind, kind, page_limit(limit), offset))]

    def backup(self, destination: Path) -> None:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents accidental replacement of any database or source file.
        with destination.open('xb'):
            pass
        target = sqlite3.connect(destination)
        try:
            self.connection.backup(target)
        finally:
            target.close()


def sample_row(recording_id: str, sequence: int, stint_id: int, snapshot_id: int,
               tick: int, captured_at: float, values: dict) -> tuple:
    if not isinstance(values, dict) or type(tick) is not int or not -(2**63) <= tick < 2**63:
        raise ValueError('A sample requires an integer tick and an object of values')
    if isinstance(captured_at, bool) or not isinstance(captured_at, (int, float)) or not math.isfinite(captured_at):
        raise ValueError('captured_at must be a finite Unix timestamp')
    return (recording_id, sequence, stint_id, snapshot_id, tick, captured_at,
            numeric(values.get('SessionNum'), integer=True), numeric(values.get('SessionTime')),
            numeric(values.get('Lap'), integer=True), numeric(values.get('LapDistPct')), encode(values))
