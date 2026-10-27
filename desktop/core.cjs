'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

class TaskError extends Error { constructor(message, code='HALTED') { super(message); this.code=code; } }
const canonical = value => JSON.stringify(value && typeof value==='object' ? Array.isArray(value) ? value.map(v=>JSON.parse(canonical(v))) : Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])) : value);
const hash = value => crypto.createHash('sha256').update(typeof value==='string' ? value : canonical(value)).digest('hex');
const clone = value => JSON.parse(JSON.stringify(value));
function webUrl(value) {
  let u; try { u=new URL(value); } catch { throw new TaskError('Enter a complete http:// or https:// website address.'); }
  if (!['http:','https:'].includes(u.protocol)||u.username||u.password) throw new TaskError('Only HTTP(S) websites without passwords in the URL are supported.');
  return u;
}
function interpolate(value, row) {
  if(typeof value!=='string') return value;
  return value.replace(/\{\{([a-zA-Z][a-zA-Z0-9_]{0,39})\}\}/g,(_,key)=>{
    if(!(key in row)||typeof row[key]!=='string') throw new TaskError(`Enter a value for ${key}.`);
    return row[key];
  });
}
function siteUrl(value,row) {
  const parsed = value.replace(/\{\{([a-zA-Z][a-zA-Z0-9_]{0,39})\}\}/g,(_,key)=>{
    if(!(key in row)) throw new TaskError(`Enter a value for ${key}.`);
    return encodeURIComponent(row[key]);
  });
  return webUrl(parsed).href;
}
const PRIVATE = /password|passwd|secret|token|api[-_ ]?key|credential|one[-_ ]?time|credit.?card|cc-number|cc-csc|cvv/i;
function locator(spec) {
  if(!spec||typeof spec!=='object'||!['css','label','role','placeholder','testid','text'].includes(spec.kind)) throw new TaskError('A taught control has no supported locator.');
  if(Object.values(spec).some(v=>typeof v!=='string'||v.length>500)) throw new TaskError('A taught locator is invalid or too long.');
  if(spec.kind==='css' && (!spec.value||spec.value.startsWith('xpath=')||spec.value.startsWith('//'))) throw new TaskError('Teach this control again with a supported selector.');
}
function definition(task) {
  const result=Object.fromEntries(['type','startUrl','steps','rows','count','outputFolder','sourceSelector','checks','newOnly','allowedOrigins','imageOrigins','target'].map(k=>[k,task[k]??null]));
  for(const key of ['pagination','dedupeScope','skipSimilar'])if(task[key]!==undefined)result[key]=task[key];
  return result;
}
const taskHash = task => hash(definition(task));
function pagination(spec,options={}) {
  if(spec===undefined)return;
  if(!spec||!['scroll','next','none'].includes(spec.kind)||!Number.isInteger(spec.maxPages)||spec.maxPages<1||spec.maxPages>100)throw new TaskError('Choose scrolling, a Next control, or one page, with a 1–100 page limit.');
  if(spec.kind==='next'&&(!options.draft||spec.locator))locator(spec.locator);
}
function validate(task,options={}) {
  if(!task||!['images','replay','transfer'].includes(task.type)) throw new TaskError('Choose image downloads or a taught task.');
  if(typeof task.name!=='string'||!task.name.trim()||task.name.length>100) throw new TaskError('Give this workflow a name (up to 100 characters).');
  if(!Array.isArray(task.rows)||task.rows.length<1||task.rows.length>50) throw new TaskError('Enter 1–50 rows of variable values.');
  for(const row of task.rows) {
    if(!row||Array.isArray(row)||typeof row!=='object'||Object.keys(row).length>20||Object.entries(row).some(([k,v])=>!(/^[a-zA-Z][a-zA-Z0-9_]{0,39}$/.test(k))||typeof v!=='string'||v.length>4000)) throw new TaskError('Variable values must be text, with short names.');
    const url=siteUrl(task.startUrl,row);
    if(!task.allowedOrigins?.includes(new URL(url).origin)) throw new TaskError('The starting website is missing from the reviewed scope.');
  }
  if(!Array.isArray(task.allowedOrigins)||task.allowedOrigins.length<1||task.allowedOrigins.length>30||task.allowedOrigins.some(o=>webUrl(o).origin!==o)) throw new TaskError('Review the exact websites used by this workflow.');
  if(!Array.isArray(task.imageOrigins)||task.imageOrigins.length>30||task.imageOrigins.some(o=>webUrl(o).origin!==o)) throw new TaskError('Image origins must be exact HTTP(S) origins.');
  if(!Array.isArray(task.steps)||task.steps.length>200) throw new TaskError('A workflow can contain at most 200 taught actions.');
  for(const step of task.steps) {
    if(step.blocked) throw new TaskError('The recording includes a private or unsupported action. Remove it or teach again.');
    if(!['click','fill','select','check','press','navigate','wait'].includes(step.op)) throw new TaskError('This recorded action is not supported.');
    if(['click','fill','select','check','press'].includes(step.op)) locator(step.locator);
    if(step.op==='check'&&typeof step.checked!=='boolean') throw new TaskError('The checkbox state was not recorded.');
    if(step.op==='press'&&!['Enter','Tab','Escape','ArrowDown','ArrowUp','ArrowLeft','ArrowRight',' '].includes(step.value)) throw new TaskError('An unsupported key was recorded.');
    if(step.op==='wait'&&(!Number.isInteger(step.amount)||step.amount<0||step.amount>10000)) throw new TaskError('Wait steps must be between 0 and 10 seconds.');
    if(['fill','select'].includes(step.op)&&typeof step.value!=='string') throw new TaskError('A recorded input value is missing.');
    for(const row of task.rows) {
      if(['fill','select'].includes(step.op)) interpolate(step.value,row);
      if(step.op==='navigate'&&!task.allowedOrigins.includes(new URL(siteUrl(step.value,row)).origin)) throw new TaskError('A navigation leaves the reviewed websites.');
    }
  }
  if(!options.draft&&!['images','transfer'].includes(task.type)&&(!Array.isArray(task.checks)||task.checks.length===0)) throw new TaskError('Add a visible result check before running a taught task.');
  if(!Array.isArray(task.checks)||task.checks.length>20||task.checks.some(c=>!['text','url'].includes(c.kind)||typeof c.expected!=='string'||!c.expected.trim()||c.expected.length>4000)) throw new TaskError('Add valid visible-text or final-URL result checks.');
  if(['images','transfer'].includes(task.type)) {
    if(!Number.isInteger(task.count)||task.count<1||task.count>100) throw new TaskError('Choose 1–100 images per run.');
    if(typeof task.sourceSelector!=='string'||!task.sourceSelector||task.sourceSelector.length>500) throw new TaskError('Choose an image group in the browser.');
    if(typeof task.outputFolder!=='string'||!path.isAbsolute(task.outputFolder)) throw new TaskError('Choose a local download folder.');
    if(typeof task.newOnly!=='boolean') throw new TaskError('Choose whether each run collects new images.');
    pagination(task.pagination,options);
    if(task.dedupeScope!==undefined&&!['workflow','library'].includes(task.dedupeScope))throw new TaskError('Choose this workflow or the whole library for duplicate history.');
    if(task.skipSimilar!==undefined&&typeof task.skipSimilar!=='boolean')throw new TaskError('Choose whether to skip visually similar images.');
  }
  if(task.type==='transfer') {
    const t=task.target;
    if(!t&&options.draft)return task;
    if(!t||!task.allowedOrigins.includes(webUrl(t.url).origin)||!task.allowedOrigins.includes(webUrl(t.galleryUrl).origin)) throw new TaskError('Review the destination upload and gallery websites.');
    locator(t.fileInput); if(t.submit) locator(t.submit);
    if(typeof t.gallerySelector!=='string'||!t.gallerySelector) throw new TaskError('Choose the destination gallery image group.');
    pagination(t.pagination,options);
  }
  return task;
}

function retryFileOperation(operation) {
  // Windows scanners can briefly hold either side of an atomic replacement.
  // Keep the old file intact and retry only sharing/permission locks, for ~1 second.
  const waits=[20,40,80,160,320,500];
  for(let attempt=0;;attempt++){
    try{return operation();}
    catch(error){
      if(!['EBUSY','EACCES','EPERM'].includes(error.code)||attempt===waits.length)throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,waits[attempt]);
    }
  }
}
function atomicWrite(file,data) {
  fs.mkdirSync(path.dirname(file),{recursive:true}); const temp=file+'.tmp';
  const fd=retryFileOperation(()=>fs.openSync(temp,'w',0o600));
  try {fs.writeFileSync(fd,JSON.stringify(data,null,2));fs.fsyncSync(fd);} finally {fs.closeSync(fd);}
  if(fs.existsSync(file))retryFileOperation(()=>fs.copyFileSync(file,file+'.bak'));
  retryFileOperation(()=>fs.renameSync(temp,file));
}
class Store {
  constructor(folder) {
    this.folder=folder; this.file=path.join(folder,'workflows.json'); this.data={schema:1,tasks:[],runs:[],occurrences:{}};
    let recovered=false;
    if(fs.existsSync(this.file)) {
      try {this.load(this.file);} catch(e) { if(fs.existsSync(this.file+'.bak')) {
        this.load(this.file+'.bak');
        // Preserve the only intact copy before the recovery flush rotates backups.
        fs.renameSync(this.file,this.file+'.corrupt-'+Date.now()+'-'+crypto.randomBytes(3).toString('hex'));
        recovered=true;
      } else throw e; }
    }
    let changed=false;
    for(const run of this.data.runs) if(run.status==='RUNNING') {
      run.status='NEEDS_REVIEW';run.error='The app closed during this run. Inspect its outcome before starting again.';run.finishedAt=new Date().toISOString();
      const task=this.data.tasks.find(t=>t.id===run.taskId);if(task?.schedule)task.schedule.enabled=false;changed=true;
    }
    for(const key of Object.keys(this.data.occurrences)) if(this.data.occurrences[key].status==='RUNNING') {const o=this.data.occurrences[key];o.status='NEEDS_REVIEW';const task=this.data.tasks.find(t=>t.id===o.taskId);if(task?.schedule)task.schedule.enabled=false;changed=true;}
    if(recovered){for(const task of this.data.tasks){if(task.schedule)task.schedule.enabled=false;this.data.runs.unshift({id:crypto.randomUUID(),taskId:task.id,taskName:task.name,sha:task.sha,rowIndex:0,inputs:{},trigger:'recovery',status:'NEEDS_REVIEW',startedAt:new Date().toISOString(),finishedAt:new Date().toISOString(),items:[],events:[],error:'The local database was restored from its backup. Check the site for effects newer than this backup before running again.'});}changed=true;}
    if(changed)this.flush();
  }
  load(file) {
    const envelope=JSON.parse(fs.readFileSync(file,'utf8'));
    if(envelope.sha!==hash(envelope.data)||envelope.data?.schema!==1||!Array.isArray(envelope.data.tasks)||!Array.isArray(envelope.data.runs)) throw new TaskError('The local workflow database failed its integrity check. Preserve it and restore its backup.');
    this.data=envelope.data;
  }
  flush(){atomicWrite(this.file,{sha:hash(this.data),data:this.data});}
  get(id){const t=this.data.tasks.find(t=>t.id===id);if(!t)throw new TaskError('Workflow not found.');return t;}
  save(input) {
    validate(input,{draft:true});const old=input.id?this.data.tasks.find(t=>t.id===input.id):null;
    const task={...clone(input),id:old?.id||crypto.randomUUID(),revision:(old?.revision||0)+1,updatedAt:new Date().toISOString()};
    task.sha=taskHash(task);
    task.approvedSha=old?.sha===task.sha?old.approvedSha:null;
    task.rehearsals=old?.sha===task.sha?old.rehearsals||[]:[];
    task.schedule=old?.schedule?clone(old.schedule):null;
    if(task.schedule?.enabled&&(!task.approvedSha||task.rehearsals.length!==task.rows.length))task.schedule.enabled=false;
    if(old)this.data.tasks[this.data.tasks.indexOf(old)]=task;else this.data.tasks.push(task);
    this.flush();return task;
  }
  approve(id,sha) {const t=this.get(id);if(taskHash(t)!==sha||t.sha!==sha)throw new TaskError('The workflow changed. Review its current actions before approving.');validate(t);t.approvedSha=sha;this.flush();return t;}
  begin(id,rowIndex,trigger='manual',requestId=null) {
    const t=this.get(id);validate(t);
    if(t.archived)throw new TaskError('This workflow is archived.');
    if(t.approvedSha!==taskHash(t))throw new TaskError('Review and approve this workflow first.');
    if(!Number.isInteger(rowIndex)||rowIndex<0||rowIndex>=t.rows.length)throw new TaskError('Choose a row of variable values.');
    const run={id:crypto.randomUUID(),taskId:id,taskName:t.name,sha:t.sha,rowIndex,inputs:clone(t.rows[rowIndex]),trigger,status:'RUNNING',startedAt:new Date().toISOString(),items:[],events:[],error:null,...(requestId?{requestId}:{})};
    this.data.runs.unshift(run);this.flush();return run;
  }
  finish(run,status,error=null) {
    run.status=status;run.error=error;run.finishedAt=new Date().toISOString();
    const t=this.get(run.taskId);
    if(status==='VERIFIED'&&t.sha===run.sha)t.rehearsals=[...new Set([...(t.rehearsals||[]),run.rowIndex])];
    if(status!=='VERIFIED'&&t.schedule)t.schedule.enabled=false;
    this.flush();
  }
  acknowledge(runId,{confirmedAbsent=false}={}) {
    const run=this.data.runs.find(r=>r.id===runId);
    if(!run||run.status!=='NEEDS_REVIEW')throw new TaskError('Choose a run that needs review.');
    const unresolved=run.items.filter(i=>['UPLOADING','NEEDS_REVIEW'].includes(i.state));
    if(unresolved.length&&!confirmedAbsent)throw new TaskError('Inspect the destination gallery and explicitly confirm that unresolved uploads are absent before allowing a retry.');
    const at=new Date().toISOString();
    for(const item of unresolved){item.state='RESOLVED_NOT_UPLOADED';item.resolvedAt=at;}
    run.acknowledged=true;run.acknowledgedAt=at;this.flush();return run;
  }
  knownItems(taskId,scope='workflow'){return this.data.runs.filter(r=>scope==='library'||r.taskId===taskId).flatMap(r=>r.items.filter(i=>i.sha256&&i.file));}
  known(taskId){return new Set(this.knownItems(taskId).map(i=>i.sha256));}
  pendingItems(task,rowIndex){
    const confirmed=new Set(this.data.runs.filter(r=>r.taskId===task.id).flatMap(r=>r.items.filter(i=>i.state==='CONFIRMED').map(i=>i.sha256)));
    return this.data.runs.filter(r=>r.taskId===task.id&&r.sha===task.sha&&r.rowIndex===rowIndex&&r.status!=='RUNNING')
      .flatMap(r=>r.items.filter(i=>['DOWNLOADED','RESOLVED_NOT_UPLOADED'].includes(i.state)&&!confirmed.has(i.sha256)));
  }
  snapshot(){return clone({tasks:this.data.tasks,runs:this.data.runs.slice(0,100)});}
}

function zoneParts(at,zone) {
  const f=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  return Object.fromEntries(f.formatToParts(new Date(at)).filter(p=>p.type!=='literal').map(p=>[p.type,Number(p.value)]));
}
function validateSchedule(spec) {
  if(!spec||!/^([01]\d|2[0-3]):[0-5]\d$/.test(spec.time))throw new TaskError('Choose a daily time in HH:MM format.');
  try {zoneParts(Date.now(),spec.timezone);}catch{throw new TaskError('Choose a valid timezone.');}
}
function occurrenceOn(day,spec) {
  const [h,m]=spec.time.split(':').map(Number);const base=Date.UTC(day.year,day.month-1,day.day,h,m);
  const offsets=new Set([-86400000,-43200000,0,43200000,86400000].map(d=>{const a=base+d,p=zoneParts(a,spec.timezone);return Date.UTC(p.year,p.month-1,p.day,p.hour,p.minute,p.second)-a;}));
  const candidates=[...offsets].map(off=>base-off).filter(a=>{const p=zoneParts(a,spec.timezone);return p.year===day.year&&p.month===day.month&&p.day===day.day&&p.hour===h&&p.minute===m;});
  return candidates.length?Math.min(...candidates):null;
}
function dueAt(spec,after,direction=1) {
  validateSchedule(spec);const p=zoneParts(after,spec.timezone);
  for(let i=0;i<370;i++) {
    const d=new Date(Date.UTC(p.year,p.month-1,p.day+direction*i));
    const at=occurrenceOn({year:d.getUTCFullYear(),month:d.getUTCMonth()+1,day:d.getUTCDate()},spec);
    if(at!==null&&(direction===1?at>after:at<=after))return at;
  }
  throw new TaskError('No daily occurrence found.');
}
class DailyQueue {
  constructor(store,execute,clock=()=>Date.now(),canStart=()=>true){this.store=store;this.execute=execute;this.clock=clock;this.canStart=canStart;this.ticking=false;}
  enable(id,enabled,time,timezone) {
    const t=this.store.get(id),spec={time,timezone};validateSchedule(spec);
    if(enabled&&(t.approvedSha!==taskHash(t)||t.rehearsals?.length!==t.rows.length))throw new TaskError('Run and verify every configured value row before turning on daily automation.');
    t.schedule={...spec,enabled:!!enabled,nextDue:new Date(dueAt(spec,this.clock())).toISOString(),rowCursor:t.schedule?.rowCursor||0};this.store.flush();
  }
  async tick() {
    if(this.ticking||!this.canStart())return [];this.ticking=true;const reports=[];
    try {
      const now=this.clock();
      for(const t of this.store.data.tasks) {
        if(!this.canStart())break;
        if(!t.schedule?.enabled||Date.parse(t.schedule.nextDue)>now)continue;
        const at=dueAt(t.schedule,now,-1),key=t.id+':'+new Date(at).toISOString();
        t.schedule.nextDue=new Date(dueAt(t.schedule,now)).toISOString();
        if(this.store.data.occurrences[key]){this.store.flush();continue;}
        const row=t.schedule.rowCursor%t.rows.length;
        this.store.data.occurrences[key]={status:'RUNNING',taskId:t.id};this.store.flush();
        let result;
        try {result=await this.execute(t.id,row,'daily');}catch(e){result={status:'NEEDS_REVIEW',error:e.message};}
        this.store.data.occurrences[key]={status:result.status,taskId:t.id,runId:result.id||null};
        if(result.status==='VERIFIED')t.schedule.rowCursor=(row+1)%t.rows.length;else t.schedule.enabled=false;
        this.store.flush();reports.push(result);
      }
      return reports;
    }finally{this.ticking=false;}
  }
}
function draft(options={}) {
  const url=options.startUrl||'https://www.pinterest.com/search/pins/?q={{topic}}';
  const pinterest=/(^|\.)pinterest\.com$/.test(new URL(siteUrl(url,{topic:'example'})).hostname);
  return {name:options.name||'Daily images',type:options.type||'images',startUrl:url,steps:[],rows:[{topic:options.topic||'nature landscape'}],count:20,
    outputFolder:options.outputFolder||'',sourceSelector:pinterest?'a[href*="/pin/"] img':'img',checks:[],newOnly:true,pagination:{kind:'scroll',maxPages:50},dedupeScope:'workflow',skipSimilar:false,
    allowedOrigins:pinterest?['https://www.pinterest.com','https://in.pinterest.com','https://s.pinimg.com']:[new URL(siteUrl(url,{topic:'example'})).origin],imageOrigins:options.imageOrigins||(pinterest?['https://i.pinimg.com']:[]),target:null,schedule:null};
}
module.exports={TaskError,hash,clone,webUrl,interpolate,siteUrl,PRIVATE,locator,definition,taskHash,validate,pagination,atomicWrite,Store,zoneParts,occurrenceOn,dueAt,DailyQueue,draft};
