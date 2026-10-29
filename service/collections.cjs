'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Store,draft,hash,clone,atomicWrite,zoneParts}=require('../desktop/core.cjs');
const {Runner,imageInfo}=require('../desktop/engine.cjs');
const {ServiceBrowser}=require('./browser.cjs');
const {ImgflipCatalog}=require('./imgflip.cjs');
const {FlickrFeed}=require('./flickr.cjs');
const {OpenverseSearch}=require('./openverse.cjs');
const {sources,request}=require('./sources.cjs');
class Collections{
  constructor(folder,options={}){
    this.folder=path.resolve(folder);this.options=options;this.sources=sources(options.sources);this.runs=new Store(path.join(this.folder,'runner'));
    const historyFile=path.join(this.folder,'cloud-history.json');
    if(fs.existsSync(historyFile)){
      if(fs.statSync(historyFile).size>4000000)throw new Error('Cloud duplicate history exceeds its bound.');
      const history=JSON.parse(fs.readFileSync(historyFile,'utf8'));
      if(!Array.isArray(history)||history.length>20000||history.some(i=>!i||!/^[0-9a-f]{64}$/.test(i.sha256)||typeof i.source!=='string'||i.source.length>2000))throw new Error('Invalid cloud duplicate history.');
      const local=this.runs.knownItems.bind(this.runs);
      this.runs.knownItems=(id,scope)=>[...local(id,scope),...(scope==='library'?history:[])];
    }
    if(!Number.isInteger(options.dailyLimit??20)||(options.dailyLimit??20)<1||(options.dailyLimit??20)>10000)throw new Error('Daily image budget must be an integer from 1 to 10000.');
    this.file=path.join(this.folder,'collections.json');this.data={schema:1,jobs:[]};this.active=null;this.pumping=false;
    if(fs.existsSync(this.file)){const envelope=JSON.parse(fs.readFileSync(this.file,'utf8'));if(envelope.sha!==hash(envelope.data)||envelope.data?.schema!==1)throw new Error('Collection journal integrity failed. Preserve it before restoring a backup.');this.data=envelope.data;}
    for(const job of this.data.jobs)if(['RUNNING','WAITING_FOR_LOGIN'].includes(job.status)){job.status='INTERRUPTED';job.error='Worker restarted. Resume this request to reconcile its saved files.';}
    this.flush();
  }
  flush(){atomicWrite(this.file,{sha:hash(this.data),data:this.data});}
  day(){const p=zoneParts(Date.now(),this.options.timezone||'Asia/Kolkata');return `${p.year}-${String(p.month).padStart(2,'0')}-${String(p.day).padStart(2,'0')}`;}
  used(day=this.day()){return new Set(this.runs.data.runs.filter(r=>this.runs.get(r.taskId).collectionDay===day).flatMap(r=>r.items.map(i=>i.sha256))).size;}
  create(body){
    const existing=this.data.jobs.find(j=>j.requestId===body?.requestId),spec=request(body,existing?.sourceRecipes||this.sources,this.options.maxImages||100),digest=hash(spec);
    if(existing){if(existing.requestHash!==digest)throw new Error('That requestId belongs to different collection parameters.');if(existing.status==='QUEUED')this.pump().catch(error=>this.options.onError?.(error));return {job:clone(existing),reused:true};}
    if(spec.destination==='stickerdock'&&!this.options.sink)throw new Error('StickerDock storage is not configured on this worker.');
    if(this.used()>=(this.options.dailyLimit||20))throw new Error('The configured daily image budget is already used.');
    if(this.data.jobs.filter(j=>j.status==='QUEUED').length>=50)throw new Error('Collection queue is full.');
    const job={id:crypto.randomUUID(),...spec,sourceRecipes:clone(this.sources.filter(s=>spec.sources.includes(s.id))),requestHash:digest,day:this.day(),status:'QUEUED',createdAt:new Date().toISOString(),items:[],events:[],sourceStatus:{},error:null};
    this.data.jobs.unshift(job);this.flush();this.pump().catch(error=>this.options.onError?.(error));return {job:clone(job),reused:false};
  }
  get(id){const job=this.data.jobs.find(j=>j.id===id);if(!job)throw new Error('Collection not found.');return clone(job);}
  event(job,text){job.events.push({at:new Date().toISOString(),text});if(job.events.length>200)job.events.shift();this.flush();}
  resume(id){const job=this.data.jobs.find(j=>j.id===id);if(!job||!['INTERRUPTED','PARTIAL','AUTH_REQUIRED','DELIVERY_FAILED','FAILED','CANCELLED'].includes(job.status))throw new Error('Choose an interrupted or incomplete collection.');job.status='QUEUED';job.error=null;job.sourceStatus={};delete job.cancelled;this.flush();this.pump().catch(error=>this.options.onError?.(error));return clone(job);}
  stop(id){const job=this.data.jobs.find(j=>j.id===id);if(!job)throw new Error('Collection not found.');if(this.active?.job.id===id){job.cancelled=true;this.active.abort.abort();this.active.runner?.stop();}else if(job.status==='QUEUED')job.status='CANCELLED';this.flush();}
  recover(job){
    const tasks=this.runs.data.tasks.filter(t=>t.collectionId===job.id),byId=new Map(tasks.map(t=>[t.id,t]));
    const known=new Set(job.items.map(i=>i.sha256));
    for(const run of this.runs.data.runs.filter(r=>byId.has(r.taskId)))for(const item of run.items){if(known.has(item.sha256))continue;known.add(item.sha256);const t=byId.get(run.taskId);job.items.push({...item,platform:t.platform,topic:run.inputs.topic,runId:run.id});}
    this.flush();
  }
  pump(){
    if(this.pumpTask)return this.pumpTask;
    this.pumpTask=this.drain().finally(()=>{this.pumpTask=null;});return this.pumpTask;
  }
  async drain(){
    this.pumping=true;try{let job;while(!this.closing&&(job=this.data.jobs.find(j=>j.status==='QUEUED')))await this.execute(job);}finally{this.pumping=false;}
  }
  async close(){
    this.closing=true;if(this.active)this.stop(this.active.job.id);
    await this.pumpTask;
  }
  async execute(job){
    job.status='RUNNING';job.startedAt||=new Date().toISOString();job.error=null;this.active={job,runner:null,abort:new AbortController()};this.recover(job);this.event(job,'Collection started: '+job.limit+' images total across all sources and topics.');
    // Freeze the reviewed recipe once. Updating/removing a source never changes a queued retry.
    const recipes=job.sourceRecipes||clone(this.sources.filter(s=>job.sources.includes(s.id)));
    const quota=Math.max(1,Math.ceil(job.limit/(job.sources.length*job.topics.length))),pairs=job.topics.flatMap(topic=>job.sources.map(id=>({topic,source:recipes.find(s=>s.id===id)})));
    const browsers=new Map();let timedOut=false;
    const timer=setTimeout(()=>{timedOut=true;this.stop(job.id);},this.options.jobTimeoutMs||15*60*1000);
    try{
      if(pairs.some(p=>!p.source))throw new Error('A source used by this legacy request is missing. Restore its original recipe before resuming.');
      sources(recipes);job.sourceRecipes=recipes;this.flush();
      for(let round=0;round<2&&job.items.length<job.limit;round++)for(const {topic,source} of pairs){
        if(job.cancelled||job.items.length>=job.limit)break;
        if(['AUTH_REQUIRED','FAILED','HALTED'].includes(job.sourceStatus[source.id]?.status))continue;
        const allowance=Math.min(job.limit-job.items.length,(this.options.dailyLimit||20)-this.used(),round===0?quota:job.limit);
        if(allowance<=0)break;
        try{
          let browser=browsers.get(source.id);
          if(!browser){const Provider=source.provider==='imgflip'?ImgflipCatalog:source.provider==='flickr'?FlickrFeed:source.provider==='openverse'?OpenverseSearch:ServiceBrowser;browser=await Provider.open(path.join(this.folder,'profiles',source.id),{...this.options.browser,catalogFetch:this.options.catalogFetch,catalogHistory:this.runs.knownItems('', 'library').map(i=>i.source).filter(Boolean),onAuth:url=>{job.status='WAITING_FOR_LOGIN';this.event(job,'Human sign-in/check required for '+source.id);this.options.onAuth?.({jobId:job.id,source:source.id,url});}});browsers.set(source.id,browser);}
          if(job.cancelled)break;
          job.status='RUNNING';
          const task=this.runs.save({...draft({startUrl:source.searchUrl,outputFolder:path.join(this.folder,'downloads'),imageOrigins:source.imageOrigins||[]}),
            name:'Collection '+job.id.slice(0,8)+' '+source.id,type:'images',count:allowance,rows:[{topic}],sourceSelector:source.selector,outputFolder:this.options.outputFolder||path.join(this.folder,'downloads'),
            allowedOrigins:source.allowedOrigins,steps:source.steps||[],checks:source.checks||[],pagination:source.pagination||{kind:'scroll',maxPages:30},dedupeScope:'library',skipSimilar:true,
            collectionId:job.id,collectionDay:this.day(),platform:source.id});
          this.runs.approve(task.id,task.sha);const runner=new Runner(this.runs,browser);browser.runner=runner;this.active.runner=runner;
          const result=await runner.run(task.id);job.status='RUNNING';this.recover(job);job.sourceStatus[source.id]={status:result.status,lastError:result.error||null};this.event(job,source.id+': '+result.items.length+' saved ('+result.status+').');
        }catch(error){job.sourceStatus[source.id]={status:'FAILED',lastError:String(error.message).slice(0,300)};this.event(job,source.id+': '+String(error.message).slice(0,200));}
      }
      if(!job.cancelled)for(const item of job.items){const meta=await imageInfo(fs.readFileSync(item.file));if(meta.sha256!==item.sha256)throw new Error('A saved source changed before final collection verification.');}
      if(!job.cancelled&&job.destination==='stickerdock')for(const item of job.items){
        if(job.cancelled)break;if(item.delivery)continue;
        const local=await imageInfo(fs.readFileSync(item.file));if(local.sha256!==item.sha256)throw new Error('A saved source changed before storage delivery.');
        this.event(job,'Storing source '+(job.items.indexOf(item)+1)+'/'+job.items.length+' in StickerDock.');
        item.delivery=await this.options.sink.store({...item,collectionId:job.id},this.active.abort.signal);this.flush();
      }
      const delivered=job.destination==='local'?job.items.length:job.items.filter(i=>i.delivery).length;
      job.status=job.cancelled?'CANCELLED':delivered===job.limit?(job.destination==='local'?'VERIFIED_LOCAL':'VERIFIED_STORAGE'):job.items.length?'PARTIAL':Object.values(job.sourceStatus).some(s=>s.status==='AUTH_REQUIRED')?'AUTH_REQUIRED':'FAILED';
      job.error=timedOut?'Collection reached its time limit.':delivered<job.limit?`${delivered}/${job.limit} images verified. Review source status or resume after sign-in.`:null;
    }catch(error){job.status=job.cancelled?'CANCELLED':job.destination==='stickerdock'?'DELIVERY_FAILED':'FAILED';job.error=String(error.message).slice(0,500);}
    finally{clearTimeout(timer);for(const b of browsers.values())await b.close().catch(()=>{});job.finishedAt=new Date().toISOString();this.flush();this.active=null;}
  }
}
module.exports={Collections};
