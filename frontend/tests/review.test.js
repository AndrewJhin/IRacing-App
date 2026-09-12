import test from 'node:test';
import assert from 'node:assert/strict';
import {filterLaps,dateRange,pathFor,displayTrace,gearLabel} from '../live.js';
test('stint and condition filters intersect and empty choices remain empty',()=>{
 const laps=[{id:'a',stint_id:1,eligible:true,complete:true,incident_known:true},{id:'b',stint_id:2,incident:true,complete:true,incident_known:true},{id:'c',stint_id:2,complete:false,gap:true,incident_known:false}];
 assert.deepEqual(filterLaps(laps,'2','incident').map(l=>l.id),['b']);assert.deepEqual(filterLaps(laps,'2','clean'),[]);assert.deepEqual(filterLaps(laps,'all','partial').map(l=>l.id),['c']);
});
test('date filter uses local midnight and an exclusive next midnight',()=>{
 const params=new URLSearchParams(dateRange('2026-09-09'));assert.equal(Number(params.get('from')),new Date(2026,8,9).getTime()/1000);assert.equal(Number(params.get('until')),new Date(2026,8,10).getTime()/1000);
});
test('sector zoom scales both signs of steering and preserves gear values',()=>{
 const p=displayTrace({items:[{x:.25,steering:-Math.PI/2,gear:-1},{x:.5,steering:Math.PI/2,gear:0}]});assert.equal(p[0].steering,-90);assert.equal(p[1].steering,90);
 const path=pathFor(p,'steering',90,-90,.25,.5);assert.match(path,/M54.00,111.00/);assert.match(path,/L896.00,17.00/);assert.equal(gearLabel(-1),'R');assert.equal(gearLabel(0),'N');assert.equal(gearLabel(null),'—');
});
