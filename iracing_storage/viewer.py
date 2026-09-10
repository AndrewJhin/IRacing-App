"""Incremental, read-only projections for the session viewer. No synthetic values."""

from __future__ import annotations

import copy
import json
import math
import re
import threading
import time
from collections import OrderedDict


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def object_value(value):
    return value if isinstance(value, dict) else {}


def text(value, fallback):
    return str(value) if isinstance(value, (str, int)) and str(value).strip() else fallback


def identity(info):
    info = object_value(info)
    weekend = object_value(info.get('WeekendInfo'))
    driver_info = object_value(info.get('DriverInfo'))
    drivers = driver_info.get('Drivers', [])
    driver = next((item for item in drivers if isinstance(item, dict)
                   and item.get('CarIdx') == driver_info.get('DriverCarIdx')), {}) if isinstance(drivers, list) else {}
    track_name = text(weekend.get('TrackDisplayName') or weekend.get('TrackName'), 'Track not yet identified')
    car_name = text(driver.get('CarScreenName') or driver.get('CarPath'), 'Car not yet identified')
    length = weekend.get('TrackLength')
    match = re.fullmatch(r'\s*([\d.]+)\s*(km|m|mi)\s*', length or '') if isinstance(length, str) else None
    length_km = None
    if match:
        try:
            length_km = float(match[1]) * {'km': 1, 'm': .001, 'mi': 1.609344}[match[2]]
        except ValueError:
            pass
    return {
        'track': {'id': text(weekend.get('TrackID'), track_name) + ':' + text(weekend.get('TrackConfigName'), ''),
                  'name': track_name, 'layout': text(weekend.get('TrackConfigName'), ''),
                  'country': text(weekend.get('TrackCountry'), ''), 'length_km': length_km},
        'car': {'id': text(driver.get('CarID') or driver.get('CarPath'), car_name), 'name': car_name},
    }


def library(store, limit=100, offset=0, started_from=None, started_until=None):
    rows = store.list_recordings(limit=limit, offset=offset, started_from=started_from, started_until=started_until)
    items = []
    for row in rows:
        snapshot = store.connection.execute(
            'SELECT session_json FROM snapshots WHERE recording_id=? ORDER BY id DESC LIMIT 1', (row['id'],)).fetchone()
        items.append({key: row[key] for key in ('id', 'started_at', 'ended_at', 'status', 'sample_count', 'source_kind')} |
                     identity(json.loads(snapshot[0]) if snapshot else None))
    return {'items': items, 'has_more': len(items) == limit, 'next_offset': offset + len(items)}


def is_gap(previous, sample):
    if not previous:
        return False
    a, b = number(previous['session_time']), number(sample['session_time'])
    return (sample['sequence'] != previous['sequence'] + 1 or
            sample['tick'] <= previous['tick'] or sample['tick'] > previous['tick'] + 1 or
            (a is not None and b is not None and (b < a or b - a > .25)))


def sector_layout(info):
    """Use only track-provided SDK boundaries; never assume three sectors."""
    sectors = object_value(object_value(info).get('SplitTimeInfo')).get('Sectors')
    if not isinstance(sectors, list) or not sectors:
        return []
    if any(not isinstance(s, dict) or number(s.get('SectorStartPct')) is None for s in sectors):
        return []
    starts = sorted(s['SectorStartPct'] for s in sectors)
    if starts[0] != 0 or starts[-1] >= 1 or len(set(starts)) != len(starts):
        return []
    return [{'number': i+1, 'start': start, 'end': (starts+[1.0])[i+1]}
            for i, start in enumerate(starts)]


class Accumulator:
    """Only lap aggregates and one previous row stay in memory, not raw telemetry."""
    def __init__(self, sectors=None):
        self.sequence = -1
        self.sectors = sectors or []
        self.previous = None
        self.laps = []
        self.latest = None
        self.first_time = None

    def consume(self, sample):
        values = sample['values']
        previous = self.previous
        old = self.laps[-1] if self.laps else None
        clock_reset = previous and number(sample['session_time']) is not None and number(previous['session_time']) is not None and sample['session_time'] < previous['session_time']
        new_group = (old is None or sample['stint_id'] != old['stint_id'] or sample['session_num'] != old['session_num']
                     or sample['lap'] != old['number'] or clock_reset)
        crossing = bool(previous and previous['stint_id'] == sample['stint_id']
                        and previous['session_num'] == sample['session_num']
                        and number(previous['lap']) is not None and sample['lap'] == previous['lap'] + 1
                        and number(previous['lap_distance']) is not None and previous['lap_distance'] > .9
                        and number(sample['lap_distance']) is not None and 0 <= sample['lap_distance'] < .1
                        and not is_gap(previous, sample))
        if new_group:
            if old:
                old['closed'] = True
                last_time = number(values.get('LapLastLapTime'))
                completed = number(values.get('LapCompleted'))
                old['seconds'] = last_time if crossing and completed == old['number'] and last_time is not None and last_time > 0 else None
                old['finish_observed'] = crossing
                old['complete'] = bool(crossing and old['start_observed'] and old['seconds'] is not None)
                # The boundary sample may be the first report of an incident at the finish.
                incident = number(values.get('PlayerCarMyIncidentCount'))
                if incident is not None and old['incident_end'] is not None and incident > old['incident_end']:
                    old['incident'] = True
            distance, elapsed = number(sample['lap_distance']), number(values.get('LapCurrentLapTime'))
            start_observed = crossing or bool(old is None and distance is not None and 0 <= distance <= .01
                                               and elapsed is not None and 0 <= elapsed <= 1)
            old = {'id': str(sample['sequence']), 'number': sample['lap'], 'stint_id': sample['stint_id'],
                   'session_num': sample['session_num'], 'start_sequence': sample['sequence'],
                   'end_sequence': sample['sequence'], 'snapshot_id': sample['snapshot_id'], 'samples': 0,
                   'start_observed': start_observed, 'complete': False, 'closed': False, 'seconds': None,
                   'finish_observed': False,
                   'gap': False, 'pit': False, 'incident': False, 'incident_known': True,
                   'incident_end': None, 'elapsed': None, 'sector_crossings': {}}
            self.laps.append(old)
        elif is_gap(previous, sample):
            old['gap'] = True
        if not new_group and previous and number(previous['lap_distance']) is not None and number(sample['lap_distance']) is not None:
            old['gap'] |= sample['lap_distance'] < previous['lap_distance'] - .02
        old['end_sequence'] = sample['sequence']
        if previous and not new_group and not is_gap(previous, sample):
            x0, x1 = number(previous['lap_distance']), number(sample['lap_distance'])
            t0 = number(previous['values'].get('LapCurrentLapTime'))
            t1 = number(values.get('LapCurrentLapTime'))
            if all(v is not None for v in (x0, x1, t0, t1)) and 0 <= x0 < x1 <= 1 and 0 <= t0 < t1:
                for sector in self.sectors[1:]:
                    boundary = sector['start']
                    if x0 < boundary <= x1:
                        old['sector_crossings'][str(sector['number'])] = t0 + (t1-t0)*(boundary-x0)/(x1-x0)
        # Some SDK updates publish the last-lap timing after the crossing tick.
        if len(self.laps) >= 2:
            finished = self.laps[-2]
            last_time = number(values.get('LapLastLapTime'))
            if (finished['seconds'] is None and finished['finish_observed']
                    and finished['stint_id'] == sample['stint_id'] and finished['session_num'] == sample['session_num']
                    and number(values.get('LapCompleted')) == finished['number']
                    and last_time is not None and last_time > 0):
                finished['seconds'] = last_time
                finished['complete'] = finished['start_observed']
        old['samples'] += 1
        old['elapsed'] = number(values.get('LapCurrentLapTime'))
        old['pit'] |= values.get('OnPitRoad') is True or values.get('IsInGarage') is True or values.get('IsOnTrack') is False
        incident = number(values.get('PlayerCarMyIncidentCount'))
        old['incident_known'] &= incident is not None
        if incident is not None and old['incident_end'] is not None:
            old['incident'] |= incident > old['incident_end']
            old['gap'] |= incident < old['incident_end']
        old['incident_end'] = incident
        self.sequence = sample['sequence']
        self.previous = sample
        self.latest = {'sequence': sample['sequence'], 'captured_at': sample['captured_at'],
                       'snapshot_id': sample['snapshot_id'], 'lap_id': old['id'],
                       'speed': number(values.get('Speed')), 'throttle': number(values.get('Throttle')),
                       'brake': number(values.get('Brake')), 'gear': number(values.get('Gear')),
                       'rpm': number(values.get('RPM')), 'fuel': number(values.get('FuelLevel')),
                       'air_temp': number(values.get('AirTemp')), 'track_temp': number(values.get('TrackTempCrew')) if number(values.get('TrackTempCrew')) is not None else number(values.get('TrackTemp')),
                       'wind': number(values.get('WindVel')), 'lap_distance': sample['lap_distance']}
        if self.first_time is None:
            self.first_time = sample['captured_at']

    def result(self, recording):
        laps = copy.deepcopy(self.laps)
        for lap in laps:
            lap['eligible'] = bool(lap['complete'] and lap['incident_known'] and not lap['gap'] and not lap['pit'] and not lap['incident'])
            boundaries = [0.0] + [lap['sector_crossings'].get(str(s['number'])) for s in self.sectors[1:]] + [lap['seconds']]
            lap['sector_seconds'] = [b-a if lap['eligible'] and a is not None and b is not None and b > a else None
                                     for a, b in zip(boundaries, boundaries[1:])] if self.sectors else []
            lap.pop('sector_crossings', None)
            lap['status'] = ('Pit / garage' if lap['pit'] else 'Incident' if lap['incident'] else 'Data gap' if lap['gap']
                             else 'Complete' if lap['complete'] else 'Partial' if lap['closed']
                             else 'In progress' if recording['status'] == 'recording' else 'Unfinished')
            lap['validity'] = ('Incident observed' if lap['incident'] else
                               'No incident observed' if lap['incident_known'] else 'Incident data unavailable')
        eligible = [lap for lap in laps if lap['eligible']]
        best = min(eligible, key=lambda lap: lap['seconds']) if eligible else None
        average = sum(lap['seconds'] for lap in eligible) / len(eligible) if eligible else None
        deviation = math.sqrt(sum((lap['seconds'] - average) ** 2 for lap in eligible) / len(eligible)) if eligible else None
        latest = self.latest
        age = max(0, time.time() - latest['captured_at']) if latest else None
        live_state = ('Receiving telemetry' if age is not None and age < 5 else 'Waiting for telemetry') if recording['status'] == 'recording' else recording['status'].capitalize()
        sector_stats = []
        for i, sector in enumerate(self.sectors):
            times = [lap['sector_seconds'][i] for lap in eligible if lap['sector_seconds'][i] is not None]
            sector_stats.append(sector | {'best': min(times) if times else None,
                                         'average': sum(times)/len(times) if times else None, 'count': len(times)})
        return {'laps': laps, 'best': best, 'average': average, 'deviation': deviation, 'sectors': sector_stats,
                'eligible_count': len(eligible), 'processed_count': self.sequence + 1,
                'caught_up': self.sequence + 1 >= recording['sample_count'],
                'latest': latest, 'live_state': live_state, 'sample_age_seconds': age,
                'observed_duration': latest['captured_at'] - self.first_time if latest else 0}


class Viewer:
    def __init__(self):
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def overview(self, store, recording_id):
        with self.lock:
            # A read transaction gives the row count and stream the same committed snapshot.
            with store.connection:
                store.connection.execute('BEGIN')
                recording = store.recording(recording_id)
                first_snapshot = store.connection.execute(
                    'SELECT session_json FROM snapshots WHERE recording_id=? ORDER BY id LIMIT 1', (recording_id,)).fetchone()
                accumulator = self.cache.get(recording_id)
                if accumulator is None or accumulator.sequence >= recording['sample_count']:
                    accumulator = Accumulator(sector_layout(json.loads(first_snapshot[0]) if first_snapshot else None))
                    self.cache[recording_id] = accumulator
                self.cache.move_to_end(recording_id)
                while len(self.cache) > 8:
                    self.cache.popitem(last=False)
                rows = store.connection.execute(
                    'SELECT * FROM samples WHERE recording_id=? AND sequence>? ORDER BY sequence LIMIT 25000',
                    (recording_id, accumulator.sequence))
                for row in rows:
                    sample = dict(row)
                    sample['values'] = json.loads(sample.pop('values_json'))
                    accumulator.consume(sample)
                snapshot = store.connection.execute(
                    'SELECT id,session_json FROM snapshots WHERE recording_id=? ORDER BY id DESC LIMIT 1', (recording_id,)).fetchone()
                result = accumulator.result(recording)
                setups = []
                for row in store.connection.execute(
                    'SELECT id,stint_id,captured_at,setup_json,parse_error,provenance FROM snapshots '
                    'WHERE id IN (SELECT min(id) FROM snapshots WHERE recording_id=? GROUP BY stint_id) ORDER BY id',
                    (recording_id,)):
                    setup = dict(row)
                    setup['setup'] = json.loads(setup.pop('setup_json'))
                    setups.append(setup)
                return result | {'recording': recording, **identity(json.loads(snapshot['session_json']) if snapshot else None),
                                 'stint_setups': setups,
                                 'latest_snapshot_id': snapshot['id'] if snapshot else None}


def trace(store, recording_id, start, end, limit=1200, start_pct=0.0, end_pct=1.0):
    if start < 0 or end < start or not 40 <= limit <= 5000:
        raise ValueError('Invalid trace range or limit')
    if not 0 <= start_pct < end_pct <= 1:
        raise ValueError('Invalid distance range')
    where = ' WHERE recording_id=? AND sequence>=? AND sequence<=?'
    params = [recording_id, start, end]
    if start_pct != 0 or end_pct != 1:
        where += ' AND lap_distance>=? AND lap_distance<=?'
        params += [start_pct, end_pct]
    count = store.connection.execute('SELECT count(*) FROM samples' + where, params).fetchone()[0]
    bucket_size = max(1, math.ceil(count / (limit // 6)))
    points, bucket, previous, bucket_gap = [], [], None, False

    def flush():
        if not bucket:
            return
        speed = [item for item in bucket if item['speed'] is not None]
        brake = [item for item in bucket if item['brake'] is not None]
        steering = [item for item in bucket if item['steering'] is not None]
        selected = [bucket[0], bucket[-1], min(speed, key=lambda p: p['speed']) if speed else bucket[0],
                    max(brake, key=lambda p: p['brake']) if brake else bucket[0],
                    min(steering, key=lambda p: p['steering']) if steering else bucket[0],
                    max(steering, key=lambda p: p['steering']) if steering else bucket[0]]
        selected = sorted({item['sequence']: item for item in selected}.values(), key=lambda p: p['sequence'])
        for item in selected:
            item['gap'] = bucket_gap
            for channel in ('speed', 'throttle', 'brake', 'steering', 'elapsed', 'gear'):
                if any(point[channel] is None for point in bucket):
                    item[channel] = None
            points.append(item)

    for row in store.connection.execute('SELECT * FROM samples' + where + ' ORDER BY sequence', params):
        sample = dict(row)
        values = json.loads(sample.pop('values_json'))
        sample['values'] = values
        point = {'sequence': sample['sequence'], 'x': number(sample['lap_distance']),
                 'elapsed': number(values.get('LapCurrentLapTime')), 'speed': number(values.get('Speed')),
                 'throttle': number(values.get('Throttle')), 'brake': number(values.get('Brake')),
                 'gear': number(values.get('Gear')), 'steering': number(values.get('SteeringWheelAngle')),
                 'session_time': number(sample['session_time'])}
        bucket_gap |= (is_gap(previous, sample) or point['x'] is None
                       or bool(previous and (previous['lap'] != sample['lap'] or previous['stint_id'] != sample['stint_id']
                                              or previous['session_num'] != sample['session_num'])))
        bucket.append(point)
        previous = sample
        if len(bucket) >= bucket_size:
            flush()
            bucket, bucket_gap = [], False
    flush()
    return {'items': points, 'source_samples': count, 'downsampled': count > len(points),
            'start': start, 'end': end}
