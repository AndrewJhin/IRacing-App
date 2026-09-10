import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from iracing_local import capture, is_active_driving_session
from iracing_storage import Store, RecordingWriter
from iracing_storage.viewer import Viewer, sector_layout, library, trace

RAW = '''WeekendInfo:
  TrackDisplayName: Test circuit
SplitTimeInfo:
  Sectors:
    - SectorNum: 0
      SectorStartPct: 0.0
    - SectorNum: 1
      SectorStartPct: 0.333
    - SectorNum: 2
      SectorStartPct: 0.667
CarSetup:
  Wing: 4
'''

class ReviewTests(unittest.TestCase):
 def test_pit_entry_and_car_exit_close_stints_without_garage_snapshots(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);db=root/'nested'/'data.sqlite3';profile=root/'profile.json';profile.write_text('{"selected_fields": []}')
   active={'IsOnTrack':True,'IsOnTrackCar':True,'IsInGarage':False,'OnPitRoad':False,'SessionNum':0}
   garage=active|{'IsInGarage':True,'IsOnTrack':False}
   pit=active|{'OnPitRoad':True}
   states=[garage,pit,active,active,pit,pit,garage,pit,active,active,garage]
   sdk=SimpleNamespace(is_initialized=True,is_connected=True,_header=SimpleNamespace(tick_rate=60),
     _var_buffer_latest=SimpleNamespace(tick_count=0),startup=Mock(),shutdown=Mock())
   def tick():
    sdk._var_buffer_latest.tick_count+=1
    if sdk._var_buffer_latest.tick_count>len(states):raise KeyboardInterrupt
   sdk.freeze_var_buffer_latest=tick
   with patch('iracing_local.irsdk.IRSDK',return_value=sdk),patch('iracing_local.header_catalog',return_value=[{'name':'Speed'}]),patch('iracing_local.raw_session_info',return_value=RAW) as raw,patch('iracing_local.read_selected_variables',side_effect=[(v,[]) for v in states]):
    capture(root/'captures',profile,database=db)
   with Store(db,readonly=True) as store:
    recording=store.recording(store.list_recordings()[0]['id'])
    self.assertEqual(recording['sample_count'],4)
    self.assertEqual(len(recording['stints']),2)
    self.assertEqual([s['metadata']['start_reason'] for s in recording['stints']],['pit_exit','pit_exit'])
    self.assertEqual([s['metadata']['end_reason'] for s in recording['stints']],['pit_entry','car_exit'])
    self.assertEqual(len(store.snapshots(recording['id'])),2)
    self.assertEqual(raw.call_count,2)
    self.assertEqual(store.connection.execute('select count(distinct snapshot_id) from samples').fetchone()[0],2)
   self.assertFalse(is_active_driving_session({'IsOnTrack':True,'IsOnTrackCar':True}))

 def test_sector_estimates_use_only_clean_complete_laps_and_variable_layout(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'db.sqlite3'
   with Store(db) as store:
    writer=RecordingWriter(store,profile={},catalog=[],source_uri='test');writer.start_stint(0,{},RAW)
    tick=0
    for lap in range(1,4):
     for i in range(100):
      tick+=1
      values={'Lap':lap,'LapDistPct':i/100,'LapCurrentLapTime':i/10,'LapLastLapTime':10,'LapCompleted':lap-1,
       'SessionNum':0,'SessionTime':tick/10,'IsOnTrack':True,'OnPitRoad':False,'IsInGarage':False,
       'PlayerCarMyIncidentCount':1 if lap>=2 and i>=30 or lap>=3 else 0,'SteeringWheelAngle':(-1 if i%2 else 1), 'Gear':3}
      writer.write_sample(tick,tick/10,values)
    writer.close()
    with Store(db,readonly=True) as reader:result=Viewer().overview(reader,writer.recording_id)
    self.assertEqual(result['eligible_count'],1)
    self.assertEqual(len(result['sectors']),3)
    for sector,seconds in zip(result['sectors'],[3.33,3.34,3.33]):
     self.assertAlmostEqual(sector['best'],seconds,places=5);self.assertEqual(sector['count'],1)
    self.assertTrue(all(t is None for t in result['laps'][1]['sector_seconds']))
    self.assertEqual(len(result['stint_setups']),1)
    points=trace(store,writer.recording_id,0,99,40,.3,.5)['items']
    self.assertTrue(all(.3<=p['x']<=.5 for p in points));self.assertLessEqual(len(points),40)
    self.assertEqual({p['steering'] for p in points},{-1,1})
    self.assertTrue(all(p['gear']==3 for p in points))
  self.assertEqual(len(sector_layout({'SplitTimeInfo':{'Sectors':[{'SectorStartPct':i/5} for i in range(5)]}})),5)
  self.assertEqual(sector_layout({}),[])
  self.assertEqual(sector_layout({'SplitTimeInfo':{'Sectors':[{'SectorStartPct':.2}]}}),[])

 def test_library_date_range_is_applied_before_pagination(self):
  with tempfile.TemporaryDirectory() as tmp,Store(Path(tmp)/'db.sqlite3') as store:
   with store.connection:
    for i in range(110):store.create_recording(profile={},catalog=[],source_kind='test',started_at=100+i)
   result=library(store,limit=2,started_from=100,started_until=103)
   self.assertEqual([r['started_at'] for r in result['items']],[102,101]);self.assertTrue(result['has_more'])
   self.assertEqual([r['started_at'] for r in library(store,limit=2,offset=2,started_from=100,started_until=103)['items']],[100])

if __name__=='__main__':unittest.main()
