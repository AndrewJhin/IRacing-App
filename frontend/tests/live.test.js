import test from 'node:test';
import assert from 'node:assert/strict';
import {LiveClient,show,lapTime,pathFor,displayTrace,nearest,leaves} from '../live.js';
const item=id=>({id,identified:true,track:{id:'track',name:'Recorded circuit'},car:{id:'car',name:'Recorded car'}});
const lap={id:'0',stint_id:1,start_sequence:0,end_sequence:100,seconds:10,eligible:true};
const overview=id=>({recording:{id,stints:[]},laps:[lap],best:lap,average:10,eligible_count:1,all_time_best:{recording_id:'older',started_at:1,lap}});
const response=data=>({ok:true,json:async()=>data});
function service(ids=['one']){
 return async path=>{
  if(path.startsWith('/api/v1/finder'))return response({recent:ids.map(item),items:ids.map(item),tracks:[item('x').track],cars:[item('x').car],total:ids.length,database_count:ids.length,searching:true});
  const id=path.split('/')[4];
  if(path.endsWith('/review'))return response(overview(id));
  if(path.endsWith('/stint-setups'))return response({items:[{id:1,stint_id:1,setup:{Chassis:{Height:'55 mm'}}}]});
  if(path.includes('/comparison'))return response({items:[{sequence:0,x:0,speed:0,throttle:0,brake:null}],lap_count:1});
  throw new Error(path);
 };
}
test('finder initially loads only lightweight metadata and does not auto-open a session',async()=>{
 const calls=[],client=new LiveClient(()=>{},path=>{calls.push(path);return service()(path);});
 try{await client.refresh();assert.equal(calls.length,1);assert.match(calls[0],/finder/);assert.equal(client.state.mode,'finder');assert.equal(client.state.overview,null);assert.equal(client.timer,undefined);}finally{client.stop();}
});
test('search sessions require circuit and car; recent shortcuts explicitly choose both',async()=>{
 const client=new LiveClient(()=>{},service());
 try{
  await client.search();await client.selectRecording('one');assert.equal(client.state.mode,'finder');assert.match(client.state.error,/circuit and car/);
  await client.selectFilter('trackId','track');await client.selectRecording('one');assert.equal(client.state.mode,'finder');
  await client.selectFilter('carId','car');await client.selectRecording('one');assert.equal(client.state.mode,'review');assert.equal(client.state.overview.recording.id,'one');
  await client.back();client.state.trackId=client.state.carId='all';await client.selectRecording('one',true);assert.equal(client.state.trackId,'track');assert.equal(client.state.carId,'car');
 }finally{client.stop();}
});
test('review loads one session; traces and setups are lazy and cached',async()=>{
 const calls=[],client=new LiveClient(()=>{},path=>{calls.push(path);return service()(path);});
 try{
  await client.search();await client.selectRecording('one',true);
  assert.equal(calls.length,2);assert.ok(calls[1].endsWith('/one/review'));assert.equal(client.state.referenceSource,'best');
  await client.openTab('stints');assert.equal(calls.length,2);
  await client.openTab('analytics');assert.equal(calls.filter(p=>p.includes('/comparison')).length,2);
  assert.ok(calls.some(p=>p.includes('source=best')));assert.ok(calls.some(p=>p.includes('source=lap')));
  await client.openTab('summary');await client.openTab('analytics');assert.equal(calls.length,4);
  await client.openTab('setup');assert.equal(client.state.snapshots[0].setup.Chassis.Height,'55 mm');
  await client.openTab('setup');assert.equal(calls.length,5);
 }finally{client.stop();}
});
test('average uses all clean session laps, range requests and duplicate sources share a request',async()=>{
 const calls=[],client=new LiveClient(()=>{},path=>{calls.push(path);return service()(path);});
 try{
  await client.search();await client.selectRecording('one',true);client.state.selectedSource=client.state.referenceSource='average';
  client.state.selectedStint='99';client.state.selectedCondition='incident';client.state.rangeStart=.2;client.state.rangeEnd=.4;
  await client.openTab('analytics');const requests=calls.filter(p=>p.includes('/comparison'));
  assert.equal(requests.length,1);assert.match(requests[0],/source=average/);assert.match(requests[0],/start_pct=0.2&end_pct=0.4/);assert.doesNotMatch(requests[0],/stint|condition/);
 }finally{client.stop();}
});
test('out-of-order session responses cannot overwrite the selected session',async()=>{
 let release,entered;const started=new Promise(resolve=>entered=resolve);
 const client=new LiveClient(()=>{},async path=>{if(path.endsWith('/one/review')){entered();return new Promise(resolve=>release=()=>resolve(response(overview('one'))));}return service(['one','two'])(path);});
 try{await client.search();const old=client.selectRecording('one',true);await started;await client.selectRecording('two',true);release();await old;assert.equal(client.state.overview.recording.id,'two');}finally{client.stop();}
});
test('search keeps filters optional and sends pagination and exact circuit/car IDs',async()=>{
 const calls=[],client=new LiveClient(()=>{},path=>{calls.push(path);return service()(path);});
 try{await client.search();assert.doesNotMatch(calls[0],/from=|until=/);client.state.query='GT3';client.state.date='2026-09-09';client.state.offset=20;client.state.trackId='track';client.state.carId='car';await client.search();assert.match(calls[1],/offset=20/);assert.match(calls[1],/track=track/);assert.match(calls[1],/car=car/);assert.match(calls[1],/q=GT3/);assert.match(calls[1],/from=/);}finally{client.stop();}
});
test('connection errors recover without fabricated sessions',async()=>{
 let fail=true;const client=new LiveClient(()=>{},path=>fail?Promise.reject(new Error('offline')):service([])(path));
 try{await client.search();assert.equal(client.state.error,'offline');assert.deepEqual(client.state.recent,[]);fail=false;await client.search();assert.equal(client.state.error,null);assert.equal(client.state.overview,null);}finally{client.stop();}
});
test('default browser fetch keeps its global receiver',async()=>{
 const original=globalThis.fetch;const receivers=[];globalThis.fetch=function(path){receivers.push(this);if(this!==globalThis)throw new TypeError('Illegal invocation');return service()(path);};
 const client=new LiveClient(()=>{});
 try{await client.search();await client.selectRecording('one',true);assert.equal(client.state.error,null);assert.ok(receivers.length>=2);assert.ok(receivers.every(r=>r===globalThis));}finally{client.stop();globalThis.fetch=original;}
});
test('trace conversion preserves zero, missing values and path breaks',()=>{
 const points=displayTrace({items:[{x:0,speed:0,brake:null,throttle:0},{x:.1,speed:null,throttle:1,brake:.2},{x:.2,speed:50,throttle:.5,brake:0,gap:true},{x:.21,speed:40,throttle:.5,brake:0}]});
 assert.equal(points[0].speed,0);assert.equal(points[1].speed,null);assert.equal(points[2].speed,180);
 assert.equal((pathFor(points,'speed',300).match(/M/g)||[]).length,2);assert.equal(nearest(points,.9),null);
 assert.equal(show(null),'—');assert.equal(lapTime(null),'—');assert.deepEqual(leaves({Tires:{pressures:[140,142]}}).map(i=>i.path),['Tires / pressures / 0','Tires / pressures / 1']);
});
