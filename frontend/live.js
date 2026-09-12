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
    this.onChange=onChange;this.fetcher=fetcher;this.generation=0;this.stopped=false;this.cache=new Map();
    this.state={mode:'finder',tab:'summary',recent:[],library:[],tracks:[],cars:[],total:0,databaseCount:0,
      hasMore:false,offset:0,searching:false,date:'',query:'',trackId:'all',carId:'all',recordingId:null,
      overview:null,snapshots:[],setupsLoaded:false,snapshotId:null,traces:{selected:null,reference:null},
      selectedSource:'lap',referenceSource:'lap',lapId:null,referenceId:null,
      selectedStint:'all',referenceStint:'all',selectedCondition:'all',referenceCondition:'all',
      rangeStart:0,rangeEnd:1,focus:'all',loading:false,error:null};
  }
  visible(){return this.state.library;}
  laps(side){return filterLaps(this.state.overview?.laps||[],this.state[`${side}Stint`],this.state[`${side}Condition`]);}
  choice(side){
    const s=this.state,source=s[`${side}Source`];
    if(source==='best')return s.overview?.all_time_best?.lap||null;
    if(source==='average')return s.overview?.eligible_count?{seconds:s.overview.average,eligible:true,status:`Average of ${s.overview.eligible_count} clean laps`}:null;
    return s.overview?.laps.find(l=>l.id===s[side==='selected'?'lapId':'referenceId'])||null;
  }
  stop(){this.stopped=true;this.cancel();}
  cancel(){this.generation++;this.controller?.abort();this.state.loading=false;}
  async json(path,signal){
    const response=await this.fetcher(path,{signal,cache:'no-store'});
    if(!response.ok)throw new Error(response.status===404?'Session or endpoint unavailable. Restart the viewer after updating.':'Cannot load this session. Check the viewer terminal, then retry.');
    return response.json();
  }
  async run(work){
    if(this.stopped)return;
    this.cancel();const generation=this.generation,controller=new AbortController();this.controller=controller;
    const current=()=>generation===this.generation&&!this.stopped;
    const timeout=setTimeout(()=>controller.abort(),120000);
    this.state.loading=true;this.state.error=null;this.onChange(this.state);
    try{await work(controller.signal,current);}
    catch(error){if(current())this.state.error=error.name==='AbortError'?'Loading timed out. Retry to finish indexing your sessions.':error.message;}
    finally{clearTimeout(timeout);if(current()){this.state.loading=false;this.onChange(this.state);}}
  }
  async search(){
    return this.run(async(signal,current)=>{
      const s=this.state,params=new URLSearchParams({limit:'20',offset:String(s.offset)});
      if(s.trackId!=='all')params.set('track',s.trackId);
      if(s.carId!=='all')params.set('car',s.carId);
      if(s.query.trim())params.set('q',s.query.trim());
      const data=await this.json(`/api/v1/finder?${params}${s.date?dateRange(s.date):''}`,signal);
      if(!current())return;
      Object.assign(s,{recent:data.recent,library:data.items,tracks:data.tracks,cars:data.cars,total:data.total,
        databaseCount:data.database_count,hasMore:data.has_more,searching:data.searching});
    });
  }
  selectFilter(key,value){this.state[key]=value;this.state.offset=0;return this.search();}
  async selectRecording(id,fromRecent=false){
    const s=this.state,item=[...s.recent,...s.library].find(r=>r.id===id);
    if(!item?.identified){s.error='This session does not yet identify its circuit and car.';this.onChange(s);return;}
    if(fromRecent){s.trackId=item.track.id;s.carId=item.car.id;}
    if(s.trackId==='all'||s.carId==='all'||s.trackId!==item.track.id||s.carId!==item.car.id){
      s.error='Choose this session’s circuit and car before opening analysis.';this.onChange(s);return;
    }
    s.recordingId=id;s.mode='review';s.tab='summary';s.overview=null;s.snapshots=[];s.setupsLoaded=false;
    s.snapshotId=null;s.traces={selected:null,reference:null};s.lapId=null;s.referenceId=null;
    s.selectedSource='lap';s.referenceSource='lap';s.selectedStint=s.referenceStint='all';
    s.selectedCondition=s.referenceCondition='all';s.rangeStart=0;s.rangeEnd=1;s.focus='all';this.cache.clear();
    return this.loadReview();
  }
  async loadReview(){
    return this.run(async(signal,current)=>{
      const data=await this.json(`/api/v1/recordings/${encodeURIComponent(this.state.recordingId)}/review`,signal);
      if(!current())return;
      this.state.overview=data;this.state.referenceSource=data.all_time_best?'best':'lap';
    });
  }
  back(){this.cancel();this.state.mode='finder';return this.search();}
  openTab(tab){
    this.cancel();this.state.tab=tab;this.onChange(this.state);
    if(tab==='analytics')return this.loadTraces();
    if(tab==='setup')return this.loadSetups();
  }
  async loadSetups(){
    if(this.state.setupsLoaded)return;
    return this.run(async(signal,current)=>{
      const data=await this.json(`/api/v1/recordings/${encodeURIComponent(this.state.recordingId)}/stint-setups`,signal);
      if(!current())return;
      this.state.snapshots=data.items;this.state.setupsLoaded=true;this.state.snapshotId=data.items[0]?.id||null;
    });
  }
  async loadTraces(){
    if(!this.state.overview)return;
    return this.run(async(signal,current)=>{
      const s=this.state;
      const selected=this.laps('selected'),reference=this.laps('reference');
      if(!selected.some(l=>l.id===s.lapId))s.lapId=selected.find(l=>l.eligible)?.id||selected[0]?.id||null;
      if(!reference.some(l=>l.id===s.referenceId))s.referenceId=reference.find(l=>l.id===s.overview.best?.id)?.id||reference[0]?.id||null;
      const pending=new Map();
      const load=side=>{
        const source=s[side+'Source'],lapId=s[side==='selected'?'lapId':'referenceId'];
        if(source==='lap'&&lapId===null)return Promise.resolve(null);
        if(source==='best'&&!s.overview.all_time_best)return Promise.resolve(null);
        if(source==='average'&&!s.overview.eligible_count)return Promise.resolve(null);
        const params=new URLSearchParams({source,start_pct:String(s.rangeStart),end_pct:String(s.rangeEnd)});
        if(source==='lap')params.set('lap_id',lapId);
        const url=`/api/v1/recordings/${encodeURIComponent(s.recordingId)}/comparison?${params}`;
        if(this.cache.has(url))return Promise.resolve(this.cache.get(url));
        if(!pending.has(url))pending.set(url,this.json(url,signal).then(data=>{
          if(current()){this.cache.set(url,data);while(this.cache.size>16)this.cache.delete(this.cache.keys().next().value);}return data;
        }));
        return pending.get(url);
      };
      s.traces={selected:null,reference:null};
      const [a,b]=await Promise.all([load('selected'),load('reference')]);
      if(current())s.traces={selected:a,reference:b};
    });
  }
  refresh(){return this.state.mode==='finder'?this.search():this.state.tab==='analytics'?this.loadTraces():this.state.tab==='setup'?this.loadSetups():this.loadReview();}
}
