import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from iracing_local import StintWriter, capture
from iracing_storage import RecordingWriter, Store
from iracing_storage.api import create_server
from iracing_storage.database import default_database, encode, sample_row
from iracing_storage.importer import import_capture


RAW_A = 'WeekendInfo:\n  TrackName: Suzuka\nCarSetup:\n  Chassis:\n    RideHeight: 55 mm\n'
RAW_B = 'WeekendInfo:\n  TrackName: Suzuka\nCarSetup:\n  Tires:\n    Pressures: [140, 142]\n  Aero:\n    Wing: 4\n'
CATALOG = [{'name': 'Speed', 'unit': 'm/s', 'type': 'float', 'count': 1}]
PROFILE = {'profile_id': 'test', 'version': '1', 'selected_fields': ['Speed']}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / 'storage.sqlite3'
        self.store = Store(self.db)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def writer(self, **kwargs):
        writer = RecordingWriter(self.store, profile=PROFILE, catalog=CATALOG, source_uri='test', **kwargs)
        writer.start_stint(0, {'started_at': 100.0}, RAW_A)
        return writer

    def fixture(self, *, legacy=False):
        root = self.root / ('legacy' if legacy else 'capture')
        (root / 'catalog').mkdir(parents=True)
        (root / 'catalog' / 'live_variables.json').write_text(encode(CATALOG), encoding='utf-8')
        (root / 'profile.json').write_text(encode(PROFILE), encoding='utf-8')
        writer = StintWriter(root / 'stints', 0, {'Chassis': {'RideHeight': '55 mm'}}, RAW_A,
                             {'started_at': 100.0, 'profile_id': 'test'})
        writer.write_telemetry(100, {'Speed': 10, 'Lap': 1, 'SessionNum': 0})
        writer.write_session_update(2, RAW_B)
        writer.write_telemetry(1, {'Speed': 20, 'Lap': 1, 'SessionNum': 1, 'NewChannel': [1, True, None]})
        writer.close()
        if legacy:
            (writer.directory / 'initial_session_info.yaml').unlink()
            (writer.directory / 'session_info_updates.jsonl').write_text(
                encode({'update': 2, 'raw_yaml': RAW_B}) + '\n', encoding='utf-8')
        return root

    def test_migrations_preserve_data_and_reject_newer_or_unrelated_databases(self):
        with self.store.connection:
            document_id = self.store.add_document('future', {'anything': [1, 2]})
        with Store(self.db) as reopened:
            self.assertEqual(reopened.documents()[0]['id'], document_id)
        self.store.connection.execute('PRAGMA user_version=999')
        with self.assertRaisesRegex(ValueError, 'newer'):
            Store(self.db)
        unrelated = self.root / 'unrelated.sqlite3'
        with sqlite3.connect(unrelated) as connection:
            connection.execute('CREATE TABLE original (id INTEGER)')
        connection.close()
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            Store(unrelated)

    def test_flexible_fields_nonfinite_arrays_and_unavailable_are_preserved(self):
        writer = self.writer(batch_size=1)
        values = {'Speed': 0, 'Future field.with[brackets]': [True, None, 3],
                  'Missing': {'_unavailable': True, 'reason': 'read_error'},
                  'Lap': {'_unavailable': True}, 'Bad': [math.nan, math.inf, -math.inf]}
        writer.write_sample(10, 100.5, values)
        writer.close()
        item = self.store.samples(writer.recording_id)['items'][0]
        self.assertEqual(item['values']['Speed'], 0)
        self.assertEqual(item['values']['Future field.with[brackets]'], [True, None, 3])
        self.assertTrue(item['values']['Missing']['_unavailable'])
        self.assertIsNone(item['lap'])
        self.assertEqual(item['values']['Bad'][0], {'_nonfinite': 'nan'})
        unknown = self.store.samples(writer.recording_id, channels=['NotCaptured'])['items'][0]
        self.assertEqual(unknown['values']['NotCaptured']['reason'], 'not_recorded')
        self.assertEqual(self.store.connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_batches_are_visible_to_reader_and_close_flushes(self):
        writer = self.writer(batch_size=3)
        with Store(self.db, readonly=True) as reader:
            writer.write_sample(1, 100.0, {'Speed': 1})
            self.assertEqual(reader.recording(writer.recording_id)['sample_count'], 0)
            writer.write_sample(2, 100.1, {'Speed': 2})
            writer.write_sample(3, 100.2, {'Speed': 3})
            self.assertEqual(reader.recording(writer.recording_id)['sample_count'], 3)
            writer.write_sample(4, 100.3, {'Speed': 4})
            writer.close('interrupted')
            self.assertEqual(reader.recording(writer.recording_id)['sample_count'], 4)
            self.assertEqual(reader.recording(writer.recording_id)['status'], 'interrupted')
            with self.assertRaises(sqlite3.OperationalError):
                reader.connection.execute('DELETE FROM samples')

    def test_idle_flush_and_unclosed_recording_status(self):
        writer = self.writer()
        writer.write_sample(1, 100.0, {'Speed': 3})
        writer.last_flush -= 2
        writer.flush_if_due()
        with Store(self.db, readonly=True) as reader:
            self.assertEqual(reader.recording(writer.recording_id)['sample_count'], 1)
            self.assertEqual(reader.recording(writer.recording_id)['status'], 'recording')
        writer.close()

    def test_setup_changes_are_linked_to_correct_samples_without_fixed_car_schema(self):
        writer = self.writer()
        writer.write_sample(100, 100.0, {'Lap': 1})
        writer.session_update(2, RAW_B)
        writer.write_sample(1, 101.0, {'Lap': 1})
        writer.close()
        samples = self.store.samples(writer.recording_id)['items']
        self.assertNotEqual(samples[0]['snapshot_id'], samples[1]['snapshot_id'])
        snapshots = self.store.snapshots(writer.recording_id)
        self.assertEqual(snapshots[0]['setup']['Chassis']['RideHeight'], '55 mm')
        self.assertEqual(snapshots[1]['setup']['Tires']['Pressures'], [140, 142])
        self.assertEqual(snapshots[0]['raw_session_yaml'], RAW_A)
        flattened = self.store.connection.execute('SELECT path,value FROM setup_fields WHERE snapshot_id=?',
                                                  (snapshots[1]['id'],)).fetchall()
        self.assertIn(('$.Tires.Pressures[0]', 140), [tuple(row) for row in flattened])

    def test_process_crash_keeps_committed_batches_without_claiming_completion(self):
        database = self.root / 'crashed.sqlite3'
        script = '''
import os, sys
from iracing_storage import Store, RecordingWriter
store = Store(sys.argv[1])
writer = RecordingWriter(store, profile={}, catalog=[], source_uri='crash-test', batch_size=2)
writer.start_stint(0, {}, 'CarSetup: {}')
writer.write_sample(1, 100, {'Speed': 1})
writer.write_sample(2, 101, {'Speed': 2})
writer.write_sample(3, 102, {'Speed': 3})
os._exit(9)
'''
        process = subprocess.run([sys.executable, '-c', script, str(database)], capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 9, process.stderr.decode())
        with Store(database, readonly=True) as reopened:
            recording = reopened.list_recordings()[0]
            self.assertEqual(recording['sample_count'], 2)
            self.assertEqual(recording['status'], 'recording')
            self.assertEqual(len(reopened.samples(recording['id'])['items']), 2)
            self.assertEqual(reopened.connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_recording_closed_rejects_further_mutation(self):
        writer = self.writer()
        writer.close()
        with self.assertRaises(ValueError):
            writer.write_sample(1, 100, {})
        with self.assertRaises(ValueError):
            writer.start_stint(1, {}, RAW_A)
        with self.assertRaises(ValueError):
            writer.session_update(2, RAW_B)

    def test_default_database_is_stable_across_packaged_hosts_and_can_be_overridden(self):
        with patch.dict(os.environ, {'IRACING_DATABASE': '', 'LOCALAPPDATA': str(self.root / 'app-cache')}):
            self.assertEqual(default_database(), Path.home() / '.iracing-app/storage/iracing.sqlite3')
        with patch.dict(os.environ, {'IRACING_DATABASE': str(self.db)}):
            self.assertEqual(default_database(), self.db)

    def test_web_extractor_stores_response_without_real_network_call(self):
        from iracing_client import main
        payload = {'new_domain': {'per_car': [1, 2, 3]}}
        output = self.root / 'api.json'
        with patch.dict(os.environ, {'IRACING_EMAIL': 'test@example.invalid', 'IRACING_PASSWORD': 'test'}), \
             patch('iracing_client.load_dotenv'), patch('iracing_client.IRacingClient') as client, \
             patch.object(sys, 'argv', ['iracing_client.py', '--database', str(self.db), '--output', str(output)]):
            client.return_value.get_data.return_value = payload
            main()
        self.assertEqual(json.loads(output.read_text()), payload)
        self.assertEqual(self.store.documents(kind='iracing_api:/member/info')[0]['payload'], payload)

    def test_capture_interruption_and_error_flush_and_finalize(self):
        profile = self.root / 'profile.json'
        profile.write_text(encode(PROFILE), encoding='utf-8')
        for failure, status in [(KeyboardInterrupt(), 'interrupted'), (RuntimeError('SDK failure'), 'failed')]:
            with self.subTest(status=status):
                sdk = SimpleNamespace(is_initialized=True, is_connected=True, session_info_update=1,
                                      _header=SimpleNamespace(tick_rate=60), _var_buffer_latest=SimpleNamespace(tick_count=1),
                                      startup=Mock(), shutdown=Mock(), freeze_var_buffer_latest=Mock(side_effect=[None, failure]))
                with patch('iracing_local.irsdk.IRSDK', return_value=sdk), \
                     patch('iracing_local.header_catalog', return_value=CATALOG), \
                     patch('iracing_local.raw_session_info', return_value=RAW_A), \
                     patch('iracing_local.read_selected_variables', return_value=({'IsOnTrack': True, 'IsOnTrackCar': True}, [])):
                    if status == 'failed':
                        with self.assertRaisesRegex(RuntimeError, 'SDK failure'):
                            capture(self.root / status, profile, database=self.db)
                    else:
                        capture(self.root / status, profile, database=self.db)
                recording = self.store.list_recordings()[0]
                self.assertEqual(recording['status'], status)
                self.assertEqual(recording['sample_count'], 1)
                sdk.shutdown.assert_called_once()

    def test_bad_yaml_is_preserved_with_parse_error(self):
        writer = self.writer()
        writer.session_update(2, 'CarSetup: [broken')
        writer.write_sample(1, 100, {'Speed': 1})
        writer.close()
        snapshot = self.store.snapshots(writer.recording_id)[-1]
        self.assertEqual(snapshot['raw_session_yaml'], 'CarSetup: [broken')
        self.assertIsNotNone(snapshot['parse_error'])

    def test_pagination_filters_and_tick_resets(self):
        writer = self.writer()
        for tick in range(5):
            writer.write_sample(tick, 100 + tick, {'SessionNum': 0, 'Lap': 1, 'Speed': tick, 'SessionTime': tick})
        writer.start_stint(1, {}, RAW_B)
        writer.write_sample(0, 106, {'SessionNum': 1, 'Lap': 1, 'SessionTime': 0})
        writer.close()
        first = self.store.samples(writer.recording_id, limit=2)
        second = self.store.samples(writer.recording_id, after=first['next_after'], limit=2)
        self.assertTrue(first['has_more'])
        self.assertEqual([item['sequence'] for item in second['items']], [2, 3])
        filtered = self.store.samples(writer.recording_id, session_num=0, lap=1, time_min=2, time_max=3)
        self.assertEqual([item['sequence'] for item in filtered['items']], [2, 3])
        self.assertEqual(len(self.store.samples(writer.recording_id, stint_id=writer.stint_id)['items']), 1)
        with self.assertRaises(ValueError):
            self.store.samples(writer.recording_id, limit=5001)

    def test_foreign_keys_reject_cross_recording_snapshot_links(self):
        first, second = self.writer(), self.writer()
        with self.assertRaises(sqlite3.IntegrityError), self.store.connection:
            self.store.add_samples(first.recording_id, [sample_row(first.recording_id, 0, first.stint_id,
                                                                   second.snapshot_id, 1, 100.0, {})])
        self.assertEqual(self.store.recording(first.recording_id)['sample_count'], 0)
        first.close()
        second.close()

    def test_import_is_idempotent_and_roundtrips_update_boundaries(self):
        root = self.fixture()
        result = import_capture(self.store, root)
        duplicate = import_capture(self.store, root)
        self.assertEqual(result['recording_id'], duplicate['recording_id'])
        self.assertTrue(duplicate['already_imported'])
        samples = self.store.samples(result['recording_id'])['items']
        snapshots = {item['id']: item for item in self.store.snapshots(result['recording_id'])}
        self.assertEqual(snapshots[samples[0]['snapshot_id']]['setup']['Chassis']['RideHeight'], '55 mm')
        self.assertEqual(snapshots[samples[1]['snapshot_id']]['setup']['Aero']['Wing'], 4)
        self.assertEqual(samples[1]['values']['NewChannel'], [1, True, None])

    def test_legacy_import_does_not_invent_setup_update_timing(self):
        result = import_capture(self.store, self.fixture(legacy=True))
        samples = self.store.samples(result['recording_id'])['items']
        self.assertEqual(samples[0]['snapshot_id'], samples[1]['snapshot_id'])
        self.assertEqual(self.store.snapshots(result['recording_id'])[-1]['provenance'], 'legacy_update_timing_unknown')

    def test_invalid_import_rolls_back_everything_and_active_capture_is_rejected(self):
        root = self.fixture()
        telemetry = root / 'stints' / 'stint-0000' / 'telemetry.jsonl'
        with telemetry.open('a', encoding='utf-8') as stream:
            # Force at least one importer batch before the malformed tail.
            for i in range(600):
                stream.write(encode({'tick': i, 'captured_at': 101.0, 'values': {}}) + '\n')
            stream.write('{broken')
        with self.assertRaises(ValueError):
            import_capture(self.store, root)
        self.assertEqual(self.store.list_recordings(), [])
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM samples').fetchone()[0], 0)
        (root / 'capture.json').write_text('{"status":"recording"}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'closed'):
            import_capture(self.store, root)

    def test_source_changes_during_import_roll_back(self):
        root = self.fixture()
        with patch('iracing_storage.importer.capture_hash', side_effect=['before', 'after']):
            with self.assertRaisesRegex(ValueError, 'changed'):
                import_capture(self.store, root)
        self.assertEqual(self.store.list_recordings(), [])

    def test_documents_backup_and_reopen(self):
        writer = self.writer()
        writer.write_sample(1, 100, {'Speed': 2})
        writer.close()
        with self.store.connection:
            self.store.add_document('future:weather', {'nested': {'version2': [1, 2]}}, recording_id=writer.recording_id,
                                    schema_version=2)
        destination = self.root / 'backup.sqlite3'
        self.store.backup(destination)
        with Store(destination, readonly=True) as backup:
            self.assertEqual(backup.recording(writer.recording_id)['sample_count'], 1)
            self.assertEqual(backup.documents(kind='future:weather')[0]['payload']['nested']['version2'], [1, 2])
        with self.assertRaises(FileExistsError):
            self.store.backup(destination)

    def test_live_stint_writer_files_and_database_agree(self):
        recorder = RecordingWriter(self.store, profile=PROFILE, catalog=CATALOG, source_uri='test')
        writer = StintWriter(self.root / 'stints', 0, {}, RAW_A, {'started_at': 100}, storage=recorder)
        writer.write_telemetry(1, {'Speed': 12})
        writer.write_session_update(2, RAW_B)
        writer.write_telemetry(2, {'Speed': 15})
        writer.close()
        recorder.close()
        files = [json.loads(line) for line in (writer.directory / 'telemetry.jsonl').read_text().splitlines()]
        samples = self.store.samples(recorder.recording_id)['items']
        self.assertEqual([item['captured_at'] for item in files], [item['captured_at'] for item in samples])
        self.assertEqual([item['values'] for item in files], [item['values'] for item in samples])

    def test_api_reads_paginates_and_rejects_bad_input_and_writes(self):
        writer = self.writer()
        writer.write_sample(1, 100, {'Speed': 12})
        writer.write_sample(2, 101, {'Speed': 13})
        writer.close()
        server = create_server(self.db, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for path, content_type in [('/', 'text/html'), ('/app.js', 'text/javascript'),
                                       ('/data.js', 'text/javascript'), ('/styles.css', 'text/css'),
                                       ('/favicon.svg', 'image/svg+xml')]:
                with urlopen(base + path, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(content_type, response.headers['Content-Type'])
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            for path in ['/.env', '/iracing_storage/database.py', '/frontend/package.json', '/%2e%2e/.env']:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path, timeout=3)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            with urlopen(base + '/api/v1/recordings', timeout=3) as response:
                self.assertEqual(json.load(response)['items'][0]['id'], writer.recording_id)
            path = f'/api/v1/recordings/{writer.recording_id}/samples'
            with urlopen(base + path + '?channels=Speed&limit=1', timeout=3) as response:
                body = json.load(response)
                self.assertTrue(body['has_more'])
                self.assertEqual(body['items'][0]['values'], {'Speed': 12})
            for suffix, status in [('?limit=0', 400), ('?lap=bad', 400), ('?time_min=nan', 400), ('?unknown=1', 400)]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path + suffix, timeout=3)
                self.assertEqual(error.exception.code, status)
                error.exception.close()
            for request, status in [(Request(base + path, method='POST'), 501),
                                    (Request(base + path, headers={'Origin': 'https://example.com'}), 403),
                                    (Request(base + path, headers={'Host': 'example.com'}), 403),
                                    (Request(base + '/api/v1/recordings/missing'), 404)]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=3)
                self.assertEqual(error.exception.code, status)
                error.exception.close()
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()

    def test_capture_loop_disconnect_commits_final_batch(self):
        class Header:
            tick_rate = 60

        class Buffer:
            tick_count = 0

        class SDK:
            _header, _var_buffer_latest = Header(), Buffer()
            is_initialized = is_connected = True
            session_info_update = 1
            stopped = False

            def startup(self):
                pass

            def freeze_var_buffer_latest(self):
                self._var_buffer_latest.tick_count += 1
                if self._var_buffer_latest.tick_count == 2:
                    self.is_connected = False

            def shutdown(self):
                self.stopped = True

        sdk = SDK()
        profile = self.root / 'profile.json'
        profile.write_text(encode(PROFILE), encoding='utf-8')
        values = {'IsOnTrack': True, 'IsOnTrackCar': True, 'Speed': 13}
        with patch('iracing_local.irsdk.IRSDK', return_value=sdk), \
             patch('iracing_local.header_catalog', return_value=CATALOG), \
             patch('iracing_local.raw_session_info', return_value=RAW_A), \
             patch('iracing_local.read_selected_variables', return_value=(values, [])):
            capture(self.root / 'captures', profile, database=self.db)
        recording = self.store.list_recordings()[0]
        self.assertEqual(recording['status'], 'completed')
        self.assertEqual(recording['sample_count'], 2)
        self.assertTrue(sdk.stopped)
        capture_dir = next((self.root / 'captures').iterdir())
        self.assertEqual(json.loads((capture_dir / 'capture.json').read_text())['status'], 'completed')
        with Store(self.root / 'restored.sqlite3') as restored:
            result = import_capture(restored, capture_dir)
            self.assertEqual(result['recording_id'], recording['id'])
            self.assertEqual(restored.recording(recording['id'])['sample_count'], 2)


if __name__ == '__main__':
    unittest.main()
