'use strict';
const fs=require('node:fs'),path=require('node:path');
const {performance}=require('node:perf_hooks');
const {createServer}=require('./server.cjs');
const {StickerDock}=require('./stickerdock.cjs');
const {lock}=require('./lock.cjs');
const {atomicWrite}=require('../desktop/core.cjs');

function seconds(value,fallback,max){
  const n=Number(value??fallback);
  if(!Number.isInteger(n)||n<5||n>max)throw new Error('Invalid batch time limit.');
  return n*1000;
}

async function syncHistory(sink,folder){
  const history=[];let offset=0;
  for(;;){
    const page=await sink.call('ingest',{action:'history',offset});
    if(!Array.isArray(page.items)||page.items.length>200)throw new Error('Invalid cloud duplicate-history page.');
    history.push(...page.items);
    if(history.length>20000||history.some(i=>!i||!/^[0-9a-f]{64}$/.test(i.sha256)||typeof i.source!=='string'||i.source.length>2000))throw new Error('Invalid or oversized cloud duplicate history.');
    if(page.next_offset===null)break;
    if(page.next_offset!==offset+200||page.items.length!==200)throw new Error('Invalid cloud duplicate-history cursor.');
    offset=page.next_offset;
  }
  atomicWrite(path.join(folder,'cloud-history.json'),history);
  return history.length;
}

// A scheduled host must release its browser, lease loop and data lock before
// exiting. The container also has an independent process-group timeout.
async function runBatch(app,options={}){
  const now=options.now||(()=>performance.now()),wait=options.wait||(ms=>new Promise(resolve=>setTimeout(resolve,ms)));
  const started=now(),baseline=new Map(app.collections.data.jobs.map(j=>[j.id,j.finishedAt]));
  let idleAt=started,reason='queue_empty';
  try{
    for(;;){
      if(options.signal?.aborted){reason='interrupted';break;}
      if(now()-started>=options.maxRuntimeMs){reason='runtime_limit';break;}
      const busy=!!(app.collections.active||app.collections.pumping||app.bridge?.pending||app.collections.data.jobs.some(j=>j.status==='QUEUED'));
      if(busy)idleAt=now();
      else if(now()-idleAt>=options.idleMs)break;
      await wait(Math.min(1000,options.maxRuntimeMs-(now()-started)));
    }
  }finally{
    // Stop new claims synchronously before cancelling an active browser.
    const bridgeClosing=app.bridge?.close();
    await app.close();
    await bridgeClosing;
    const pending=app.bridge?.pending;
    if(pending?.local&&app.bridge.sink){
      const local=app.collections.get(pending.local);
      if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(local.status)){
        await app.bridge.sink.call('ingest',{action:'report',worker_id:app.bridge.workerId,id:pending.cloud.id,report:app.bridge.report(local)});
        app.bridge.pending=null;
      }
    }
  }
  const jobs=app.collections.data.jobs.filter(j=>!baseline.has(j.id)||j.finishedAt!==baseline.get(j.id));
  return {reason,jobs:jobs.map(j=>({id:j.id,status:j.status,saved:j.items.length,delivered:j.items.filter(i=>i.delivery).length})),
    ok:reason==='queue_empty'&&jobs.every(j=>j.status==='VERIFIED_STORAGE')};
}

async function main(){
  const maxRuntimeMs=seconds(process.env.HANDNAVIGATE_BATCH_SECONDS,1500,1800);
  const idleMs=seconds(process.env.HANDNAVIGATE_BATCH_IDLE_SECONDS,90,600);
  const folder=path.resolve(process.env.HANDNAVIGATE_DATA||path.join(__dirname,'..','runtime','service'));
  const release=lock(folder),controller=new AbortController();
  const stop=()=>controller.abort();
  process.once('SIGTERM',stop);process.once('SIGINT',stop);
  let bridgeError=false,app;
  try{
    const configFile=process.env.HANDNAVIGATE_CONFIG||path.join(folder,'stickerdock.json');
    const config=fs.existsSync(configFile)?JSON.parse(fs.readFileSync(configFile,'utf8')):{};
    const sink=new StickerDock(config.baseUrl||process.env.STICKERDOCK_BASE_URL,config.token||process.env.STICKERDOCK_INGEST_TOKEN);
    await syncHistory(sink,folder);
    app=createServer({folder,sink,cloudQueue:true,onBridgeError:()=>{bridgeError=true;}});
    if(process.env.HANDNAVIGATE_ENQUEUE_DAILY==='1')await sink.call('ingest',{action:'enqueue_daily'});
    const result=await runBatch(app,{maxRuntimeMs,idleMs,signal:controller.signal});
    console.log(JSON.stringify({batch:result.reason,jobs:result.jobs,bridgeError}));
    if(!result.ok||bridgeError)process.exitCode=1;
  }finally{await app?.close();process.removeListener('SIGTERM',stop);process.removeListener('SIGINT',stop);release();}
}
if(require.main===module)main().catch(error=>{console.error('Batch worker:',String(error.message).slice(0,200));process.exitCode=1;});
module.exports={runBatch,seconds,syncHistory};
