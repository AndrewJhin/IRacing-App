import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError
from iracing_storage import Store, RecordingWriter
from iracing_storage.viewer import Viewer
from iracing_storage.analysis import Analysis
from iracing_storage.api import create_server

RAW = '''WeekendInfo:
  TrackID: 42
  TrackDisplayName: Circuit A
  TrackConfigName: Grand Prix
DriverInfo:
  DriverCarIdx: 0
  Drivers:
    - CarIdx: 0
      CarID: 7
      CarScreenName: Car A
SplitTimeInfo:
  Sectors:
    - SectorStartPct: 0.0
    - SectorStartPct: 0.5
CarSetup:
  Chassis:
    Height: 55 mm
'''

class FinderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'data.sqlite3';self.store=Store(self.path)
  self.analysis=Analysis(Viewer())
 def tearDown(self):
  self.store.close();self.tmp.cleanup()
 def session(self,speeds=(10,),sizes=(100,),started=100,raw=RAW,dirty=False,unknown=False):
  w=RecordingWriter(self.store,profile={},catalog=[],source_uri='test');w.start_stint(0,{'started_at':started},raw)
  tick=0
  for lap,(speed,size) in enumerate(zip(speeds,sizes),1):
   for i in range(size):
    tick+=1
    values={'Lap':lap,'LapDistPct':i/size,'LapCurrentLapTime':i*.1,'LapLastLapTime':sizes[lap-2]*.1 if lap>1 else 0,
     'LapCompleted':lap-1,'SessionNum':0,'SessionTime':tick*.1,'IsOnTrack':True,'IsInGarage':False,'OnPitRoad':False,
     'Speed':speed,'Throttle':.5,'Brake':0,'SteeringWheelAngle':.2,'Gear':3 if lap==1 else 5}
    if not unknown:values['PlayerCarMyIncidentCount']=1 if dirty and i>=30 else 0
    w.write_sample(tick,started+tick*.1,values)
  tick+=1
  w.write_sample(tick,started+tick*.1,values|{'Lap':len(speeds)+1,'LapDistPct':0,'LapCurrentLapTime':0,'SessionTime':tick*.1,
   'LapLastLapTime':sizes[-1]*.1,'LapCompleted':len(speeds)})
  w.close()
  with self.store.connection:self.store.connection.execute('UPDATE recordings SET started_at=? WHERE id=?',(started,w.recording_id))
  return w.recording_id
 def test_recent_cap_empty_and_filter_before_pagination_without_sample_reads(self):
  self.assertEqual(self.analysis.finder(self.store)['recent'],[])
  for i in range(2):self.session(started=100+i)
  self.assertEqual(len(self.analysis.finder(self.store)['recent']),2)
  for i in range(6):self.session(started=200+i,raw=RAW.replace('CarID: 7','CarID: 9').replace('Car A','Car B'))
  queries=[];self.store.connection.set_trace_callback(queries.append)
  result=self.analysis.finder(self.store)
  self.assertEqual(len(result['recent']),5);self.assertEqual(result['items'],[])
  self.assertEqual([r['started_at'] for r in result['recent']],[205,204,203,202,201])
  found=self.analysis.finder(self.store,track='42:Grand Prix',car='7',limit=1)
  self.assertEqual(found['total'],2);self.assertEqual(found['items'][0]['started_at'],101);self.assertTrue(found['has_more'])
  self.assertEqual(len(self.analysis.finder(self.store,started_from=100,started_until=101,query='Car A')['items']),1)
  self.assertFalse(any('FROM samples' in q for q in queries))
 def test_all_time_best_is_clean_same_car_and_layout_across_dates_and_cached(self):
  selected=self.session(started=300,sizes=(100,))
  best=self.session(started=100,sizes=(80,))
  self.session(sizes=(70,),dirty=True)
  self.session(sizes=(60,),unknown=True)
  self.session(sizes=(50,),raw=RAW.replace('Grand Prix','Short'))
  self.session(sizes=(50,),raw=RAW.replace('CarID: 7','CarID: 8'))
  result=self.analysis.review(self.store,selected)
  self.assertEqual(result['all_time_best']['recording_id'],best)
  self.assertEqual(result['all_time_best']['lap']['seconds'],8)
  self.assertNotIn('stint_setups',result);self.assertNotIn('profile',result['recording'])
  with patch.object(self.analysis.viewer,'overview',side_effect=AssertionError('should use cached summaries')):
   self.assertEqual(self.analysis.review(self.store,selected)['all_time_best']['recording_id'],best)
  newer=self.session(started=400,sizes=(75,))
  self.assertEqual(self.analysis.review(self.store,selected)['all_time_best']['recording_id'],newer)
  comparison=self.analysis.comparison(self.store,selected,source='best',start=.2,end=.5)
  self.assertEqual(comparison['recording_id'],newer);self.assertTrue(all(.2<=p['x']<=.5 for p in comparison['items']))
  self.assertTrue(all('steering' in p and 'gear' in p for p in comparison['items']))
 def test_average_is_equal_lap_weight_not_sample_weight_and_preserves_unknowns(self):
  rid=self.session(speeds=(10,30),sizes=(100,200))
  result=self.analysis.comparison(self.store,rid,source='average')
  self.assertEqual(result['lap_count'],2);self.assertAlmostEqual(result['mean_speed'],20)
  point=result['items'][250];self.assertAlmostEqual(point['speed'],20);self.assertEqual(point['contributors']['speed'],2)
  self.assertIn(point['gear'],(3,5));self.assertEqual(result['mean_lap_seconds'],15)
  with self.store.connection:
   self.store.connection.execute("UPDATE samples SET values_json=json_set(values_json,'$.Speed',NULL) WHERE recording_id=? AND sequence=150",(rid,))
  # A fresh analysis instance simulates reopening a changed external fixture.
  missing=Analysis(Viewer()).comparison(self.store,rid,source='average',start=.2,end=.3)
  self.assertTrue(any(p['speed'] is None and p['contributors']['speed']<2 for p in missing['items']))
  self.assertIsNone(missing['mean_speed'])
 def test_no_clean_laps_and_unknown_identity_do_not_invent_benchmarks(self):
  rid=self.session(dirty=True)
  self.assertIsNone(self.analysis.review(self.store,rid)['all_time_best'])
  self.assertEqual(self.analysis.comparison(self.store,rid,source='average')['lap_count'],0)
  unknown=self.session(raw='CarSetup: {}')
  self.assertFalse(next(r for r in self.analysis.finder(self.store)['recent'] if r['id']==unknown)['identified'])
  with self.assertRaises(ValueError):self.analysis.review(self.store,unknown)
 def test_unknown_incidents_at_finish_do_not_qualify_as_clean(self):
  rid=self.session()
  with self.store.connection:
   self.store.connection.execute("UPDATE samples SET values_json=json_remove(values_json,'$.PlayerCarMyIncidentCount') WHERE recording_id=? AND sequence=100",(rid,))
  self.assertIsNone(self.analysis.review(self.store,rid)['all_time_best'])
  self.assertEqual(self.analysis.comparison(self.store,rid,source='average')['lap_count'],0)

 def test_http_lazy_endpoints(self):
  rid=self.session()
  server=create_server(self.path,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{server.server_port}/api/v1'
  def get(path):
   with urlopen(base+path,timeout=5) as r:return json.load(r)
  try:
   self.assertEqual(len(get('/finder')['recent']),1)
   result=get('/recordings/'+rid+'/review');self.assertEqual(result['all_time_best']['recording_id'],rid)
   self.assertNotIn('stint_setups',result)
   setups=get('/recordings/'+rid+'/stint-setups')['items'];self.assertEqual(len(setups),1);self.assertNotIn('setup_json',setups[0])
   self.assertEqual(get('/recordings/'+rid+'/comparison?source=average')['lap_count'],1)
   with self.assertRaises(HTTPError) as e:get('/recordings/'+rid+'/comparison?source=lap&lap_id=bad')
   self.assertEqual(e.exception.code,404)
  finally:server.shutdown();thread.join();server.server_close()

if __name__=='__main__':unittest.main()
