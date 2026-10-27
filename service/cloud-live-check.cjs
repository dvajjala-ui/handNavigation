'use strict';
// Live Admin request -> outbound bridge -> production browser/Runner -> Supabase.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {createServer}=require('./server.cjs'),{StickerDock}=require('./stickerdock.cjs'),{lock}=require('./lock.cjs');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
  const folder=path.resolve(process.env.HANDNAVIGATE_DATA||'runtime/service-live'),config=JSON.parse(fs.readFileSync(path.join(folder,'stickerdock.json'),'utf8')),release=lock(folder);process.once('exit',release);
  const sink=new StickerDock(config.baseUrl,config.token);
  const admin=async body=>{const r=await fetch(config.baseUrl+'/api/admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(90000)});const result=await r.json();if(!r.ok)throw new Error(result.error||'Admin HTTP '+r.status);return result;};
  const app=createServer({folder,sink,cloudQueue:true,dailyLimit:Number(process.env.HANDNAVIGATE_DAILY_LIMIT||20),browser:{headless:false,...(process.platform==='win32'?{channel:'chrome'}:{}),interactiveWaitMs:180000},onAuth:i=>console.log('HUMAN_ACTION_REQUIRED '+JSON.stringify(i))});
  await new Promise(r=>app.server.listen(0,'127.0.0.1',r));
  try{
    const request={topics:(process.env.HANDNAVIGATE_TOPICS||'funny dog reaction').split(','),sources:(process.env.HANDNAVIGATE_SOURCES||'reddit,pinterest').split(','),image_limit:Number(process.env.HANDNAVIGATE_COUNT||20),request_id:process.env.HANDNAVIGATE_REQUEST_ID||'live-cloud-'+crypto.randomUUID()};
    const first=await admin({action:'collection_create',...request}),id=first.job.id;
    console.log(JSON.stringify({cloudJob:id,scope:'Live production Admin queue, own HandNavigate browser and Supabase sink',total:request.image_limit}));
    let last='',job;
    for(let n=0;n<1080;n++){
      const dashboard=await admin({action:'collection_dashboard'});job=dashboard.jobs.find(j=>j.id===id);
      const local=app.bridge.pending?.local?app.collections.get(app.bridge.pending.local):null;
      const message=JSON.stringify({status:job.status,downloaded:local?.items.length??job.saved,stored:job.delivered,event:local?.events.at(-1)?.text||null});
      if(last!==message){console.log(message);last=message;}
      if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(job.status))break;
      await pause(1000);
    }
    const local=job.local_id?app.collections.get(job.local_id):null;
    const result={checkedAt:new Date().toISOString(),executor:'Production StickerDock Admin API -> Supabase queue -> HandNavigate QueueBridge/ServiceBrowser/Runner -> authenticated production intake -> verified Supabase blob and row read-back',request,id:job.id,localId:job.local_id,status:job.status,saved:job.saved,delivered:job.delivered,error:job.error,sourceStatus:job.source_status,productionSupabaseWritten:true,aiCalls:0,publications:0,items:local?.items.map(i=>({platform:i.platform,topic:i.topic,source:i.postUrl||i.source,originalSha256:i.sha256,delivery:i.delivery||null}))||[]};
    fs.mkdirSync('service/evidence',{recursive:true});fs.writeFileSync('service/evidence/cloud-live-'+job.id+'.json',JSON.stringify(result,null,2));console.log(JSON.stringify({status:job.status,saved:job.saved,delivered:job.delivered,error:job.error,sourceStatus:job.source_status}));
    assert.equal(job.status,'VERIFIED_STORAGE');assert.equal(job.delivered,request.image_limit);assert.ok(local.items.every(i=>i.delivery?.verifiedAt));
    const repeat=await admin({action:'collection_create',...request});assert.equal(repeat.job.id,id);assert.equal(repeat.reused,true);
  }finally{await app.close();release();}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
