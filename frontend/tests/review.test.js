import test from 'node:test';
import assert from 'node:assert/strict';
import {LiveClient,filterLaps,dateRange,pathFor,displayTrace,gearLabel} from '../live.js';
const ok=value=>({ok:true,json:async()=>value});
const laps=[{id:'a',stint_id:1,eligible:true,complete:true,incident_known:true,start_sequence:0,end_sequence:10},
 {id:'b',stint_id:2,incident:true,complete:true,incident_known:true,start_sequence:11,end_sequence:20},
 {id:'c',stint_id:2,complete:false,gap:true,incident_known:false,start_sequence:21,end_sequence:30}];
test('stint and condition filters intersect and empty choices remain empty',async()=>{
 assert.deepEqual(filterLaps(laps,'2','incident').map(l=>l.id),['b']);
 assert.deepEqual(filterLaps(laps,'2','clean'),[]);
 assert.deepEqual(filterLaps(laps,'all','partial').map(l=>l.id),['c']);
 const calls=[];
 const c=new LiveClient(()=>{},async path=>{calls.push(path);if(path.includes('library'))return ok({items:[{id:'r',track:{id:'t'},car:{id:'c'}}]});if(path.endsWith('overview'))return ok({recording:{sample_count:31},laps,stint_setups:[]});return ok({items:[]});});
 try{
  await c.refresh();c.state.selectedStint='2';c.state.selectedCondition='clean';await c.refresh(false);
  assert.equal(c.state.lapId,null);assert.equal(c.state.traces.selected,null);
  assert.equal(calls.filter(p=>p.includes('library')).length,1);
  assert.equal(c.timer,undefined);
  c.state.selectedCondition='incident';c.state.rangeStart=.3;c.state.rangeEnd=.5;await c.refresh(false);
  assert.equal(c.state.lapId,'b');assert.ok(calls.some(p=>p.includes('start_pct=0.3&end_pct=0.5')));
 }finally{c.stop();}
});
test('date filter uses local midnight and an exclusive next midnight',()=>{
 const params=new URLSearchParams(dateRange('2026-09-09'));
 assert.equal(Number(params.get('from')),new Date(2026,8,9).getTime()/1000);
 assert.equal(Number(params.get('until')),new Date(2026,8,10).getTime()/1000);
});
test('sector zoom scales both signs of steering and preserves gear values',()=>{
 const p=displayTrace({items:[{x:.25,steering:-Math.PI/2,gear:-1},{x:.5,steering:Math.PI/2,gear:0}]});
 assert.equal(p[0].steering,-90);assert.equal(p[1].steering,90);
 const path=pathFor(p,'steering',90,-90,.25,.5);
 assert.match(path,/M54.00,111.00/);assert.match(path,/L896.00,17.00/);
 assert.equal(gearLabel(-1),'R');assert.equal(gearLabel(0),'N');assert.equal(gearLabel(null),'—');
});
test('initial history load finishes multiple pages without periodic polling',async()=>{
 let count=0;
 const c=new LiveClient(()=>{},async path=>path.includes('library')?ok({items:[{id:'r',track:{id:'t'},car:{id:'c'}}]}):
 path.endsWith('overview')?ok({recording:{sample_count:50000},laps:[],stint_setups:[],caught_up:++count>=2,processed_count:count*25000}):ok({items:[]}));
 try{await c.refresh();assert.equal(count,2);assert.equal(c.state.error,null);assert.equal(c.timer,undefined);}finally{c.stop();}
});
