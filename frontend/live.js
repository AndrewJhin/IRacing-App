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
export function pathFor(points,key,max,min=0) {
  let path='', open=false;
  for (const point of points) {
    if (point.gap) open=false;
    const value=point[key];
    if (!finite(point.x) || point.x<0 || point.x>1 || !finite(value)) { open=false; continue; }
    const x=54+point.x*842, y=111-(Math.max(min,Math.min(max,value))-min)/(max-min)*94;
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
    brake:finite(point.brake)?point.brake*100:null}));
}

export class LiveClient {
  constructor(onChange, fetcher=globalThis.fetch, interval=1500) {
    this.onChange=onChange; this.fetcher=fetcher; this.interval=interval;
    this.state={library:[],hasMore:false,libraryLimit:100,trackId:'all',carId:'all',recordingId:null,
      overview:null,snapshots:[],traces:{selected:null,reference:null},lapId:null,referenceId:null,
      followLap:true,snapshotId:null,followSnapshot:true,error:null,loading:true};
    this.generation=0; this.cache=new Map(); this.stopped=false;
  }
  visible() {
    return this.state.library.filter(item=>(this.state.trackId==='all'||item.track.id===this.state.trackId)
      && (this.state.carId==='all'||item.car.id===this.state.carId));
  }
  clearDetail() {
    Object.assign(this.state,{overview:null,snapshots:[],traces:{selected:null,reference:null},
      lapId:null,referenceId:null,snapshotId:null,followLap:true,followSnapshot:true});
    this.cache.clear();
  }
  selectRecording(id) { this.state.recordingId=id; this.clearDetail(); return this.refresh(); }
  selectFilter(key,id) {
    this.state[key]=id;
    if(key==='trackId')this.state.carId='all';
    this.state.recordingId=null; this.clearDetail(); return this.refresh();
  }
  stop() { this.stopped=true; this.generation++; this.controller?.abort(); clearTimeout(this.timer); }
  async json(path,signal) {
    const response=await this.fetcher(path,{signal,cache:'no-store'});
    if(!response.ok)throw new Error(response.status===404?'Recording or viewer endpoint is unavailable. Restart the viewer after updating.':'Cannot read the database right now. Retrying automatically.');
    return response.json();
  }
  async refresh() {
    if(this.stopped)return;
    clearTimeout(this.timer); this.controller?.abort();
    const generation=++this.generation, controller=new AbortController(); this.controller=controller;
    const timeout=setTimeout(()=>controller.abort(),20000);
    const isCurrent=()=>generation===this.generation&&!this.stopped;
    this.state.loading=true; this.onChange(this.state);
    try {
      // Fetch every requested library page; adding a new recording never shifts a stored selection by array index.
      let library=[],page;
      for(let offset=0;offset<this.state.libraryLimit;offset+=100) {
        page=await this.json(`/api/v1/library?limit=100&offset=${offset}`,controller.signal);
        if(!isCurrent())return;
        library.push(...page.items);
        if(!page.has_more)break;
      }
      this.state.library=Array.from(new Map(library.map(item=>[item.id,item])).values());
      this.state.hasMore=!!page.has_more;
      if(this.state.trackId!=='all'&&!library.some(item=>item.track.id===this.state.trackId))this.state.trackId='all';
      if(this.state.carId!=='all'&&!library.some(item=>item.car.id===this.state.carId))this.state.carId='all';
      const visible=this.visible();
      if(!visible.some(item=>item.id===this.state.recordingId)) {
        this.state.recordingId=visible[0]?.id||null; this.clearDetail();
      }
      const id=this.state.recordingId;
      if(id) {
        const base=`/api/v1/recordings/${encodeURIComponent(id)}`;
        const overview=await this.json(`${base}/overview`,controller.signal);
        if(!isCurrent())return;
        this.state.overview=overview;
        let after=this.state.snapshots.at(-1)?.id||0;
        while(overview.latest_snapshot_id && after<overview.latest_snapshot_id) {
          const page=await this.json(`${base}/snapshots?after=${after}&limit=100`,controller.signal);
          if(!isCurrent())return;
          if(!page.items.length)break;
          this.state.snapshots.push(...page.items.map(item=>({id:item.id,stint_id:item.stint_id,captured_at:item.captured_at,
            setup:item.setup,parse_error:item.parse_error,provenance:item.provenance})));
          after=page.items.at(-1).id;
        }
        if(this.state.followSnapshot || !this.state.snapshots.some(item=>item.id===this.state.snapshotId))
          this.state.snapshotId=this.state.snapshots.at(-1)?.id||null;
        const laps=overview.laps;
        if(this.state.followLap || !laps.some(lap=>lap.id===this.state.lapId))this.state.lapId=laps.at(-1)?.id||null;
        if(!laps.some(lap=>lap.id===this.state.referenceId))this.state.referenceId=overview.best?.id||laps[0]?.id||null;
        const load=async lapId=>{
          const lap=laps.find(item=>item.id===lapId);
          if(!lap)return null;
          const key=`${id}:${lap.start_sequence}:${lap.end_sequence}`;
          if(this.cache.has(key))return this.cache.get(key);
          const result=await this.json(`${base}/trace?start=${lap.start_sequence}&end=${lap.end_sequence}`,controller.signal);
          if(isCurrent()) { this.cache.set(key,result); while(this.cache.size>8)this.cache.delete(this.cache.keys().next().value); }
          return result;
        };
        this.state.traces={selected:null,reference:null};
        const selected=await load(this.state.lapId);
        const reference=await load(this.state.referenceId);
        if(!isCurrent())return;
        this.state.traces={selected,reference};
      }
      this.state.error=null;
    } catch(error) {
      if(isCurrent())this.state.error=error.name==='AbortError'?'The viewer request timed out. Retrying automatically.':error.message;
    } finally {
      clearTimeout(timeout);
      if(isCurrent()) {
        this.state.loading=false; this.onChange(this.state);
        this.timer=setTimeout(()=>this.refresh(),this.interval);
      }
    }
  }
}
