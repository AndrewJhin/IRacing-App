"""Atomic, streaming import of closed capture directories, including legacy exports."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .database import Store, sample_row


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def capture_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.yaml', '.csv'):
            digest.update(path.relative_to(root).as_posix().encode('utf-8') + b'\0')
            digest.update(str(path.stat().st_size).encode('ascii') + b'\0')
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
    return digest.hexdigest()


def json_lines(path: Path):
    if not path.exists():
        return
    with path.open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError('expected a JSON object')
                    yield item
                except (ValueError, KeyError) as exc:
                    raise ValueError(f'{path.name}:{line_number}: {exc}') from exc


def import_capture(store: Store, root: Path) -> dict:
    root = root.resolve()
    if not (root / 'catalog' / 'live_variables.json').is_file():
        raise ValueError('Choose one capture directory containing catalog/ and stints/')
    manifest_path = root / 'capture.json'
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    if manifest.get('status') == 'recording':
        raise ValueError('Capture is marked recording; import only a closed capture')
    fingerprint = capture_hash(root)
    directories = sorted((root / 'stints').glob('stint-*'))
    if not directories:
        raise ValueError('Capture contains no stints')
    # A single transaction includes deduplication, metadata and streamed sample batches.
    # A malformed final line or a changing source rolls back the entire import.
    with store.connection:
        store.connection.execute('BEGIN IMMEDIATE')
        existing = store.connection.execute('SELECT id FROM recordings WHERE import_hash=?', (fingerprint,)).fetchone()
        if existing:
            return {'recording_id': existing[0], 'already_imported': True}
        original_id = manifest.get('recording_id')
        if original_id and store.connection.execute('SELECT 1 FROM recordings WHERE id=?', (original_id,)).fetchone():
            raise ValueError('This capture already has a live recording in this database; import into a different database to restore it')
        metadata = read_json(directories[0] / 'metadata.json')
        profile_path = root / 'profile.json'
        profile = read_json(profile_path) if profile_path.exists() else {
            'profile_id': metadata.get('profile_id'), 'version': metadata.get('profile_version'),
            'provenance': 'legacy_metadata_only'}
        recording_id = store.create_recording(
            profile=profile, catalog=read_json(root / 'catalog' / 'live_variables.json'),
            source_kind='capture_import', source_uri=str(root), started_at=metadata.get('started_at'),
            recording_id=original_id, metadata={'capture_manifest': manifest, 'import_format': 1})
        sequence, pending, last_captured_at = 0, [], None
        for directory in directories:
            match = re.fullmatch(r'stint-(\d+)', directory.name)
            if not match or not directory.is_dir():
                raise ValueError(f'Invalid stint directory: {directory.name}')
            telemetry_path = directory / 'telemetry.jsonl'
            if not telemetry_path.is_file():
                raise ValueError(f'Missing telemetry file in {directory.name}')
            stint_metadata = read_json(directory / 'metadata.json')
            stint_id = store.add_stint(recording_id, int(match.group(1)), stint_metadata)
            initial_path = directory / 'initial_session_info.yaml'
            raw = (initial_path if initial_path.exists() else directory / 'session_info.yaml').read_text(encoding='utf-8')
            setup_path = directory / 'car_setup.json'
            raw_setup_path = directory / 'car_setup.yaml'
            snapshot_id = store.add_snapshot(
                recording_id, stint_id, raw, captured_at=stint_metadata.get('started_at'),
                provenance='stint_initial' if initial_path.exists() else 'legacy_stint_setup_latest_session_info',
                setup_override=read_json(setup_path) if setup_path.exists() else None,
                use_setup_override=True,
                raw_setup_override=raw_setup_path.read_text(encoding='utf-8') if raw_setup_path.exists() else None)
            updates = iter(json_lines(directory / 'session_info_updates.jsonl'))
            next_update = next(updates, None)
            last_boundary = -1

            def save_update(item):
                return store.add_snapshot(recording_id, stint_id, item['raw_yaml'], update=item.get('update'),
                                          captured_at=item.get('captured_at'),
                                          provenance='observed_before_sample' if 'before_sample' in item
                                          else 'legacy_update_timing_unknown')

            for local_sequence, item in enumerate(json_lines(telemetry_path)):
                while next_update is not None:
                    boundary = next_update.get('before_sample')
                    if boundary is not None:
                        if type(boundary) is not int or boundary < 0 or boundary < last_boundary:
                            raise ValueError('Session update boundaries must be nonnegative and ordered')
                        if boundary > local_sequence:
                            break
                        last_boundary = boundary
                    update_id = save_update(next_update)
                    if boundary is not None:
                        snapshot_id = update_id
                    next_update = next(updates, None)
                last_captured_at = item['captured_at']
                pending.append(sample_row(recording_id, sequence, stint_id, snapshot_id,
                                          item['tick'], last_captured_at, item['values']))
                sequence += 1
                if len(pending) >= 500:
                    store.add_samples(recording_id, pending)
                    pending.clear()
            while next_update is not None:
                # Keep updates even for a stint that ended before another sample arrived.
                save_update(next_update)
                next_update = next(updates, None)
        if pending:
            store.add_samples(recording_id, pending)
        if capture_hash(root) != fingerprint:
            raise ValueError('Capture changed during import; stop the collector and retry')
        store.connection.execute('UPDATE recordings SET import_hash=? WHERE id=?', (fingerprint, recording_id))
        store.finish_recording(recording_id, 'imported', ended_at=manifest.get('ended_at', last_captured_at))
    return {'recording_id': recording_id, 'already_imported': False, 'samples': sequence}
