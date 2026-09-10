// The real-data adapter. No demo fallback, generated telemetry or database writes.
export const finite = value => typeof value === 'number' && Number.isFinite(value);
export const show = (value, digits = 1) => finite(value) ? value.toFixed(digits) : '—';
export function lapTime(seconds) {
  if (!finite(seconds) || seconds < 0) return '—';
  const ms = Math.round(seconds * 1000);
  return `${Math.floor(ms / 60000)}:${((ms % 60000) / 1000).toFixed(3).padStart(6,'0')}`;
}
export function leaves(value, path = []) {
  if (value && typeof value === 'object') return Object.entries(value).flatMap(([key,item]) => leaves(item,[...path,key]));
  return [{ path:path.join(' / '), value:value === null || value === undefined ? 'Not available' : String(value) }];
}
export function pathFor(points,key,max,min=0,start=0,end=1) {
  let path='', open=false;
  for (const point of points) {
    if (point.gap) open=false;
    const value=point[key];
    if (!finite(point.x) || point.x<start || point.x>end || !finite(value)) { open=false; continue; }
    const x=54+(point.x-start)/(end-start)*842, y=111-(Math.max(min,Math.min(max,value))-min)/(max-min)*94;
    path+=`${open?'L':'M'}${x.toFixed(2)},${y.toFixed(2)} `;
    open=true;
  }
  return path;
}
export function nearest(points,x,tolerance=.01) {
  const valid=points.filter(point=>finite(point.x) && !point.gap);
  const result=valid.reduce((best,point)=>!best || Math.abs(point.x-x)<Math.abs(best.x-x)?point:best,null);
  return result && Math.abs(result.x-x)<=tolerance ? result : null;
}
export function displayTrace(trace) {
  return (trace?.items || []).map(point=>({...point,
    speed:finite(point.speed)?point.speed*3.6:null,
    throttle:finite(point.throttle)?point.throttle*100:null,
    steering:finite(point.steering)?point.steering*180/Math.PI:null,
    brake:finite(point.brake)?point.brake*100:null}));
}

export function localDate(value=new Date()) {
  return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;
}
export function dateRange(date) {
  const start=new Date(`${date}T00:00:00`),end=new Date(start);
  if(!Number.isFinite(start.getTime()))throw new Error('Choose a valid recording date.');
  end.setDate(end.getDate()+1);
  return `&from=${start.getTime()/1000}&until=${end.getTime()/1000}`;
}
export function filterLaps(laps,stint='all',condition='all') {
  return laps.filter(lap=>(stint==='all'||String(lap.stint_id)===String(stint)) &&
    (condition==='all' || condition==='clean'&&lap.eligible || condition==='incident'&&lap.incident ||
     condition==='partial'&&!lap.complete || condition==='gap'&&lap.gap || condition==='pit'&&lap.pit ||
     condition==='unknown'&&!lap.incident_known));
}
export const gearLabel=value=>finite(value)?value===-1?'R':value===0?'N':String(value):'—';

export class LiveClient {
  constructor(onChange,fetcher=globalThis.fetch.bind(globalThis)) {
    this.onChange=onChange;this.fetcher=fetcher;
    this.state={library:[],hasMore:false,libraryLimit:100,date:localDate(),trackId:'all',carId:'all',recordingId:null,
      overview:null,snapshots:[],traces:{selected:null,reference:null},lapId:null,referenceId:null,
      selectedStint:'all',referenceStint:'all',selectedCondition:'all',referenceCondition:'all',
      snapshotId:null,rangeStart:0,rangeEnd:1,focus:'all',error:null,loading:true};
    this.generation=0;this.cache=new Map();this.stopped=false;
  }
  visible() {
    return this.state.library.filter(item=>(this.state.trackId==='all'||item.track.id===this.state.trackId)
      &&(this.state.carId==='all'||item.car.id===this.state.carId));
  }
  laps(side) {
    return filterLaps(this.state.overview?.laps||[],this.state[`${side}Stint`],this.state[`${side}Condition`]);
  }
  clearDetail() {
    Object.assign(this.state,{overview:null,snapshots:[],traces:{selected:null,reference:null},lapId:null,
      referenceId:null,snapshotId:null,selectedStint:'all',referenceStint:'all',selectedCondition:'all',
      referenceCondition:'all',rangeStart:0,rangeEnd:1,focus:'all'});
    this.cache.clear();
  }
  selectRecording(id) {this.state.recordingId=id;this.clearDetail();return this.refresh(false);}
  selectFilter(key,id) {
    this.state[key]=id;if(key==='trackId'||key==='date')this.state.carId='all';
    if(key==='date'){this.state.trackId='all';this.state.libraryLimit=100;}
    this.state.recordingId=null;this.clearDetail();return this.refresh(key==='date');
  }
  stop(){this.stopped=true;this.generation++;this.controller?.abort();}
  async json(path,signal) {
    const response=await this.fetcher(path,{signal,cache:'no-store'});
    if(!response.ok)throw new Error(response.status===404?'Viewer endpoint unavailable. Restart the Python viewer after updating.':'Cannot read the database. Check the viewer terminal, then retry.');
    return response.json();
  }
  async refresh(reloadLibrary=true) {
    if(this.stopped)return;
    this.controller?.abort();const generation=++this.generation,controller=new AbortController();this.controller=controller;
    const timeout=setTimeout(()=>controller.abort(),60000),current=()=>generation===this.generation&&!this.stopped;
    this.state.loading=true;this.onChange(this.state);
    try {
      if(reloadLibrary) {
        let library=[],page;
        for(let offset=0;offset<this.state.libraryLimit;offset+=100) {
          page=await this.json(`/api/v1/library?limit=100&offset=${offset}${dateRange(this.state.date)}`,controller.signal);
          if(!current())return;library.push(...page.items);if(!page.has_more)break;
        }
        this.state.library=Array.from(new Map(library.map(item=>[item.id,item])).values());this.state.hasMore=!!page.has_more;
      }
      const visible=this.visible();
      if(!visible.some(item=>item.id===this.state.recordingId)){this.state.recordingId=visible[0]?.id||null;this.clearDetail();}
      const id=this.state.recordingId;
      if(id) {
        const base=`/api/v1/recordings/${encodeURIComponent(id)}`;
        if(!this.state.overview||reloadLibrary) {
          let overview=await this.json(`${base}/overview`,controller.signal);
          const target=overview.recording.sample_count;
          // Finish this history load, without installing a recurring refresh timer.
          while(overview.caught_up===false&&overview.processed_count<target) {
            const previous=overview.processed_count;
            overview=await this.json(`${base}/overview`,controller.signal);
            if(!current())return;
            if(overview.processed_count<=previous)throw new Error('History loading stalled. Retry the viewer.');
          }
          if(!current())return;
          this.state.overview=overview;this.state.snapshots=overview.stint_setups||[];
        }
        const s=this.state,o=s.overview;
        if(!s.snapshots.some(item=>item.id===s.snapshotId))s.snapshotId=s.snapshots[0]?.id||null;
        const selectedLaps=this.laps('selected'),referenceLaps=this.laps('reference');
        if(!selectedLaps.some(lap=>lap.id===s.lapId))s.lapId=selectedLaps.find(lap=>lap.eligible)?.id||selectedLaps[0]?.id||null;
        if(!referenceLaps.some(lap=>lap.id===s.referenceId))s.referenceId=referenceLaps.find(lap=>lap.id===o.best?.id)?.id||referenceLaps[0]?.id||null;
        const load=async lapId=>{
          const lap=o.laps.find(lap=>lap.id===lapId);if(!lap)return null;
          const key=`${id}:${lap.start_sequence}:${lap.end_sequence}:${s.rangeStart}:${s.rangeEnd}`;
          if(this.cache.has(key))return this.cache.get(key);
          const result=await this.json(`${base}/trace?start=${lap.start_sequence}&end=${lap.end_sequence}&start_pct=${s.rangeStart}&end_pct=${s.rangeEnd}`,controller.signal);
          if(current()){this.cache.set(key,result);while(this.cache.size>8)this.cache.delete(this.cache.keys().next().value);}return result;
        };
        s.traces={selected:null,reference:null};
        const selected=await load(s.lapId),reference=await load(s.referenceId);
        if(!current())return;s.traces={selected,reference};
      }
      this.state.error=null;
    } catch(error){if(current())this.state.error=error.name==='AbortError'?'The request timed out. Retry to finish loading.':error.message;}
    finally {clearTimeout(timeout);if(current()){this.state.loading=false;this.onChange(this.state);}}
  }
}
