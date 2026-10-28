'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {atomicWrite}=require('../desktop/core.cjs');
const ACTIVE=new Set(['QUEUED','RUNNING','WAITING_FOR_LOGIN']);
class QueueBridge{
  constructor(collections,sink,options={}){
    this.collections=collections;this.sink=sink;this.options=options;this.stopped=false;this.pending=null;
    const file=path.join(collections.folder,'cloud-worker.json');
    if(fs.existsSync(file))this.workerId=JSON.parse(fs.readFileSync(file,'utf8')).id;
    else{this.workerId=crypto.randomUUID();atomicWrite(file,{id:this.workerId});}
    if(!/^[0-9a-f-]{36}$/.test(this.workerId))throw new Error('Invalid persisted cloud worker identity.');
  }
  report(local){return {status:local.status==='VERIFIED_LOCAL'?'FAILED':local.status,
    local_id:local.id,saved:local.items.length,delivered:local.items.filter(i=>i.delivery).length,
    error:local.error||null,source_status:local.sourceStatus||{},events:(local.events||[]).slice(-20)};}
  async tick(){
    if(this.stopped)return;
    if(!this.pending){
      if(this.collections.active||this.collections.data.jobs.some(j=>j.status==='QUEUED'))return;
      const supported_sources=(this.collections.sources||[]).map(s=>({id:s.id,name:s.name||s.id}));
      const claimedAt=Date.now(),{job}=await this.sink.call('ingest',{action:'claim',worker_id:this.workerId,...(supported_sources.length?{supported_sources}:{})});
      if(!job)return;
      this.pending={cloud:job,local:null,lastConfirmed:claimedAt};
      try{
        let {job:local,reused}=this.collections.create({requestId:'cloud:'+job.id,topics:job.topics,sources:job.sources,limit:job.image_limit,destination:'stickerdock'});
        if(reused&&!ACTIVE.has(local.status)&&local.status!=='VERIFIED_STORAGE')local=this.collections.resume(local.id);
        this.pending.local=local.id;
      }catch(error){
        try{await this.sink.call('ingest',{action:'report',worker_id:this.workerId,id:job.id,report:{status:'FAILED',saved:0,delivered:0,error:String(error.message).slice(0,500)}});}
        finally{this.pending=null;}return;
      }
    }
    const pending=this.pending;
    const live=this.collections.data.jobs.find(j=>j.id===pending.local);
    if(live&&ACTIVE.has(live.status))this.collections.recover(live);
    const local=this.collections.get(pending.local);
    const report=this.report(local);if(report.status==='QUEUED')report.status='RUNNING';
    const reportedAt=Date.now(),result=await this.sink.call('ingest',{action:'report',worker_id:this.workerId,id:pending.cloud.id,report});
    pending.lastConfirmed=reportedAt;
    if(result.job.cancel_requested&&ACTIVE.has(local.status))this.collections.stop(local.id);
    if(!ACTIVE.has(local.status))this.pending=null;
  }
  start(){
    if(this.loop)return this;
    this.watchdog=setInterval(()=>{if(this.pending?.local&&Date.now()-this.pending.lastConfirmed>90000){this.collections.stop(this.pending.local);this.pending=null;this.options.onError?.(new Error('Worker heartbeat could not be confirmed; local run stopped before lease expiry.'));}},1000);
    this.loop=(async()=>{while(!this.stopped){try{await this.tick();}catch(error){
      this.options.onError?.(error);
      if(this.pending?.local&&(/HTTP 400/.test(error.message)||Date.now()-this.pending.lastConfirmed>90000)){this.collections.stop(this.pending.local);this.pending=null;}
    }
    if(!this.stopped)await new Promise(resolve=>{this.wake=resolve;this.timer=setTimeout(resolve,this.options.intervalMs||15000);});
    }})();return this;
  }
  async close(){this.stopped=true;clearInterval(this.watchdog);clearTimeout(this.timer);this.wake?.();await this.loop;}
}
module.exports={QueueBridge};
