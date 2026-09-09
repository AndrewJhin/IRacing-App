import test from 'node:test';
import assert from 'node:assert/strict';
import { tracks, cars, sessionsFor, metrics, lapTime, telemetry, setupFor, setupLeaves } from '../data.js';

test('all selectable track/car/session combinations have internally consistent lap metrics', () => {
  for (const track of tracks) for (const car of cars) for (const session of sessionsFor(track.id,car.id)) {
    const result = metrics(session);
    assert.equal(session.track.id,track.id);
    assert.equal(session.car.id,car.id);
    assert.equal(result.best.status,'Clean');
    assert.ok(result.optimal <= result.best.seconds + 1e-9);
    assert.ok(result.average >= result.best.seconds);
    assert.equal(result.cleanCount,session.laps.filter(lap => lap.status === 'Clean').length);
    for (const lap of session.laps) assert.ok(Math.abs(lap.sectors.reduce((sum,value)=>sum+value,0)-lap.seconds)<1e-9);
  }
});

test('distance-aligned traces are bounded and end at their recorded lap time', () => {
  for (const track of tracks) {
    const session = sessionsFor(track.id,'porsche')[0];
    for (const lapNumber of [1,12,14]) {
      const points = telemetry(session,lapNumber);
      assert.equal(points.length,181);
      assert.equal(points[0].distance,0);
      assert.equal(points.at(-1).distance,track.length);
      assert.equal(points[0].elapsed,0);
      assert.ok(Math.abs(points.at(-1).elapsed-session.laps[lapNumber-1].seconds)<1e-9);
      points.forEach(point => {
        assert.ok(Number.isFinite(point.speed) && point.speed>=0 && point.speed<=300);
        assert.ok(point.throttle>=0 && point.throttle<=100);
        assert.ok(point.brake>=0 && point.brake<=100);
      });
    }
  }
});

test('setups preserve different car schemas and snapshot changes', () => {
  assert.ok('TC slip' in setupFor('ferrari').Electronics);
  assert.ok(!('TC slip' in setupFor('porsche').Electronics));
  assert.ok('Drivetrain' in setupFor('bmw'));
  assert.ok(!('Drivetrain' in setupFor('ferrari')));
  for (const car of cars) {
    assert.notDeepEqual(setupFor(car.id,1),setupFor(car.id,2));
    assert.ok(setupLeaves(setupFor(car.id)).every(item => item.path && typeof item.value === 'string'));
  }
  assert.deepEqual(setupLeaves({ future: { axles: [4,8] } }).map(item=>item.path), ['future / axles / 0','future / axles / 1']);
});

test('lap formatting carries rounding into the next minute', () => {
  assert.equal(lapTime(119.9999),'2:00.000');
  assert.equal(lapTime(121.384),'2:01.384');
  assert.equal(lapTime(Number.NaN),'—');
});
