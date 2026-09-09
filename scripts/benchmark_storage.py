"""Synthetic storage-only throughput check; creates no production recordings."""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iracing_storage import RecordingWriter, Store


def main():
    profile = json.loads((Path(__file__).resolve().parents[1] / 'practice_profile.json').read_text())
    catalog = [{'name': name, 'type': 'float', 'count': 6 if '[6]' in name else 1}
               for name in profile['selected_fields']]
    values = {item['name']: [1.25] * 6 if item['count'] == 6 else 1.25 for item in catalog}
    samples = 3600
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / 'benchmark.sqlite3'
        with Store(database) as store:
            writer = RecordingWriter(store, profile=profile, catalog=catalog, source_uri='synthetic-benchmark')
            writer.start_stint(0, {'started_at': 0}, 'CarSetup:\n  Aero:\n    Wing: 4\n')
            start = time.perf_counter()
            for tick in range(samples):
                values.update(SessionNum=0, SessionTime=tick / 60, Lap=1, LapDistPct=tick / samples)
                writer.write_sample(tick, tick / 60, values)
            writer.close()
            elapsed = time.perf_counter() - start
            query_start = time.perf_counter()
            page = store.samples(writer.recording_id, channels=['Speed', 'Brake', 'Throttle'], limit=1000)
            query_ms = (time.perf_counter() - query_start) * 1000
            assert store.recording(writer.recording_id)['sample_count'] == samples
            assert len(page['items']) == 1000
            assert store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        size = database.stat().st_size
        print(json.dumps({'samples': samples, 'channels': len(catalog), 'elapsed_seconds': round(elapsed, 3),
                          'samples_per_second': round(samples / elapsed), 'query_1000_samples_ms': round(query_ms, 2),
                          'database_mb': round(size / 1_000_000, 2),
                          'estimated_database_gb_per_hour_at_60hz': round(size * 60 / 1_000_000_000, 2)}, indent=2))


if __name__ == '__main__':
    main()
