import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

from iracing_storage import Store, RecordingWriter
from iracing_storage.api import create_server
from iracing_storage.viewer import Viewer, identity, library, trace


RAW = '''WeekendInfo:
  TrackID: 42
  TrackDisplayName: Test circuit
  TrackConfigName: Grand Prix
  TrackLength: 5.807 km
DriverInfo:
  DriverCarIdx: 3
  Drivers:
    - CarIdx: 1
      CarScreenName: Opponent
    - CarIdx: 3
      CarID: 7
      CarScreenName: Player car
CarSetup:
  Chassis:
    RideHeight: 55 mm
'''


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / 'viewer.sqlite3'
        self.store = Store(self.database)
        self.writer = RecordingWriter(self.store, profile={}, catalog=[], source_uri='test', batch_size=60)
        self.writer.start_stint(0, {}, RAW)
        self.viewer = Viewer()
        self.tick = 0

    def tearDown(self):
        self.writer.close()
        self.store.close()
        self.temp.cleanup()

    def point(self, lap, fraction, **values):
        self.tick += 1
        defaults = {'Lap': lap, 'LapDistPct': fraction, 'LapCurrentLapTime': fraction * 10,
                    'LapCompleted': lap - 1, 'LapLastLapTime': 10.0 if lap > 1 else 0,
                    'SessionNum': 0, 'SessionTime': self.tick * .1, 'Speed': 50.0,
                    'Throttle': .8, 'Brake': 0.0, 'Gear': 4, 'IsOnTrack': True,
                    'OnPitRoad': False, 'IsInGarage': False, 'PlayerCarMyIncidentCount': 0}
        defaults.update(values)
        self.writer.write_sample(self.tick, time.time(), defaults)

    def lap(self, number, start=0, **values):
        for index in range(start, 100):
            self.point(number, index / 100, **values)

    def overview(self):
        with Store(self.database, readonly=True) as reader:
            return self.viewer.overview(reader, self.writer.recording_id)

    def test_identity_uses_player_not_first_driver_and_unknowns_are_explicit(self):
        result = library(self.store)['items'][0]
        self.assertEqual(result['track']['name'], 'Test circuit')
        self.assertEqual(result['track']['length_km'], 5.807)
        self.assertEqual(result['car']['name'], 'Player car')
        unknown = identity(None)
        self.assertIsNone(unknown['track']['length_km'])
        self.assertIn('not yet identified', unknown['car']['name'])

    def test_live_incremental_lap_completion_and_no_duplicate_processing(self):
        self.lap(1)
        self.writer.flush()
        first = self.overview()
        self.assertEqual(first['eligible_count'], 0)
        self.assertEqual(first['laps'][0]['status'], 'In progress')
        self.point(2, 0)
        self.writer.flush()
        second = self.overview()
        self.assertEqual(second['eligible_count'], 1)
        self.assertEqual(second['best']['seconds'], 10)
        self.assertEqual(second['processed_count'], 101)
        self.assertEqual(second['live_state'], 'Receiving telemetry')
        again = self.overview()
        self.assertEqual(again['laps'], second['laps'])
        self.assertEqual(again['latest']['speed'], 50)
        self.writer.close('interrupted')
        final = self.overview()
        self.assertEqual(final['live_state'], 'Interrupted')
        self.assertEqual(final['laps'][-1]['status'], 'Unfinished')

    def test_delayed_last_lap_timing_waits_for_completed_counter(self):
        self.lap(1)
        self.point(2, 0, LapCompleted=0, LapLastLapTime=99)
        self.writer.flush()
        self.assertEqual(self.overview()['eligible_count'], 0)
        self.point(2, .01, LapCompleted=1, LapLastLapTime=10)
        self.writer.flush()
        self.assertEqual(self.overview()['best']['seconds'], 10)

    def test_partial_lap_pit_gap_incident_and_reset_do_not_become_best(self):
        self.lap(1, start=40)
        self.lap(2, OnPitRoad=True)
        self.lap(3, start=0)
        # A dropped SDK tick disqualifies an otherwise fully observed lap.
        self.tick += 3
        self.point(3, .995)
        self.lap(4, PlayerCarMyIncidentCount=1)
        self.point(5, 0, PlayerCarMyIncidentCount=2)
        self.writer.flush()
        result = self.overview()
        self.assertEqual(result['eligible_count'], 0)
        self.assertEqual([lap['status'] for lap in result['laps'][:4]], ['Partial', 'Pit / garage', 'Incident', 'Incident'])
        self.point(1, .1, SessionTime=0)
        self.writer.flush()
        result = self.overview()
        self.assertEqual(len({lap['id'] for lap in result['laps']}), len(result['laps']))
        self.assertEqual(result['laps'][-1]['number'], 1)
        self.assertFalse(result['laps'][-1]['start_observed'])

    def test_missing_incidents_and_sensor_markers_remain_unknown(self):
        missing = {'_unavailable': True}
        self.lap(1, PlayerCarMyIncidentCount=missing, Speed=missing)
        self.point(2, 0, PlayerCarMyIncidentCount=missing, Speed=missing)
        self.writer.flush()
        result = self.overview()
        self.assertIn('unavailable', result['laps'][0]['validity'])
        self.assertIsNone(result['latest']['speed'])
        points = trace(self.store, self.writer.recording_id, 0, 99)['items']
        self.assertTrue(all(point['speed'] is None for point in points))
        self.assertTrue(any(point['throttle'] == .8 for point in points))

    def test_trace_is_bounded_and_retains_spikes_and_missing_segments(self):
        for index in range(1000):
            self.point(1, index/1000, Speed=10 if index == 157 else 50,
                       Brake=.95 if index == 548 else 0,
                       Throttle={'_unavailable': True} if index == 701 else .8)
        self.writer.flush()
        result = trace(self.store, self.writer.recording_id, 0, 999, limit=100)
        self.assertLessEqual(len(result['items']), 100)
        self.assertEqual(result['source_samples'], 1000)
        self.assertTrue(result['downsampled'])
        self.assertEqual(min(point['speed'] for point in result['items']), 10)
        self.assertEqual(max(point['brake'] for point in result['items']), .95)
        self.assertTrue(any(point['throttle'] is None for point in result['items']))
        self.assertEqual(result['items'][-1]['sequence'], 999)

    def test_http_reader_sees_newly_committed_capture_and_setup(self):
        server = create_server(self.database, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/api/v1'

        def get(path):
            with urlopen(base + path, timeout=5) as response:
                return json.load(response)

        try:
            recording_id = get('/library')['items'][0]['id']
            path = '/recordings/' + recording_id
            self.point(1, 0)
            self.assertEqual(get(path + '/overview')['processed_count'], 0)
            self.writer.flush()
            self.assertEqual(get(path + '/overview')['processed_count'], 1)
            self.writer.session_update(2, RAW.replace('55 mm', '54 mm'))
            self.point(1, .01)
            self.writer.flush()
            result = get(path + '/overview')
            self.assertEqual(result['processed_count'], 2)
            snapshots = get(path + '/snapshots')['items']
            self.assertEqual(snapshots[-1]['id'], result['latest_snapshot_id'])
            self.assertEqual(snapshots[-1]['setup']['Chassis']['RideHeight'], '54 mm')
            self.assertEqual(get(path + '/trace?start=0&end=1')['source_samples'], 2)
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
