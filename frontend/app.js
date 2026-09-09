import { LiveClient, finite, show, lapTime, leaves, pathFor, nearest, displayTrace } from './live.js';

const app=document.querySelector('#app');
const ui={tab:'summary',filter:'all',cursor:.45,compare:true,deferred:false,dragging:false};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=name=>`<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">${({
  chart:'<path d="M4 4v16h16M7 14l4-5 4 3 5-8"/>',
  layers:'<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
  sliders:'<path d="M4 7h5m4 0h7M4 17h9m4 0h3"/><circle cx="11" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
  arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
  flag:'<path d="M5 21V4m0 1c5-5 9 5 14 0v10c-5 5-9-5-14 0"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
  database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>'
})[name]||'<circle cx="12" cy="12" r="8"/>'}</svg>`;
const date=value=>finite(value)?new Date(value*1000).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'}):'Date unavailable';
const clock=value=>finite(value)?new Date(value*1000).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'}):'Time unavailable';
const lapLabel=lap=>`Lap ${lap.number??'?'} · Stint ${stintNumber(lap.stint_id)} · Session ${lap.session_num??'?'}`;
const stintNumber=id=>{const stint=client.state.overview?.recording.stints.find(item=>item.id===id);return stint?stint.number+1:id;};

const client=new LiveClient(()=>{
  // Don't close an open picker or steal the distance slider while polling.
  if(document.activeElement?.tagName==='SELECT'||ui.dragging){ui.deferred=true;return;}
  render();
});
document.addEventListener('focusout',()=>setTimeout(()=>{if(ui.deferred&&!['SELECT','INPUT'].includes(document.activeElement?.tagName)){ui.deferred=false;render();}},0));
window.addEventListener('pagehide',()=>client.stop());
window.addEventListener('pointerup',()=>{ui.dragging=false;if(ui.deferred)render();});
document.addEventListener('change',event=>{if(event.target.tagName==='SELECT')event.target.blur();});

function picker(id,label,items,selected) {
  return `<label class="picker" for="${id}"><span class="eyebrow">${label}</span><select id="${id}" class="live-picker"><option value="all">All ${label.toLowerCase()}s</option>${items.map(item=>`<option value="${esc(item.id)}" ${item.id===selected?'selected':''}>${esc(item.name)}</option>`).join('')}</select></label>`;
}
function sidebar() {
  const s=client.state;
  const tracks=Array.from(new Map(s.library.map(item=>[item.track.id,item.track])).values());
  const cars=Array.from(new Map(s.library.filter(item=>s.trackId==='all'||item.track.id===s.trackId).map(item=>[item.car.id,item.car])).values());
  const visible=client.visible();
  return `<aside class="sidebar"><a class="brand" href="#main"><span class="brand-mark">A</span><span>APEX<small>SESSION STUDIO</small></span></a><div class="library-label">${icon('layers')} Session library</div>
    <div class="filters">${picker('track-select','Circuit',tracks,s.trackId)}${picker('car-select','Car',cars,s.carId)}</div><div class="sidebar-heading"><span>RECORDINGS</span><span>${visible.length}</span></div>
    <div class="session-list">${visible.map(item=>`<button class="session-card ${s.recordingId===item.id?'selected':''}" data-recording="${esc(item.id)}" aria-pressed="${s.recordingId===item.id}"><span class="session-date">${esc(date(item.started_at))}<span>${esc(clock(item.started_at))}</span></span><strong>${esc(item.track.name)}</strong><span class="session-car">${esc(item.car.name)}</span><span class="session-bottom"><span>${esc(item.status)}</span><b>${item.sample_count.toLocaleString()} samples</b></span></button>`).join('')||'<p class="sidebar-empty">No recordings in this selection.</p>'}</div>
    ${s.hasMore?'<button class="text-button" id="load-older">Load older recordings</button>':''}<div class="sidebar-bottom"><div class="storage-status">${icon('database')}<span>Local database<small>${s.error?'Connection interrupted':s.loading?'Refreshing…':'Auto-refresh · 1.5 seconds'}</small></span><span class="status-dot ${s.error?'offline':''}"></span></div></div></aside>`;
}
function empty(title,body) {return `<section class="panel empty-panel">${icon('database')}<h2>${esc(title)}</h2><p>${esc(body)}</p></section>`;}
function metric(label,value,note,tone='') {return `<article class="metric ${tone}"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-note">${note}</div></article>`;}
function latestPanel(o) {
  const latest=o.latest||{};
  return `<section class="panel"><div class="panel-heading"><h2>Latest telemetry</h2><span class="eyebrow">${o.sample_age_seconds===null?'NO SAMPLES':`${show(o.sample_age_seconds,0)}S AGO`}</span></div><div class="live-values">${[
    ['Speed',finite(latest.speed)?latest.speed*3.6:null,'km/h'],['Gear',latest.gear,''],['RPM',latest.rpm,''],
    ['Throttle',finite(latest.throttle)?latest.throttle*100:null,'%'],['Brake',finite(latest.brake)?latest.brake*100:null,'%'],['Fuel',latest.fuel,'L']
  ].map(([label,value,unit])=>`<div><span>${label}</span><strong>${label==='Gear'&&value===-1?'R':label==='Gear'&&value===0?'N':show(value,label==='Fuel'?1:0)}<small>${unit}</small></strong></div>`).join('')}</div><div class="panel-footnote">${esc(o.live_state)} · Committed samples from extraction</div></section>`;
}
function pace(o) {
  const laps=o.laps.filter(lap=>lap.eligible);
  if(!laps.length)return empty('Waiting for a complete lap','Lap pace appears after an observed start and finish, with no detected pit activity, incident or telemetry gap.');
  const min=Math.min(...laps.map(lap=>lap.seconds))-.25,max=Math.max(...laps.map(lap=>lap.seconds))+.25;
  const x=index=>55+index/Math.max(1,laps.length-1)*645,y=value=>170-(value-min)/(max-min)*140;
  return `<section class="panel pace-panel"><div class="panel-heading"><div><h2>Observed lap pace</h2><p>Complete laps without detected gaps or incidents</p></div></div><svg class="pace-chart" viewBox="0 0 750 225" role="img" aria-label="Observed completed lap times">${[0,1,2,3].map(i=>{const value=min+(max-min)*i/3;return `<line x1="55" x2="710" y1="${y(value)}" y2="${y(value)}" class="chart-grid"/><text x="0" y="${y(value)+4}" class="axis-label">${lapTime(value).slice(0,-1)}</text>`;}).join('')}<polyline points="${laps.map((lap,index)=>`${x(index)},${y(lap.seconds)}`).join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"/>${laps.map((lap,index)=>`<circle cx="${x(index)}" cy="${y(lap.seconds)}" r="4" fill="var(--accent)"><title>${esc(lapLabel(lap))}: ${lapTime(lap.seconds)}</title></circle>${index%Math.max(1,Math.ceil(laps.length/8))===0?`<text x="${x(index)}" y="205" text-anchor="middle" class="axis-label">${lap.number??'?'}</text>`:''}`).join('')}</svg></section>`;
}
function table(o) {
  const laps=ui.filter==='complete'?o.laps.filter(lap=>lap.eligible):o.laps;
  return `<section class="panel lap-panel"><div class="panel-heading"><div><h2>Lap history</h2><p>Unique segments are kept across stints and session resets</p></div><select id="lap-filter" class="small-select" aria-label="Filter laps"><option value="all">All segments</option><option value="complete" ${ui.filter==='complete'?'selected':''}>Complete laps</option></select></div><div class="table-scroll" id="lap-scroll"><table><thead><tr><th>Lap / stint</th><th>Time</th><th>Δ best</th><th>Samples</th><th>Coverage</th><th></th></tr></thead><tbody>${laps.map(lap=>`<tr class="${lap.id===o.best?.id?'best-row':''}"><td><span class="lap-number">${lap.number??'?'}</span> <span class="muted">/ ${stintNumber(lap.stint_id)}</span>${lap.id===o.best?.id?'<span class="best-tag">BEST</span>':''}</td><td class="mono strong">${lapTime(lap.seconds)}${!lap.closed&&finite(lap.elapsed)?`<small class="elapsed-note">${lapTime(lap.elapsed)} elapsed</small>`:''}</td><td class="mono muted">${lap.eligible&&o.best?`+${show(lap.seconds-o.best.seconds,3)}`:'—'}</td><td class="mono">${lap.samples.toLocaleString()}</td><td><span class="lap-status ${lap.eligible?'clean':'other'}">${esc(lap.status)}</span><small class="validity-note">${esc(lap.validity)}</small></td><td><button class="icon-button" data-lap="${lap.id}" aria-label="Analyze ${esc(lapLabel(lap))}">${icon('arrow')}</button></td></tr>`).join('')||'<tr><td colspan="6">No laps recorded yet.</td></tr>'}</tbody></table></div></section>`;
}
function summary(o) {
  return `<div class="metric-grid">${metric('Best observed lap',lapTime(o.best?.seconds),o.best?esc(lapLabel(o.best)):'Waiting for a complete lap','highlight')}${metric('Average lap',lapTime(o.average),finite(o.deviation)?`± ${show(o.deviation,3)}s standard deviation`:'Complete laps only')}${metric('Complete laps',o.eligible_count,`${o.laps.length} observed segments`)}${metric('Recorded samples',o.recording.sample_count.toLocaleString(),`${show(o.observed_duration/60,1)} minutes observed`)}</div><div class="summary-grid">${pace(o)}${latestPanel(o)}</div><div class="lower-grid">${table(o)}<div class="summary-side"><section class="panel conditions-panel"><div class="panel-heading"><h2>Recorded conditions</h2></div><dl>${[
    ['Circuit length',o.track.length_km,'km'],['Air temperature',o.latest?.air_temp,'°C'],['Track temperature',o.latest?.track_temp,'°C'],['Wind',finite(o.latest?.wind)?o.latest.wind*3.6:null,'km/h']
  ].map(([label,value,unit])=>`<div><dt>${label}</dt><dd>${show(value)} <span>${unit}</span></dd></div>`).join('')}</dl></section><section class="panel"><div class="panel-heading"><h2>Timing coverage</h2></div><p class="panel-copy">Lap times use the recorded SDK lap timing. Missing values remain unavailable. Sector times and an optimal lap are not fabricated from distance or example data.</p><p class="panel-copy">“Complete” describes capture coverage. Incident validity is shown separately when its channel is unavailable.</p></section></div></div>`;
}
function lapPicker(id,label,value,o) {
  return `<label class="lap-picker"><span class="eyebrow">${label}</span><select id="${id}">${o.laps.map(lap=>`<option value="${lap.id}" ${lap.id===value?'selected':''}>${esc(lapLabel(lap))} · ${lapTime(lap.seconds)} · ${esc(lap.status)}</option>`).join('')}</select></label>`;
}
function chart(selected,reference,key,label,unit,max) {
  return `<div class="trace-block"><div class="trace-heading"><h3>${label}<span>${unit}</span></h3><div class="trace-values"><span class="accent" data-live="${key}">—</span><span class="purple" data-reference="${key}">—</span></div></div><svg class="trace-chart" data-trace="${key}" viewBox="0 0 920 136" role="img" aria-label="Recorded ${label.toLowerCase()} by lap distance">${[0,.5,1].map(f=>`<line x1="54" x2="896" y1="${111-f*94}" y2="${111-f*94}" class="chart-grid"/><text x="12" y="${115-f*94}" class="axis-label">${Math.round(max*f)}</text>`).join('')}${[0,.25,.5,.75,1].map(f=>`<text x="${54+f*842}" y="132" text-anchor="middle" class="axis-label">${f*100}%</text>`).join('')}<path d="${pathFor(reference,key,max)}" fill="none" stroke="var(--purple)" stroke-width="2" stroke-dasharray="5 3"/><path d="${pathFor(selected,key,max)}" fill="none" stroke="var(--accent)" stroke-width="2"/><line class="crosshair" x1="${54+ui.cursor*842}" x2="${54+ui.cursor*842}" y1="17" y2="111" stroke="var(--text)" stroke-opacity=".4" stroke-dasharray="3 4"/></svg></div>`;
}
function analytics(o) {
  if(!o.laps.length)return empty('No telemetry yet','Start extraction and drive on track. Live traces will appear as samples are committed.');
  const s=client.state, selected=displayTrace(s.traces.selected), reference=displayTrace(s.traces.reference);
  const a=o.laps.find(lap=>lap.id===s.lapId),b=o.laps.find(lap=>lap.id===s.referenceId);
  const gap=a?.eligible&&b?.eligible?a.seconds-b.seconds:null;
  const maxSpeed=Math.max(300,...selected.map(p=>finite(p.speed)?p.speed:0),...reference.map(p=>finite(p.speed)?p.speed:0));
  return `<div class="comparison-toolbar">${lapPicker('selected-lap','Selected lap',s.lapId,o)}${lapPicker('reference-lap','Reference lap',s.referenceId,o)}<label class="compare-toggle"><input type="checkbox" id="follow-lap" ${s.followLap?'checked':''}>Follow current lap</label></div><div class="analytics-grid"><section class="panel telemetry-panel"><div class="panel-heading"><div><h2>Recorded telemetry</h2><p>Lap distance · Gaps remain visible</p></div><div class="trace-legend"><span><i></i> Selected</span><span><i></i> Reference</span></div></div><div class="telemetry-stack">${chart(selected,reference,'speed','Speed','km/h',maxSpeed)}${chart(selected,reference,'throttle','Throttle','%',100)}${chart(selected,reference,'brake','Brake','%',100)}</div><div class="distance-control"><div><label for="distance-cursor">Inspect observed distance</label><output id="distance-value">${show(ui.cursor*100)}%</output></div><input type="range" id="distance-cursor" min="0" max="1000" value="${Math.round(ui.cursor*1000)}" aria-label="Inspect lap distance"><div class="range-labels"><span>0%</span><span>100% OF LAP</span></div></div><div class="panel-footnote">${s.traces.selected?.source_samples?.toLocaleString()||0} source samples in selected segment. Chart reduction preserves representative speed minima and brake maxima. No interpolation across gaps.</div></section><div class="analytics-side">${latestPanel(o)}<section class="panel lap-detail"><div class="panel-heading"><h2>Lap comparison</h2></div><dl><div><dt>Selected time</dt><dd>${lapTime(a?.seconds)}</dd></div><div><dt>Reference time</dt><dd>${lapTime(b?.seconds)}</dd></div><div><dt>Lap time difference</dt><dd>${finite(gap)?`${gap>=0?'+':''}${show(gap,3)}s`:'—'}</dd></div><div><dt>Selected coverage</dt><dd>${esc(a?.status||'Loading')}</dd></div></dl><div class="panel-footnote">A delta is shown only for two eligible complete laps. At the cursor, readouts use nearby recorded samples within 1% of lap distance.</div></section></div></div>`;
}
function setup(o) {
  const s=client.state,index=s.snapshots.findIndex(item=>item.id===s.snapshotId),snapshot=s.snapshots[index];
  if(!snapshot)return empty('No setup snapshot yet','Session and setup information will appear after extraction starts a stint.');
  const previous=s.snapshots[index-1],before=new Map(leaves(previous?.setup).map(item=>[item.path,item.value]));
  const compare=ui.compare&&!!previous;
  const rows=(value,prefix=[])=>leaves(value,prefix).map(item=>{const changed=compare&&before.get(item.path)!==item.value;return `<div class="setup-row ${changed?'changed':''}"><dt>${esc(item.path)}</dt><dd>${changed?`<del>${esc(before.get(item.path)??'Not present')}</del>`:''}<span>${esc(item.value)}</span></dd></div>`;}).join('');
  const setupValue=snapshot.setup;
  const groups=setupValue&&typeof setupValue==='object'?Object.entries(setupValue):[];
  const removed=compare?leaves(previous.setup).filter(item=>!new Set(leaves(setupValue).map(row=>row.path)).has(item.path)):[];
  return `<div class="setup-toolbar"><label><span class="eyebrow">SNAPSHOT</span><select id="setup-snapshot">${s.snapshots.map(item=>`<option value="${item.id}" ${item.id===s.snapshotId?'selected':''}>Stint ${stintNumber(item.stint_id)} · ${esc(clock(item.captured_at))} · #${item.id}</option>`).join('')}</select></label><label class="compare-toggle"><input id="follow-snapshot" type="checkbox" ${s.followSnapshot?'checked':''}>Follow latest</label><label class="compare-toggle"><input id="compare-setup" type="checkbox" ${compare?'checked':''} ${!previous?'disabled':''}>Compare previous snapshot</label></div><div class="setup-overview"><div><h2>${esc(o.car.name)}</h2><p>${esc(date(snapshot.captured_at))} · ${esc(clock(snapshot.captured_at))} · Stint ${stintNumber(snapshot.stint_id)}</p></div><span class="snapshot-badge">Read-only recorded setup</span></div>${snapshot.parse_error?'<div class="notice">Some session YAML could not be parsed. Available setup values are shown below.</div>':''}${snapshot.provenance?.startsWith('legacy')?'<div class="notice">Imported legacy setup: its exact relationship to sample timing may be unknown.</div>':''}${setupValue===null||setupValue===undefined?empty('Car setup not exposed','The SDK did not provide a parsed CarSetup for this snapshot.'):`<div class="setup-sections">${groups.length?groups.map(([name,value])=>`<section class="panel setup-card"><div class="panel-heading"><h2>${esc(name)}</h2></div><dl>${rows(value,[name])}</dl></section>`).join(''):`<section class="panel setup-card"><dl>${rows(setupValue)}</dl></section>`}</div>`}${removed.length?`<section class="panel setup-card"><div class="panel-heading"><h2>No longer present</h2></div><dl>${removed.map(item=>`<div class="setup-row"><dt>${esc(item.path)}</dt><dd><del>${esc(item.value)}</del></dd></div>`).join('')}</dl></section>`:''}<p class="panel-copy">Values and units follow the actual car setup. A snapshot is an SDK observation, not proof of the exact instant a garage change took effect.</p>`;
}
function render() {
  ui.deferred=false;
  const s=client.state,o=s.overview;
  const focus=document.activeElement?.id;
  const scroll=document.querySelector('#lap-scroll')?.scrollTop;
  const libraryScroll=document.querySelector('.sidebar')?.scrollTop;
  const status=s.error?'CONNECTION INTERRUPTED':o?o.live_state.toUpperCase():s.loading?'CONNECTING':'LOCAL DATABASE';
  app.innerHTML=`${sidebar()}<main id="main" tabindex="-1"><header class="topbar"><div class="breadcrumb">WORKSPACE <span>Session review</span></div><span class="demo-badge ${s.error?'error-badge':''}"><span></span>${esc(status)}</span></header><div class="main-content">${s.error?`<div class="notice" role="status">${icon('info')}${esc(s.error)} Last loaded values may be stale.<button id="retry" class="small-select">Retry now</button></div>`:''}${o?`<div class="session-header"><div><div class="eyebrow session-kicker">${esc(date(o.recording.started_at))} · ${esc(clock(o.recording.started_at))} · ${esc(o.recording.status)}</div><h1>${esc(o.track.name)}${o.track.layout?`<span class="layout-tag">${esc(o.track.layout)}</span>`:''}</h1><div class="car-subtitle">${esc(o.car.name)} <span class="header-separator">/</span> ${esc(o.track.country)}</div></div></div><div class="tabbar"><div role="tablist" aria-label="Session views">${['summary','analytics','setup'].map(tab=>`<button id="tab-${tab}" class="tab ${ui.tab===tab?'active':''}" role="tab" aria-selected="${ui.tab===tab}" aria-controls="session-panel" tabindex="${ui.tab===tab?0:-1}" data-tab="${tab}">${icon(tab==='setup'?'sliders':tab==='analytics'?'chart':'layers')}${tab[0].toUpperCase()+tab.slice(1)}</button>`).join('')}</div><span class="preview-label">Recorded data · Auto-refresh</span></div>${!o.caught_up?`<div class="notice">Loading history: ${o.processed_count.toLocaleString()} of ${o.recording.sample_count.toLocaleString()} samples processed. Statistics below are provisional.</div>`:''}<div id="session-panel" role="tabpanel" aria-labelledby="tab-${ui.tab}">${ui.tab==='summary'?summary(o):ui.tab==='analytics'?analytics(o):setup(o)}</div>`:empty(s.loading?'Connecting to your recordings…':s.error?'Viewer unavailable':s.library.length?'No matching recording':'Ready for your first drive',s.loading?'Reading the local database.':s.error?'Start or restart the viewer command, then retry.':s.library.length?'Choose another circuit or car.':'Start iracing_local.py with the simulator open, then drive on track. Your new recording will appear here automatically.')}<footer class="main-footer"><span>APEX / SESSION STUDIO</span><span>Actual local recordings · No demo substitution</span></footer></div></main>`;
  bind();
  if(focus)document.getElementById(focus)?.focus({preventScroll:true});
  if(scroll!==undefined&&document.querySelector('#lap-scroll'))document.querySelector('#lap-scroll').scrollTop=scroll;
  if(libraryScroll!==undefined)document.querySelector('.sidebar').scrollTop=libraryScroll;
}
function bind() {
  document.querySelector('#track-select').onchange=event=>client.selectFilter('trackId',event.target.value);
  document.querySelector('#car-select').onchange=event=>client.selectFilter('carId',event.target.value);
  document.querySelectorAll('[data-recording]').forEach(button=>button.onclick=()=>client.selectRecording(button.dataset.recording));
  document.querySelector('#load-older')?.addEventListener('click',()=>{client.state.libraryLimit+=100;client.refresh();});
  document.querySelector('#retry')?.addEventListener('click',()=>client.refresh());
  document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{ui.tab=button.dataset.tab;render();document.querySelector(`#tab-${ui.tab}`).focus();});
  document.querySelector('[role=tablist]')?.addEventListener('keydown',event=>{
    const tabs=['summary','analytics','setup'];let i=tabs.indexOf(ui.tab);
    if(event.key==='ArrowRight')i=(i+1)%3;else if(event.key==='ArrowLeft')i=(i+2)%3;else if(event.key==='Home')i=0;else if(event.key==='End')i=2;else return;
    event.preventDefault();ui.tab=tabs[i];render();document.querySelector(`#tab-${ui.tab}`).focus();
  });
  document.querySelector('#lap-filter')?.addEventListener('change',event=>{ui.filter=event.target.value;render();});
  document.querySelectorAll('[data-lap]').forEach(button=>button.onclick=()=>{client.state.lapId=button.dataset.lap;client.state.followLap=false;ui.tab='analytics';client.state.traces={selected:null,reference:null};client.refresh();});
  for(const [id,key] of [['selected-lap','lapId'],['reference-lap','referenceId']])document.getElementById(id)?.addEventListener('change',event=>{client.state[key]=event.target.value;if(key==='lapId')client.state.followLap=false;client.state.traces={selected:null,reference:null};client.refresh();});
  document.querySelector('#follow-lap')?.addEventListener('change',event=>{client.state.followLap=event.target.checked;client.refresh();});
  document.querySelector('#setup-snapshot')?.addEventListener('change',event=>{client.state.snapshotId=Number(event.target.value);client.state.followSnapshot=false;render();});
  document.querySelector('#follow-snapshot')?.addEventListener('change',event=>{client.state.followSnapshot=event.target.checked;client.refresh();});
  document.querySelector('#compare-setup')?.addEventListener('change',event=>{ui.compare=event.target.checked;render();});
  if(ui.tab==='analytics'&&document.querySelector('#distance-cursor')) {
    const a=displayTrace(client.state.traces.selected),b=displayTrace(client.state.traces.reference);
    const inspect=x=>{
      ui.cursor=Math.max(0,Math.min(1,x));const selected=nearest(a,ui.cursor),reference=nearest(b,ui.cursor);
      const length=client.state.overview?.track.length_km;
      document.querySelector('#distance-value').textContent=`${show(ui.cursor*100)}%${finite(length)?` · ${show(ui.cursor*length,3)} km`:''}`;
      document.querySelector('#distance-cursor').value=Math.round(ui.cursor*1000);
      for(const key of ['speed','throttle','brake']) {
        document.querySelector(`[data-live="${key}"]`).textContent=show(selected?.[key]);
        document.querySelector(`[data-reference="${key}"]`).textContent=show(reference?.[key]);
      }
      document.querySelectorAll('.crosshair').forEach(line=>{line.setAttribute('x1',54+ui.cursor*842);line.setAttribute('x2',54+ui.cursor*842);});
    };
    document.querySelector('#distance-cursor').oninput=event=>inspect(Number(event.target.value)/1000);
    document.querySelector('#distance-cursor').onpointerdown=()=>{ui.dragging=true;};
    document.querySelectorAll('[data-trace]').forEach(svg=>svg.onpointermove=event=>{const r=svg.getBoundingClientRect();inspect(((event.clientX-r.left)/r.width*920-54)/842);});
    inspect(ui.cursor);
  }
}
render();
client.refresh();
