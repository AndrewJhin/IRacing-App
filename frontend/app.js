import { tracks, cars, sessionsFor, metrics, lapTime, delta, duration, telemetry, setupFor, setupLeaves } from './data.js';

const state = { track: 'suzuka', car: 'porsche', session: 0, tab: 'summary', lap: 14, reference: 12, snapshot: 2, compareSetup: true, lapFilter: 'all', cursor: .45 };
const app = document.querySelector('#app');
const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const iconPaths = {
  flag: '<path d="M5 21V4m0 1c5-5 9 5 14 0v10c-5 5-9-5-14 0"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  chart: '<path d="M4 4v16h16M7 14l4-5 4 3 5-8"/>',
  grid: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  sliders: '<path d="M4 7h5m4 0h7M4 17h9m4 0h3"/><circle cx="11" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
  clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
  car: '<path d="m5 8 2-4h10l2 4M4 8h16v10H4zM7 18v2m10-2v2M7 12h1m8 0h1"/>',
  track: '<path d="M7 4h10a4 4 0 0 1 4 4v3a3 3 0 0 1-3 3h-4v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V8a4 4 0 0 1 4-4Z"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>'
};
function icon(name, extra = '') { return `<svg class="icon ${extra}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.chart}</svg>`; }
function current() { return sessionsFor(state.track, state.car)[state.session]; }
function picker(id, label, options, selected, iconName) {
  return `<label class="picker" for="${id}"><span class="eyebrow">${label}</span><span class="select-wrap">${icon(iconName)}<select id="${id}">${options.map(item => `<option value="${item.id}" ${item.id === selected ? 'selected' : ''}>${escape(item.name)}</option>`).join('')}</select></span></label>`;
}
function sidebar(session) {
  const sessions = sessionsFor(state.track, state.car);
  return `<aside class="sidebar"><a class="brand" href="#main" aria-label="Apex session studio"><span class="brand-mark">A</span><span>APEX<small>SESSION STUDIO</small></span></a>
    <div class="library-label">${icon('layers')} Session library <span class="tiny-badge">DEMO</span></div>
    <div class="filters">${picker('track-select', 'Circuit', tracks, state.track, 'track')}${picker('car-select', 'Car', cars, state.car, 'car')}</div>
    <div class="sidebar-heading"><span>SESSIONS</span><span>03</span></div>
    <div class="session-list">${sessions.map((item, index) => `<button class="session-card ${index === state.session ? 'selected' : ''}" data-session="${index}" aria-pressed="${index === state.session}"><span class="session-date">${item.date}<span>${item.time}</span></span><strong>${item.title}</strong><span class="session-bottom"><span>${item.laps.length} laps <i>·</i> Practice</span><b>${lapTime(metrics(item).best.seconds)}</b></span></button>`).join('')}</div>
    <div class="sidebar-bottom"><div class="storage-status">${icon('database')}<span>Local workspace<small id="storage-status">Interactive demo</small></span><span class="status-dot"></span></div><div class="profile"><span class="avatar">AJ</span><span>Andrew Jhin<small>Driver workspace</small></span></div></div>
  </aside>`;
}

function metricCard(label, value, annotation, tone = '', suffix = '') {
  return `<article class="metric ${tone}"><div class="metric-label">${label}</div><div class="metric-value">${value}${suffix ? `<span>${suffix}</span>` : ''}</div><div class="metric-note">${annotation}</div></article>`;
}

function trackDiagram(session, compact = false) {
  return `<svg class="track-diagram ${compact ? 'compact' : ''}" viewBox="20 15 475 240" role="img" aria-label="Illustrative ${escape(session.track.name)} circuit schematic"><path d="${session.track.path}" fill="none" stroke="#333940" stroke-width="13" stroke-linejoin="round"/><path d="${session.track.path}" fill="none" stroke="var(--accent)" stroke-width="3" stroke-linecap="round"/><path d="${session.track.path}" pathLength="100" fill="none" stroke="var(--purple)" stroke-width="4" stroke-dasharray="28 72" stroke-dashoffset="-33"/><rect x="87" y="139" width="10" height="10" rx="2" fill="var(--text)"/><text x="70" y="171">START</text><text x="184" y="47" class="sector-label">S1</text><text x="382" y="93" class="sector-label purple">S2</text><text x="231" y="209" class="sector-label">S3</text></svg>`;
}

function paceChart(session, m) {
  const clean = session.laps.filter(lap => lap.status === 'Clean');
  const min = m.best.seconds - .5, max = Math.max(...clean.map(lap => lap.seconds)) + .5;
  const x = number => 50 + (number - 1) / (session.laps.length - 1) * 660;
  const y = seconds => 175 - (seconds - min) / (max - min) * 145;
  const points = clean.map(lap => `${x(lap.number)},${y(lap.seconds)}`).join(' ');
  return `<svg class="pace-chart" viewBox="0 0 750 225" role="img" aria-label="Clean lap times throughout the session. Best lap ${m.best.number}, ${lapTime(m.best.seconds)}.">
    <defs><linearGradient id="pace-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#d9f77a" stop-opacity=".16"/><stop offset="100%" stop-color="#d9f77a" stop-opacity="0"/></linearGradient></defs>
    ${[0,1,2,3].map(i => { const value = min + (max-min) * i/3; return `<line x1="50" x2="716" y1="${y(value)}" y2="${y(value)}" class="chart-grid"/><text x="0" y="${y(value)+4}" class="axis-label">${lapTime(value).slice(0,-2)}</text>`; }).join('')}
    <polygon points="${x(clean[0].number)},180 ${points} ${x(clean.at(-1).number)},180" fill="url(#pace-fill)"/>
    <polyline points="${points}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round"/>
    <line x1="${x(m.best.number)}" x2="${x(m.best.number)}" y1="18" y2="184" stroke="var(--accent)" stroke-opacity=".3" stroke-dasharray="4 5"/>
    ${clean.map(lap => `<g><circle cx="${x(lap.number)}" cy="${y(lap.seconds)}" r="${lap.number === m.best.number ? 6 : 3.5}" fill="${lap.number === m.best.number ? 'var(--accent)' : 'var(--panel)'}" stroke="var(--accent)" stroke-width="2"/><title>Lap ${lap.number}: ${lapTime(lap.seconds)}</title></g>`).join('')}
    <rect x="${x(m.best.number)-45}" y="4" width="90" height="24" rx="5" fill="var(--accent)"/><text x="${x(m.best.number)}" y="20" text-anchor="middle" class="best-label">BEST · LAP ${m.best.number}</text>
    ${session.laps.filter((lap, index) => index % 3 === 0 || index === session.laps.length-1).map(lap => `<text x="${x(lap.number)}" y="210" text-anchor="middle" class="axis-label">${String(lap.number).padStart(2,'0')}</text>`).join('')}
  </svg>`;
}

function lapTable(session, m) {
  const laps = state.lapFilter === 'clean' ? session.laps.filter(lap => lap.status === 'Clean') : session.laps;
  return `<section class="panel lap-panel"><div class="panel-heading"><div><h2>Lap breakdown</h2><p>Select a lap to explore its telemetry</p></div><label class="sr-only" for="lap-filter">Filter laps</label><select class="small-select" id="lap-filter"><option value="all" ${state.lapFilter === 'all' ? 'selected' : ''}>All laps</option><option value="clean" ${state.lapFilter === 'clean' ? 'selected' : ''}>Clean laps</option></select></div>
    <div class="table-scroll"><table><thead><tr><th>Lap</th><th>Time</th><th>Δ best</th><th>Sector 1</th><th>Sector 2</th><th>Sector 3</th><th>Status</th><th><span class="sr-only">Open lap</span></th></tr></thead><tbody>${laps.map(lap => `<tr class="${lap.number === m.best.number ? 'best-row' : ''}"><td><span class="lap-number">${String(lap.number).padStart(2,'0')}</span>${lap.number === m.best.number ? '<span class="best-tag">BEST</span>' : ''}</td><td class="mono strong">${lapTime(lap.seconds)}</td><td class="mono ${lap.number === m.best.number ? 'accent' : 'muted'}">${lap.status === 'Clean' ? (lap.number === m.best.number ? '—' : delta(lap.seconds-m.best.seconds)) : '—'}</td>${lap.sectors.map((value,index) => `<td class="mono ${Math.abs(value-m.sectors[index]) < .0001 ? 'purple' : ''}">${value.toFixed(3)}</td>`).join('')}<td><span class="lap-status ${lap.status === 'Clean' ? 'clean' : 'other'}"><span></span>${lap.status}</span></td><td><button class="icon-button lap-open" data-lap="${lap.number}" aria-label="Analyze lap ${lap.number}">${icon('arrow')}</button></td></tr>`).join('')}</tbody></table></div></section>`;
}

function summary(session) {
  const m = metrics(session);
  return `<div class="metric-grid">${metricCard('Best lap', lapTime(m.best.seconds), `${icon('flag')} Lap ${String(m.best.number).padStart(2,'0')} <span class="note-divider">/</span> Stint ${m.best.stint}`, 'highlight')}${metricCard('Optimal lap', lapTime(m.optimal), `<span class="purple">${(m.best.seconds-m.optimal).toFixed(3)}s</span> potential from best sectors`)}${metricCard('Average clean lap', lapTime(m.average), `<span class="muted">± ${m.deviation.toFixed(3)}s</span> standard deviation`)}${metricCard('Laps completed', session.laps.length, `${m.cleanCount} clean <span class="note-divider">/</span> ${duration(m.duration)} total`, '', 'laps')}</div>
    <div class="summary-grid"><section class="panel pace-panel"><div class="panel-heading"><div><h2>Finding the pace</h2><p>Clean lap progression</p></div><div class="legend"><span class="legend-dot"></span> Lap time</div></div>${paceChart(session,m)}<div class="chart-footer"><span>LAP NUMBER</span><span>${icon('info')} Out, pit and invalid laps excluded</span></div></section>
    <section class="panel circuit-panel"><div class="panel-heading"><h2>${escape(session.track.layout)}</h2><span class="eyebrow">${escape(session.track.country)}</span></div>${trackDiagram(session,true)}<div class="circuit-stats"><span><b>${session.track.length.toFixed(3)}</b> km</span><span><b>${session.track.corners}</b> corners</span><span class="schematic-label">Schematic</span></div></section></div>
    <div class="lower-grid">${lapTable(session,m)}<div class="summary-side"><section class="panel sectors-panel"><div class="panel-heading"><div><h2>Time on the table</h2><p>Best lap vs. best individual sectors</p></div>${icon('chart')}</div>${m.sectors.map((best,index) => { const gap = m.best.sectors[index]-best; return `<div class="sector-row"><span class="sector-number">S${index+1}</span><div class="sector-values"><span>${best.toFixed(3)}<small>BEST SECTOR</small></span><span class="purple">${gap < .001 ? 'Matched' : delta(gap)+'s'}</span></div><div class="sector-bar"><span style="width:${Math.max(4,Math.min(100,gap/.5*100))}%"></span></div></div>`; }).join('')}<button class="text-button" data-tab="analytics">Explore lap comparison ${icon('arrow')}</button></section>
    <section class="panel conditions-panel"><div class="panel-heading"><h2>Track conditions</h2>${icon('sun')}</div><dl><div><dt>Air temperature</dt><dd>${session.airTemp.toFixed(1)}<span>°C</span></dd></div><div><dt>Track temperature</dt><dd>${session.trackTemp.toFixed(1)}<span>°C</span></dd></div><div><dt>Track usage</dt><dd>${session.grip}</dd></div><div><dt>Wind speed</dt><dd>${session.wind}<span>km/h</span></dd></div></dl><div class="weather-footer"><span class="status-dot"></span> Dry track <span>Clear skies</span></div></section></div></div>`;
}

function render() {
  const session = current();
  app.innerHTML = `${sidebar(session)}<main id="main" tabindex="-1"><header class="topbar"><div class="breadcrumb">WORKSPACE ${icon('chevron')} <span>Session review</span></div><span class="demo-badge"><span></span> DEMO SESSIONS</span></header>
    <div class="main-content"><div class="session-header"><div><div class="eyebrow session-kicker">${escape(session.title)} <span>·</span> ${session.date} <span>·</span> ${session.time}</div><h1>${escape(session.track.name)}<span class="layout-tag">${escape(session.track.layout)}</span></h1><div class="car-subtitle">${icon('car')} ${escape(session.car.name)} <span class="car-generation">${session.car.generation}</span><span class="header-separator">/</span> Practice session</div></div><div class="session-number"><span>SESSION</span><b>${String(3-state.session).padStart(2,'0')}</b></div></div>
    <div class="tabbar"><div role="tablist" aria-label="Session views">${[['summary','grid','Summary'],['analytics','chart','Analytics'],['setup','sliders','Setup']].map(([id,symbol,label]) => `<button id="tab-${id}" class="tab ${state.tab === id ? 'active' : ''}" role="tab" aria-selected="${state.tab === id}" aria-controls="session-panel" tabindex="${state.tab === id ? '0' : '-1'}" data-tab="${id}">${icon(symbol)}${label}</button>`).join('')}</div><span class="preview-label">Sample data · Interface preview</span></div>
    <div id="session-panel" role="tabpanel" aria-labelledby="tab-${state.tab}" tabindex="0">${state.tab === 'summary' ? summary(session) : state.tab === 'analytics' ? analytics(session) : setup(session)}</div>
    <footer class="main-footer"><span>APEX <span class="footer-dot">/</span> SESSION STUDIO</span><span>Illustrative sessions and telemetry. Your recordings are unchanged.</span></footer></div></main>`;
  bind();
}

function lapPicker(session, id, title, selected, color) {
  const best = metrics(session).best.number;
  return `<label class="lap-picker ${color}" for="${id}"><span class="eyebrow"><span class="legend-dot ${color}"></span>${title}</span><select id="${id}">${session.laps.map(lap => `<option value="${lap.number}" ${selected === lap.number ? 'selected' : ''}>Lap ${String(lap.number).padStart(2,'0')} · ${lapTime(lap.seconds)}${lap.number === best ? ' · Best lap' : lap.status !== 'Clean' ? ' · '+lap.status : ''}</option>`).join('')}</select></label>`;
}

function traceChart(session, selected, reference, key, label, unit, maximum, minimum = 0) {
  const left = 54, right = 896, top = 17, bottom = 111;
  const y = value => bottom - (value - minimum) / (maximum - minimum) * (bottom - top);
  const path = data => data.map((point,index) => `${index ? 'L' : 'M'}${(left+point.x*(right-left)).toFixed(2)},${y(point[key]).toFixed(2)}`).join(' ');
  const cursorX = left + state.cursor * (right-left);
  return `<div class="trace-block"><div class="trace-heading"><h3>${label}<span>${unit}</span></h3><div class="trace-values"><span class="accent" data-live="${key}">—</span><span class="purple" data-reference="${key}">—</span></div></div>
    <svg class="trace-chart" data-trace="${key}" viewBox="0 0 920 136" role="img" aria-label="${label} comparison by lap distance; numerical values are available with the distance slider below">
    ${[minimum,minimum+(maximum-minimum)/2,maximum].map(value => `<line x1="${left}" x2="${right}" y1="${y(value)}" y2="${y(value)}" class="chart-grid"/><text x="13" y="${y(value)+4}" class="axis-label">${Number.isInteger(value) ? value : value.toFixed(2)}</text>`).join('')}
    ${[0,.25,.5,.75,1].map(x => `<line x1="${left+x*(right-left)}" x2="${left+x*(right-left)}" y1="${top}" y2="${bottom}" class="chart-grid vertical"/><text x="${left+x*(right-left)}" y="132" text-anchor="middle" class="axis-label">${(x*session.track.length).toFixed(2)}</text>`).join('')}
    <path d="${path(reference)}" fill="none" stroke="var(--purple)" stroke-width="2" stroke-opacity=".8" stroke-dasharray="5 3"/>
    <path d="${path(selected)}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    <line class="crosshair" x1="${cursorX}" x2="${cursorX}" y1="${top}" y2="${bottom}" stroke="var(--text)" stroke-opacity=".5" stroke-dasharray="3 4"/>
    </svg></div>`;
}

function analytics(session) {
  const lap = session.laps.find(item => item.number === state.lap);
  const referenceLap = session.laps.find(item => item.number === state.reference);
  const gap = lap.seconds-referenceLap.seconds;
  const selected = telemetry(session,state.lap), reference = telemetry(session,state.reference);
  const deltaTrace = selected.map((point,index) => ({ ...point, delta: point.elapsed-reference[index].elapsed }));
  const zeroTrace = reference.map(point => ({ ...point, delta: 0 }));
  const range = Math.max(.25,Math.abs(gap)*1.12);
  const selectedBad = lap.status !== 'Clean' || referenceLap.status !== 'Clean';
  return `<div class="comparison-toolbar">${lapPicker(session,'selected-lap','Selected lap',state.lap,'accent')}${lapPicker(session,'reference-lap','Reference lap',state.reference,'purple')}
    <div class="comparison-gap"><span class="eyebrow">LAP DELTA</span><strong class="${gap < 0 ? 'accent' : gap > 0 ? 'orange' : 'muted'}">${delta(gap)}<small>s</small></strong><span>${gap === 0 ? 'Same lap time' : gap > 0 ? 'Slower than reference' : 'Faster than reference'}</span></div></div>
    ${selectedBad ? `<div class="notice">${icon('info')} This comparison includes an ${lap.status !== 'Clean' ? lap.status.toLowerCase() : referenceLap.status.toLowerCase()}. Its timing is not a clean-lap benchmark.</div>` : ''}
    <div class="analytics-grid"><section class="panel telemetry-panel"><div class="panel-heading"><div><h2>Every input. Every corner.</h2><p>Distance-aligned telemetry</p></div><div class="trace-legend"><span><i></i> Lap ${state.lap}</span><span><i></i> Lap ${state.reference}</span></div></div>
    <div class="telemetry-stack">${traceChart(session,selected,reference,'speed','Speed','km/h',300)}${traceChart(session,selected,reference,'throttle','Throttle','%',100)}${traceChart(session,selected,reference,'brake','Brake','%',100)}${traceChart(session,deltaTrace,zeroTrace,'delta','Time delta','s',range,-range)}</div>
    <div class="distance-control"><div><label for="distance-cursor">Inspect lap distance</label><output id="distance-value" for="distance-cursor">${(state.cursor*session.track.length).toFixed(3)} km</output></div><input id="distance-cursor" type="range" min="0" max="180" value="${Math.round(state.cursor*180)}" aria-label="Inspect telemetry by lap distance"><div class="range-labels"><span>START / FINISH</span><span>${session.track.length.toFixed(3)} KM</span></div></div></section>
    <div class="analytics-side"><section class="panel"><div class="panel-heading"><h2>Sector comparison</h2><span class="eyebrow">Δ REF</span></div>${trackDiagram(session)}<div class="comparison-sectors">${lap.sectors.map((value,index) => { const difference = value-referenceLap.sectors[index]; return `<div class="comparison-sector"><span class="sector-number">S${index+1}</span><div><div class="sector-times"><span>${value.toFixed(3)}</span><span class="${difference <= 0 ? 'accent' : 'orange'}">${delta(difference)}s</span></div><div class="split-bar"><span style="width:${Math.min(100,Math.abs(difference)/Math.max(.1,Math.abs(gap))*100)}%;background:var(--${difference <= 0 ? 'accent' : 'orange'})"></span></div><small>Reference ${referenceLap.sectors[index].toFixed(3)}</small></div></div>`; }).join('')}</div><div class="panel-footnote">Schematic circuit · Illustrative traces</div></section>
    <section class="panel lap-detail"><div class="panel-heading"><h2>Lap ${String(lap.number).padStart(2,'0')} at a glance</h2>${icon('flag')}</div><dl><div><dt>Lap time</dt><dd>${lapTime(lap.seconds)}</dd></div><div><dt>Stint</dt><dd>0${lap.stint}</dd></div><div><dt>Fuel at lap start</dt><dd>${lap.fuel.toFixed(1)} L</dd></div><div><dt>Lap status</dt><dd class="${lap.status === 'Clean' ? 'accent' : 'orange'}">${lap.status}</dd></div></dl><button class="text-button" data-view-setup="${lap.stint}">View stint setup ${icon('arrow')}</button></section>
    <div class="analytics-tip">${icon('info')}<p>Move across a chart, or use the distance slider, to inspect both laps at the same point.</p></div></div></div>`;
}

function setupTime(session,snapshot) {
  const [hour,minute] = session.time.split(':').map(Number);
  const additional = snapshot === 1 ? 0 : Math.round(session.laps.slice(0,9).reduce((sum,lap) => sum+lap.seconds,0)/60);
  const total = hour*60+minute+additional;
  return `${String(Math.floor(total/60)%24).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`;
}
function setupRows(value, previous, compare) {
  const before = new Map(setupLeaves(previous).map(item => [item.path,item.value]));
  return setupLeaves(value).map(item => {
    const changed = compare && before.get(item.path) !== item.value;
    return `<div class="setup-row ${changed ? 'changed' : ''}"><dt>${escape(item.path)}</dt><dd>${changed ? `<del>${escape(before.get(item.path) ?? 'Not present')}</del>` : ''}<span>${escape(item.value ?? 'Not available')}</span>${changed ? '<span class="change-dot" aria-label="Changed from previous snapshot"></span>' : ''}</dd></div>`;
  }).join('');
}
function setup(session) {
  const configuration = setupFor(session.car.id,state.snapshot), previous = setupFor(session.car.id,1);
  const compare = state.compareSetup && state.snapshot === 2;
  const leaves = setupLeaves(configuration), before = new Map(setupLeaves(previous).map(item => [item.path,item.value]));
  const changedCount = leaves.filter(item => before.get(item.path) !== item.value).length;
  return `<div class="setup-toolbar"><label for="setup-snapshot"><span class="eyebrow">SETUP SNAPSHOT</span><select id="setup-snapshot"><option value="2" ${state.snapshot === 2 ? 'selected' : ''}>Stint 02 · ${setupTime(session,2)} · Pit entry</option><option value="1" ${state.snapshot === 1 ? 'selected' : ''}>Stint 01 · ${setupTime(session,1)} · On-track start</option></select></label><label class="compare-toggle"><input id="compare-setup" type="checkbox" ${compare ? 'checked' : ''} ${state.snapshot === 1 ? 'disabled' : ''}><span>Compare with stint 01</span></label></div>
    <div class="setup-overview"><div class="setup-overview-icon">${icon('sliders')}</div><div><h2>${escape(session.car.name)} <span>${session.car.generation}</span></h2><p>Stint ${String(state.snapshot).padStart(2,'0')} snapshot <span>·</span> ${leaves.length} parameters <span>·</span> ${setupTime(session,state.snapshot)}</p></div><span class="snapshot-badge">${compare ? changedCount+' changes from stint 01' : 'Read-only snapshot'}</span></div>
    <section class="setup-section"><div class="section-heading"><h2>Tires & alignment</h2><span>Cold values at stint start</span></div><div class="tire-grid">${Object.entries(configuration.Tires).map(([position,values],index) => `<article class="panel tire-card"><div class="tire-heading"><span class="corner-tag">${['LF','RF','LR','RR'][index]}</span><h3>${position}</h3></div><dl>${setupRows(values,previous.Tires[position],compare)}</dl></article>`).join('')}</div></section>
    <div class="setup-layout"><div class="setup-sections">${Object.entries(configuration).filter(([name]) => name !== 'Tires').map(([name,values]) => `<section class="panel setup-card"><div class="panel-heading"><h2>${escape(name)}</h2>${icon(name === 'Electronics' ? 'chart' : 'sliders')}</div><dl>${setupRows(values,previous[name],compare)}</dl></section>`).join('')}</div>
    <aside class="setup-sidebar"><section class="panel snapshot-history"><div class="panel-heading"><h2>Session snapshots</h2>${icon('clock')}</div>${[1,2].map(number => `<button class="snapshot-item ${state.snapshot === number ? 'active' : ''}" data-snapshot="${number}"><span class="timeline-dot"></span><span><strong>Stint 0${number}</strong><small>${setupTime(session,number)} · ${number === 1 ? 'On-track start' : 'Pit entry'}</small></span>${number === state.snapshot ? icon('check') : icon('chevron')}</button>`).join('')}<div class="panel-footnote">Captured when each stint started</div></section><div class="setup-explainer">${icon('layers')}<h3>Every car has its own setup.</h3><p>Parameters follow the selected car. Switch cars to preview different electronics, aero and drivetrain settings.</p><p>Original values and units are preserved.</p></div></aside></div>`;
}

function bind() {
  document.querySelector('#track-select').addEventListener('change', event => { state.track = event.target.value; state.session = 0; resetLaps(); render(); document.querySelector('#track-select').focus(); });
  document.querySelector('#car-select').addEventListener('change', event => { state.car = event.target.value; state.session = 0; resetLaps(); render(); document.querySelector('#car-select').focus(); });
  document.querySelectorAll('[data-session]').forEach(button => button.addEventListener('click', () => { state.session = Number(button.dataset.session); resetLaps(); render(); document.querySelector(`[data-session="${state.session}"]`).focus(); }));
  document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => { state.tab = button.dataset.tab; render(); document.querySelector(`#tab-${state.tab}`).focus(); }));
  document.querySelector('[role="tablist"]').addEventListener('keydown', event => {
    const tabs = ['summary','analytics','setup']; let index = tabs.indexOf(state.tab);
    if (event.key === 'ArrowRight') index = (index + 1) % 3;
    else if (event.key === 'ArrowLeft') index = (index + 2) % 3;
    else if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = 2;
    else return;
    event.preventDefault(); state.tab = tabs[index]; render(); document.querySelector(`#tab-${state.tab}`).focus();
  });
  document.querySelector('#lap-filter')?.addEventListener('change', event => { state.lapFilter = event.target.value; render(); document.querySelector('#lap-filter').focus(); });
  document.querySelectorAll('[data-lap]').forEach(button => button.addEventListener('click', () => { state.lap = Number(button.dataset.lap); state.tab = 'analytics'; render(); document.querySelector('#tab-analytics').focus(); }));
  for (const [id,property] of [['selected-lap','lap'],['reference-lap','reference'],['setup-snapshot','snapshot']]) {
    document.getElementById(id)?.addEventListener('change', event => { state[property] = Number(event.target.value); render(); document.getElementById(id).focus(); });
  }
  document.querySelector('#compare-setup')?.addEventListener('change', event => { state.compareSetup = event.target.checked; render(); document.querySelector('#compare-setup').focus(); });
  document.querySelectorAll('[data-snapshot]').forEach(button => button.addEventListener('click', () => { state.snapshot = Number(button.dataset.snapshot); render(); document.querySelector(`[data-snapshot="${state.snapshot}"]`).focus(); }));
  document.querySelectorAll('[data-view-setup]').forEach(button => button.addEventListener('click', () => { state.snapshot = Number(button.dataset.viewSetup); state.tab = 'setup'; render(); document.querySelector('#tab-setup').focus(); }));
  if (state.tab === 'analytics') {
    const session = current(), selected = telemetry(session,state.lap), reference = telemetry(session,state.reference);
    const updateCursor = index => {
      index = Math.max(0,Math.min(180,index)); state.cursor = index/180;
      const a = selected[index], b = reference[index];
      document.querySelector('#distance-value').textContent = `${a.distance.toFixed(3)} km`;
      document.querySelector('#distance-cursor').value = index;
      for (const [key,unit] of [['speed','km/h'],['throttle','%'],['brake','%'],['delta','s']]) {
        document.querySelector(`[data-live="${key}"]`).textContent = key === 'delta' ? `${delta(a.elapsed-b.elapsed)} ${unit}` : `${a[key].toFixed(1)} ${unit}`;
        document.querySelector(`[data-reference="${key}"]`).textContent = key === 'delta' ? 'Reference 0.000' : `${b[key].toFixed(1)} ${unit}`;
      }
      document.querySelectorAll('.crosshair').forEach(line => { line.setAttribute('x1',54+state.cursor*842); line.setAttribute('x2',54+state.cursor*842); });
    };
    document.querySelector('#distance-cursor').addEventListener('input', event => updateCursor(Number(event.target.value)));
    document.querySelectorAll('[data-trace]').forEach(svg => {
      const inspect = event => { const bounds = svg.getBoundingClientRect(); const position = ((event.clientX-bounds.left)/bounds.width*920-54)/842; updateCursor(Math.round(position*180)); };
      svg.addEventListener('pointermove', inspect);
      svg.addEventListener('pointerdown', inspect);
    });
    updateCursor(Math.round(state.cursor*180));
  }
}
function resetLaps() { state.lap = Math.min(14,current().laps.length); state.reference = metrics(current()).best.number; state.snapshot = 2; }
render();
