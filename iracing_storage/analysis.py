"""Lightweight session discovery, cached personal bests and clean-lap composites."""
from __future__ import annotations

import copy
import json
import math
import threading
from collections import OrderedDict, Counter

from .viewer import identity, object_value, number, is_gap, trace

CHANNELS = {'speed': 'Speed', 'throttle': 'Throttle', 'brake': 'Brake',
            'steering': 'SteeringWheelAngle', 'gear': 'Gear'}


def identified(info):
    weekend = object_value(info.get('WeekendInfo'))
    driver_info = object_value(info.get('DriverInfo'))
    drivers = driver_info.get('Drivers')
    driver = next((d for d in drivers if isinstance(d, dict) and d.get('CarIdx') == driver_info.get('DriverCarIdx')), {}) if isinstance(drivers, list) else {}
    return bool(weekend.get('TrackID') is not None or weekend.get('TrackName') or weekend.get('TrackDisplayName')) and bool(driver.get('CarID') is not None or driver.get('CarPath') or driver.get('CarScreenName'))


class Analysis:
    def __init__(self, viewer):
        self.viewer = viewer
        self.lock = threading.RLock()
        self.identities = {}
        self.summaries = OrderedDict()
        self.composites = OrderedDict()
        self.bests = {}

    def catalog(self, store):
        """No sample reads: cache parsed identity by immutable snapshot ID."""
        rows = store.connection.execute(
            'SELECT id,started_at,ended_at,status,sample_count, '
            '(SELECT max(id) FROM snapshots WHERE recording_id=r.id) AS snapshot_id '
            'FROM recordings r ORDER BY started_at DESC,id').fetchall()
        items = []
        with self.lock:
            present = set()
            for row in rows:
                item = dict(row); rid = item['id']; present.add(rid)
                cached = self.identities.get(rid)
                if cached is None or cached[0] != item['snapshot_id']:
                    snapshot = store.connection.execute('SELECT session_json FROM snapshots WHERE id=?', (item['snapshot_id'],)).fetchone()
                    info = object_value(json.loads(snapshot[0]) if snapshot else None)
                    cached = (item['snapshot_id'], identity(info) | {'identified': identified(info)})
                    self.identities[rid] = cached
                items.append(item | cached[1])
            for rid in self.identities.keys() - present:
                del self.identities[rid]
                self.bests.pop(rid, None)
        return items

    def finder(self, store, *, track=None, car=None, query='', started_from=None, started_until=None, offset=0, limit=20):
        if not 1 <= limit <= 100 or offset < 0 or len(query) > 200:
            raise ValueError('Invalid search')
        if any(v is not None and not math.isfinite(v) for v in (started_from, started_until)):
            raise ValueError('Invalid date')
        items = self.catalog(store)
        recent = items[:5]
        query = query.strip().casefold()
        base = [item for item in items if (started_from is None or item['started_at'] >= started_from)
                and (started_until is None or item['started_at'] < started_until)
                and (not query or query in (' '.join([item['track']['name'], item['track']['layout'], item['car']['name'], item['id'], item['status']])).casefold())]
        tracks = {r['track']['id']: r['track'] for r in base if r['identified'] and (not car or r['car']['id'] == car)}
        cars = {r['car']['id']: r['car'] for r in base if r['identified'] and (not track or r['track']['id'] == track)}
        matched = [r for r in base if (not track or r['track']['id'] == track) and (not car or r['car']['id'] == car)]
        # The unfiltered landing page shows only the five recent sessions.
        searching = bool(track or car or query or started_from is not None or started_until is not None)
        public = lambda r: {k: v for k, v in r.items() if k not in ('sample_count', 'snapshot_id')}
        return {'recent': [public(r) for r in recent], 'items': [public(r) for r in matched[offset:offset+limit]] if searching else [],
                'total': len(matched) if searching else 0, 'database_count': len(items),
                'has_more': searching and offset+limit < len(matched), 'offset': offset,
                'tracks': sorted(tracks.values(), key=lambda r: r['name']),
                'cars': sorted(cars.values(), key=lambda r: r['name']), 'searching': searching}

    def signature(self, store, rid):
        row = store.connection.execute('SELECT sample_count,status,ended_at, '
            '(SELECT max(id) FROM snapshots WHERE recording_id=r.id) FROM recordings r WHERE id=?', (rid,)).fetchone()
        if row is None:
            raise KeyError(rid)
        return tuple(row)

    def overview(self, store, rid):
        with self.lock:
            signature = self.signature(store, rid)
            cached = self.summaries.get(rid)
            if cached is None or cached[0] != signature:
                overview = self.viewer.overview(store, rid, complete=True, include_setups=False)
                # Do not send the capture profile, storage paths or setup payloads in review responses.
                overview['recording'] = {k: overview['recording'][k] for k in ('id','started_at','ended_at','status','sample_count','stints')}
                overview.pop('stint_setups', None)
                self.summaries[rid] = (signature, overview)
            self.summaries.move_to_end(rid)
            while len(self.summaries) > 64:
                self.summaries.popitem(last=False)
            return copy.deepcopy(self.summaries[rid][1])

    def personal_best(self, store, rid):
        catalog = self.catalog(store)
        selected = next((r for r in catalog if r['id'] == rid), None)
        if selected is None:
            raise KeyError(rid)
        if not selected['identified']:
            raise ValueError('Session needs an identified circuit and car')
        best = None
        for item in catalog:
            if not item['identified'] or (item['track']['id'],item['car']['id']) != (selected['track']['id'],selected['car']['id']):
                continue
            signature = (item['sample_count'], item['status'], item['ended_at'], item['snapshot_id'])
            with self.lock:
                cached = self.bests.get(item['id'])
                if cached is None or cached[0] != signature:
                    cached = (signature, self.overview(store, item['id'])['best'])
                    self.bests[item['id']] = cached
                candidate = cached[1]
            if candidate and (best is None or (candidate['seconds'],item['started_at'],item['id'],candidate['start_sequence']) <
                              (best['lap']['seconds'],best['started_at'],best['recording_id'],best['lap']['start_sequence'])):
                best = {'recording_id': item['id'], 'started_at': item['started_at'], 'lap': candidate,
                        'track': item['track'], 'car': item['car']}
        return best

    def review(self, store, rid):
        # Finding the best also verifies the selected session has a circuit/car.
        best = self.personal_best(store, rid)
        return self.overview(store, rid) | {'all_time_best': best}

    def setups(self, store, rid):
        store.recording(rid)
        return {'items': [{k: row[k] for k in row.keys() if k != 'setup_json'} | {'setup': json.loads(row['setup_json'])} for row in store.connection.execute(
            'SELECT id,stint_id,captured_at,setup_json,parse_error,provenance FROM snapshots '
            'WHERE id IN (SELECT min(id) FROM snapshots WHERE recording_id=? GROUP BY stint_id) ORDER BY id', (rid,))]}

    def comparison(self, store, rid, *, source='lap', lap_id=None, start=0.0, end=1.0):
        if not 0 <= start < end <= 1:
            raise ValueError('Invalid distance range')
        overview = self.overview(store, rid)
        if source == 'average':
            signature = self.signature(store, rid)
            key = (rid, signature, start, end)
            with self.lock:
                if key not in self.composites:
                    self.composites[key] = average_trace(store, rid, [l for l in overview['laps'] if l['eligible']], start, end)
                self.composites.move_to_end(key)
                while len(self.composites) > 16:
                    self.composites.popitem(last=False)
                return copy.deepcopy(self.composites[key])
        if source == 'best':
            best = self.personal_best(store, rid)
            if best is None:
                return {'items': [], 'kind': 'best', 'lap_count': 0, 'lap': None}
            trace_rid, lap = best['recording_id'], best['lap']
        elif source == 'lap':
            trace_rid = rid
            lap = next((l for l in overview['laps'] if l['id'] == lap_id), None)
            if lap is None:
                raise KeyError(lap_id)
        else:
            raise ValueError('Invalid comparison source')
        return trace(store, trace_rid, lap['start_sequence'], lap['end_sequence'], start_pct=start, end_pct=end) | {
            'kind': source, 'recording_id': trace_rid, 'lap': lap, 'lap_count': 1}


def average_trace(store, rid, laps, start=0.0, end=1.0, count=501):
    """Equal lap weighting at shared distances. Missing coverage stays missing."""
    if not laps:
        return {'items': [], 'kind': 'average', 'lap_count': 0, 'mean_lap_seconds': None, 'mean_speed': None}
    xs = [start + i*(end-start)/(count-1) for i in range(count)]
    sums = [{key: 0.0 for key in CHANNELS if key != 'gear'} for _ in xs]
    counts = [{key: 0 for key in CHANNELS} for _ in xs]
    gears = [Counter() for _ in xs]
    lap_speeds = []
    for lap in laps:
        index, previous, integral, duration, speed_missing = 0, None, 0.0, 0.0, False
        for row in store.connection.execute('SELECT sequence,tick,session_time,lap_distance,values_json FROM samples '
            'WHERE recording_id=? AND sequence>=? AND sequence<=? ORDER BY sequence', (rid,lap['start_sequence'],lap['end_sequence'])):
            sample = dict(row); values = json.loads(sample.pop('values_json')); x = number(sample['lap_distance'])
            sample['channels'] = {key: number(values.get(name)) for key,name in CHANNELS.items()}
            if previous is not None:
                x0 = number(previous['lap_distance']); t0 = number(previous['session_time']); t1 = number(sample['session_time'])
                if x0 is not None and x is not None and 0 <= x0 < x <= 1 and x-x0 <= .02 and not is_gap(previous,sample):
                    a,b = previous['channels'],sample['channels']
                    while index < count and xs[index] < x0:
                        index += 1
                    while index < count and xs[index] <= x:
                        fraction = (xs[index]-x0)/(x-x0)
                        for key in CHANNELS:
                            if a[key] is not None and b[key] is not None:
                                counts[index][key] += 1
                                if key == 'gear':
                                    # A modal recorded gear is meaningful; a fractional gear is not.
                                    gears[index][a[key] if fraction < .5 else b[key]] += 1
                                else:
                                    sums[index][key] += a[key]+fraction*(b[key]-a[key])
                        index += 1
                    lo,hi = max(start,x0),min(end,x)
                    if lo < hi and t0 is not None and t1 is not None and t1 > t0:
                        if a['speed'] is None or b['speed'] is None:
                            speed_missing = True
                        else:
                            u,v = (lo-x0)/(x-x0),(hi-x0)/(x-x0)
                            left,right = a['speed']+u*(b['speed']-a['speed']),a['speed']+v*(b['speed']-a['speed'])
                            dt = (t1-t0)*(v-u); integral += (left+right)*.5*dt; duration += dt
            previous = sample
        lap_speeds.append(integral/duration if duration and not speed_missing else None)
    items = []
    for i,x in enumerate(xs):
        item = {'x':x, 'sequence':i, 'gap':False, 'contributors':counts[i]}
        for key in CHANNELS:
            item[key] = (sorted(gears[i].items(),key=lambda kv:(-kv[1],kv[0]))[0][0] if key == 'gear' else sums[i][key]/len(laps)) if counts[i][key] == len(laps) else None
        items.append(item)
    return {'items':items, 'kind':'average', 'lap_count':len(laps),
            'mean_lap_seconds':sum(l['seconds'] for l in laps)/len(laps),
            'mean_speed':sum(lap_speeds)/len(lap_speeds) if all(v is not None for v in lap_speeds) else None,
            'method':'Equal lap weighting; interpolation only between adjacent samples. Every lap must contribute per channel. Gear is the mode.'}
