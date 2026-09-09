// Synthetic demonstration data. This module never writes into the user's database.
export const tracks = [
  { id: 'suzuka', name: 'Suzuka Circuit', layout: 'Grand Prix', country: 'Japan', length: 5.807, corners: 18, base: 121.384,
    path: 'M92 145 C53 121 47 81 70 66 L148 43 Q172 38 186 57 L203 87 Q214 106 237 97 L295 78 Q319 73 331 91 L350 124 Q363 143 380 130 L410 103 Q423 92 439 106 L458 126 Q474 143 459 160 L432 187 Q417 202 401 181 L373 146 Q360 132 346 148 L306 193 Q293 208 278 194 L236 154 Q219 139 203 153 L174 176 Q147 199 120 175 Z' },
  { id: 'spa', name: 'Spa-Francorchamps', layout: 'Grand Prix', country: 'Belgium', length: 7.004, corners: 19, base: 137.612,
    path: 'M69 187 L94 137 L127 141 L161 86 Q171 70 193 71 L281 77 Q299 80 307 98 L331 139 L366 119 Q382 112 398 129 L438 168 Q451 183 433 194 L355 204 L319 181 L285 197 L238 158 Q224 148 205 164 L143 211 Q125 222 107 212 Z' },
  { id: 'watkins', name: 'Watkins Glen', layout: 'Boot', country: 'United States', length: 5.472, corners: 11, base: 105.728,
    path: 'M78 160 L105 76 Q110 60 130 60 L196 66 L227 93 L323 73 Q341 71 348 86 L378 140 L443 158 Q461 163 450 181 L425 216 Q416 230 397 218 L357 189 L297 174 L271 132 L237 145 L218 192 Q211 210 191 209 L102 193 Q72 189 78 160 Z' }
];
export const cars = [
  { id: 'porsche', name: 'Porsche 911 GT3 R', generation: '992', number: '92', offset: 0 },
  { id: 'ferrari', name: 'Ferrari 296 GT3', generation: 'GT3', number: '16', offset: -.286 },
  { id: 'bmw', name: 'BMW M4 GT3', generation: 'GT3', number: '24', offset: .417 }
];

const offsets = [19.32, 3.12, 2.64, 1.94, 1.52, 1.07, .85, .64, 31.4, 1.18, .29, 0, .58, .763, .33, .412, 2.62, .187];
export function sessionsFor(trackId, carId) {
  const track = tracks.find(item => item.id === trackId);
  const car = cars.find(item => item.id === carId);
  if (!track || !car) return [];
  return [
    { id: `${trackId}-${carId}-evening`, title: 'Evening practice', date: '07 SEP 2026', time: '20:05', trackTemp: 31.8, airTemp: 24.2, grip: 'Moderate', wind: 12, seed: 1, count: 18, added: 0 },
    { id: `${trackId}-${carId}-long`, title: 'Long-run practice', date: '06 SEP 2026', time: '14:32', trackTemp: 35.4, airTemp: 26.8, grip: 'High', wind: 8, seed: 2, count: 24, added: .428 },
    { id: `${trackId}-${carId}-baseline`, title: 'Baseline testing', date: '05 SEP 2026', time: '10:18', trackTemp: 27.6, airTemp: 21.1, grip: 'Low', wind: 6, seed: 3, count: 14, added: 1.136 }
  ].map(session => {
    const laps = Array.from({ length: session.count }, (_, index) => {
      const offset = offsets[index % offsets.length] + (index >= offsets.length ? .35 : 0);
      const seconds = track.base + car.offset + session.added + offset;
      const status = index === 0 ? 'Out lap' : index === 8 ? 'Pit lap' : index === 16 ? 'Invalid' : 'Clean';
      const sector1 = seconds * .335 + Math.sin(index * 1.8) * .22;
      const sector2 = seconds * .391 + Math.cos(index * 1.3) * .23;
      return { number: index + 1, seconds, status, stint: index < 8 ? 1 : 2,
        sectors: [sector1, sector2, seconds - sector1 - sector2], fuel: 64 - index * 2.62 };
    });
    return { ...session, track, car, laps };
  });
}

export function metrics(session) {
  const clean = session.laps.filter(lap => lap.status === 'Clean');
  const best = clean.reduce((a, b) => a.seconds < b.seconds ? a : b);
  const average = clean.reduce((total, lap) => total + lap.seconds, 0) / clean.length;
  const deviation = Math.sqrt(clean.reduce((total, lap) => total + (lap.seconds - average) ** 2, 0) / clean.length);
  const sectors = [0, 1, 2].map(index => Math.min(...clean.map(lap => lap.sectors[index])));
  return { best, average, deviation, sectors, optimal: sectors.reduce((a, b) => a + b, 0),
    cleanCount: clean.length, duration: session.laps.reduce((total, lap) => total + lap.seconds, 0) + 132 };
}

export function lapTime(seconds) {
  if (!Number.isFinite(seconds)) return '—';
  const milliseconds = Math.round(seconds * 1000);
  return `${Math.floor(milliseconds / 60000)}:${((milliseconds % 60000) / 1000).toFixed(3).padStart(6, '0')}`;
}
export function delta(seconds, precision = 3) {
  return `${seconds < 0 ? '−' : '+'}${Math.abs(seconds).toFixed(precision)}`;
}
export function duration(seconds) { return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`; }

export function telemetry(session, lapNumber) {
  const lap = session.laps.find(item => item.number === lapNumber);
  if (!lap) return [];
  // A schematic trace for interaction design, not a simulation of the real circuit.
  const brakeZones = session.track.id === 'spa' ? [.06, .22, .43, .56, .72, .93] : [.05, .16, .29, .45, .59, .74, .91];
  const best = metrics(session).best;
  return Array.from({ length: 181 }, (_, index) => {
    const x = index / 180;
    const braking = Math.max(...brakeZones.map(zone => Math.exp(-(((x - zone) / .019) ** 2))));
    const corner = Math.max(...brakeZones.map(zone => Math.exp(-(((x - zone - .025) / .043) ** 2))));
    const penalty = Math.max(0, lap.seconds - best.seconds);
    const speed = Math.max(62, 253 - corner * 161 + Math.sin(x * 28) * 15 - penalty * (2 + corner * 2));
    const throttle = Math.max(0, Math.min(100, 100 - corner * 103 - braking * 35));
    const brake = Math.max(0, Math.min(100, braking * 94 + Math.sin(x * 31 + lapNumber) * braking * 3));
    const progress = x + Math.sin(x * Math.PI * 6) * .015;
    return { x, distance: x * session.track.length, speed, throttle, brake,
      gear: Math.max(1, Math.min(6, Math.floor((speed - 35) / 39) + 1)),
      elapsed: progress * lap.seconds };
  });
}

export function setupFor(carId, snapshot = 2) {
  const later = snapshot === 2;
  const setup = {
    'Tires': {
      'Left front': { 'Cold pressure': '140 kPa', 'Camber': '−3.5°', 'Toe': '−0.1 mm' },
      'Right front': { 'Cold pressure': '140 kPa', 'Camber': '−3.5°', 'Toe': '−0.1 mm' },
      'Left rear': { 'Cold pressure': later ? '142 kPa' : '140 kPa', 'Camber': '−3.0°', 'Toe': '+0.2 mm' },
      'Right rear': { 'Cold pressure': later ? '142 kPa' : '140 kPa', 'Camber': '−3.0°', 'Toe': '+0.2 mm' }
    },
    'Chassis': {
      'Front': { 'Ride height': later ? '54 mm' : '55 mm', 'Anti-roll bar': '4', 'Spring rate': '180 N/mm' },
      'Rear': { 'Ride height': '72 mm', 'Anti-roll bar': later ? '3' : '4', 'Spring rate': '160 N/mm' }
    },
    'Aero & balance': { 'Rear wing': later ? '8' : '9', 'Brake bias': later ? '52.4%' : '53.0%', 'Fuel at start': later ? '42 L' : '64 L' },
    'Electronics': { 'Traction control': '4', 'ABS': '3', 'Engine map': '1' }
  };
  if (carId === 'ferrari') {
    setup.Electronics = { 'TC slip': later ? '5' : '6', 'TC cut': '4', 'ABS': '4', 'Engine map': '1' };
    setup['Aero & balance']['Rear wing'] = later ? '6' : '7';
  }
  if (carId === 'bmw') {
    setup.Electronics = { 'Traction control': '5', 'ABS': '5', 'Throttle shape': '2' };
    setup.Drivetrain = { 'Differential preload': later ? '100 Nm' : '120 Nm' };
  }
  return setup;
}

export function setupLeaves(value, path = []) {
  if (value !== null && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, item]) => setupLeaves(item, [...path, key]));
  }
  return [{ path: path.join(' / '), label: path.at(-1), value }];
}
