import test from 'node:test';
import assert from 'node:assert/strict';
import {LiveClient,show,lapTime,pathFor,displayTrace,nearest,leaves} from '../live.js';

const recording=id=>({id,track:{id:'track',name:'Recorded circuit'},car:{id:'car',name:'Recorded car'}});
const overview=id=>({recording:{id},laps:[{id:'0',start_sequence:0,end_sequence:2}],best:null,latest_snapshot_id:1});
const response=data=>({ok:true,json:async()=>data});
function service(ids=['one']) {
  return async path=>{
    if(path.startsWith('/api/v1/library'))return response({items:ids.map(recording),has_more:false});
    const id=path.split('/')[4];
    if(path.endsWith('/overview'))return response(overview(id));
    if(path.includes('/snapshots'))return response({items:[{id:1,setup:{Chassis:{Height:'55 mm'}}}]});
    if(path.includes('/trace'))return response({items:[{sequence:0,x:0,speed:0,throttle:0,brake:null}],source_samples:1});
    throw new Error(path);
  };
}

test('real adapter handles empty database, later discovery, and selected recording identity',async()=>{
  let ids=[];
  const client=new LiveClient(()=>{},path=>service(ids)(path),100000);
  try {
    await client.refresh();assert.equal(client.state.overview,null);
    ids=['one'];await client.refresh();assert.equal(client.state.recordingId,'one');
    ids=['two','one'];await client.refresh();assert.equal(client.state.recordingId,'one');
    await client.selectRecording('two');assert.equal(client.state.overview.recording.id,'two');
    assert.equal(client.state.snapshots[0].setup.Chassis.Height,'55 mm');
  } finally {client.stop();}
});

test('out-of-order responses cannot overwrite another recording selection',async()=>{
  let release,entered;
  const started=new Promise(resolve=>entered=resolve);
  const fetcher=async path=>{
    if(path==='/api/v1/recordings/one/overview') {entered();return new Promise(resolve=>release=()=>resolve(response(overview('one'))));}
    return service(['one','two'])(path);
  };
  const client=new LiveClient(()=>{},fetcher,100000);
  try {
    const old=client.refresh();await started;
    await client.selectRecording('two');release();await old;
    assert.equal(client.state.recordingId,'two');
    assert.equal(client.state.overview.recording.id,'two');
  } finally {client.stop();}
});

test('connection errors are explicit and recover without fabricated records',async()=>{
  let fail=true;
  const client=new LiveClient(()=>{},path=>fail?Promise.reject(new Error('offline')):service()(path),100000);
  try {
    await client.refresh();assert.equal(client.state.error,'offline');assert.deepEqual(client.state.library,[]);
    fail=false;await client.refresh();assert.equal(client.state.error,null);assert.equal(client.state.recordingId,'one');
  } finally {client.stop();}
});

test('trace conversion preserves zero and missing values and path breaks',()=>{
  const points=displayTrace({items:[{x:0,speed:0,brake:null,throttle:0},
    {x:.1,speed:null,throttle:1,brake:.2},{x:.2,speed:50,throttle:.5,brake:0,gap:true},
    {x:.21,speed:40,throttle:.5,brake:0}]});
  assert.equal(points[0].speed,0);assert.equal(points[1].speed,null);
  assert.equal(points[2].speed,180);assert.equal(points[1].throttle,100);
  assert.equal((pathFor(points,'speed',300).match(/M/g)||[]).length,2);
  assert.equal(nearest(points,.9),null);
  assert.equal(show(null),'—');assert.equal(lapTime(null),'—');
  assert.deepEqual(leaves({Tires:{pressures:[140,142]}}).map(item=>item.path),['Tires / pressures / 0','Tires / pressures / 1']);
});
